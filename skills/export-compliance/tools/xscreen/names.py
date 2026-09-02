"""Deterministic name normalization and string-similarity primitives.

No randomness, no learned models, no network. Every function here is a pure
function of its inputs, so a screening run in 2031 that re-reads the same list
snapshot reproduces the 2026 result byte for byte. That property is the whole
reason the matching layer is not an LLM.

Scope note: transliteration folding here is heuristic and tuned for recall,
not linguistic correctness. It is designed to over-generate candidates that a
later stage narrows -- the expensive error in export compliance is the missed
hit, not the extra review.
"""

from __future__ import annotations

import re
import unicodedata
from functools import lru_cache

# --------------------------------------------------------------------------
# Corporate form equivalence
# --------------------------------------------------------------------------
# Legal-form suffixes carry almost no discriminating power ("Acme LLC" vs
# "Acme Ltd" is the same risk) but they wreck edit-distance scores. They are
# stripped for the comparison key and preserved on the record for display.
#
# Only true legal forms belong here. This set once also stripped words like
# "trust", "fund", "holding", "group" and "international" -- organizational
# nouns that are part of the NAME, not the legal wrapper -- which made
# "Alpha Fund" and "Alpha Trust" normalize to the same key and band EXACT at
# score 1.0. EXACT means an automatic CONFIRMED_HIT floor that the
# adjudicator is forbidden to dissent from, so the over-stripping turned a
# one-shared-word coincidence into an uncontestable hit. Those words now stay
# in the token stream; the containment and discriminating-token rules still
# catch a listed "Wagner" inside "Wagner Group".

CORPORATE_SUFFIXES: frozenset[str] = frozenset(
    """
    inc incorporated corp corporation co company llc lc llp lp lllp plc ltd
    limited pte pty gmbh mbh ag kg gbr ohg kgaa se sarl sas sa spa srl snc
    bv nv cv oy oyj ab as asa aps kft zrt doo dd ad sp zoo sro spol akz
    ooo oao zao pao ao pjsc ojsc cjsc jsc ojs npo fgup gup mup fsue sue
    kk yk gk kabushiki gaisha kaisha yugen godo
    sdn bhd berhad tbk pt persero
    lda unipessoal eirl srlcv
    fze fzco fzc fzllc wll saog saoc kscc bsc eood ood ead uab sia sasu eurl
    """.split()
)

# Tokens that add no discriminating value inside a name.
NOISE_TOKENS: frozenset[str] = frozenset(
    "the a an and of for et und y e de del della di da le la les los las el al".split()
)

# Word-level equivalences seen constantly in list data.
WORD_EQUIV: dict[str, str] = {
    "company": "co",
    "corporation": "corp",
    "incorporated": "inc",
    "limited": "ltd",
    "international": "intl",
    "manufacturing": "mfg",
    "technologies": "tech",
    "technology": "tech",
    "industrial": "indl",
    "engineering": "engrg",
    "scientific": "sci",
    "research": "res",
    "development": "dev",
    "import": "imp",
    "export": "exp",
    "trading": "trade",
    "brothers": "bros",
    "saint": "st",
    "mount": "mt",
    "and": "",
}

_DIACRITIC_EXTRA = str.maketrans({
    "ø": "o", "Ø": "O", "đ": "d", "Đ": "D", "ł": "l", "Ł": "L",
    "æ": "ae", "Æ": "AE", "œ": "oe", "Œ": "OE", "ß": "ss",
    "ð": "d", "Ð": "D", "þ": "th", "Þ": "TH", "ı": "i",
})

# `\w` counts the underscore as a word character, so "ACME_TRADING" stayed
# one token and shared nothing with "ACME TRADING". Exports that squash a
# name into an identifier-safe field do exactly that.
_PUNCT_RE = re.compile(r"[^\w\s]|_", re.UNICODE)
_WS_RE = re.compile(r"\s+")
# An apostrophe INSIDE a word marks an elision or a glottal stop, not a word
# boundary: "Sa'id" is "Said", "O'Brien" is "OBrien" on the next system over.
# Treating it as separation split the token, and "Sa'id al-Harbi" scored a
# 0.70 ceiling against a listed "Said al-Harbi" -- an early exit, no
# candidate. The benchmark's internal_apostrophe class measured 20.9%.
_INNER_APOSTROPHE_RE = re.compile(r"(?<=\w)['\u2019\u02bc\u2018`](?=\w)")


