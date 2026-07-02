"""Drift evaluation — does revision-at-a-stable-path beat append-only notes?

Same 3-arm methodology as werewolf/gnosia (cold / markdown / gemmery), but on a
task where staying CURRENT matters: at game 30 of a 60-game history, P2's tells
INVERT. Phase A: P2 is silent when innocent and fakes a Seer claim when it is
the wolf. Phase B (reformed/new meta): P2 claims Seer *habitually as an innocent*
and its wolf tell becomes SILENCE. The other players are stable controls.

* markdown arm: the classic notes.md — every observation appended chronologically,
  read it all. The evidence CONTRADICTS itself across phases; the reader must
  notice the drift on its own.
* gemmery arm: the skill's discipline — dossiers at stable paths, REVISED when
  the drift was detected (mechanically templated from a recency window, so no
  hand-written intelligence is injected); prior versions in history; the
  revision consumed the phase-B observations that forced it.
* cold arm: transcripts only.

Deterministic backbone: a likelihood-ratio detector fed profiles built from
ALL 60 games (the md-analog) vs a recent window (the dossier-analog) vs cold,
scored over 300 mechanically-generated test games.
"""
from __future__ import annotations

import json
import random
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from gemmery import (Action, Gem, GitStore, IndexKeys, KnowledgeBody, Kind,  # noqa: E402
                     ObservationBody, Provenance, TestSpec)

PLAYERS = ["P1", "P2", "P3", "P4"]
N_HIST, DRIFT_AT, WINDOW = 60, 45, 15
HIDE_P = 0.5   # in the current regime wolves HIDE their tell half the time
TS = 1_700_200_000

# behavior vocabulary per game: what each player visibly did
#   seer_claim | silent | accuse:<target> | bandwagon
def tells(phase):
    """tells[player][role] -> behavior. P2 INVERTS at phase B; others stable."""
    t = {
        "P1": {"vil": "accuse:P2", "wolf": "accuse:P0"},
        "P3": {"vil": "bandwagon", "wolf": "silent"},
        "P4": {"vil": "accuse:P1", "wolf": "bandwagon"},
    }
    if phase == "A":
        t["P2"] = {"vil": "silent", "wolf": "seer_claim"}
    else:  # inverted: the SAME behaviors mean the OPPOSITE
        t["P2"] = {"vil": "seer_claim", "wolf": "silent"}
    return t


def gen_game(i, rng, phase=None, wolf=None):
    phase = phase or ("A" if i < DRIFT_AT else "B")
    t = tells(phase)
    if wolf is None:
        # phase A is P2-wolf-biased: builds a STRONG stale "P2 fakes Seer" signal
        wolf = ("P2" if rng.random() < 0.4 else rng.choice(PLAYERS)) if phase == "A" \
            else rng.choice(PLAYERS)
    beh = {}
    for p in PLAYERS:
        if p == wolf:
            # in the current regime wolves often HIDE: mimic their innocent self
            if phase == "B" and rng.random() < HIDE_P:
                beh[p] = t[p]["vil"]
            else:
                beh[p] = t[p]["wolf"]
        else:
            beh[p] = t[p]["vil"]
    return {"i": i, "phase": phase, "wolf": wolf, "behavior": beh}


def render_behavior(p, b):
    return {"seer_claim": f'{p} claimed to be the Seer ("trust me").',
            "silent": f"{p} stayed silent, offering nothing.",
            "bandwagon": f"{p} echoed the day's leading accusation.",
            }.get(b) or f'{p} said: "I think {b.split(":")[1]} is the werewolf."'


def transcript(g):
    return "\n".join("  " + render_behavior(p, g["behavior"][p]) for p in PLAYERS)


def record_line(g, p):
    role = "the WEREWOLF" if g["wolf"] == p else "innocent"
    return f"Game {g['i']:02d}: {p} was {role}. {render_behavior(p, g['behavior'][p])}"


