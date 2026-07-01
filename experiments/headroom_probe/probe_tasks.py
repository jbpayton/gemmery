"""Empirical headroom probe (real-world tasks).

The v2 pilot showed textbook algorithms have no headroom for a strong model. This
probe locates where *real-world* headroom actually is, by spanning tasks from a
famous pitfall (predicted low headroom — the model knows it) to a
project-specific fact (predicted high headroom — the model cannot know it cold).

Each task is framed as a realistic SITUATION (the trap is not named), carries a
`memory_hint` (the transferable lesson a memory would surface), and a runnable
`ScoredVerifier` that exercises the trap. We screen a COLD agent (no hint) to see
which tasks it fails — those are the regime where memory could matter.
"""

from __future__ import annotations

from dataclasses import dataclass

from gemmery.eval.tasks_v2 import ScoredVerifier


@dataclass
class ProbeTask:
    id: str
    predicted_headroom: str          # low | medium | high
    problem_text: str                # realistic situation; trap NOT named
    contract: str
    memory_hint: str                 # the transferable lesson
    verifier: ScoredVerifier

    def prompt(self, with_memory: bool) -> str:
        p = f"{self.problem_text}\n\n{self.contract}"
        if with_memory:
            p += f"\n\n[Note from an unrelated past project] {self.memory_hint}"
        return p


# --------------------------------------------------------------------------- #
# 1. DST local-day bucketing  (predicted LOW headroom — famous pitfall)
# --------------------------------------------------------------------------- #
def _dst_events():
    # Dense grid tightly around both 2024 US DST transitions, so a fixed-offset
    # solution misassigns a large fraction (the trap bites hard), plus events
    # near local midnight where the offset error flips the calendar day.
    import datetime as dt
    out = []
    for start in ("2024-03-09", "2024-11-02"):
        base = dt.datetime.fromisoformat(start + "T00:00:00+00:00")
        for k in range(288):  # 3 days, every 15 min
            out.append(int((base + dt.timedelta(minutes=15 * k)).timestamp()))
    return out


def _dst_harness(ns):
    from datetime import datetime
    from zoneinfo import ZoneInfo
    fn = ns["count_by_local_day"]
    tz = "America/New_York"
    zi = ZoneInfo(tz)
    events = _dst_events()
    truth = {}
    for ts in events:
        d = datetime.fromtimestamp(ts, zi).date().isoformat()
        truth[d] = truth.get(d, 0) + 1
    got = fn(list(events), tz)
    if not isinstance(got, dict):
        return 0.0
    got = {str(k): int(v) for k, v in got.items()}
    correct = sum(min(got.get(d, 0), c) for d, c in truth.items())
    return correct / len(events)


_DST = ProbeTask(
    id="dst_local_day",
    predicted_headroom="low",
    problem_text=(
        "Our analytics shows a 'daily active' count per calendar day in the "
        "customer's own region. Around the start/end of daylight saving, the "
        "numbers look off — events land on the wrong day and one day's total is "
        "short while its neighbor is heavy."),
    contract=(
        "Implement `count_by_local_day(utc_timestamps, tz_name)`: given a list of "
        "UTC epoch seconds and an IANA timezone name, return a dict mapping each "
        "local calendar date (ISO 'YYYY-MM-DD') to the number of events that fall "
        "on it in that timezone."),
    memory_hint=(
        "Bucket by the local date from a real tz database (zoneinfo), converting "
        "each instant individually — never a fixed UTC offset. Offsets change at "
        "DST, and DST days are 23 or 25 hours long, so a constant offset "
        "misassigns events near midnight on transition weekends."),
    verifier=ScoredVerifier(
        entry_point="count_by_local_day", harness=_dst_harness, threshold=0.97,
        reference_solution=(
            "def count_by_local_day(utc_timestamps, tz_name):\n"
            "    from datetime import datetime\n"
            "    from zoneinfo import ZoneInfo\n"
            "    zi = ZoneInfo(tz_name); out = {}\n"
            "    for ts in utc_timestamps:\n"
            "        d = datetime.fromtimestamp(ts, zi).date().isoformat()\n"
            "        out[d] = out.get(d, 0) + 1\n"
            "    return out\n"),
        naive_solution=(  # fixed -5h offset, no tz db
            "def count_by_local_day(utc_timestamps, tz_name):\n"
            "    from datetime import datetime, timezone, timedelta\n"
            "    off = timezone(timedelta(hours=-5)); out = {}\n"
            "    for ts in utc_timestamps:\n"
            "        d = datetime.fromtimestamp(ts, off).date().isoformat()\n"
            "        out[d] = out.get(d, 0) + 1\n"
            "    return out\n")),
)


