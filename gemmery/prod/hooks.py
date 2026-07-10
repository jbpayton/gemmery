"""The three hook bodies + project wiring. See package docstring."""
from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from pathlib import Path

from . import dossiers, get_store, project_root, store_path

INJECT_CAP = 6000
TAIL = 30000


def _outcomes():
    return store_path() / "outcomes.jsonl"


def _log(msg):
    store_path().mkdir(exist_ok=True)
    with open(store_path() / "librarian.log", "a") as f:
        f.write(f"[{time.strftime('%Y-%m-%d %H:%M')}] {msg}\n")


# ---------------------------------------------------------------- inject -- #
def inject() -> None:
    import os
    if os.environ.get("GEMMERY_NO_HOOKS"):
        return
    sp = store_path()
    if not (sp / ".git").exists() and not (sp / "HEAD").exists():
        return
    store = get_store()
    ds = dossiers(store)
    if not ds:
        return
    TOP_K = 8
    ranked = []
    for path, sha, g in ds:
        notes = store.notes(sha)
        cr = notes["credit"].get("total", 0)
        cites = citation_count(store, sha)
        vals = [v for v in notes["success"].values() if isinstance(v, (int, float))]
        wins = sum(1 for v in vals if v >= 0.5)
        nver = len(store.history(path))
        # earned standing first, then evidence volume, then citations
        ranked.append((-(cr), -(wins + cites * 0.25), path, sha, g,
                       cr, cites, wins, len(vals) - wins, nver))
    ranked.sort()
    lines = ["# Gemmery memory (earned dossiers for this project)",
             "Cite any dossier you actually use as [[its-path]]. If one is "
             "wrong, say so - it will be revised against your session.", ""]
    for (_, _, path, sha, g, cr, cites, wins, losses, nver) in ranked[:TOP_K]:
        lines.append(f"## [[{path}]]  (v{nver}, outcomes {wins}W/{losses}L, "
                     f"credit {cr:+.2f}, cited {cites}x)")
        lines.append(g.reasoning_text().strip()[:800])
        lines.append("")
    if len(ranked) > TOP_K:
        lines.append(f"...and {len(ranked) - TOP_K} more dossiers - "
                     f"run `gemmery status` to list them all.")
    print("\n".join(lines)[:INJECT_CAP])


# ---------------------------------------------------------- outcome hook -- #
def outcome_hook() -> None:
    import os
    if os.environ.get("GEMMERY_NO_HOOKS"):
        return
    from ..store.redact import redact
    try:
        h = json.load(sys.stdin)
    except Exception:
        return
    cmd = (h.get("tool_input") or {}).get("command", "")
    if "pytest" not in cmd:
        return
    resp = h.get("tool_response") or {}
    text = (str(resp.get("stdout", "")) + str(resp.get("stderr", ""))
            if isinstance(resp, dict) else str(resp))
    m = re.search(r"(\d+ failed|\d+ passed|\d+ error)[^\n]*", text)
    if not m:
        return
    ok = "failed" not in m.group(0) and "error" not in m.group(0)
    store_path().mkdir(exist_ok=True)
    with open(_outcomes(), "a") as f:
        f.write(json.dumps({"ts": time.strftime("%Y-%m-%d %H:%M"),
                            "command": redact(cmd[:200].encode())[0].decode(),
                            "ok": ok, "summary": m.group(0)[:120]}) + "\n")