# --------------------------------------------------------------------------- #
# profiles + deterministic detector (likelihood ratio per observed behavior)
# --------------------------------------------------------------------------- #
def profile(games, window=None):
    gs = games[-window:] if window else games
    prof = {p: {} for p in PLAYERS}
    for g in gs:
        for p in PLAYERS:
            b = g["behavior"][p]
            cell = prof[p].setdefault(b, [0, 0])   # [as_wolf, as_innocent]
            cell[0 if g["wolf"] == p else 1] += 1
    return prof


def detect(game, prof, rng):
    best, score_best = None, -1e9
    for p in PLAYERS:
        b = game["behavior"][p]
        w, v = prof[p].get(b, [0, 0])
        score = (w + 0.5) / (w + v + 1.0) + rng.random() * 1e-9
        if score > score_best:
            best, score_best = p, score
    return best


def deterministic_backbone(hist):
    rng = random.Random(9)
    tests = [gen_game(1000 + k, rng, phase="B") for k in range(300)]
    out = {}
    for label, prof in [("all-history (md-analog)", profile(hist)),
                        (f"recent-{WINDOW} (dossier-analog)", profile(hist, WINDOW))]:
        ok = sum(detect(t, prof, rng) == t["wolf"] for t in tests)
        out[label] = ok / len(tests)
    out["cold (uniform)"] = 0.25
    # the discriminating cell: P2 is the wolf (silent — its NEW tell)
    p2t = [t for t in tests if t["wolf"] == "P2"]
    out["P2-wolf cell, all-history"] = sum(
        detect(t, profile(hist), rng) == "P2" for t in p2t) / len(p2t)
    out["P2-wolf cell, recent"] = sum(
        detect(t, profile(hist, WINDOW), rng) == "P2" for t in p2t) / len(p2t)
    return out


# --------------------------------------------------------------------------- #
# dossiers: mechanically templated from a window (no hand-written intelligence)
# --------------------------------------------------------------------------- #
def dossier_text(p, prof_window, version, note=""):
    lines = [f"# Tell dossier: {p} (v{version})", ""]
    if note:
        lines += [note, ""]
    lines.append("Behavior counts in the evidence window (as wolf / as innocent):")
    for b, (w, v) in sorted(prof_window[p].items()):
        lines.append(f"  - {b}: wolf {w} / innocent {v}")
    strongest = max(prof_window[p].items(),
                    key=lambda kv: (kv[1][0] + 0.5) / (sum(kv[1]) + 1.0))
    lines.append(f"\nCurrent wolf-indicative behavior: **{strongest[0]}** "
                 f"({strongest[1][0]} wolf / {strongest[1][1]} innocent in window).")
    return "\n".join(lines)


