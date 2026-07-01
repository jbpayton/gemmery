"""A Gnosia-style social-deduction engine for the scaled memory experiment.

Not a faithful reimplementation of Gnosia — a *Gnosia-flavored* game rich enough
that per-player behavioral signatures are learnable and worth remembering, and
large enough (a big rotating persona pool, a subset drawn per game) that the
relevant memory for any one game is a small slice of a big history. That is the
regime where selective retrieval (Gemmery) should beat "read the whole notes
file" (the .md baseline), which is the scientific point of scaling up.

Roles: CREW, ENGINEER (night human/Gnosia scan), DOCTOR (autopsy the frozen),
GUARDIAN_ANGEL (protect another), GUARD (self-bodyguard once), AC_FOLLOWER (a
*human* who sides with the Gnosia — scans human, a trap), and a variable number
of GNOSIA. Each persona has a fixed, idiosyncratic signature — chiefly *what
power role it fake-claims when it is Gnosia* and *who it frames* — so a
counter-claim ("two Engineers") is only resolvable if you remember which persona
fakes which role.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum


class Role(str, Enum):
    CREW = "Crew"
    ENGINEER = "Engineer"
    DOCTOR = "Doctor"
    GUARDIAN_ANGEL = "Guardian Angel"
    GUARD = "Guard"
    AC_FOLLOWER = "AC Follower"
    GNOSIA = "Gnosia"


POWER_ROLES = [Role.ENGINEER, Role.DOCTOR, Role.GUARDIAN_ANGEL, Role.GUARD]
HUMAN_ROLES = [Role.CREW, *POWER_ROLES, Role.AC_FOLLOWER]

FAKE_OPTIONS = [None, Role.ENGINEER, Role.DOCTOR, Role.GUARDIAN_ANGEL]
FRAME_OPTIONS = ["engineer_claimer", "quiet", "loud", "protector_claimer", "random"]
CREW_ACCUSE = ["follow_engineer", "defensive", "suspicious_of_claimers"]


@dataclass(frozen=True)
class Persona:
    pid: str
    fake_claim: Role | None      # power role faked when this persona is Gnosia
    frame: str                   # who this persona frames when Gnosia
    reveals_role: bool           # claims its real power role when crew
    crew_accuse: str             # how it accuses when a plain crew/human
    talkative: bool


def make_pool(size: int) -> list[Persona]:
    """Deterministic pool of distinct personas (idiosyncratic signatures)."""
    pool = []
    for i in range(size):
        r = random.Random(1000 + i)
        pool.append(Persona(
            pid=f"P{i:02d}",
            fake_claim=r.choice(FAKE_OPTIONS),
            frame=r.choice(FRAME_OPTIONS),
            reveals_role=r.random() < 0.7,
            crew_accuse=r.choice(CREW_ACCUSE),
            talkative=r.random() < 0.6,
        ))
    return pool


@dataclass
class Statement:
    day: int
    speaker: str
    claim_role: Role | None = None       # a role this player publicly claims
    claim_is_lie: bool = False           # (ground truth, not shown to focal)
    scan_target: str | None = None       # engineer/fake-engineer scan subject
    scan_says_gnosia: bool | None = None
    accuse: str | None = None
    text: str = ""


@dataclass
class Game:
    seed: int
    players: list[str]
    roles: dict[str, Role]
    gnosia: list[str]
    statements: list[Statement] = field(default_factory=list)
    frozen: str | None = None
    freeze_blocked: bool = False

    def gnosia_set(self) -> set[str]:
        return set(self.gnosia)

    def public_transcript(self) -> str:
        lines = []
        for day in (1, 2):
            lines.append(f"=== Day {day} ===")
            if day == 2:
                if self.frozen:
                    lines.append(f"  (Overnight, {self.frozen} was put into cold sleep.)")
                else:
                    lines.append("  (Overnight, the Gnosia's attack was blocked — no one frozen.)")
            for s in self.statements:
                if s.day == day and s.text:
                    lines.append("  " + s.text)
        return "\n".join(lines)


# --------------------------------------------------------------------------- #
def _assign_roles(players, n_gnosia, rng) -> tuple[dict, list]:
    roles = {}
    shuffled = players[:]
    rng.shuffle(shuffled)
    gnosia = shuffled[:n_gnosia]
    for p in gnosia:
        roles[p] = Role.GNOSIA
    rest = shuffled[n_gnosia:]
    # one of each power role if room, maybe an AC follower, rest crew
    specials = list(POWER_ROLES)
    if len(rest) >= 6 and rng.random() < 0.6:
        specials = specials + [Role.AC_FOLLOWER]
    for i, p in enumerate(rest):
        roles[p] = specials[i] if i < len(specials) else Role.CREW
    return roles, gnosia


def _most_claimed(game, role) -> str | None:
    for s in game.statements:
        if s.claim_role == role:
            return s.speaker
    return None


def _accuse_target(persona: Persona, pid, game, rng, alive, is_evil):
    """Pick an accusation target for a player based on persona/role/info."""
    others = [p for p in alive if p != pid]
    if not others:
        return None
    if is_evil:  # Gnosia or AC follower: frame per persona
        if persona.frame == "engineer_claimer":
            e = _most_claimed(game, Role.ENGINEER)
            if e and e != pid:
                return e
        if persona.frame == "protector_claimer":
            g = _most_claimed(game, Role.GUARDIAN_ANGEL)
            if g and g != pid:
                return g
        if persona.frame == "loud":
            counts = {}
            for s in game.statements:
                if s.accuse:
                    counts[s.speaker] = counts.get(s.speaker, 0) + 1
            loud = [p for p in others if counts.get(p, 0) > 0]
            if loud:
                return max(loud, key=lambda p: counts.get(p, 0))
        if persona.frame == "quiet":
            counts = {p: 0 for p in others}
            for s in game.statements:
                if s.speaker in counts:
                    counts[s.speaker] += 1
            return min(others, key=lambda p: counts[p])
        return rng.choice(others)
    # honest human
    if persona.crew_accuse == "follow_engineer":
        for s in game.statements:
            if s.claim_role == Role.ENGINEER and s.scan_says_gnosia and s.scan_target in others:
                return s.scan_target
    if persona.crew_accuse == "suspicious_of_claimers":
        claimers = [s.speaker for s in game.statements
                    if s.claim_role in POWER_ROLES and s.speaker in others]
        if len(claimers) >= 2:
            return claimers[-1]  # suspect the later (counter) claim
    return rng.choice(others)


def _run_night(game, rng):
    alive = game.players
    # Gnosia freeze the biggest threat: a claimed Engineer, else a random human.
    target = _most_claimed(game, Role.ENGINEER)
    if not target or target in game.gnosia_set():
        humans = [p for p in alive if p not in game.gnosia_set()]
        target = rng.choice(humans) if humans else None
    # protection
    ga = [p for p, r in game.roles.items() if r == Role.GUARDIAN_ANGEL]
    guard = [p for p, r in game.roles.items() if r == Role.GUARD]
    protected = set()
    if ga:
        cand = [p for p in alive if p != ga[0] and p not in game.gnosia_set()]
        if cand:
            protected.add(rng.choice(cand))
    if guard:
        protected.add(guard[0])  # self-bodyguard
    if target and target in protected:
        game.freeze_blocked = True
        game.frozen = None
    else:
        game.frozen = target


def _engineer_scan(game, rng):
    eng = [p for p, r in game.roles.items() if r == Role.ENGINEER]
    if not eng:
        return None
    suspects = [p for p in game.players if p != eng[0]]
    tgt = rng.choice(suspects)
    return (eng[0], tgt, tgt in game.gnosia_set())


def run_game(seed, pool: list[Persona], n_players=8, n_gnosia=2,
             focal=None) -> Game:
    rng = random.Random(seed)
    chosen = rng.sample([p.pid for p in pool], n_players)
    if focal and focal not in chosen:
        chosen[0] = focal
    pmap = {p.pid: p for p in pool}
    roles, gnosia = _assign_roles(chosen, n_gnosia, rng)
    if focal:
        roles[focal] = Role.CREW  # focal is a plain crew (hold role variance out)
        if focal in gnosia:
            gnosia.remove(focal)
            # promote someone else to keep gnosia count
            for p in chosen:
                if p != focal and roles[p] not in (Role.GNOSIA,):
                    roles[p] = Role.GNOSIA
                    gnosia.append(p)
                    break
    game = Game(seed=seed, players=chosen, roles=roles, gnosia=gnosia)

    scan = _engineer_scan(game, rng)  # decided at night, announced day 2

    # ---- Day 1: vibes + accusations (no power claims yet) ----
    for pid in chosen:
        if pid == focal:
            continue
        persona = pmap[pid]
        is_evil = roles[pid] in (Role.GNOSIA, Role.AC_FOLLOWER)
        if not persona.talkative and rng.random() < 0.5:
            continue
        acc = _accuse_target(persona, pid, game, rng, chosen, is_evil)
        st = Statement(1, pid, accuse=acc,
                       text=f"{pid}: \"I've got a bad feeling about {acc}.\"" if acc else "")
        if acc:
            game.statements.append(st)

    _run_night(game, rng)

    # ---- Day 2: power claims / counter-claims / reactions ----
    for pid in chosen:
        if pid == focal:
            continue
        persona = pmap[pid]
        role = roles[pid]
        is_evil = role in (Role.GNOSIA, Role.AC_FOLLOWER)

        # power-role claims
        if role == Role.GNOSIA and persona.fake_claim is not None:
            # fake a power role and (if faking Engineer) a framing scan
            if persona.fake_claim == Role.ENGINEER:
                victim = _accuse_target(persona, pid, game, rng, chosen, True) or \
                    rng.choice([p for p in chosen if p != pid])
                game.statements.append(Statement(
                    2, pid, claim_role=Role.ENGINEER, claim_is_lie=True,
                    scan_target=victim, scan_says_gnosia=True, accuse=victim,
                    text=f"{pid}: \"I'm the Engineer. My scan flags {victim} as Gnosia.\""))
                continue
            game.statements.append(Statement(
                2, pid, claim_role=persona.fake_claim, claim_is_lie=True,
                text=f"{pid}: \"Trust me — I'm the {persona.fake_claim.value}.\""))
            continue

        if role == Role.ENGINEER and persona.reveals_role and scan:
            _, tgt, is_g = scan
            game.statements.append(Statement(
                2, pid, claim_role=Role.ENGINEER, scan_target=tgt,
                scan_says_gnosia=is_g, accuse=(tgt if is_g else None),
                text=f"{pid}: \"I'm the Engineer — I scanned {tgt}: "
                     f"{'GNOSIA' if is_g else 'human'}.\""))
            continue

        if role == Role.DOCTOR and persona.reveals_role and game.frozen:
            fr = game.roles[game.frozen]
            game.statements.append(Statement(
                2, pid, claim_role=Role.DOCTOR,
                text=f"{pid}: \"As the Doctor, I examined {game.frozen}: they were "
                     f"{'Gnosia' if fr == Role.GNOSIA else 'human'}.\""))
            continue

        if role in (Role.GUARDIAN_ANGEL, Role.GUARD) and persona.reveals_role \
                and rng.random() < 0.6:
            game.statements.append(Statement(
                2, pid, claim_role=role,
                text=f"{pid}: \"I'm the {role.value}, for what it's worth.\""))
            continue

        # otherwise: accuse
        acc = _accuse_target(persona, pid, game, rng, chosen, is_evil)
        if acc:
            game.statements.append(Statement(
                2, pid, accuse=acc,
                text=f"{pid}: \"I still think {acc} is one of them.\""))

    return game


# --------------------------------------------------------------------------- #
# Reference detectors (no LLM) — validate that per-persona tells are learnable.
# --------------------------------------------------------------------------- #
def behavior_summary(game: Game, pid: str) -> str:
    ss = [s for s in game.statements if s.speaker == pid]
    bits = []
    for s in ss:
        if s.claim_role == Role.ENGINEER and s.scan_target:
            bits.append(f"claimed Engineer and flagged {s.scan_target}")
        elif s.claim_role:
            bits.append(f"claimed {s.claim_role.value}")
        elif s.accuse:
            bits.append(f"accused {s.accuse}")
    return "; ".join(bits) or "was quiet"


def build_profiles(past: list[Game]) -> dict[str, dict]:
    """Per-persona history, incl. per-claimed-role Gnosia/human counts (the tell
    that resolves counter-claims: 'this persona fakes Doctor when Gnosia')."""
    prof: dict[str, dict] = {}
    for g in past:
        for pid in g.players:
            p = prof.setdefault(pid, {"gnosia": 0, "human": 0, "claim_role": {}})
            is_g = pid in g.gnosia_set()
            p["gnosia" if is_g else "human"] += 1
            for s in g.statements:
                if s.speaker == pid and s.claim_role:
                    cr = p["claim_role"].setdefault(s.claim_role.value, [0, 0])
                    cr[0 if is_g else 1] += 1  # [as_gnosia, as_human]
    return prof


def cold_detector(game: Game, rng: random.Random) -> str:
    """Memoryless: believe an Engineer claim and accuse whoever it flags; if two
    Engineers claim, guess between the flagged targets. Exploitable by fakes."""
    flags = [s.scan_target for s in game.statements
             if s.claim_role == Role.ENGINEER and s.scan_says_gnosia and s.scan_target]
    if flags:
        return rng.choice(flags)
    accused = [s.accuse for s in game.statements if s.accuse]
    return rng.choice(accused) if accused else rng.choice(game.players)


def memory_detector(game: Game, profiles: dict, rng: random.Random) -> str:
    """Score each present player by P(Gnosia | the role they claimed this game),
    learned from THAT persona's own history — resolves counter-claims."""
    best, best_s = None, -1e9
    for pid in game.players:
        pr = profiles.get(pid)
        claims = [s.claim_role.value for s in game.statements
                  if s.speaker == pid and s.claim_role]
        if not pr:
            score = 0.25
        else:
            score = pr["gnosia"] / (pr["gnosia"] + pr["human"] + 1e-9)  # base rate
            for cr in claims:
                g_as, h_as = pr["claim_role"].get(cr, [0, 0])
                # Laplace-smoothed P(gnosia | this persona claimed this role)
                score = max(score, (g_as + 0.5) / (g_as + h_as + 1.0))
        score += rng.random() * 1e-6
        if score > best_s:
            best, best_s = pid, score
    return best or rng.choice(game.players)