# -------------------------------------------------------------- librarian -- #
PROMPT = """You are the memory librarian for this project. Below: the current
dossier index, then the tail of a working session that just ended.

Decide what (if anything) from this session is DURABLE JUDGMENT worth keeping
for future sessions: a rule with its why, a falsified assumption, a gotcha
with its precondition, a decision with its rationale. NOT facts restatable
from the code, NOT session narrative. Most sessions yield 0-2 items; empty
lists are a good answer. If the session contradicts an existing dossier,
REVISE it (same path) rather than adding a new one.

Each item's content must be: the rule/decision (1-2 sentences), WHY (the
evidence from this session), a falsifiable claim if possible, and citations
into the raw record (file paths, commit shas). <=150 words. Optionally
declare "tests": substrings of pytest commands whose pass/fail should credit
or debit this dossier.

Additionally: the session CITED the dossiers listed below. For each, judge
from the transcript whether it actually HELPED (its rule was applied and the
work went right), MISLED (following it caused a wrong turn or it was called
out as wrong), or was neutral. Judge only what the transcript shows.

Return ONLY JSON: {"capture": [{"path": "knowledge/<slug>", "content": "...",
"tests": ["..."]}], "revise": [{"path": "<existing path>", "content": "...",
"tests": ["..."]}], "verdicts": [{"path": "<cited path>",
"verdict": "helped"|"misled"|"neutral", "why": "<=15 words"}]}

=== CURRENT DOSSIERS ===
%s

=== CITED THIS SESSION ===
%s

=== SESSION TAIL ===
%s
"""


def _fold_outcomes(store) -> int:
    of = _outcomes()
    if not of.exists():
        return 0
    rows = [json.loads(l) for l in of.read_text().splitlines() if l.strip()]
    if not rows:
        return 0
    tagged, matched = 0, set()
    for path, sha, g in dossiers(store):
        declared = (g.action().args or {}).get("tests", []) if g.action() else []
        for t in declared:
            for ri, r in enumerate(rows):
                if t in r["command"]:
                    # unique per event: the same test can pass AND fail within
                    # one ledger minute; each outcome must count, not overwrite
                    tid = f"{t[:40]}@{r['ts']}#{time.time_ns() % 10**9}"
                    store.tag_outcome(sha, tid, ok=r["ok"])
                    store.attach_success(sha, tid, 1.0 if r["ok"] else 0.0)
                    store.attach_credit(sha, 0.1 if r["ok"] else -0.2)
                    tagged += 1
                    matched.add(ri)
    keep = [r for ri, r in enumerate(rows) if ri not in matched][-200:]
    of.write_text("".join(json.dumps(r) + "\n" for r in keep))
    return tagged


def _transcript_tail(path) -> tuple[str, str]:
    """(dialogue tail, assistant-only text). Citations are counted ONLY in
    assistant text - the injected context contains [[paths]] by design and
    must not credit itself."""
    msgs, assistant = [], []
    try:
        for line in open(path):
            try:
                j = json.loads(line)
            except Exception:
                continue
            m = j.get("message") or {}
            role, content = m.get("role"), m.get("content")
            if role not in ("user", "assistant") or not content:
                continue
            parts = [content] if isinstance(content, str) else \
                    [b["text"] for b in content
                     if isinstance(b, dict) and b.get("type") == "text"]
            msgs += [f"{role}: {t}" for t in parts]
            if role == "assistant":
                assistant += parts
    except Exception as e:
        _log(f"transcript parse failed: {e}")
    return "\n\n".join(msgs)[-TAIL:], "\n".join(assistant)[-TAIL:]


def _apply_ops(store, ops) -> int:
    from ..model import Action, Gem, IndexKeys, Kind, KnowledgeBody, Provenance
    if isinstance(ops, str):
        raw = ops
        if "```" in raw:
            raw = raw.split("```")[1].lstrip("json").strip()
        m = re.search(r"\{.*\}", raw, re.S)
        ops = json.loads(m.group(0) if m else raw)
    n = 0
    existing = {p for p, _, _ in dossiers(store)}
    for verb in ("capture", "revise"):
        for item in ops.get(verb, []):
            path = item["path"]
            if not path.startswith("knowledge/"):
                path = "knowledge/" + path.split("/")[-1]
            gem = Gem(kind=Kind.knowledge,
                      provenance=Provenance("librarian", "session-end"),
                      body=KnowledgeBody(
                          action=Action("dossier", {"tests": item.get("tests", [])}),
                          reasoning=item["content"],
                          belief=item["content"][:120]),
                      index_keys=IndexKeys(action_type="dossier",
                                           domain=["prod"]))
            if verb == "revise" or path in existing:
                store.revise(gem, path)
            else:
                store.capture(gem, path=path)
            n += 1
    return n


