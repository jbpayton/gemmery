"""PostToolUse hook (Bash): record pytest outcomes to the open-loop ledger.

No LLM, no store writes here - just append {ts, command, ok, summary} to
outcomes.jsonl; the session-end librarian folds these into tag_outcome on
gems whose declared tests match.
"""
import json, re, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from prod_store import OUTCOMES, STORE_PATH

def main():
    try:
        h = json.load(sys.stdin)
    except Exception:
        return
    cmd = (h.get("tool_input") or {}).get("command", "")
    if "pytest" not in cmd:
        return
    resp = h.get("tool_response") or {}
    text = ""
    if isinstance(resp, dict):
        text = str(resp.get("stdout", "")) + str(resp.get("stderr", ""))
    else:
        text = str(resp)
    m = re.search(r"(\d+ failed|\d+ passed|\d+ error)[^\n]*", text)
    if not m:
        return
    ok = "failed" not in m.group(0) and "error" not in m.group(0)
    STORE_PATH.mkdir(exist_ok=True)
    with open(OUTCOMES, "a") as f:
        f.write(json.dumps({"ts": time.strftime("%Y-%m-%d %H:%M"),
                            "command": cmd[:200], "ok": ok,
                            "summary": m.group(0)[:120]}) + "\n")

if __name__ == "__main__":
    main()