# --------------------------------------------------------------------------- #
# 2. UTF-8 safe truncation  (predicted MEDIUM — non-famous byte edge case)
# --------------------------------------------------------------------------- #
def _max_utf8_prefix(data: bytes, mx: int) -> bytes:
    cut = min(mx, len(data))
    while cut > 0:
        try:
            data[:cut].decode("utf-8")
            return data[:cut]
        except UnicodeDecodeError:
            cut -= 1
    return b""


def _utf8_harness(ns):
    fn = ns["truncate_utf8"]
    samples = [
        "héllo wörld".encode(), "日本語のテスト".encode(),
        "emoji 😀🎉 mix".encode(), "café ☕ résumé".encode(),
        "plain ascii only".encode(),
    ]
    ok = tot = 0
    for data in samples:
        for mx in range(0, len(data) + 2):
            tot += 1
            try:
                r = fn(data, mx)
                assert isinstance(r, (bytes, bytearray))
                assert len(r) <= mx and data.startswith(bytes(r))
                bytes(r).decode("utf-8")
                assert bytes(r) == _max_utf8_prefix(data, mx)
                ok += 1
            except Exception:
                pass
    return ok / tot


_UTF8 = ProbeTask(
    id="utf8_truncate",
    predicted_headroom="medium",
    problem_text=(
        "We cap user 'bio' text to a fixed number of bytes before storing it in a "
        "fixed-width column. Occasionally the saved value comes back corrupted — a "
        "replacement glyph at the end — and a downstream parser rejects the row."),
    contract=(
        "Implement `truncate_utf8(data, max_bytes)`: given UTF-8 `bytes` and a "
        "byte cap, return the longest prefix of `data` that is at most "
        "`max_bytes` bytes AND is itself valid UTF-8 (never split a multi-byte "
        "character)."),
    memory_hint=(
        "Slicing a UTF-8 byte string at an arbitrary offset can cut a multi-byte "
        "character in half, producing invalid UTF-8. Back the cut off to the "
        "nearest character boundary (bytes where the top bits are not a "
        "continuation `10xxxxxx`)."),
    verifier=ScoredVerifier(
        entry_point="truncate_utf8", harness=_utf8_harness, threshold=0.99,
        reference_solution=(
            "def truncate_utf8(data, max_bytes):\n"
            "    cut = min(max_bytes, len(data))\n"
            "    while 0 < cut < len(data) and (data[cut] & 0xC0) == 0x80:\n"
            "        cut -= 1\n"
            "    return data[:cut]\n"),
        naive_solution=(
            "def truncate_utf8(data, max_bytes):\n"
            "    return data[:max_bytes]\n")),
)


# --------------------------------------------------------------------------- #
# 3. Idempotent retry under lost ack (predicted MEDIUM — subtle failure mode)
# --------------------------------------------------------------------------- #
def _idem_harness(ns):
    fn = ns["charge_once"]

    class Gateway:
        def __init__(self):
            self.seen = {}          # key -> response (dedup store)
            self.effects = 0        # real charges applied
            self._flip = True       # first call: apply effect then drop the ack

        def charge(self, key, amount):
            if key in self.seen:
                return self.seen[key]          # deduped: no new effect
            self.effects += 1                  # the money actually moves
            self.seen[key] = {"ok": True, "amount": amount}
            if self._flip:
                self._flip = False
                raise TimeoutError("gateway ack lost (but charge applied)")
            return self.seen[key]

    trials = 0
    good = 0
    for t in range(5):
        trials += 1
        g = Gateway()
        try:
            fn(g, f"order-{t}", 100)
        except Exception:
            pass
        good += 1 if g.effects == 1 else 0     # exactly one real charge
    return good / trials