def _capture_citations(store, assistant_text) -> dict[str, str]:
    """Usage is signal: every [[path]] the agent actually cited gets a
    zero-delta credit event (a usage marker - it counts, it doesn't score).
    Returns {path: tip_sha} of cited dossiers for the verdict pass."""
    cited = {}
    for path in set(re.findall(r"\[\[([A-Za-z0-9_/.\-]+)\]\]", assistant_text)):
        h = store.history(path)
        if h:
            store.attach_credit(h[0], 0.0, test=f"cited@{time.strftime('%Y-%m-%d %H:%M')}")
            cited[path] = h[0]
    return cited


def citation_count(store, sha) -> int:
    from ..valuation import CREDIT_REF, parse_log
    return sum(1 for ev in parse_log(store._read_note(sha, CREDIT_REF))
               if str(ev.get("test", "")).startswith("cited@"))


def _apply_verdicts(store, ops, cited) -> int:
    """Weak-evidence valuation for cited dossiers: the librarian's judgment,
    signed as such (source distinguishes it from test outcomes). Failures
    debit 2x what successes credit; neutral writes nothing."""
    n = 0
    ts = time.strftime("%Y-%m-%d %H:%M")
    for v in ops.get("verdicts", []):
        sha = cited.get(v.get("path"))
        verdict = v.get("verdict")
        if not sha or verdict not in ("helped", "misled"):
            continue
        ok = verdict == "helped"
        store.attach_success(sha, f"session-judgment@{ts}#{time.time_ns() % 10**9}",
                             1.0 if ok else 0.0, source="librarian-judgment")
        store.attach_credit(sha, 0.05 if ok else -0.10)
        n += 1
    return n


def librarian(argv: list[str]) -> None:
    import os
    if os.environ.get("GEMMERY_NO_HOOKS"):
        return  # we ARE the librarian's own model call - never recurse
    model = os.environ.get("GEMMERY_LIBRARIAN_MODEL", "haiku")
    try:
        h = json.load(sys.stdin)
    except Exception:
        h = {}
    trigger = h.get("hook_event_name", "SessionEnd")
    tp = h.get("transcript_path") or (argv[0] if argv else None)
    store = get_store()
    tagged = _fold_outcomes(store)
    if not tp or not Path(tp).exists():
        _log(f"[{trigger}] outcomes tagged={tagged}; no transcript, done")
        return
    tail, assistant_text = _transcript_tail(tp)
    cited = _capture_citations(store, assistant_text)
    if len(tail) < 500:
        _log(f"[{trigger}] outcomes tagged={tagged}; cited={len(cited)}; "
             f"session too small, skipped")
        return
    idx = "\n".join(f"- [[{p}]] {g.body.belief[:90]}"
                    for p, _, g in dossiers(store)) or "(none yet)"
    cited_block = "\n".join(f"- [[{p}]]" for p in cited) or "(none)"
    try:
        r = subprocess.run(["claude", "-p", PROMPT % (idx, cited_block, tail),
                            "--model", model],
                           capture_output=True, text=True, timeout=180,
                           env={**os.environ, "GEMMERY_NO_HOOKS": "1"})
        raw = r.stdout.strip()
        if "```" in raw:
            raw = raw.split("```")[1].lstrip("json").strip()
        m = re.search(r"\{.*\}", raw, re.S)
        ops = json.loads(m.group(0) if m else raw)
        n = _apply_ops(store, ops)
        nv = _apply_verdicts(store, ops, cited)
        _log(f"[{trigger}] outcomes tagged={tagged}; cited={len(cited)}; "
             f"ops={n}; verdicts={nv} (model={model})")
        subprocess.run(["git", "-C", str(store_path()), "gc", "--auto",
                        "--quiet"], capture_output=True, timeout=120)
    except Exception as e:
        _log(f"[{trigger}] outcomes tagged={tagged}; cited={len(cited)}; "
             f"librarian failed: {e}")


