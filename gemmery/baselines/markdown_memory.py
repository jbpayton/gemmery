"""A plain-markdown memory backend — the naive baseline (spec §0 / GitOfThoughts).

This is the "just write notes to a `.md` file and read them back" mechanism: no
DAG, no index, no selective retrieval, no immutable records. It exists so every
experiment can compare Gemmery against the simplest possible memory and find out
*when* structure actually earns its keep versus when a flat scratchpad suffices
(the honest, kill-switch question).

Contract deliberately mirrors how an agent uses a scratchpad:
  * ``capture(text)``  — append a note (mutable, unstructured, unbounded).
  * ``read_all()``     — dump the whole file back (the naive retrieval).
  * ``grep(query)``    — optional keyword filter (a slightly-less-naive read).

Where this loses to Gemmery, in principle: it grows without bound (context bloat
as history accumulates), has no structured pre-filter (you re-read everything or
grep by surface words), notes are the agent's own possibly-lossy summaries rather
than immutable records, and it cannot walk a topology (frontier, diff, credit).
Whether any of that *matters* for a given task is exactly what we measure.
"""

from __future__ import annotations

from pathlib import Path


class MarkdownMemory:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("# Memory notes\n\n")

    def capture(self, text: str, *, heading: str | None = None) -> None:
        chunk = ""
        if heading:
            chunk += f"\n## {heading}\n"
        chunk += f"- {text.strip()}\n"
        with self.path.open("a") as f:
            f.write(chunk)

    def read_all(self) -> str:
        """The naive baseline: read the entire notes file."""
        return self.path.read_text()

    def grep(self, query: str) -> str:
        """A slightly-less-naive read: keyword-filtered lines."""
        q = query.lower()
        return "\n".join(
            ln for ln in self.path.read_text().splitlines() if q in ln.lower()
        )

    def size_chars(self) -> int:
        return len(self.path.read_text())

    def clear(self) -> None:
        self.path.write_text("# Memory notes\n\n")
