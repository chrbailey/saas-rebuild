"""Deterministic candidate generation and scoring.

Two stages:

1. **Blocking** -- an inverted index over name tokens and consonant skeletons
   narrows ~20k listed parties to a handful per subject without comparing
   every pair. Token document frequency suppresses the blocks that would
   otherwise fire on every "trading company" in the file.
2. **Scoring** -- a fixed weighted combination of five string signals, then a
   rule-based band assignment.

Both stages are pure functions of (subject, index). No sampling, no
thresholds learned from data, no LLM. Re-running on the same list snapshot
produces identical output, which is what makes a screening record defensible
years later.

Deliberate design choices worth knowing before you tune anything:

* **Country and address never demote a band.** List addresses are sparse and
  often historical; a subject in Germany can absolutely be the SDN listed at a
  Moscow address. Geography is emitted as a *signal* for the adjudicator and
  is never allowed to clear a name hit on its own.
* **The floor is set for recall.** WEAK exists to be reviewed, not to be
  believed. Raising the floor to cut review volume trades a cheap cost
  (an analyst reads a row) for an expensive one (a shipment to a blocked
  party). Tune the other direction only with evidence.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable

from .models import Candidate, ListedParty, MatchBand, SubjectParty
from .names import (
    core_tokens,
    fold,
    initials,
    is_acronym_of,
    jaro_winkler,
    levenshtein_ratio,
    normalized,
    skeleton,
    sorted_normalized,
    sorted_skeleton,
    token_containment,
    token_set_ratio,
)
from .rules import Policy, default_policy
from .sources import legal_effect_for

# Signal weights. They sum to 1.0; changing them changes every historical
# score, so the engine version in models.py must be bumped alongside.
WEIGHTS: dict[str, float] = {
    "jaro_winkler": 0.35,
    "token_set": 0.20,
    "containment": 0.20,
    "levenshtein": 0.15,
    "skeleton": 0.10,
}

# Band thresholds.
STRONG_FLOOR = 0.90
WEAK_FLOOR = 0.78

# A token appearing in more than this fraction of listed names is too common
# to use as a blocking key on its own.
BLOCK_DF_CEILING = 0.02

# Ceiling on how many index entries one query may pull into scoring.
#
# The safety argument for capping at all: an exact match shares *every* token
# with the query, so it necessarily appears in the postings of the query's
# RAREST token. Blocking that always expands the rarest token first therefore
# cannot lose an exact match, no matter where the cap falls. What the cap
# costs is recall on partial matches through highly common tokens -- and when
# it bites, `BlockResult.truncated_tokens` records exactly which tokens were
# not expanded, so the loss is disclosed rather than silent.
MAX_BLOCK_ENTRIES = 20_000

# Names shorter than this (in folded characters) are matched only on exact
# equality of the normalized form -- fuzzy matching two-letter names produces
# nothing but noise.
SHORT_NAME_CHARS = 4

# Whitespace-insensitive comparison is allowed only once the squashed name is
# this long. "Ga zprom Neft" against "GAZPROM NEFT" was a complete miss --
# no shared token, no shared skeleton, a score in the 0.5s -- because every
# signal is token-based and an OCR split or a keying slip moves a token
# boundary. Compared with the spaces removed the two are identical. Below
# this length the same comparison unites unrelated short strings ("A C ME" /
# "ACME"), so it is gated the way SHORT_NAME_CHARS gates fuzzy matching.
COMPACT_MIN_CHARS = 6


@dataclass
class BlockResult:
    """Entries selected for scoring, plus what blocking chose not to expand."""

    entries: set[int]
    truncated_tokens: list[str]


@dataclass
class IndexedName:
    uid: str
    listed_name: str
    source: str
    norm: str
    toks: tuple[str, ...]
    skel: str
    sorted_norm: str = ""
    sorted_skel: str = ""
    # `norm` with the whitespace removed; see COMPACT_MIN_CHARS.
    compact: str = ""


class ListIndex:
    """Inverted index over every name and alias of every listed party."""

    def __init__(self) -> None:
        self.entries: list[IndexedName] = []
        self.parties: dict[str, ListedParty] = {}
        self._token_postings: dict[str, set[int]] = defaultdict(set)
        self._skel_postings: dict[str, set[int]] = defaultdict(set)
        # initials of a multi-token listed name -> entries. An acronym shares
        # no token and no skeleton with its expansion, so without a dedicated
        # posting the acronym band rule was unreachable through blocking.
        self._acronym_postings: dict[str, set[int]] = defaultdict(set)
        # whitespace-stripped normalized name -> entries. A token-split name
        # shares no token with its listed form, so without this posting the
        # compact band rule was unreachable through blocking.
        self._compact_postings: dict[str, set[int]] = defaultdict(set)
        self._df: dict[str, int] = defaultdict(int)
        self._common_cache: set[str] | None = None
        self._built = False

    def add(self, party: ListedParty) -> None:
        self.parties[party.uid] = party
        for nm in party.all_names():
            idx = len(self.entries)
            toks = core_tokens(nm)
            if not toks:
                continue
            norm = normalized(nm)
            compact = norm.replace(" ", "")
            self.entries.append(
                IndexedName(
                    uid=party.uid,
                    listed_name=nm,
                    source=party.source,
                    norm=norm,
                    toks=toks,
                    skel=skeleton(nm),
                    sorted_norm=sorted_normalized(nm),
                    sorted_skel=sorted_skeleton(nm),
                    compact=compact,
                )
            )
            if len(compact) >= COMPACT_MIN_CHARS:
                self._compact_postings[compact].add(idx)
            for t in set(toks):
                self._token_postings[t].add(idx)
                self._df[t] += 1
            for st in set(skeleton(nm).split()):
                if st:
                    self._skel_postings[st].add(idx)
            if len(toks) >= 2:
                acro = initials(toks)
                if len(acro) >= 3:
                    self._acronym_postings[acro].add(idx)
        self._built = False
        self._common_cache = None

    def add_all(self, parties: Iterable[ListedParty]) -> None:
        for p in parties:
            self.add(p)

    def build(self) -> "ListIndex":
        # Freeze the common-token set once. Recomputing it per query turns
        # blocking into an O(vocabulary) scan on every subject, which is the
        # difference between a 30-second run and a 30-minute one on a real
        # list of ~20k parties.
        self._common_cache = self._compute_common_tokens()
        self._built = True
        return self

    @property
    def size(self) -> int:
        return len(self.entries)

    def _compute_common_tokens(self) -> set[str]:
        if not self.entries:
            return set()
        ceiling = max(2, int(len(self.entries) * BLOCK_DF_CEILING))
        return {t for t, df in self._df.items() if df > ceiling}

    def _common_tokens(self) -> set[str]:
        if self._built and self._common_cache is not None:
            return self._common_cache
        return self._compute_common_tokens()

    def block(self, name: str) -> "BlockResult":
        """Candidate entry indices for a query name, rarest token first.

        Tokens are expanded in ascending document-frequency order so the most
        discriminating evidence is always spent first, and expansion stops at
        `MAX_BLOCK_ENTRIES`. A name made entirely of common words ("General
        Trading Company") still gets screened -- it just gets screened against
        the postings of its least common word rather than against everything.
        """
        toks = core_tokens(name)
        if not toks:
            return BlockResult(set(), [])

        keys: list[tuple[int, str, str]] = []
        for t in set(toks):
            keys.append((self._df.get(t, 0), t, "token"))
        for st in set(skeleton(name).split()):
            if st:
                keys.append((len(self._skel_postings.get(st, ())), st, "skeleton"))
        # Acronym reachability, in both directions. An initialism shares no
        # token and no skeleton with its expansion, so "IRGC" pulled ZERO
        # candidates against a list carrying only "Islamic Revolutionary
        # Guard Corps" -- the acronym band rule below only ever fired when
        # the list itself carried the acronym as an alias, i.e. when it was
        # already an exact match.
        for t in set(toks):
            if len(t) >= 3 and t in self._acronym_postings:
                keys.append((len(self._acronym_postings[t]), t, "acronym"))
        # A dotted or spaced initialism ("R.R.M.", "R R M") folds to single
        # letters and reached no posting at all, while the scoring rule would
        # have accepted it: the benchmark's acronym class lost every such
        # case at blocking. Treat an all-single-letter query as its joined
        # initialism.
        if len(toks) >= 3 and all(len(t) == 1 for t in toks):
            joined = "".join(toks)
            if joined in self._acronym_postings:
                keys.append((len(self._acronym_postings[joined]), joined, "acronym"))
            if joined in self._token_postings:
                keys.append((self._df.get(joined, 0), joined, "token"))
        if len(toks) >= 2:
            acro = initials(toks)
            if len(acro) >= 3 and acro in self._token_postings:
                keys.append((self._df.get(acro, 0), acro, "token"))
        # Whitespace-insensitive reachability: a listed name whose squashed
        # form equals the query's is a candidate whatever the token split.
        compact = normalized(name).replace(" ", "")
        if len(compact) >= COMPACT_MIN_CHARS and compact in self._compact_postings:
            keys.append((len(self._compact_postings[compact]), compact, "compact"))
        keys.sort(key=lambda k: (k[0], k[1]))

        out: set[int] = set()
        truncated: list[str] = []
        lookup = {"token": self._token_postings, "skeleton": self._skel_postings,
                  "acronym": self._acronym_postings, "compact": self._compact_postings}
        for df, key, kind in keys:
            if out and len(out) >= MAX_BLOCK_ENTRIES:
                truncated.append(f"{key} (df={df})")
                continue
            out |= lookup[kind].get(key, set())
        return BlockResult(out, truncated)


def score_pair(subject_name: str, entry: IndexedName,
               early_exit: bool = True) -> tuple[float, dict[str, float | bool]]:
    """Score one subject name against one indexed listed name.

    `early_exit=False` forces the full computation. It exists so the test
    suite can prove the optimization is behaviour-preserving rather than
    merely assert that it is.
    """
    s_norm = normalized(subject_name)
    s_toks = core_tokens(subject_name)
    s_skel = skeleton(subject_name)
    s_sorted = sorted_normalized(subject_name)
    s_sorted_skel = sorted_skeleton(subject_name)

    # Set-based signals first. They cost hash lookups; the string metrics
    # below cost O(n*m) each and dominate the run time on a real list.
    ts_early = token_set_ratio(s_toks, entry.toks)
    cont_early = token_containment(s_toks, entry.toks)
    skel_cont_early = token_containment(tuple(s_skel.split()), tuple(entry.skel.split()))
    acronym = (is_acronym_of(subject_name, entry.toks)
               or is_acronym_of(entry.listed_name, s_toks))
    # Whitespace-insensitive signals (see COMPACT_MIN_CHARS). `compact_equal`
    # is deliberately exclusive of `exact_normalized`: it names the case where
    # ONLY the token boundaries differ. Containment is one squashed form inside
    # the other; on its own it proves little ("ivanov" sits inside
    # "ivanovamaria"), so the band rule additionally demands a shared
    # discriminating token, which screen_name supplies.
    s_compact = s_norm.replace(" ", "")
    e_compact = entry.compact or entry.norm.replace(" ", "")
    compact_ok = min(len(s_compact), len(e_compact)) >= COMPACT_MIN_CHARS
    compact_equal = compact_ok and s_norm != entry.norm and s_compact == e_compact
    compact_containment = (compact_ok and s_compact != e_compact
                           and (s_compact in e_compact or e_compact in s_compact))

    # Provable early exit, in two parts.
    #
    # Part one, the score ceiling. Jaro-Winkler and the Levenshtein ratio are
    # both bounded above by 1.0, so with the set signals already known the
    # best score this pair could possibly reach is:
    #
    #     w_jw*1 + w_ts*ts + w_cont*cont + w_lev*1 + w_skel*skel_cont
    #
    # (`skel_signal` is at most `skel_cont`, because skeleton equality implies
    # skeleton containment of 1.0.) Below the WEAK floor, the pair cannot band
    # *on score*.
    #
    # Part two, the bypass rules. Several band rules fire without consulting
    # the score at all, and a low ceiling does not bound them -- a full
    # skeleton containment contributes only 0.10 to the ceiling but is worth
    # STRONG on its own, and a compact-equal pair can sit near 0.5. So each
    # bypass condition independently suppresses the exit.
    # (The brute-force equivalence test in the suite exists because the first
    # version of this argument got exactly that case wrong.)
    s_skel_toks_early = tuple(s_skel.split())
    e_skel_toks_early = tuple(entry.skel.split())
    multi_token = min(len(s_skel_toks_early), len(e_skel_toks_early)) >= 2

    ceiling = (
        WEIGHTS["jaro_winkler"]
        + WEIGHTS["token_set"] * ts_early
        + WEIGHTS["containment"] * cont_early
        + WEIGHTS["levenshtein"]
        + WEIGHTS["skeleton"] * skel_cont_early
    )
    bypass_possible = (
        acronym                                          # acronym rule
        or cont_early >= 1.0                             # containment + skeleton rule, exact rules
        or (skel_cont_early >= 1.0 and multi_token)      # skeleton containment rule
        or compact_equal                                 # compact rule
        or compact_containment                           # compact containment rule
    )
    if early_exit and ceiling < WEAK_FLOOR and not bypass_possible:
        return 0.0, {
            "jaro_winkler": 0.0, "token_set": round(ts_early, 4),
            "containment": round(cont_early, 4), "levenshtein": 0.0,
            "skeleton_equal": False,
            "skeleton_containment": round(skel_cont_early, 4),
            "skeleton_multi_token": False,
            "exact_normalized": False, "exact_reordered": False,
            "acronym": False,
            "compact_equal": False, "compact_containment": False,
            "below_band_ceiling": round(ceiling, 4),
        }

    # Compare both the ordered and the token-sorted rendering, and keep the
    # better of the two. Without this, "PETROV, Vasiliy Ivanovich" and
    # "Vasily Ivanovic Petrov" score like unrelated strings.
    jw_ordered = jaro_winkler(s_norm, entry.norm)
    jw_sorted = jaro_winkler(s_sorted, entry.sorted_norm)
    jw = max(jw_ordered, jw_sorted)
    # Cap the edit-distance search at the point below which it cannot lift
    # the score over the WEAK floor. With jaro and skeleton already at their
    # best possible values (that is what `ceiling` assumes),
    #     score_max(lev) = ceiling - w_lev * (1 - lev)
    # so the smallest lev that could still band is
    #     (WEAK_FLOOR - ceiling) / w_lev + 1.
    # Below that the pair is NONE either way, and a NONE pair's score is never
    # reported, so capping changes no recorded value.
    lev_floor = min(0.99, max(0.0, (WEAK_FLOOR - ceiling) / WEIGHTS["levenshtein"] + 1.0))
    lev = max(levenshtein_ratio(s_norm, entry.norm, lev_floor),
              levenshtein_ratio(s_sorted, entry.sorted_norm, lev_floor))
    ts, cont = ts_early, cont_early
    skel_eq = 1.0 if (s_skel and (s_skel == entry.skel
                                  or s_sorted_skel == entry.sorted_skel)) else 0.0

    # Skeleton containment catches the dropped-name-part case: a Western
    # document writes "Vasiliy Petroff" for a party the list carries as
    # "PETROV, Vasiliy Ivanovich". Every skeleton token of the shorter name is
    # present in the longer one, but no whole-string metric sees it.
    skel_cont = skel_cont_early
    skel_signal = skel_eq if skel_eq else (skel_cont if multi_token else 0.0)

    score = (
        WEIGHTS["jaro_winkler"] * jw
        + WEIGHTS["token_set"] * ts
        + WEIGHTS["containment"] * cont
        + WEIGHTS["levenshtein"] * lev
        + WEIGHTS["skeleton"] * skel_signal
    )

    signals: dict[str, float | bool] = {
        "jaro_winkler": round(jw, 4),
        "token_set": round(ts, 4),
        "containment": round(cont, 4),
        "levenshtein": round(lev, 4),
        "skeleton_equal": bool(skel_eq),
        "skeleton_containment": round(skel_cont, 4),
        "skeleton_multi_token": multi_token,
        "exact_normalized": s_norm == entry.norm,
        "exact_reordered": s_norm != entry.norm and s_sorted == entry.sorted_norm,
        "acronym": acronym,
        "compact_equal": compact_equal,
        "compact_containment": compact_containment,
    }
    return round(score, 4), signals


def assign_band(score: float, signals: dict[str, float | bool], subject_name: str,
                entry: IndexedName) -> MatchBand:
    """Rule-based band. Order matters; first rule that fires wins."""
    s_norm = normalized(subject_name)

    if signals.get("exact_normalized"):
        return "EXACT"

    # The same token multiset in a different order is the same name. "PETROV,
    # Vasiliy Ivanovich" and "Vasiliy Ivanovich Petrov" are not a fuzzy match;
    # they are the same string written by two different systems.
    if signals.get("exact_reordered"):
        return "EXACT"

    # An initialism that resolves exactly is a strong signal on its own; list
    # data and shipping documents disagree about this constantly. It must
    # outrank the short-name gate below: acronyms are short by construction,
    # and behind the gate this rule was dead for the 3-letter initialisms
    # that dominate real trade documents. (is_acronym_of refuses 2-letter
    # forms; those genuinely are noise.)
    if signals.get("acronym"):
        return "STRONG"

    # Very short names: exact only. Fuzzy matching "SU" against "SUN", "SUD",
    # "SUR" generates pure noise and buries real hits.
    if len(s_norm.replace(" ", "")) < SHORT_NAME_CHARS or len(
        entry.norm.replace(" ", "")
    ) < SHORT_NAME_CHARS:
        return "NONE"

    # The normalized forms differ only in where the token boundaries fall:
    # "Ga zprom Neft" against "GAZPROM NEFT". Same letters, same order, no
    # shared token -- so no other rule could see it. Not EXACT, because a
    # split name is degraded evidence and EXACT auto-confirms.
    if signals.get("compact_equal"):
        return "STRONG"

    # Full containment of the shorter name plus a matching skeleton means the
    # names differ only by extra qualifiers and vowel drift.
    if signals.get("containment") == 1.0 and signals.get("skeleton_equal"):
        return "STRONG"

    # Every skeleton token of the shorter name appears in the longer one, and
    # there are at least two of them. This is the dropped-name-part case: a
    # missing patronymic, a missing division word, a shortened trade name.
    # The two-token floor keeps generic single words from firing it.
    if signals.get("skeleton_containment") == 1.0 and signals.get("skeleton_multi_token"):
        return "STRONG"

    # Single-token containment, but only when the shared token is rare enough
    # in the list to discriminate. "Gazprom" against "Gazprom Neft" is a hit;
    # "Trading" against "Acme Trading Corp" is not, and the two are
    # distinguishable only by how common the token is across the whole list.
    #
    # Without this rule those single-token cases were a *complete miss*, not a
    # demoted one: containment was 1.0 and skeleton containment was 1.0, but
    # the two-token floor blocked both bypass rules and the residual score
    # (~0.58-0.71) sat below the WEAK floor, so nothing was ever reported.
    if signals.get("containment") == 1.0 and signals.get("discriminating_containment"):
        return "STRONG"

    # One squashed form inside the other, with a shared token rare enough to
    # carry identity: "Ga zprom Neft Trading" against "GAZPROM NEFT" shares
    # only "neft". Without the discriminating guard "Gene ral Trading" would
    # sit inside every "General Trading Company N" on the list.
    if signals.get("compact_containment") and signals.get("discriminating_containment"):
        return "STRONG"

    if score >= STRONG_FLOOR:
        return "STRONG"
    if score >= WEAK_FLOOR:
        return "WEAK"
    return "NONE"


def geo_signals(subject: SubjectParty, party: ListedParty,
                policy: Policy | None = None) -> dict[str, object]:
    """Geography agreement, recorded but never used to demote a band.

    Agreement is EQUALITY after each side is resolved to an ISO code through
    the policy file's country aliases (folded string equality when a value
    does not resolve). It used to be a substring test, and "us" is a
    substring of "rUSsia": a U.S.-addressed subject was reported as agreeing
    with a Moscow listing, the one direction this signal must never err in,
    because an adjudicator reads "agrees" as corroboration.
    """
    p = policy or default_policy()

    def key(raw: str) -> str:
        return p.resolve_country(raw) or fold(raw)

    subj_country = key(subject.country or subject.destination_country)
    listed = {key(c) for c in party.countries if c}
    if not subj_country or not listed:
        return {"country_evidence": "insufficient"}
    if subj_country in listed:
        return {"country_evidence": "agrees", "listed_countries": party.countries}
    return {"country_evidence": "differs", "listed_countries": party.countries}


def discriminating(index: ListIndex, q_toks: tuple[str, ...],
                   e_toks: tuple[str, ...]) -> bool:
    """Do the shared tokens carry enough identity to stand alone?

    This is what `_common_tokens` was built for. A token appearing across a
    large fraction of the list ("trading", "company", "group") tells you
    nothing about identity; a token appearing once or twice is close to a
    name. Only the latter justifies banding on containment alone.
    """
    shared = set(q_toks) & set(e_toks)
    if not shared:
        return False
    common = index._common_tokens()
    return any(t not in common for t in shared)


def screen_name(
    subject: SubjectParty,
    index: ListIndex,
    min_band: MatchBand = "WEAK",
    diagnostics: dict | None = None,
    policy: Policy | None = None,
) -> list[Candidate]:
    """All candidates for one subject, best first.

    Every alias the operator supplied is screened as well as the primary name;
    the best-scoring name/alias pair per listed party survives. `policy`
    supplies the country aliases for the geography signal; the shipped file
    is used when none is given.
    """
    order = {"EXACT": 3, "STRONG": 2, "WEAK": 1, "NONE": 0}
    floor = order[min_band]
    best: dict[str, Candidate] = {}

    query_names = [subject.name, *[a for a in subject.aliases if a]]
    truncated: list[str] = []
    for qname in query_names:
        if not core_tokens(qname):
            continue
        blocked = index.block(qname)
        truncated.extend(blocked.truncated_tokens)
        for idx in blocked.entries:
            entry = index.entries[idx]
            score, signals = score_pair(qname, entry)
            if signals.get("containment") == 1.0 or signals.get("compact_containment"):
                signals["discriminating_containment"] = discriminating(
                    index, core_tokens(qname), entry.toks)
            band = assign_band(score, signals, qname, entry)
            if order[band] < floor:
                continue
            party = index.parties[entry.uid]
            signals = dict(signals)
            signals["matched_subject_name"] = qname
            # A hit through a weak alias is real but lower-quality evidence;
            # the disposition floor and guardrails read this signal.
            if party.weak_aliases and entry.listed_name.lower() in {
                w.lower() for w in party.weak_aliases
            }:
                signals["weak_alias"] = True
            signals.update(geo_signals(subject, party, policy))
            cand = Candidate(
                listed_uid=entry.uid,
                listed_name=entry.listed_name,
                listed_source=entry.source,
                score=score,
                band=band,
                signals=signals,
                legal_effect=legal_effect_for(entry.source),
                listed_party=party.to_dict(),
            )
            prev = best.get(entry.uid)
            if prev is None or (order[cand.band], cand.score) > (order[prev.band], prev.score):
                best[entry.uid] = cand

    out = list(best.values())
    # Blocking truncation is disclosed on every candidate rather than logged
    # somewhere a reader will not look. An analyst reading a near-miss needs
    # to know the search was bounded.
    #
    # Per-candidate disclosure alone fails in exactly the case that matters
    # most: if truncation dropped the ONLY match, there are no candidates left
    # to carry the warning and the caller sees a clean empty result. So it is
    # also reported through `diagnostics`, which the pipeline turns into a
    # rule flag on the case whether or not anything survived.
    if truncated:
        marks = sorted(set(truncated))
        for c in out:
            c.signals["blocking_truncated_tokens"] = marks
        if diagnostics is not None:
            diagnostics["blocking_truncated_tokens"] = marks
    # Deterministic ordering: band, then score, then uid as the tie-break so
    # two runs never disagree about row order in the report.
    out.sort(key=lambda c: (-order[c.band], -c.score, c.listed_uid))
    return out


def tuning_digest() -> str:
    """Digest of every constant that changes a score or a band.

    `engine_version` is a hand-maintained string, so it cannot be trusted to
    move when someone edits a weight. This can, and it goes on every result:
    a 2031 auditor comparing two runs needs to see that the thresholds moved,
    not infer it.
    """
    from .models import stable_digest

    return stable_digest({
        "weights": WEIGHTS,
        "strong_floor": STRONG_FLOOR,
        "weak_floor": WEAK_FLOOR,
        "block_df_ceiling": BLOCK_DF_CEILING,
        "max_block_entries": MAX_BLOCK_ENTRIES,
        "short_name_chars": SHORT_NAME_CHARS,
        "compact_min_chars": COMPACT_MIN_CHARS,
    })
