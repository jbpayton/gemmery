"""Generate a self-contained, browsable HTML explorer for any Gemmery store.

Usage: python tools/store_browser.py <store_path> <out.html> [title]

One static file, no server: ref selector (main + every alternate-reality
branch), drill-down file tree, per-gem detail (reasoning, action, tests,
consumed edges as links, success/credit notes, version history), commit log,
and client-side search over reasoning text.
"""
from __future__ import annotations

import html
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gemmery import GitStore  # noqa: E402
from dataclasses import asdict  # noqa: E402


def build_tree(store, ref_tip):
    def walk(path):
        entries = store.ls(path, sha=ref_tip)
        node = []
        for e in sorted(entries):
            if e.endswith("/"):
                name = e[:-1]
                sub = (path + "/" + name).strip("/")
                child = walk(sub)
                is_gem = any(c.get("file") == "meta.json" for c in child)
                node.append({"name": name, "path": sub, "gem": is_gem,
                             "children": [] if is_gem else child})
            else:
                node.append({"file": e})
        return node
    return [n for n in walk("") if "name" in n]


def collect(store_path, title):
    store = GitStore(store_path)
    refs = ["main"] + store.list_branches(prefix="frontier/")
    gems, ref_data, commits = {}, [], {}
    for ref in refs:
        tip = store._ref_target(f"refs/heads/{ref}")
        if tip is None:
            continue
        tip = str(tip)
        shas = store._git_lines(["log", "--format=%H", ref])
        commits[ref] = []
        for sha in shas:
            commit = store.repo.get(__import__("pygit2").Oid(hex=sha))
            summary = commit.message.splitlines()[0]
            path = store.gem_path(sha) or ""
            commits[ref].append({"sha": sha, "summary": summary, "path": path})
            if sha in gems:
                continue
            try:
                g = store.read_gem(sha)
            except Exception:
                continue
            notes = store.notes(sha)
            action = g.action()
            gems[sha] = {
                "sha": sha, "kind": g.kind.value, "path": path,
                "actor": g.provenance.actor, "ts": g.provenance.timestamp,
                "action": (action.name if action else ""),
                "args": (action.args if action else {}),
                "reasoning": g.reasoning_text(),
                "pre": g.pre(),
                "tests": [t.id for t in g.tests()],
                "consumed": g.consumed, "incited_by": g.incited_by,
                "reversibility": g.reversibility_class.value,
                "index_keys": asdict(g.index_keys),
                "success": notes["success"], "credit": notes["credit"],
                "ref": ref,
            }
        ref_data.append({"name": ref, "tip": tip, "tree": build_tree(store, tip)})

    # map path@ref -> current sha (for tree clicks)
    path_sha = {}
    for ref in refs:
        for c in commits.get(ref, []):
            key = f"{ref}::{c['path']}"
            if c["path"] and key not in path_sha:   # log is newest-first
                path_sha[key] = c["sha"]
    return {"title": title, "refs": ref_data, "gems": gems,
            "commits": commits, "path_sha": path_sha}


