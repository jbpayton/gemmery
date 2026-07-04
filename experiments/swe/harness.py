"""SWE living-repo harness: worktrees, prompts, librarian application, scoring.

Protocol per issue k (chronological):
  solve-fresh(k) and solve-mem(k) run in parallel (identical except the memory
  arm's prompt carries the CURRENT dossiers from the store);
  then librarian(k) sees the reveal (gold files) + both answers and decides
  what to capture/revise (intentional capture, Invariant 5) as JSON
  {"capture": [{"path": ..., "content": ...}], "revise": [...]} which
  apply_librarian() writes into the real GitStore.
Scoring: recall@5 and top-1 hit vs the gold patch's files.
"""
from __future__ import annotations
import json, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT.parents[1] / "data" / "swe"
REPO = DATA / "django-repo"
WT = DATA / "worktrees"
sys.path.insert(0, str(ROOT.parents[1]))

SEL = json.load(open(DATA / "selected.json"))


def setup_worktrees():
    WT.mkdir(exist_ok=True)
    for s in SEL:
        dst = WT / s["instance_id"]
        if not dst.exists():
            subprocess.run(["git", "-C", str(REPO), "worktree", "add", "--detach",
                            str(dst), s["base_commit"]], capture_output=True)
    print("worktrees:", len(list(WT.iterdir())))


def store():
    from gemmery import GitStore
    return GitStore(ROOT / "store", actor="librarian")


def dossier_block():
    st = store()
    try:
        listing = st.tree_listing()
    except Exception:
        return "(memory is empty — no dossiers yet)"
    if not listing.strip():
        return "(memory is empty — no dossiers yet)"
    parts = []
    for line in listing.splitlines():
        if line.strip().endswith("reasoning.md"):
            path = "/".join(p.strip() for p in []) # placeholder
    # walk gem dirs
    def walk(prefix=""):
        for e in st.ls(prefix):
            if e.endswith("/"):
                sub = (prefix + "/" + e[:-1]).strip("/")
                if "reasoning.md" in st.ls(sub):
                    txt = st.read_file(sub + "/reasoning.md").decode()
                    parts.append(f"--- dossier {sub} ---\n{txt}")
                else:
                    walk(sub)
    walk()
    return "\n\n".join(parts) or "(memory is empty — no dossiers yet)"


def write_solve_prompts(k):
    s = SEL[k]
    wt = WT / s["instance_id"]
    base = (f"You are debugging Django (working tree: {wt} — explore it with "
            "grep/read tools as needed; it is at the exact commit where this "
            "issue was reported).\n\n=== ISSUE ===\n"
            + s["problem"][:4000] +
            "\n\nIdentify WHERE the fix belongs. Return ONLY JSON: "
            '{"files": ["path/rel/to/repo.py", ... up to 5, ranked most-likely '
            'first], "plan": "2-3 sentences on the fix"}.\n')
    (ROOT / f"prompt_fresh_{k}.txt").write_text(base)
    mem = base.replace("=== ISSUE ===",
        "=== YOUR MEMORY OF THIS REPO (dossiers from previous issues; written "
        "by you; trust the specifics) ===\n" + dossier_block() +
        "\n\n=== ISSUE ===")
    (ROOT / f"prompt_mem_{k}.txt").write_text(mem)
    return wt


def write_librarian_prompt(k, mem_answer):
    s = SEL[k]
    block = dossier_block()
    p = (f"You are the memory librarian for an agent working Django issues in "
         "chronological order. Issue just completed:\n\n"
         + s["problem"][:2500] +
         f"\n\nThe agent's localization answer was: {mem_answer}\n"
         f"THE ACTUAL FIX (now public repo history) touched: {s['files']}\n\n"
         f"Current dossiers:\n{block}\n\n"
         "Decide what is WORTH REMEMBERING for future issues in this repo "
         "(subsystem maps, recurring modules, gotchas, correction of wrong "
         "beliefs). Quality over quantity — capture only durable, non-obvious "
         "facts; revise dossiers that proved wrong or incomplete (stable path = "
         "revision). Return ONLY JSON: {\"capture\": [{\"path\": "
         "\"knowledge/...\", \"content\": \"markdown\"}], \"revise\": [{\"path\": "
         "..., \"content\": ...}]} — empty lists are fine if nothing is worth it.\n")
    (ROOT / f"prompt_lib_{k}.txt").write_text(p)


def apply_librarian(k):
    from gemmery import Action, Gem, IndexKeys, KnowledgeBody, Kind, Provenance
    st = store()
    raw = (ROOT / "out" / f"lib_{k}.json").read_text().strip()
    if "```" in raw:
        raw = raw.split("```")[1].lstrip("json").strip()
    ops = json.loads(raw)
    n = 0
    for verb in ("capture", "revise"):
        for item in ops.get(verb, []):
            gem = Gem(kind=Kind.knowledge,
                      provenance=Provenance("librarian", f"issue-{k}"),
                      body=KnowledgeBody(
                          action=Action(verb + "_dossier", {"issue": SEL[k]["instance_id"]}),
                          reasoning=item["content"],
                          belief=item["path"]),
                      index_keys=IndexKeys(action_type="dossier",
                                           domain=[SEL[k]["instance_id"]]))
            if verb == "revise":
                st.revise(gem, item["path"])
            else:
                st.capture(gem, path=item["path"])
            n += 1
    print(f"librarian issue {k}: applied {n} dossier ops; store now "
          f"{st.count_commits()} gems")


def score():
    import re
    res = {}
    for arm in ("fresh", "mem"):
        rows = []
        for k, s in enumerate(SEL):
            f = ROOT / "out" / f"{arm}_{k}.json"
            if not f.exists():
                continue
            raw = f.read_text().strip()
            if "```" in raw:
                raw = raw.split("```")[1].lstrip("json").strip()
            try:
                ans = json.loads(raw)
            except json.JSONDecodeError:
                continue
            pred = [p.strip("/") for p in ans.get("files", [])][:5]
            gold = set(s["files"])
            hit5 = len(gold & set(pred)) / len(gold)
            top1 = 1.0 if pred and pred[0] in gold else 0.0
            rows.append((k, round(hit5, 3), top1))
        if rows:
            res[arm] = {"n": len(rows),
                        "recall@5": round(sum(r[1] for r in rows)/len(rows), 3),
                        "top1": round(sum(r[2] for r in rows)/len(rows), 3),
                        "rows": rows}
    print(json.dumps(res, indent=1))
    return res


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "setup":
        setup_worktrees()
    elif cmd == "prompts":
        write_solve_prompts(int(sys.argv[2]))
        print("prompts written for issue", sys.argv[2])
    elif cmd == "librarian":
        write_librarian_prompt(int(sys.argv[2]), sys.argv[3] if len(sys.argv) > 3 else "?")
    elif cmd == "apply":
        apply_librarian(int(sys.argv[2]))
    elif cmd == "score":
        score()
