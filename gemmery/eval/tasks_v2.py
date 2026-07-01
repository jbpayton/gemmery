"""Open-ended, objective-scored task set (Phase-0 v2).

The v1 seed set was *over-constrained*: each problem named its technique
("memoize this"), so it had one solution, a capable model solved it cold, and
"transfer" degenerated into recognizing a textbook pattern (answer-copying, not
method transfer).  This set fixes that.

Design rules (the shape that makes memory's value *measurable*):

1. **State a situation, never a technique.** "The game stutters under load",
   not "add a cache".
2. **Verify against an objective, not an exact output.** Each task has a
   :class:`ScoredVerifier` that runs the candidate against seeded instances and
   returns a continuous score in [0, 1] (Invariant 2: success is continuous and
   signed).  There is a *design space*; many solutions are valid, and "better vs
   worse" is what's measured.
3. **The transferable unit is an *approach/insight*, not a snippet.** Each
   ``approach_id`` is instantiated across surface-dissimilar domains; transfer
   means applying an insight found on a different-surface problem.
4. **Verifiers must discriminate.** Every approach ships a ``reference_solution``
   (a strong approach that should clear the threshold) and a ``naive_solution``
   (a plausible weak one that should NOT).  ``validate_discrimination`` asserts
   reference >= threshold > naive — a verifier that can't tell them apart is
   useless.

NOTE on execution: scoring runs candidate code via ``exec``.  Canonical/naive
solutions here are first-party; a real run with model-written code must sandbox.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Callable, Optional


# --------------------------------------------------------------------------- #
# Verifier
# --------------------------------------------------------------------------- #
@dataclass
class ScoredVerifier:
    entry_point: str                 # function/class the solver must define
    harness: Callable[[dict], float] # (exec'd namespace) -> score in [0, 1]
    threshold: float                 # score >= threshold => success (primary metric)
    reference_solution: str          # strong approach (clears threshold)
    naive_solution: str = ""         # weak baseline (should NOT clear threshold)

    @property
    def test_id(self) -> str:
        return f"score::{self.entry_point}"

    def score(self, code: str) -> float:
        ns: dict = {}
        try:
            exec(code, ns)  # noqa: S102 - first-party in tests; sandbox for model code
            if self.entry_point not in ns:
                return 0.0
            return float(self.harness(ns))
        except Exception:
            return 0.0


@dataclass
class Task:
    id: str
    family: str                # heuristic | optimization | property | debug_feature
    approach_id: str           # the transferable insight (shared across surfaces)
    surface_domain: str
    problem_text: str          # the SURFACE NARRATIVE only (situation, domain words)
    approach_sketch: str       # the transferable method/insight (for solution-sim + memory)
    contract: str = ""         # the API spec (entry point + signature) given to the solver
    verifier: Optional[ScoredVerifier] = None

    def prompt(self) -> str:
        """What the solver sees: the situation plus the API contract."""
        return f"{self.problem_text}\n\n{self.contract}".strip()

    # Aliases so v2 tasks drop into the v1 infra (decorrelation/harness/recall),
    # which key off schema_id / solution_sketch.  Decorrelation embeds
    # ``problem_text`` (narrative only), so the shared API contract does not
    # inflate same-approach surface similarity.
    @property
    def schema_id(self) -> str:
        return self.approach_id

    @property
    def solution_sketch(self) -> str:
        return self.approach_sketch


# Registry of approaches filled in by the family modules below.
APPROACHES: dict[str, str] = {}
_TASKS: list[Task] = []


def _register(task: Task) -> Task:
    _TASKS.append(task)
    return task


# --------------------------------------------------------------------------- #
# Helpers shared by harnesses
# --------------------------------------------------------------------------- #
def _clip01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _norm(candidate: float, naive: float, strong: float, *, higher_is_better=True) -> float:
    """Map a raw objective onto [0,1] between a naive floor and a strong anchor."""
    if higher_is_better:
        if strong <= naive:
            return 1.0 if candidate >= strong else 0.0
        return _clip01((candidate - naive) / (strong - naive))
    else:  # lower is better (makespan, length, runtime)
        if naive <= strong:
            return 1.0 if candidate <= strong else 0.0
        return _clip01((naive - candidate) / (naive - strong))


# =========================================================================== #
# FAMILY 1 — Heuristic / strategy design (objective = score on instances)
# =========================================================================== #

# --- Approach H_value_density: greedy by value-per-cost under a budget ------ #
APPROACHES["value_density_greedy"] = (
    "Selection under a budget: rank candidates by value-per-unit-cost (not raw "
    "value or raw cost), then take greedily while the budget holds; this beats "
    "value-first or cost-first ordering and gets near the optimal subset."
)


def _knapsack_optimal(items, budget):
    # 0/1 knapsack DP over (small) integer budget -> optimal value
    dp = [0] * (budget + 1)
    for v, c in items:
        for b in range(budget, c - 1, -1):
            dp[b] = max(dp[b], dp[b - c] + v)
    return dp[budget]


def _value_density_harness(entry: str):
    def harness(ns: dict) -> float:
        fn = ns[entry]
        rng = random.Random(7)
        scores = []
        for _ in range(40):
            n = 18
            # Wide cost spread + a tight budget is where value-first greedy
            # wastes budget on expensive high-value items and ratio-first wins.
            items = [(rng.randint(1, 60), rng.randint(1, 30)) for _ in range(n)]
            budget = max(1, sum(c for _, c in items) // 6)
            opt = _knapsack_optimal(items, budget)
            if opt == 0:
                continue
            sel = fn([dict(value=v, cost=c) for v, c in items], budget)
            idxs = list(sel or [])
            if len(set(idxs)) != len(idxs):
                scores.append(0.0); continue
            cost = sum(items[i][1] for i in idxs if 0 <= i < n)
            val = sum(items[i][0] for i in idxs if 0 <= i < n)
            scores.append(0.0 if cost > budget else val / opt)
        return sum(scores) / len(scores)
    return harness


_VD_REF = (
    "def {ep}(items, budget):\n"
    "    order = sorted(range(len(items)), key=lambda i: items[i]['value']/items[i]['cost'], reverse=True)\n"
    "    kept, spent = [], 0\n"
    "    for i in order:\n"
    "        if spent + items[i]['cost'] <= budget:\n"
    "            kept.append(i); spent += items[i]['cost']\n"
    "    return kept\n"
)
_VD_NAIVE = (
    "def {ep}(items, budget):\n"
    "    order = sorted(range(len(items)), key=lambda i: items[i]['value'], reverse=True)\n"
    "    kept, spent = [], 0\n"
    "    for i in order:\n"
    "        if spent + items[i]['cost'] <= budget:\n"
    "            kept.append(i); spent += items[i]['cost']\n"
    "    return kept\n"
)


_VD_CONTRACT = (
    "Implement `select(items, budget)`: `items` is a list of dicts each with "
    "keys `value` (the benefit) and `cost`; return the list of chosen indices "
    "whose total `cost` does not exceed `budget`."
)


def _vd_task(tid, surface, narrative):
    ep = "select"
    return _register(Task(
        id=tid, family="heuristic", approach_id="value_density_greedy",
        surface_domain=surface, problem_text=narrative, contract=_VD_CONTRACT,
        approach_sketch=APPROACHES["value_density_greedy"],
        verifier=ScoredVerifier(
            entry_point=ep, harness=_value_density_harness(ep), threshold=0.90,
            reference_solution=_VD_REF.format(ep=ep),
            naive_solution=_VD_NAIVE.format(ep=ep)),
    ))


_vd_task("cdn_admit", "cdn",
         "An edge node can only hold so many bytes before it has to drop "
         "something. Each object it might keep takes up a known amount of room "
         "and would serve a known number of future visitors straight from the "
         "edge. The team wants the node to answer as many visits as it can from "
         "what it keeps, without overflowing the space it has.")
_vd_task("ad_budget", "advertising",
         "A marketing group has a fixed amount to spend this quarter and a long "
         "shortlist of possible placements. Each placement quotes a price and an "
         "analyst's estimate of how many sign-ups it would drive. They want the "
         "mix of placements that brings in the most sign-ups while staying inside "
         "the money they have.")
_vd_task("foodbank", "logistics",
         "Volunteers loading a relief truck can only fit so much before it is "
         "full. Every pallet waiting on the dock takes a known share of the "
         "deck and would feed a known number of households. They want the truck "
         "to leave carrying the load that helps the most households and still "
         "closes its doors.")


# --- Approach H_lpt: sort descending, place on the least-loaded ------------- #
APPROACHES["longest_first_balance"] = (
    "Partitioning items across bins/machines to balance load: process the "
    "largest items first and always place the next item where it hurts least "
    "(the currently least-loaded bin). Largest-first + least-loaded beats "
    "arbitrary or smallest-first order and keeps the max load low."
)


def _lpt_harness(entry: str):
    def harness(ns: dict) -> float:
        fn = ns[entry]
        rng = random.Random(11)
        scores = []
        for _ in range(25):
            m = rng.randint(3, 5)
            jobs = [rng.randint(1, 20) for _ in range(rng.randint(12, 18))]
            # anchors on the same instance
            naive_ms = _lpt_makespan(jobs, m, order="asis")
            strong_ms = _lpt_makespan(jobs, m, order="desc")
            assign = fn(list(jobs), m)
            ms = _assignment_makespan(jobs, m, assign)
            if ms is None:
                scores.append(0.0); continue
            scores.append(_norm(ms, naive_ms, strong_ms, higher_is_better=False))
        return sum(scores) / len(scores)
    return harness


def _assignment_makespan(jobs, m, assign):
    if assign is None or len(assign) != len(jobs):
        return None
    loads = [0] * m
    for j, b in zip(jobs, assign):
        if not (0 <= b < m):
            return None
        loads[b] += j
    return max(loads)


def _lpt_makespan(jobs, m, order):
    idx = sorted(range(len(jobs)), key=lambda i: jobs[i], reverse=(order == "desc"))
    loads = [0] * m
    for i in idx:
        b = min(range(m), key=lambda k: loads[k])
        loads[b] += jobs[i]
    return max(loads)


_LPT_REF = (
    "def {ep}(jobs, m):\n"
    "    order = sorted(range(len(jobs)), key=lambda i: jobs[i], reverse=True)\n"
    "    loads = [0]*m; assign=[0]*len(jobs)\n"
    "    for i in order:\n"
    "        b = min(range(m), key=lambda k: loads[k])\n"
    "        assign[i]=b; loads[b]+=jobs[i]\n"
    "    return assign\n"
)
_LPT_NAIVE = (
    "def {ep}(jobs, m):\n"
    "    return [i % m for i in range(len(jobs))]\n"  # round-robin in arrival order
)


_LPT_CONTRACT = (
    "Implement `assign(jobs, m)`: `jobs` is a list of numeric loads and `m` is "
    "the number of bins; return a list the same length as `jobs` mapping each "
    "job to a bin index in 0..m-1, keeping the most-loaded bin as light as "
    "possible."
)


def _lpt_task(tid, surface, narrative):
    ep = "assign"
    return _register(Task(
        id=tid, family="heuristic", approach_id="longest_first_balance",
        surface_domain=surface, problem_text=narrative, contract=_LPT_CONTRACT,
        approach_sketch=APPROACHES["longest_first_balance"],
        verifier=ScoredVerifier(
            entry_point=ep, harness=_lpt_harness(ep), threshold=0.85,
            reference_solution=_LPT_REF.format(ep=ep),
            naive_solution=_LPT_NAIVE.format(ep=ep)),
    ))


_lpt_task("ci_shards", "devops",
          "Our test pipeline fans a big pile of test files out over several "
          "build agents running side by side. Each file takes a known time, and "
          "the whole run is only as fast as whichever agent finishes last. Right "
          "now some agents sit idle while one slogs through the heavy files.")
_lpt_task("disk_pack", "storage",
          "We are spreading a collection of archive files across a handful of "
          "drives. Every file has a fixed size, and what we care about is that no "
          "single drive ends up far more crammed than the others — the fullest "
          "drive is what runs out of room first.")
_lpt_task("rider_vans", "delivery",
          "A depot splits the morning's parcels among its delivery vans before "
          "they set off. Each parcel has a weight, and a fair, safe split means "
          "the most heavily laden van is carrying as little as we can manage "
          "given how the weights fall.")


# =========================================================================== #
# FAMILY 3 — Behavioral / property design (verified by property tests)
# =========================================================================== #

# --- Approach P_rolling_window: admit under a true rolling-window bound ------ #
APPROACHES["rolling_window_limit"] = (
    "Enforce 'at most N events per window' against a *sliding* window, not a "
    "fixed/aligned one: track the timestamps of recent admits and admit only "
    "when the count within the trailing window stays under N. Fixed-window "
    "counters look right but double-admit across the boundary; the rolling view "
    "stays safe while admitting as early as possible."
)


class _RefLimiter:
    def __init__(self, n, w):
        self.n, self.w, self.log = n, w, []

    def allow(self, t):
        self.log = [x for x in self.log if x > t - self.w]
        if len(self.log) < self.n:
            self.log.append(t); return True
        return False


def _schedules(rng):
    out = []
    # steady sub-rate
    out.append(("steady", 5, 10.0, [i * 2.5 for i in range(30)]))
    # bursty: clumps of arrivals
    b = []
    for k in range(6):
        base = k * 12.0
        b += [base + j * 0.1 for j in range(10)]
    out.append(("burst", 5, 10.0, sorted(b)))
    # over-rate flood
    out.append(("flood", 4, 8.0, [i * 0.5 for i in range(40)]))
    # random jitter
    t = 0.0; r = []
    for _ in range(35):
        t += rng.uniform(0.3, 3.0); r.append(round(t, 3))
    out.append(("jitter", 6, 9.0, r))
    return out


def _limiter_harness(entry: str):
    def harness(ns: dict) -> float:
        Cls = ns[entry]
        rng = random.Random(3)
        scores = []
        for _name, n, w, sched in _schedules(rng):
            # candidate run
            try:
                lim = Cls(n, w)
                admitted = [t for t in sched if lim.allow(t)]
            except Exception:
                scores.append(0.0); continue
            # SAFETY: no rolling window of length w contains > n admits
            safe = True
            for i, te in enumerate(admitted):
                cnt = sum(1 for x in admitted if te - w < x <= te)
                if cnt > n:
                    safe = False; break
            if not safe:
                scores.append(0.0); continue
            # UTILIZATION vs the optimal early-admit (the reference is optimal)
            ref = _RefLimiter(n, w)
            ideal = sum(1 for t in sched if ref.allow(t))
            scores.append(len(admitted) / ideal if ideal else 1.0)
        return sum(scores) / len(scores)
    return harness


_LIM_REF = (
    "class {ep}:\n"
    "    def __init__(self, n, w):\n"
    "        self.n, self.w, self.log = n, w, []\n"
    "    def allow(self, t):\n"
    "        self.log = [x for x in self.log if x > t - self.w]\n"
    "        if len(self.log) < self.n:\n"
    "            self.log.append(t); return True\n"
    "        return False\n"
)
# Fixed-window counter: resets every aligned window -> double-admits at borders.
_LIM_NAIVE = (
    "class {ep}:\n"
    "    def __init__(self, n, w):\n"
    "        self.n, self.w, self.count, self.bucket = n, w, 0, None\n"
    "    def allow(self, t):\n"
    "        b = int(t // self.w)\n"
    "        if b != self.bucket:\n"
    "            self.bucket, self.count = b, 0\n"
    "        if self.count < self.n:\n"
    "            self.count += 1; return True\n"
    "        return False\n"
)


_LIM_CONTRACT = (
    "Implement a class `Limiter(n, w)` with a method `allow(t) -> bool`, called "
    "once per event in non-decreasing time order `t`; return True to admit. The "
    "count of admitted events within any trailing window of length `w` must "
    "never exceed `n`, while admitting as many as that rule allows."
)


def _lim_task(tid, surface, narrative):
    ep = "Limiter"
    return _register(Task(
        id=tid, family="property", approach_id="rolling_window_limit",
        surface_domain=surface, problem_text=narrative, contract=_LIM_CONTRACT,
        approach_sketch=APPROACHES["rolling_window_limit"],
        verifier=ScoredVerifier(
            entry_point=ep, harness=_limiter_harness(ep), threshold=0.85,
            reference_solution=_LIM_REF.format(ep=ep),
            naive_solution=_LIM_NAIVE.format(ep=ep)),
    ))


_lim_task("api_quota", "api",
          "Customers keep tripping our abuse protection. Traffic arrives in "
          "clumps, and the contract we sold promises each account a ceiling on "
          "calls over any recent stretch of time. The current check resets on a "
          "fixed clock tick, so a clump straddling a tick sails through at double "
          "the rate we promised, and support is fielding the complaints.")
_lim_task("queue_shaper", "messaging",
          "Whenever our dispatcher releases work too densely, the service it "
          "feeds tips over. Operations agreed on a ceiling for how much may go "
          "out over any recent few moments, and within that we want throughput "
          "as high as it allows — no more stampedes that knock the consumer "
          "offline.")
_lim_task("spawn_gate", "gamedev",
          "Playtesters say the arena feels unfair when too many creatures pop in "
          "right on top of each other. The designers set a cap on how many may "
          "appear across any recent slice of play, and we want to keep waves "
          "feeling intense by spawning right up to that cap but never past it.")


# --------------------------------------------------------------------------- #
# Build + validate
# --------------------------------------------------------------------------- #
def build_tasks() -> list[Task]:
    """All v2 tasks (deduplicated, stable order)."""
    seen, out = set(), []
    for t in _TASKS:
        if t.id not in seen:
            seen.add(t.id); out.append(t)
    return out


@dataclass
class Discrimination:
    approach_id: str
    surface: str
    task_id: str
    threshold: float
    reference_score: float
    naive_score: float
    discriminates: bool


def validate_discrimination(tasks: Optional[list[Task]] = None) -> list[Discrimination]:
    """Assert each verifier separates a strong approach from a weak one.

    A verifier where the naive baseline also clears the threshold (or the
    reference does not) cannot measure whether a method helped — it is useless
    for the experiment.  This is the per-task analogue of the kill-switch.
    """
    tasks = tasks if tasks is not None else build_tasks()
    out = []
    for t in tasks:
        v = t.verifier
        if v is None:
            continue
        ref = v.score(v.reference_solution)
        naive = v.score(v.naive_solution) if v.naive_solution else 0.0
        out.append(Discrimination(
            approach_id=t.approach_id, surface=t.surface_domain, task_id=t.id,
            threshold=v.threshold, reference_score=ref, naive_score=naive,
            discriminates=(ref >= v.threshold and naive < v.threshold)))
    return out


# =========================================================================== #
# FAMILY 2 — Optimization ("make it fast/good-enough")
# =========================================================================== #
# Verified deterministically by *element-access count* (not flaky wall-clock):
# a re-scanning solution touches the data O(range) times per query; a cumulative
# precompute touches it ~O(n) once and answers queries without touching it.

class _Counting:
    """A sequence that counts element accesses (the 'cost' meter)."""

    def __init__(self, data):
        self._d = list(data); self.n_access = 0

    def __len__(self):
        return len(self._d)

    def __getitem__(self, k):
        if isinstance(k, slice):
            r = range(*k.indices(len(self._d)))
            self.n_access += len(r)
            return [self._d[i] for i in r]
        self.n_access += 1
        return self._d[k]

    def __iter__(self):
        for x in self._d:
            self.n_access += 1
            yield x


APPROACHES["cumulative_precompute"] = (
    "Answer many range-aggregate queries by precomputing a cumulative/prefix "
    "structure once (one pass), then each query is O(1) arithmetic on the prefix "
    "array instead of re-scanning the range. Trades a single linear preprocess "
    "for constant-time queries."
)


def _prefix_harness(entry: str):
    def harness(ns: dict) -> float:
        Cls = ns[entry]
        rng = random.Random(5)
        scores = []
        for _ in range(4):
            N = 1500
            raw = [rng.randint(0, 100) for _ in range(N)]
            qs = []
            for _q in range(400):
                a, b = rng.randrange(N), rng.randrange(N + 1)
                qs.append((min(a, b), max(a, b)))
            pre = [0]
            for x in raw:
                pre.append(pre[-1] + x)
            truth = [pre[hi] - pre[lo] for lo, hi in qs]
            data = _Counting(raw)
            try:
                q = Cls(data)
                out = [q.query(lo, hi) for lo, hi in qs]
            except Exception:
                scores.append(0.0); continue
            if out != truth:
                scores.append(0.0); continue  # must be correct first
            naive_acc = sum(hi - lo for lo, hi in qs)  # re-scan each query
            strong_acc = N                              # single pass
            scores.append(_norm(data.n_access, naive_acc, strong_acc,
                                higher_is_better=False))
        return sum(scores) / len(scores)
    return harness


_PRE_REF = (
    "class {ep}:\n"
    "    def __init__(self, data):\n"
    "        self.p = [0]\n"
    "        for x in data: self.p.append(self.p[-1] + x)\n"
    "    def query(self, lo, hi):\n"
    "        return self.p[hi] - self.p[lo]\n"
)
_PRE_NAIVE = (
    "class {ep}:\n"
    "    def __init__(self, data):\n"
    "        self.data = data\n"
    "    def query(self, lo, hi):\n"
    "        return sum(self.data[i] for i in range(lo, hi))\n"
)


_PRE_CONTRACT = (
    "Implement a class `RangeQuerier(data)` (data is a fixed sequence of "
    "numbers) with a method `query(lo, hi)` returning the sum of data[lo:hi]. "
    "It will be constructed once and queried very many times; keep repeated "
    "queries cheap."
)


def _pre_task(tid, surface, narrative):
    ep = "RangeQuerier"
    return _register(Task(
        id=tid, family="optimization", approach_id="cumulative_precompute",
        surface_domain=surface, problem_text=narrative, contract=_PRE_CONTRACT,
        approach_sketch=APPROACHES["cumulative_precompute"],
        verifier=ScoredVerifier(
            entry_point=ep, harness=_prefix_harness(ep), threshold=0.85,
            reference_solution=_PRE_REF.format(ep=ep),
            naive_solution=_PRE_NAIVE.format(ep=ep)),
    ))


_pre_task("ts_dashboard", "observability",
          "Analysts keep dragging the selector on our metrics chart to ask for "
          "the total over this stretch of history, then that one, then another. "
          "The series itself never changes once loaded, but every drag walks the "
          "whole selected span again, and the panel visibly stalls before it "
          "redraws.")
_pre_task("pixel_band", "imaging",
          "In the photo tool, when someone sweeps a selection brush along a row "
          "of the picture we report the combined brightness under it. People "
          "scrub back and forth constantly, and each little move re-adds every "
          "pixel beneath the selection, so the readout lags behind the cursor.")
_pre_task("ngram_range", "text-analytics",
          "Reviewers highlight passages of a long manuscript and we show the "
          "combined weight of the words they covered. The manuscript is fixed for "
          "the session, but every new highlight re-tallies the whole span from "
          "scratch, and on book-length inputs the number arrives noticeably late.")


# =========================================================================== #
# FAMILY 4 — Debug / feature (build it to satisfy a behavior suite)
# =========================================================================== #
APPROACHES["recursive_descent_precedence"] = (
    "Evaluate an operator language with one parse routine per precedence level "
    "(lowest-binding handled outermost, highest innermost, recursing for "
    "parentheses), so precedence and associativity fall out of the call "
    "structure. A flat left-to-right fold gets precedence wrong."
)


def _cases_harness(entry: str, cases):
    def harness(ns: dict) -> float:
        fn = ns[entry]
        ok = 0
        for expr, expected in cases:
            try:
                got = fn(expr)
                if isinstance(expected, float):
                    ok += abs(got - expected) < 1e-6
                else:
                    ok += (got == expected)
            except Exception:
                pass
        return ok / len(cases)
    return harness


_ARITH_CASES = [
    ("2+3*4", 14), ("(2+3)*4", 20), ("2**3**2", 512), ("10-2-3", 5),
    ("2*3+4*5", 26), ("100/4/5", 5), ("2+2**3", 10), ("(1+2)*(3+4)", 21),
    ("7-3+2", 6), ("2*2**3", 16),
]
_BOOL_CASES = [
    ("T or F and F", True), ("not T or T", True), ("T and F or T", True),
    ("not (T or F)", False), ("F or F or T", True), ("T and T and F", False),
    ("not F and T", True), ("(T or F) and F", False),
]

_ARITH_REF = r'''
def {ep}(s):
    toks=[]; i=0
    while i < len(s):
        c=s[i]
        if c==' ': i+=1; continue
        if c=='*' and i+1<len(s) and s[i+1]=='*': toks.append('**'); i+=2; continue
        if c in '+-*/()': toks.append(c); i+=1; continue
        j=i
        while j<len(s) and (s[j].isdigit() or s[j]=='.'): j+=1
        toks.append(s[i:j]); i=j
    pos=[0]
    def peek():
        return toks[pos[0]] if pos[0]<len(toks) else None
    def eat():
        t=toks[pos[0]]; pos[0]+=1; return t
    def expr():
        v=term()
        while peek() in ('+','-'):
            op=eat(); v = v+term() if op=='+' else v-term()
        return v
    def term():
        v=power()
        while peek() in ('*','/'):
            op=eat(); v = v*power() if op=='*' else v/power()
        return v
    def power():
        v=factor()
        if peek()=='**':
            eat(); v = v ** power()
        return v
    def factor():
        t=peek()
        if t=='(':
            eat(); v=expr(); eat(); return v
        if t=='-':
            eat(); return -factor()
        return float(eat())
    r=expr()
    return int(r) if r==int(r) else r
'''
_ARITH_NAIVE = r'''
def {ep}(s):
    # flat left-to-right, ignores precedence
    s=s.replace('(','').replace(')','').replace('**','^')
    toks=s.split()
    if len(toks)==1: return float(toks[0])
    import re
    parts=re.findall(r'\d+\.?\d*|[+\-*/^]', s.replace(' ',''))
    v=float(parts[0]); i=1
    while i<len(parts):
        op=parts[i]; n=float(parts[i+1]); i+=2
        v = v+n if op=='+' else v-n if op=='-' else v*n if op=='*' else v/n if op=='/' else v**n
    return int(v) if v==int(v) else v
'''

_BOOL_REF = r'''
def {ep}(s):
    toks=s.replace('(',' ( ').replace(')',' ) ').split()
    pos=[0]
    def peek(): return toks[pos[0]] if pos[0]<len(toks) else None
    def eat(): t=toks[pos[0]]; pos[0]+=1; return t
    def or_():
        v=and_()
        while peek()=='or':
            eat(); rhs=and_(); v = v or rhs  # force rhs: 'or' short-circuits the parse
        return v
    def and_():
        v=not_()
        while peek()=='and':
            eat(); rhs=not_(); v = v and rhs  # force rhs: 'and' short-circuits the parse
        return v
    def not_():
        if peek()=='not': eat(); return not not_()
        return atom()
    def atom():
        t=eat()
        if t=='(':
            v=or_(); eat(); return v
        return t=='T'
    return or_()
'''
_BOOL_NAIVE = r'''
def {ep}(s):
    toks=s.replace('(','').replace(')','').split()
    v = toks[0]=='T'; i=1
    while i<len(toks):
        op=toks[i]
        if op=='not': v = (toks[i+1]!='T'); i+=2; continue
        rhs = toks[i+1]=='T'; i+=2
        v = (v or rhs) if op=='or' else (v and rhs)
    return v
'''


def _eval_task(tid, surface, narrative, contract, cases, ref, naive):
    ep = "evaluate"
    return _register(Task(
        id=tid, family="debug_feature", approach_id="recursive_descent_precedence",
        surface_domain=surface, problem_text=narrative, contract=contract,
        approach_sketch=APPROACHES["recursive_descent_precedence"],
        verifier=ScoredVerifier(
            entry_point=ep, harness=_cases_harness(ep, cases), threshold=0.99,
            reference_solution=ref.format(ep=ep),
            naive_solution=naive.format(ep=ep)),
    ))


_eval_task("calc_arith", "developer-tools",
           "Users of our spreadsheet type little formulas into the cell bar and "
           "expect them to come out the way a calculator would. Right now the "
           "results are wrong whenever a formula mixes operations, because the "
           "current code just folds the symbols together from left to right.",
           "Implement `evaluate(s)` returning the numeric value of an arithmetic "
           "string over `+ - * /`, exponent `**`, and parentheses. Honor "
           "precedence: `**` binds tightest and is right-associative, then `*` "
           "and `/`, then `+` and `-`; parentheses override.",
           _ARITH_CASES, _ARITH_REF, _ARITH_NAIVE)
_eval_task("calc_bool", "rules-engine",
           "Our product lets non-engineers write toggle conditions for feature "
           "rollouts as short logic phrases. Lately some flags fire when they "
           "shouldn't: the evaluator reads the words strictly in order and "
           "ignores how the connectives are meant to group.",
           "Implement `evaluate(s)` returning the boolean value of a string over "
           "the literals `T` and `F`, the connectives `not`/`and`/`or`, and "
           "parentheses. Honor precedence: `not` binds tightest, then `and`, "
           "then `or`; parentheses override.",
           _BOOL_CASES, _BOOL_REF, _BOOL_NAIVE)


# --- Approach O_single_pass_seen: hash-set single pass vs nested scan -------- #
APPROACHES["single_pass_seen"] = (
    "Detect a repeat / membership condition in one linear pass while remembering "
    "what you've already seen in a hash set, instead of an O(n^2) nested loop "
    "that re-compares every earlier element. One pass, constant-time membership."
)


def _seen_harness(entry: str):
    def harness(ns: dict) -> float:
        fn = ns[entry]
        rng = random.Random(13)
        scores = []
        for _ in range(6):
            N = 600
            # mostly no-duplicate (worst case for the nested scan)
            raw = rng.sample(range(100000), N) if rng.random() < 0.7 else \
                [rng.randint(0, 50) for _ in range(N)]
            # truth
            seen = set(); truth = -1
            for i, x in enumerate(raw):
                if x in seen:
                    truth = i; break
                seen.add(x)
            data = _Counting(raw)
            try:
                got = fn(data)
            except Exception:
                scores.append(0.0); continue
            if got != truth:
                scores.append(0.0); continue
            naive_acc = N * N  # nested loop on the no-dup case
            strong_acc = 2 * N
            scores.append(_norm(data.n_access, naive_acc, strong_acc,
                                higher_is_better=False))
        return sum(scores) / len(scores)
    return harness


_SEEN_REF = (
    "def {ep}(data):\n"
    "    seen=set()\n"
    "    for i,x in enumerate(data):\n"
    "        if x in seen: return i\n"
    "        seen.add(x)\n"
    "    return -1\n"
)
_SEEN_NAIVE = (
    "def {ep}(data):\n"
    "    for i in range(len(data)):\n"
    "        for j in range(i):\n"
    "            if data[i]==data[j]: return i\n"
    "    return -1\n"
)


_SEEN_CONTRACT = (
    "Implement `first_repeat_index(data)` returning the index of the first "
    "element whose value already appeared earlier in `data`, or -1 if every "
    "value is distinct. It must stay fast on long inputs."
)


def _seen_task(tid, surface, narrative):
    ep = "first_repeat_index"
    return _register(Task(
        id=tid, family="optimization", approach_id="single_pass_seen",
        surface_domain=surface, problem_text=narrative, contract=_SEEN_CONTRACT,
        approach_sketch=APPROACHES["single_pass_seen"],
        verifier=ScoredVerifier(
            entry_point=ep, harness=_seen_harness(ep), threshold=0.85,
            reference_solution=_SEEN_REF.format(ep=ep),
            naive_solution=_SEEN_NAIVE.format(ep=ep)),
    ))


_seen_task("dup_txn", "payments",
           "Our charge-back team needs to be told the moment a payment reference "
           "comes through that we have already seen earlier in the day's feed — "
           "the first one that recurs. The check we have grinds to a halt on the "
           "common case where the whole day's feed is clean.")
_seen_task("dup_frame", "video",
           "While ingesting a long capture, the editor wants the position of the "
           "earliest frame that is a repeat of one shown before it, so it can cut "
           "the loop. Comparing each frame against all the ones before it makes "
           "import crawl on lengthy footage.")
