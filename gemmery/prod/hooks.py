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
    sp = store_path()
    if not (sp / ".git").exists() and not (sp / "HEAD").exists():
        return
    store = get_store()
    ds = dossiers(store)
    if not ds:
        return
    lines = ["# Gemmery memory (earned dossiers for this project)",
             "Cite any dossier you actually use as [[its-path]]. If one is "
             "wrong, say so - it will be revised against your session.", ""]
    for path, sha, g in ds:
        notes = store.notes(sha)
        cr = notes["credit"].get("total", 0)
        vals = [v for v in notes["success"].values() if isinstance(v, (int, float))]
        wins = sum(1 for v in vals if v >= 0.5)
        nver = len(store.history(path))
        lines.append(f"## [[{path}]]  (v{nver}, outcomes {wins}W/{len(vals)-wins}L, "
                     f"credit {cr:+.2f})")
        lines.append(g.reasoning_text().strip()[:800])
        lines.append("")
    print("\n".join(lines)[:INJECT_CAP])


# ---------------------------------------------------------- outcome hook -- #
def outcome_hook() -> None:
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

Return ONLY JSON: {"capture": [{"path": "knowledge/<slug>", "content": "...",
"tests": ["..."]}], "revise": [{"path": "<existing path>", "content": "...",
"tests": ["..."]}]}

=== CURRENT DOSSIERS ===
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


def _transcript_tail(path) -> str:
    msgs = []
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
            if isinstance(content, str):
                msgs.append(f"{role}: {content}")
            else:
                msgs += [f"{role}: {b['text']}" for b in content
                         if isinstance(b, dict) and b.get("type") == "text"]
    except Exception as e:
        _log(f"transcript parse failed: {e}")
    return "\n\n".join(msgs)[-TAIL:]


def _apply_ops(store, raw) -> int:
    from ..model import Action, Gem, IndexKeys, Kind, KnowledgeBody, Provenance
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


def librarian(argv: list[str]) -> None:
    import os
    model = os.environ.get("GEMMERY_LIBRARIAN_MODEL", "haiku")
    try:
        h = json.load(sys.stdin)
    except Exception:
        h = {}
    tp = h.get("transcript_path") or (argv[0] if argv else None)
    store = get_store()
    tagged = _fold_outcomes(store)
    if not tp or not Path(tp).exists():
        _log(f"outcomes tagged={tagged}; no transcript, done")
        return
    tail = _transcript_tail(tp)
    if len(tail) < 500:
        _log(f"outcomes tagged={tagged}; session too small, skipped")
        return
    idx = "\n".join(f"- [[{p}]] {g.body.belief[:90]}"
                    for p, _, g in dossiers(store)) or "(none yet)"
    try:
        r = subprocess.run(["claude", "-p", PROMPT % (idx, tail),
                            "--model", model],
                           capture_output=True, text=True, timeout=180)
        n = _apply_ops(store, r.stdout.strip())
        _log(f"outcomes tagged={tagged}; librarian ops applied={n} (model={model})")
        subprocess.run(["git", "-C", str(store_path()), "gc", "--auto",
                        "--quiet"], capture_output=True, timeout=120)
    except Exception as e:
        _log(f"outcomes tagged={tagged}; librarian failed: {e}")


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
                  f"{notes['credit'].get('total', 0):+.2f}")
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
