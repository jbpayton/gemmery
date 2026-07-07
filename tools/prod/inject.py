"""SessionStart hook: inject the repo's earned dossiers as context.

Numbers and credit lead (presentation determines application); content is
capped; agents are told to cite dossiers by [[path]] so the P1 gate can
measure real use.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from prod_store import get_store, dossiers, STORE_PATH

CAP = 6000

def main():
    if not (STORE_PATH / ".git").exists() and not (STORE_PATH / "HEAD").exists():
        return  # no store yet -> inject nothing
    store = get_store()
    ds = dossiers(store)
    if not ds:
        return
    lines = ["# Gemmery memory (earned dossiers for this repo)",
             "Cite any dossier you actually use as [[its-path]]. If one is "
             "wrong, say so - it will be revised against your session.", ""]
    for path, sha, g in ds:
        notes = store.notes(sha)
        cr = notes["credit"].get("total", 0)
        succ = notes["success"]
        vals = [v for v in succ.values() if isinstance(v, (int, float))]
        wins = sum(1 for v in vals if v >= 0.5)
        losses = len(vals) - wins
        nver = len(store.history(path))
        head = g.reasoning_text().strip()
        lines.append(f"## [[{path}]]  (v{nver}, outcomes {wins}W/{losses}L, credit {cr:+.2f})")
        lines.append(head[:800])
        lines.append("")
    text = "\n".join(lines)
    print(text[:CAP])

if __name__ == "__main__":
    main()