TEMPLATE = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>__TITLE__</title><style>
 body{font-family:ui-monospace,Menlo,Consolas,monospace;margin:0;display:flex;
      height:100vh;background:#0e1117;color:#d7dce2;font-size:13px}
 #side{width:390px;min-width:300px;overflow:auto;border-right:1px solid #2a2f3a;
       padding:10px}
 #main{flex:1;overflow:auto;padding:18px 26px}
 h1{font-size:15px;color:#8ab4f8;margin:4px 0 10px}
 select,input{width:100%;background:#161b24;color:#d7dce2;border:1px solid #2a2f3a;
       padding:5px;margin-bottom:8px;border-radius:4px}
 details{margin-left:10px} summary{cursor:pointer;color:#9aa4b2}
 .gem{cursor:pointer;color:#7ee0a3} .gem:hover{text-decoration:underline}
 .file{color:#5b6472;margin-left:24px}
 .tag{display:inline-block;background:#1d2432;border-radius:3px;padding:1px 7px;
      margin:0 4px 4px 0;color:#8ab4f8;font-size:11px}
 .credit-pos{color:#7ee0a3}.credit-neg{color:#ef8a8a}
 pre{background:#161b24;border:1px solid #2a2f3a;border-radius:6px;padding:12px;
     white-space:pre-wrap;line-height:1.45}
 a{color:#8ab4f8;cursor:pointer;text-decoration:none} a:hover{text-decoration:underline}
 .commit{padding:3px 0;border-bottom:1px dotted #222836}
 .muted{color:#5b6472} .sec{margin-top:16px;color:#e2b96f;font-size:12px;
       text-transform:uppercase;letter-spacing:1px}
 table{border-collapse:collapse}td{padding:2px 10px 2px 0;vertical-align:top}
</style></head><body>
<div id="side">
 <h1>__TITLE__</h1>
 <div class="muted" id="stats"></div>
 <div class="sec">reality (ref)</div><select id="ref"></select>
 <div class="sec">search reasoning</div><input id="q" placeholder="type to filter gems…">
 <div class="sec">memory file system</div><div id="tree"></div>
 <div class="sec">commits (this reality)</div><div id="log"></div>
</div>
<div id="main"><div class="muted">Select a reality on the left, drill into the
 file system, click any <span class="gem">gem</span> — or search. Every gem
 shows its reasoning, evidence edges, and earned valuation.</div></div>
<script>
const D = __DATA__;
const gems = D.gems, pathSha = D.path_sha;
const refSel = document.getElementById('ref');
D.refs.forEach(r=>{const o=document.createElement('option');o.value=r.name;
  o.textContent=r.name+(r.name==='main'?'  (accepted reality)':'');refSel.appendChild(o);});
document.getElementById('stats').textContent =
  Object.keys(gems).length+' gems · '+(D.refs.length-1)+' alternate-reality branches';
function esc(s){return (s??'').toString().replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]))}
function treeHTML(nodes, ref){let h='';for(const n of nodes){
  if(n.gem){const sha=pathSha[ref+'::'+n.path]||'';
    h+=`<div style="margin-left:10px">◆ <span class="gem" onclick="show('${sha}')">${esc(n.name)}</span></div>`;}
  else if(n.name){h+=`<details open><summary>${esc(n.name)}/</summary>${treeHTML(n.children,ref)}</details>`;}
}return h;}
function renderRef(){const ref=refSel.value;const r=D.refs.find(x=>x.name===ref);
  document.getElementById('tree').innerHTML=treeHTML(r.tree,ref);
  const log=D.commits[ref]||[];
  document.getElementById('log').innerHTML=log.map(c=>
    `<div class="commit"><a onclick="show('${c.sha}')">${c.sha.slice(0,8)}</a> ${esc(c.summary)}</div>`).join('');}
refSel.onchange=renderRef; renderRef();
function fmtSuccess(s){return Object.entries(s).map(([k,v])=>
  `<span class="tag">${esc(k)}: ${v==='pending'?'⊥ pending':v}</span>`).join('')||'<span class="muted">none</span>';}
function show(sha){const g=gems[sha];if(!g)return;const cr=g.credit.total;
  const consumed=(g.consumed||[]).map(s=>{const t=gems[s];
    return `<div>↳ <a onclick="show('${s}')">${s.slice(0,10)}</a> <span class="muted">${t?esc(t.path):'(external)'}</span></div>`}).join('')||'<span class="muted">none</span>';
  document.getElementById('main').innerHTML=`
   <h1>${esc(g.path||'(no path)')} <span class="muted">· ${esc(g.kind)} · ${esc(g.ref)}</span></h1>
   <div><span class="tag">actor ${esc(g.actor)}</span><span class="tag">action ${esc(g.action)}</span>
    <span class="tag">reversibility ${esc(g.reversibility)}</span>
    ${g.tests.map(t=>`<span class="tag">test ${esc(t)}</span>`).join('')}</div>
   <div class="sec">reasoning.md</div><pre>${esc(g.reasoning)||'<empty>'}</pre>
   <div class="sec">valuation (append-only notes)</div>
   <table><tr><td>success</td><td>${fmtSuccess(g.success)}</td></tr>
   <tr><td>credit</td><td class="${cr>=0?'credit-pos':'credit-neg'}">${cr.toFixed(3)}
     <span class="muted">(${g.credit.n_events} events)</span></td></tr></table>
   <div class="sec">evidence consumed (the why)</div>${consumed}
   ${g.incited_by?`<div class="sec">incited by</div><a onclick="show('${g.incited_by}')">${g.incited_by.slice(0,10)}</a>`:''}
   <div class="sec">pre / args</div><pre>${esc(JSON.stringify({pre:g.pre,args:g.args},null,1))}</pre>
   <div class="sec">commit</div><div class="muted">${g.sha}</div>`;
  window.scrollTo(0,0);}
document.getElementById('q').oninput=e=>{const q=e.target.value.toLowerCase();
  if(!q){renderRef();return;}
  const hits=Object.values(gems).filter(g=>(g.reasoning+g.path).toLowerCase().includes(q)).slice(0,80);
  document.getElementById('tree').innerHTML=hits.map(g=>
   `<div>◆ <span class="gem" onclick="show('${g.sha}')">${esc(g.path)}</span>
     <span class="muted">${esc(g.ref)}</span></div>`).join('')||'<div class="muted">no hits</div>';};
</script></body></html>"""


def main():
    store_path, out = sys.argv[1], sys.argv[2]
    title = sys.argv[3] if len(sys.argv) > 3 else Path(store_path).parent.name
    data = collect(store_path, title)
    html_doc = (TEMPLATE.replace("__TITLE__", html.escape(title))
                .replace("__DATA__", json.dumps(data)))
    Path(out).write_text(html_doc)
    print(f"wrote {out} ({len(html_doc)//1024} KB, {len(data['gems'])} gems, "
          f"{len(data['refs'])} refs)")


if __name__ == "__main__":
    main()