_IDEM = ProbeTask(
    id="idempotent_retry",
    predicted_headroom="medium",
    problem_text=(
        "Our checkout occasionally double-charges a customer. Digging in: the "
        "payment call sometimes throws a timeout even though the charge went "
        "through, and our code just tries again. The gateway can recognize a "
        "repeat if we ask it the right way."),
    contract=(
        "Implement `charge_once(gateway, order_id, amount)`. `gateway.charge(key, "
        "amount)` performs a charge but may raise `TimeoutError` *after* the money "
        "has moved; called again with the SAME key it returns the prior result "
        "without charging again. Ensure the customer is charged exactly once even "
        "when a timeout occurs, and return the gateway's response."),
    memory_hint=(
        "A timeout does not mean the side effect failed — the charge may have "
        "applied before the ack was lost. Retry with a STABLE idempotency key "
        "derived from the order (not a fresh key per attempt) so the gateway "
        "deduplicates the retry instead of charging twice."),
    verifier=ScoredVerifier(
        entry_point="charge_once", harness=_idem_harness, threshold=0.99,
        reference_solution=(
            "def charge_once(gateway, order_id, amount):\n"
            "    key = f'charge:{order_id}'\n"
            "    for _ in range(5):\n"
            "        try:\n"
            "            return gateway.charge(key, amount)\n"
            "        except TimeoutError:\n"
            "            continue\n"
            "    raise RuntimeError('exhausted')\n"),
        naive_solution=(  # fresh key per attempt -> double charge
            "def charge_once(gateway, order_id, amount):\n"
            "    import itertools, random\n"
            "    for i in range(5):\n"
            "        try:\n"
            "            return gateway.charge(f'{order_id}:{i}', amount)\n"
            "        except TimeoutError:\n"
            "            continue\n"
            "    raise RuntimeError('exhausted')\n")),
)


# --------------------------------------------------------------------------- #
# 4. Project-specific units fact (predicted HIGH — unknowable cold)
# --------------------------------------------------------------------------- #
def _units_harness(ns):
    fn = ns["to_celsius"]
    # ground truth: the feed encodes deci-kelvin (tenths of a kelvin)
    cases = [(2931, 293.1 - 273.15), (3000, 300.0 - 273.15), (2731, 273.1 - 273.15)]
    ok = 0
    for raw, exp in cases:
        try:
            if abs(float(fn(raw)) - exp) < 1e-6:
                ok += 1
        except Exception:
            pass
    return ok / len(cases)


_UNITS = ProbeTask(
    id="project_units_fact",
    predicted_headroom="high",
    problem_text=(
        "A dashboard shows temperatures from our `sensor_feed` integration, but "
        "every reading is wildly wrong — hundreds of degrees off. The raw integer "
        "values look like e.g. 2931, 3000, 2731. Write the converter to real "
        "Celsius."),
    contract=(
        "Implement `to_celsius(raw)`: given a raw integer reading from "
        "`sensor_feed`, return the temperature in degrees Celsius (float)."),
    memory_hint=(
        "We learned the hard way that `sensor_feed` reports temperature in "
        "deci-kelvin — tenths of a kelvin — not Celsius and not whole kelvin. So "
        "degrees Celsius = raw / 10 - 273.15."),
    verifier=ScoredVerifier(
        entry_point="to_celsius", harness=_units_harness, threshold=0.99,
        reference_solution="def to_celsius(raw):\n    return raw / 10 - 273.15\n",
        naive_solution="def to_celsius(raw):\n    return raw - 273.15\n"),  # assumes kelvin
)


# _DST is retained for reference but excluded from the screen: even the naive
# fixed-offset solution scores ~0.99 (it only misassigns events within ~1h of
# local midnight on transition days), so the verifier can't discriminate — which
# is itself the finding that day-bucketing is genuinely low-headroom for a
# capable model. The screen keeps the 3 tasks that discriminate (medium→high).
PROBE_TASKS = [_UTF8, _IDEM, _UNITS]
LOW_HEADROOM_REFERENCE = [_DST]