# ------------------------------------------------------------------ init -- #
HOOKS = {
    "SessionStart": [{"hooks": [{"type": "command",
        "command": "gemmery inject 2>/dev/null || true",
        "timeout": 20, "statusMessage": "Loading Gemmery dossiers"}]}],
    "SessionEnd": [{"hooks": [{"type": "command",
        "command": "gemmery librarian 2>/dev/null || true",
        "timeout": 180, "statusMessage": "Gemmery librarian distilling session"}]}],
    "PostToolUse": [{"matcher": "Bash", "hooks": [{"type": "command",
        "command": "gemmery outcome-hook 2>/dev/null || true", "timeout": 15}]}],
    "PreCompact": [{"hooks": [{"type": "command",
        "command": "gemmery librarian 2>/dev/null || true",
        "timeout": 180, "statusMessage": "Gemmery librarian distilling chapter"}]}],
}


def init(with_hooks: bool = True) -> None:
    root = project_root()
    get_store()  # creates .gemmery-store
    gi = root / ".gitignore"
    line = ".gemmery-store/"
    if not gi.exists() or line not in gi.read_text():
        with open(gi, "a") as f:
            f.write(f"\n# gemmery living store (it's git - back up via its own remote)\n{line}\n")
    print(f"store: {store_path()}")
    if not with_hooks:
        return
    sf = root / ".claude" / "settings.json"
    sf.parent.mkdir(exist_ok=True)
    cfg = json.loads(sf.read_text()) if sf.exists() else {}
    hooks = cfg.setdefault("hooks", {})
    added = []
    for event, entries in HOOKS.items():
        cur = hooks.setdefault(event, [])
        want = entries[0]["hooks"][0]["command"]
        if not any(want in json.dumps(e) for e in cur):
            cur.extend(entries)
            added.append(event)
    sf.write_text(json.dumps(cfg, indent=2) + "\n")
    print(f"hooks wired in {sf}: {added or 'already present'}")


# ---------------------------------------------------------------- status -- #
def status() -> None:
    """Answer 'is it working?' in one command."""
    root = project_root()
    sp = store_path()
    ok = (sp / ".git").exists() or (sp / "HEAD").exists()
    print(f"store:    {sp}  {'[ok]' if ok else '[MISSING - run: gemmery init]'}")
    if ok:
        store = get_store()
        ds = dossiers(store)
        print(f"memory:   {store.count_commits()} gems on main, "
              f"{len(ds)} dossiers in knowledge/")
        for p, sha, g in ds[:5]:
            notes = store.notes(sha)
            vals = [v for v in notes["success"].values()
                    if isinstance(v, (int, float))]
            wins = sum(1 for v in vals if v >= 0.5)
            print(f"            [[{p}]]  v{len(store.history(p))}, "
                  f"{wins}W/{len(vals)-wins}L, credit "
                  f"{notes['credit'].get('total', 0):+.2f}, "
                  f"cited {citation_count(store, sha)}x")
    sf = root / ".claude" / "settings.json"
    if sf.exists():
        txt = sf.read_text()
        wired = [e for e in ("inject", "librarian", "outcome-hook")
                 if f"gemmery {e}" in txt]
        print(f"hooks:    {len(wired)}/3 wired in {sf.name} ({', '.join(wired) or 'none'})")
    else:
        print(f"hooks:    not wired (no {sf}) - run: gemmery init")
    log = sp / "librarian.log"
    if log.exists():
        print(f"last run: {log.read_text().splitlines()[-1]}")
    else:
        print("last run: never (the librarian fires when a session ends)")