@lru_cache(maxsize=200_000)
def fold(s: str) -> str:
    """Case-fold, strip diacritics and punctuation, collapse whitespace."""
    if not s:
        return ""
    # NFKD first, the extras table second. The table maps characters NFKD
    # leaves alone (ø, đ, ł ...), but a precomposed letter that stacks an
    # accent ON one of those -- ǿ is ø plus acute -- only becomes a bare ø
    # after decomposition. Translating first let it through untouched, so
    # fold("Sǿrensen") != fold("Sørensen") and the two never blocked together.
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.translate(_DIACRITIC_EXTRA)
    s = s.casefold()
    s = _INNER_APOSTROPHE_RE.sub("", s)
    s = _PUNCT_RE.sub(" ", s)
    return _WS_RE.sub(" ", s).strip()


def _collapse_dotted_suffixes(raw: list[str]) -> list[str]:
    """Rejoin a run of single letters that spells a legal-form suffix.

    fold() keeps "L.L.C." as three tokens on purpose (initialisms must not
    collide with real words), but that left "Alpha Precision L.L.C." with
    the tokens ('l', 'l', 'c'): never stripped as a suffix, and shared with
    every other dotted L.L.C. in the list -- two unrelated "... Trading
    L.L.C." companies banded WEAK on those three letters while the same pair
    spelled "LLC" returned nothing. The run is rejoined only when the joined
    form is a known suffix, so "A.B.C." stays three tokens.
    """
    out: list[str] = []
    i = 0
    while i < len(raw):
        if len(raw[i]) == 1:
            j = i
            while j < len(raw) and len(raw[j]) == 1:
                j += 1
            joined = "".join(raw[i:j])
            if j - i >= 2 and joined in CORPORATE_SUFFIXES:
                out.append(joined)
                i = j
                continue
        out.append(raw[i])
        i += 1
    return out


@lru_cache(maxsize=200_000)
def tokens(s: str) -> tuple[str, ...]:
    """Folded tokens with word equivalences applied, noise removed."""
    out: list[str] = []
    for t in _collapse_dotted_suffixes(fold(s).split()):
        t = WORD_EQUIV.get(t, t)
        if not t or t in NOISE_TOKENS:
            continue
        out.append(t)
    return tuple(out)


@lru_cache(maxsize=200_000)
def core_tokens(s: str) -> tuple[str, ...]:
    """Tokens with corporate-form suffixes removed.

    Falls back to the full token list when stripping would empty the name --
    an entity genuinely called "Holding Group" must still be matchable.
    """
    ts = tokens(s)
    core = tuple(t for t in ts if t not in CORPORATE_SUFFIXES)
    return core if core else ts


@lru_cache(maxsize=200_000)
def normalized(s: str) -> str:
    """Single-string comparison key: core tokens, sorted-stable, space joined."""
    return " ".join(core_tokens(s))


# --------------------------------------------------------------------------
# Transliteration skeleton
# --------------------------------------------------------------------------
# Latin transliterations of Arabic, Cyrillic, Persian and Chinese names vary
# mostly in their vowels and in a handful of consonant digraphs. Collapsing
# both produces a key that unites "Mohammed"/"Muhammad"/"Mohamad" and
# "Yusuf"/"Yousef", at the cost of some over-generation.

# Order matters: longer digraphs run before the shorter ones they contain
# ("tch" before "ch"), and the single-character folds run last. The q/g/k
# fold at the end unites the most consequential transliteration family in
# OFAC history -- Qadhafi/Gaddafi/Kaddafi all render the same Arabic qāf --
# which the digraph table alone missed entirely: the three skeletons were
# qdf/gdf/kdf and never blocked into the same candidates.
_DIGRAPHS: tuple[tuple[str, str], ...] = (
    ("sch", "s"), ("tch", "c"), ("sh", "s"), ("ch", "c"), ("kh", "k"),
    ("gh", "g"), ("ph", "f"), ("th", "t"), ("zh", "j"), ("dh", "d"),
    ("ts", "c"), ("ck", "k"), ("qu", "k"), ("x", "ks"),
    ("q", "k"), ("g", "k"),
)

_VOWELS = "aeiouy"

# The Slavic patronymic/surname ending romanizes as -ov, -off, -ev, -eff, -ow,
# -ew depending on the transliteration system and the era. Normalized on the
# token, before the digraph and vowel passes, so the whole family collapses.
_SLAVIC_ENDING = re.compile(r"(off|ov|ow|ev|eff|ew|of)$")


@lru_cache(maxsize=200_000)
def skeleton(s: str) -> str:
    """Consonant skeleton of a name, robust to transliteration vowel drift."""
    out: list[str] = []
    for tok in core_tokens(s):
        t = _SLAVIC_ENDING.sub("ov", tok)
        for a, b in _DIGRAPHS:
            t = t.replace(a, b)
        # Collapse doubled letters ("Abdullah"/"Abdulah").
        t = re.sub(r"(.)\1+", r"\1", t)
        if not t:
            continue
        head, tail = t[0], t[1:]
        tail = "".join(ch for ch in tail if ch not in _VOWELS)
        out.append(head + tail)
    return " ".join(out)