def build():
    rng = random.Random(4)
    hist = [gen_game(i, rng) for i in range(N_HIST)]

    # ---- REAL gemmery store: observations -> dossiers v1 -> revised v2 ----
    if (ROOT / "store").exists():
        shutil.rmtree(ROOT / "store")
    store = GitStore(ROOT / "store", actor="focal-P0")
    obs = {p: [] for p in PLAYERS}
    for g in hist:
        for p in PLAYERS:
            gem = Gem(kind=Kind.observation,
                      provenance=Provenance("focal-P0", "hist", timestamp=TS + g["i"]),
                      body=ObservationBody(content=record_line(g, p)),
                      index_keys=IndexKeys(action_type="observation", domain=[p]))
            obs[p].append(store.capture(gem, path=f"history/{p}/game-{g['i']:02d}").sha)

    prof_A = profile(hist[:DRIFT_AT])
    prof_now = profile(hist, WINDOW)
    v1_sha, v2_sha = {}, {}
    for j, p in enumerate(PLAYERS):
        g1 = Gem(kind=Kind.knowledge,
                 provenance=Provenance("focal-P0", "hist", timestamp=TS + 200 + j),
                 body=KnowledgeBody(action=Action("consolidate_tell", {"player": p}),
                                    reasoning=dossier_text(p, prof_A, 1),
                                    belief=f"{p} tells",
                                    tests=[TestSpec(f"tell::{p}", "reveals", "predicts")]),
                 consumed=obs[p][:DRIFT_AT],
                 index_keys=IndexKeys(action_type="tell", domain=[p]))
        v1_sha[p] = store.capture(g1, path=f"knowledge/tells/{p}").sha
        note = ""
        if p == "P2":
            note = (f"**REVISED after game {DRIFT_AT}.** Recent games contradict "
                    "v1: the behaviors have inverted. See history for the "
                    "superseded version; this revision consumed the post-drift "
                    "observations.")
        g2 = Gem(kind=Kind.knowledge,
                 provenance=Provenance("focal-P0", "hist", timestamp=TS + 300 + j),
                 body=KnowledgeBody(action=Action("revise_tell", {"player": p}),
                                    reasoning=dossier_text(p, prof_now, 2, note),
                                    belief=f"{p} tells (current)",
                                    tests=[TestSpec(f"tell::{p}", "reveals", "predicts")]),
                 consumed=obs[p][DRIFT_AT:],
                 index_keys=IndexKeys(action_type="tell", domain=[p]))
        v2_sha[p] = store.revise(g2, f"knowledge/tells/{p}").sha

    # ---- markdown arm: the classic append-only notes.md -------------------
    from gemmery.baselines import MarkdownMemory
    md = MarkdownMemory(ROOT / "notes.md"); md.clear()
    for g in hist:
        for p in PLAYERS:
            md.capture(record_line(g, p))

    # ---- test games (current regime). The discriminating cell: the real wolf
    # HIDES its tell while innocent P2 shows its new Seer habit — a stale
    # reader false-positives P2. hide=None samples; hide=True forces the cell.
    trng = random.Random(77)
    spec = [("P4", True), ("P1", True), ("P2", None), ("P3", True),
            ("P1", False), ("P2", None), ("P4", None), ("P3", False)]
    tests = []
    for k, (w, hide) in enumerate(spec):
        g = gen_game(900 + k, trng, phase="B", wolf=w)
        if hide is not None and w != "P2":
            t = tells("B")
            g["behavior"][w] = t[w]["vil" if hide else "wolf"]
        tests.append(g)
    truth = {f"T{k}": t["wolf"] for k, t in enumerate(tests)}
    json.dump(truth, open(ROOT / "truth.json", "w"), indent=1)

    # ---- prompts -----------------------------------------------------------
    RULE = ("You observe games of Werewolf among P1, P2, P3, P4 — exactly one is "
            "the Werewolf each game. For EACH game below, name the most likely "
            "Werewolf. A Seer claim may be a lie. Return ONLY JSON mapping game "
            'id to player, e.g. {"T0":"P2"}.\n\n')
    games_block = "".join(f"=== GAME T{k} ===\n{transcript(t)}\n\n"
                          for k, t in enumerate(tests))

    (ROOT / "prompt_cold.txt").write_text(RULE + games_block)
    (ROOT / "prompt_md.txt").write_text(
        RULE + "[Your notes.md — every past game, chronological]\n"
        + md.read_all() + "\n" + games_block)
    doss_block = "\n\n".join(
        store.read_file(f"knowledge/tells/{p}/reasoning.md").decode()
        for p in PLAYERS)
    (ROOT / "prompt_gemmery.txt").write_text(
        RULE + "[Your memory — CURRENT tell dossiers (revised as behavior "
        "changed; superseded versions remain in history)]\n\n" + doss_block
        + "\n\n" + games_block)

    return hist, store, v1_sha, v2_sha, truth


if __name__ == "__main__":
    hist, store, v1, v2, truth = build()
    print("=== deterministic backbone (300 phase-B test games) ===")
    for k, v in deterministic_backbone(hist).items():
        print(f"  {k:34s}: {v:.2f}")
    print(f"\nstore: {store.count_commits()} gems; P2 dossier history: "
          f"{[s[:8] for s in store.history('knowledge/tells/P2')]}")
    print("prompt sizes (KB):", {a: round((ROOT / f'prompt_{a}.txt').stat().st_size / 1024, 1)
                                 for a in ("cold", "md", "gemmery")})
    print("truth:", truth)