@lru_cache(maxsize=200_000)
def sorted_normalized(s: str) -> str:
    """Order-independent comparison key.

    List files and ERP exports disagree constantly about "Surname, Given"
    versus "Given Surname", and about where a qualifier sits in a company
    name. Sorting the tokens makes the two renderings comparable without
    weakening the ordered comparison, which is kept alongside it.
    """
    return " ".join(sorted(core_tokens(s)))


@lru_cache(maxsize=200_000)
def sorted_skeleton(s: str) -> str:
    return " ".join(sorted(skeleton(s).split()))


# --------------------------------------------------------------------------
# String similarity
# --------------------------------------------------------------------------

def jaro(a: str, b: str) -> float:
    """Jaro similarity in [0, 1]."""
    if a == b:
        return 1.0
    la, lb = len(a), len(b)
    if la == 0 or lb == 0:
        return 0.0
    window = max(la, lb) // 2 - 1
    if window < 0:
        window = 0
    a_flags = [False] * la
    b_flags = [False] * lb
    matches = 0
    for i in range(la):
        lo = max(0, i - window)
        hi = min(i + window + 1, lb)
        for j in range(lo, hi):
            if b_flags[j] or a[i] != b[j]:
                continue
            a_flags[i] = b_flags[j] = True
            matches += 1
            break
    if matches == 0:
        return 0.0
    # Half the number of transposed matched characters.
    k = 0
    transpositions = 0
    for i in range(la):
        if not a_flags[i]:
            continue
        while not b_flags[k]:
            k += 1
        if a[i] != b[k]:
            transpositions += 1
        k += 1
    t = transpositions / 2
    return (matches / la + matches / lb + (matches - t) / matches) / 3


def jaro_winkler(a: str, b: str, prefix_weight: float = 0.1) -> float:
    """Jaro-Winkler similarity, capped at a 4-character common prefix."""
    j = jaro(a, b)
    if j <= 0.7:
        return j
    prefix = 0
    for x, y in zip(a[:4], b[:4]):
        if x != y:
            break
        prefix += 1
    return j + prefix * prefix_weight * (1 - j)


def levenshtein(a: str, b: str, cap: int | None = None) -> int:
    """Edit distance, with optional early exit once `cap` is exceeded."""
    if a == b:
        return 0
    if len(a) < len(b):
        a, b = b, a
    if not b:
        return len(a)
    if cap is not None and len(a) - len(b) > cap:
        return cap + 1
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        best = i
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
            best = min(best, cur[-1])
        prev = cur
        if cap is not None and best > cap:
            return cap + 1
    return prev[-1]


def levenshtein_ratio(a: str, b: str, floor: float = 0.0) -> float:
    """Similarity in [0, 1].

    `floor` lets the caller say "I only care whether this beats X", which caps
    the edit-distance search instead of filling the whole O(n*m) matrix. On a
    pathological name -- a 13 KB field, which fits comfortably inside the csv
    limit -- the uncapped version cost minutes per comparison.
    """
    if not a and not b:
        return 1.0
    m = max(len(a), len(b))
    if not m:
        return 0.0
    cap = int(m * (1.0 - floor)) if floor > 0.0 else None
    d = levenshtein(a, b, cap=cap)
    return max(0.0, 1.0 - (d / m))


def token_set_ratio(a: tuple[str, ...], b: tuple[str, ...]) -> float:
    """Jaccard overlap of token sets."""
    sa, sb = set(a), set(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def token_containment(a: tuple[str, ...], b: tuple[str, ...]) -> float:
    """Fraction of the *shorter* token set contained in the longer.

    Catches "Acme" inside "Acme Precision Machining", which Jaccard punishes
    but which is a real screening hit -- subsidiaries and trade names are
    routinely shortened on invoices.
    """
    sa, sb = set(a), set(b)
    if not sa or not sb:
        return 0.0
    short, long = (sa, sb) if len(sa) <= len(sb) else (sb, sa)
    return len(short & long) / len(short)


def initials(t: tuple[str, ...]) -> str:
    return "".join(x[0] for x in t if x)


def is_acronym_of(a: str, b_tokens: tuple[str, ...]) -> bool:
    """True when `a` reads as the initialism of `b_tokens` (KMZ / K M Z).

    Three letters minimum: on a real list, two-letter initials collide with
    half the two-token names in the file and produce nothing but noise.
    """
    a_compact = fold(a).replace(" ", "")
    if len(a_compact) < 3 or len(b_tokens) < 2:
        return False
    return a_compact == initials(b_tokens)
