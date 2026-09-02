"""Taxonomy of the ways an ERP counterparty record mangles a listed name.

Each perturbation is a pure function `(name, party, rng) -> str | None`:
the string an invoice, a customer master record or an OCR'd bill of lading
would carry for the listed party. `None` means "not applicable to this
party" (you cannot drop the patronymic from a vessel).

Every function operates on the *string* it is given and uses the party
record only as a hint (which token is the surname, which suffix is the
legal form), so two perturbations can be stacked: the second is applied to
the output of the first. Where a hint no longer holds after the first edit,
the second returns `None` and the stacker picks another.

The classes and what they stand for:

| class                | the real-world record it imitates                          |
|----------------------|------------------------------------------------------------|
| identity             | verbatim copy of the listed name (harness sanity check)    |
| legal_form_swap      | LLC on the list, GmbH / FZE / Co., Ltd. on the invoice     |
| token_reorder        | "Surname, Given Patronymic" vs "Given Patronymic Surname"  |
| translit_drift       | kh/q/g, ch/tch, sh/sch, vowel drift between systems         |
| diacritics_toggle    | ERP strips or adds accents the list does not carry         |
| typo_substitution    | one wrong interior character                                |
| typo_transposition   | two adjacent interior characters swapped                    |
| typo_deletion        | one interior character dropped                              |
| dropped_middle       | individual without middle name / patronymic                 |
| truncated_name       | entity or vessel with its last name word dropped            |
| added_qualifier      | "... Dubai Branch", "Mr. ...", "MV ..."                     |
| acronym              | initialism of a 3+ token entity name                        |
| ocr_space_insertion  | OCR splits a token: "Velm ora"                              |
| missing_space        | two tokens run together: "VelmoraPrecision"                 |
| weak_alias           | record carries only the party's generic weak aka            |
| punctuation_noise    | commas, hyphens, quotes, parentheses, trailing dots         |
| stacked_pair         | two of the above applied in sequence                        |

Interior positions only for the typo classes (never the first character):
first-character typos exist but are rare in practice, and a benchmark that
spent a fifth of its typo budget on them would measure the wrong thing.
"""

from __future__ import annotations

import random
import re
import unicodedata
from dataclasses import dataclass
from typing import Callable

from ..names import CORPORATE_SUFFIXES, core_tokens, fold, initials
from .generate import (
    BenchParty,
    DIACRITIC_MAP,
    LEGAL_FORMS,
    PREFIXES_VESSEL,
    QUALIFIERS_ENTITY,
    TITLES_INDIVIDUAL,
)

PerturbFn = Callable[[str, BenchParty, random.Random], "str | None"]


@dataclass(frozen=True)
class Perturbation:
    cls: str
    description: str
    fn: PerturbFn


@dataclass
class PerturbedSubject:
    cls: str
    name: str          # what the ERP record says
    listed_uid: str
    listed_name: str
    kind: str
    style: str


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

_ALL_FORMS_FOLDED: tuple[tuple[str, ...], ...] = tuple(
    sorted({tuple(fold(f).split()) for forms in LEGAL_FORMS.values() for f in forms},
           key=len, reverse=True)
)
_LETTERS = "abcdefghijklmnopqrstuvwxyz"


def _split_legal_form(name: str) -> tuple[list[str], list[str]]:
    """(body tokens, legal-form tokens) by matching the longest known form."""
    toks = name.split()
    folded = [fold(t) for t in toks]
    for form in _ALL_FORMS_FOLDED:
        n = len(form)
        if n and len(toks) > n and tuple(folded[-n:]) == form:
            return toks[:-n], toks[-n:]
    if len(toks) > 1 and folded[-1] in CORPORATE_SUFFIXES:
        return toks[:-1], toks[-1:]
    return toks, []


def _editable_positions(toks: list[str], min_len: int) -> list[int]:
    """Indices of tokens long enough to edit and not a legal form."""
    body, _ = _split_legal_form(" ".join(toks))
    out = []
    for i, t in enumerate(toks[:len(body)]):
        letters = sum(ch.isalpha() for ch in t)
        if letters >= min_len and fold(t) not in CORPORATE_SUFFIXES:
            out.append(i)
    return out


def _has_diacritics(s: str) -> bool:
    return any(unicodedata.combining(ch) for ch in unicodedata.normalize("NFKD", s)) \
        or any(ch in "øØđĐłŁ" for ch in s)


def _strip_diacritics(s: str) -> str:
    extra = str.maketrans({"ø": "o", "Ø": "O", "đ": "d", "Đ": "D", "ł": "l", "Ł": "L"})
    s = s.translate(extra)
    return "".join(ch for ch in unicodedata.normalize("NFKD", s) if not unicodedata.combining(ch))


def _replace_one(s: str, a: str, b: str, rng: random.Random) -> str | None:
    """Replace one random case-insensitive occurrence of `a` with `b`."""
    hits = [m.start() for m in re.finditer(re.escape(a), s, flags=re.IGNORECASE)]
    if not hits:
        return None
    i = rng.choice(hits)
    orig = s[i:i + len(a)]
    repl = b.upper() if orig.isupper() else (b[:1].upper() + b[1:] if orig[:1].isupper() else b)
    return s[:i] + repl + s[i + len(a):]


# ---------------------------------------------------------------------------
# perturbations
# ---------------------------------------------------------------------------

def p_identity(name: str, party: BenchParty, rng: random.Random) -> str | None:
    return name


def p_legal_form_swap(name: str, party: BenchParty, rng: random.Random) -> str | None:
    if party.kind != "entity":
        return None
    body, form = _split_legal_form(name)
    if not body:
        return None
    current = fold(" ".join(form))
    choices = [f for f in LEGAL_FORMS[party.style] if fold(f) != current]
    # Cross-style forms happen too: a Chinese supplier registered in Dubai.
    if rng.random() < 0.2:
        other = rng.choice([s for s in LEGAL_FORMS if s != party.style])
        choices = [f for f in LEGAL_FORMS[other] if fold(f) != current]
    if not choices:
        return None
    return " ".join(body) + " " + rng.choice(choices)


def p_token_reorder(name: str, party: BenchParty, rng: random.Random) -> str | None:
    if party.kind != "individual":
        return None
    surname = party.parts.get("surname", "")
    toks = name.split()
    matches = [i for i, t in enumerate(toks) if fold(t) == fold(surname)]
    if not matches or len(toks) < 2:
        return None
    i = matches[0]
    rest = toks[:i] + toks[i + 1:]
    if party.surname_first and i == 0:
        # Published surname-first (CJK); the record writes Western order.
        return " ".join(rest + [toks[i]])
    if rng.random() < 0.7:
        return f"{toks[i]}, {' '.join(rest)}"
    return " ".join([toks[i]] + rest)


_DRIFT_RULES: tuple[tuple[str, str], ...] = (
    ("kh", "q"), ("kh", "ch"), ("q", "k"), ("q", "gh"), ("gh", "g"), ("g", "gh"),
    ("ch", "tch"), ("tch", "ch"), ("sh", "sch"), ("sh", "ch"), ("zh", "j"),
    ("ts", "tz"), ("ph", "f"), ("ou", "u"), ("oo", "u"), ("u", "ou"),
    ("y", "i"), ("i", "y"), ("ei", "ey"), ("ai", "ay"), ("ov", "off"),
    ("ev", "eff"), ("v", "w"), ("ks", "x"), ("dj", "j"), ("ee", "i"),
    ("iy", "i"), ("ii", "i"), ("e", "i"), ("o", "u"), ("a", "e"),
)


def p_translit_drift(name: str, party: BenchParty, rng: random.Random) -> str | None:
    body, form = _split_legal_form(name)
    text = " ".join(body)
    applicable = [(a, b) for a, b in _DRIFT_RULES if re.search(re.escape(a), text, re.IGNORECASE)]
    if not applicable:
        return None
    n = 1 if rng.random() < 0.6 else 2
    out = text
    for a, b in rng.sample(applicable, min(n, len(applicable))):
        r = _replace_one(out, a, b, rng)
        if r is not None:
            out = r
    if fold(out) == fold(text):
        return None
    return " ".join([out] + form)


def p_diacritics_toggle(name: str, party: BenchParty, rng: random.Random) -> str | None:
    if _has_diacritics(name):
        return _strip_diacritics(name)
    toks = name.split()
    pos = _editable_positions(toks, 3)
    if not pos:
        return None
    for i in rng.sample(pos, min(len(pos), rng.choice((1, 1, 2)))):
        t = toks[i]
        spots = [j for j, ch in enumerate(t.lower()) if ch in DIACRITIC_MAP and j > 0]
        if not spots:
            continue
        j = rng.choice(spots)
        toks[i] = t[:j] + rng.choice(DIACRITIC_MAP[t[j].lower()]) + t[j + 1:]
    out = " ".join(toks)
    return out if out != name else None


def _typo_target(name: str, rng: random.Random, min_len: int) -> tuple[list[str], int] | None:
    toks = name.split()
    pos = _editable_positions(toks, min_len)
    if not pos:
        return None
    return toks, rng.choice(pos)


def p_typo_substitution(name: str, party: BenchParty, rng: random.Random) -> str | None:
    tgt = _typo_target(name, rng, 4)
    if tgt is None:
        return None
    toks, i = tgt
    t = toks[i]
    inner = [j for j in range(1, len(t) - 1) if t[j].isalpha()]
    if not inner:
        return None
    j = rng.choice(inner)
    new = rng.choice([c for c in _LETTERS if c != t[j].lower()])
    toks[i] = t[:j] + (new.upper() if t[j].isupper() else new) + t[j + 1:]
    return " ".join(toks)


def p_typo_transposition(name: str, party: BenchParty, rng: random.Random) -> str | None:
    tgt = _typo_target(name, rng, 4)
    if tgt is None:
        return None
    toks, i = tgt
    t = toks[i]
    inner = [j for j in range(1, len(t) - 2) if t[j].isalpha() and t[j + 1].isalpha()
             and t[j].lower() != t[j + 1].lower()]
    if not inner:
        return None
    j = rng.choice(inner)
    toks[i] = t[:j] + t[j + 1] + t[j] + t[j + 2:]
    return " ".join(toks)


def p_typo_deletion(name: str, party: BenchParty, rng: random.Random) -> str | None:
    tgt = _typo_target(name, rng, 4)
    if tgt is None:
        return None
    toks, i = tgt
    t = toks[i]
    inner = [j for j in range(1, len(t) - 1) if t[j].isalpha()]
    if not inner:
        return None
    j = rng.choice(inner)
    toks[i] = t[:j] + t[j + 1:]
    return " ".join(toks)


def p_dropped_middle(name: str, party: BenchParty, rng: random.Random) -> str | None:
    if party.kind != "individual":
        return None
    middle = party.parts.get("middle", "")
    if not middle:
        return None
    mid = fold(middle)
    body = fold(name)
    if mid not in body:
        return None
    # Remove the middle part's tokens from the string, preserving the rest.
    mid_toks = middle.split()
    toks = name.split()
    for i in range(len(toks) - len(mid_toks) + 1):
        if [fold(t) for t in toks[i:i + len(mid_toks)]] == [fold(t) for t in mid_toks]:
            out = toks[:i] + toks[i + len(mid_toks):]
            return " ".join(out) if len(out) >= 1 else None
    return None


def p_truncated_name(name: str, party: BenchParty, rng: random.Random) -> str | None:
    if party.kind == "individual":
        return None
    body, form = _split_legal_form(name)
    if len(body) < 2:
        return None
    return " ".join(body[:-1] + form)


def p_added_qualifier(name: str, party: BenchParty, rng: random.Random) -> str | None:
    if party.kind == "entity":
        body, form = _split_legal_form(name)
        q = rng.choice(QUALIFIERS_ENTITY)
        if rng.random() < 0.5:
            return " ".join(body + [q] + form)
        return " ".join(body + form + [q])
    if party.kind == "individual":
        return f"{rng.choice(TITLES_INDIVIDUAL)} {name}"
    return f"{rng.choice(PREFIXES_VESSEL)} {name}"


def p_acronym(name: str, party: BenchParty, rng: random.Random) -> str | None:
    if party.kind != "entity":
        return None
    toks = core_tokens(name)
    if len(toks) < 3:
        return None
    acro = initials(toks).upper()
    if len(acro) < 3:
        return None
    r = rng.random()
    if r < 0.6:
        return acro
    if r < 0.8:
        return ".".join(acro) + "."
    return " ".join(acro)


def p_ocr_space_insertion(name: str, party: BenchParty, rng: random.Random) -> str | None:
    tgt = _typo_target(name, rng, 5)
    if tgt is None:
        return None
    toks, i = tgt
    t = toks[i]
    j = rng.randint(2, len(t) - 2)
    toks[i] = t[:j] + " " + t[j:]
    return " ".join(toks)


def p_missing_space(name: str, party: BenchParty, rng: random.Random) -> str | None:
    body, form = _split_legal_form(name)
    if len(body) < 2:
        return None
    i = rng.randrange(len(body) - 1)
    joined = body[:i] + [body[i] + body[i + 1]] + body[i + 2:]
    return " ".join(joined + form)


def p_weak_alias(name: str, party: BenchParty, rng: random.Random) -> str | None:
    if not party.party.weak_aliases:
        return None
    return rng.choice(party.party.weak_aliases)


def p_punctuation_noise(name: str, party: BenchParty, rng: random.Random) -> str | None:
    toks = name.split()
    if not toks:
        return None
    ops = rng.sample(("comma", "hyphen", "quote", "paren", "dot", "slash"), 2)
    out = list(toks)
    for op in ops:
        if op == "comma" and len(out) >= 2:
            i = rng.randrange(len(out) - 1)
            out[i] = out[i] + ","
        elif op == "hyphen" and len(out) >= 2:
            i = rng.randrange(len(out) - 1)
            out[i] = out[i] + "-" + out[i + 1]
            del out[i + 1]
        elif op == "quote":
            i = rng.randrange(len(out))
            out[i] = f'"{out[i]}"'
        elif op == "paren" and len(out) >= 2:
            out[-1] = f"({out[-1]})"
        elif op == "dot":
            out[-1] = out[-1] + "."
        elif op == "slash" and len(out) >= 2:
            i = rng.randrange(len(out) - 1)
            out[i] = out[i] + "/"
    res = " ".join(out)
    return res if res != name else None


def p_internal_apostrophe(name: str, party: BenchParty, rng: random.Random) -> str | None:
    """An apostrophe inside a token, as Arabic ayn/hamza and Celtic and
    Romance surnames are routinely written. Kept apart from
    `punctuation_noise` because the engine treats it very differently from
    a comma: punctuation folds to a *space*, so the token splits in two."""
    tgt = _typo_target(name, rng, 4)
    if tgt is None:
        return None
    toks, i = tgt
    t = toks[i]
    inner = [j for j in range(1, len(t) - 1) if t[j - 1].isalpha() and t[j].isalpha()]
    if not inner:
        return None
    j = rng.choice(inner)
    toks[i] = t[:j] + "'" + t[j:]
    return " ".join(toks)


# Classes eligible for stacking: the ones that leave a name a downstream
# perturbation can still work on. Acronym and weak alias replace the name
# wholesale; identity is the control.
_STACKABLE: tuple[str, ...] = (
    "legal_form_swap", "token_reorder", "translit_drift", "diacritics_toggle",
    "typo_substitution", "typo_transposition", "typo_deletion", "dropped_middle",
    "truncated_name", "added_qualifier", "ocr_space_insertion", "missing_space",
    "punctuation_noise", "internal_apostrophe",
)


def p_stacked_pair(name: str, party: BenchParty, rng: random.Random) -> str | None:
    order = list(_STACKABLE)
    rng.shuffle(order)
    first = None
    for cls in order:
        r = PERTURBATIONS[cls].fn(name, party, rng)
        if r is not None and fold(r) != fold(name):
            first = (cls, r)
            break
    if first is None:
        return None
    for cls in order:
        if cls == first[0]:
            continue
        r = PERTURBATIONS[cls].fn(first[1], party, rng)
        # The second edit must not undo the first (an OCR split followed by
        # a missing-space join hands back the listed name verbatim).
        if r is not None and fold(r) != fold(first[1]) and fold(r) != fold(name) and r != name:
            return r
    return None


# ---------------------------------------------------------------------------
# registry
# ---------------------------------------------------------------------------

PERTURBATIONS: dict[str, Perturbation] = {
    p.cls: p for p in (
        Perturbation("identity", "verbatim listed name (control)", p_identity),
        Perturbation("legal_form_swap", "different legal-form suffix", p_legal_form_swap),
        Perturbation("token_reorder", "surname-first / Western-order swap", p_token_reorder),
        Perturbation("translit_drift", "transliteration digraph and vowel drift", p_translit_drift),
        Perturbation("diacritics_toggle", "diacritics added or removed", p_diacritics_toggle),
        Perturbation("typo_substitution", "one interior character substituted", p_typo_substitution),
        Perturbation("typo_transposition", "two adjacent interior characters swapped", p_typo_transposition),
        Perturbation("typo_deletion", "one interior character deleted", p_typo_deletion),
        Perturbation("dropped_middle", "middle name / patronymic dropped", p_dropped_middle),
        Perturbation("truncated_name", "last name word dropped (entity/vessel)", p_truncated_name),
        Perturbation("added_qualifier", "qualifier word, title or vessel prefix added", p_added_qualifier),
        Perturbation("acronym", "initialism of a 3+ token entity name", p_acronym),
        Perturbation("ocr_space_insertion", "space inserted inside a token", p_ocr_space_insertion),
        Perturbation("missing_space", "two tokens run together", p_missing_space),
        Perturbation("weak_alias", "only the party's generic weak aka", p_weak_alias),
        Perturbation("punctuation_noise", "commas, hyphens, quotes, parentheses", p_punctuation_noise),
        Perturbation("internal_apostrophe", "apostrophe inside a token (Sa'id, O'Brien)", p_internal_apostrophe),
        Perturbation("stacked_pair", "two perturbations applied in sequence", p_stacked_pair),
    )
}

CLASS_ORDER: tuple[str, ...] = tuple(PERTURBATIONS)


def perturb_all(parties: list[BenchParty], seed: int,
                classes: tuple[str, ...] | None = None) -> list[PerturbedSubject]:
    """Every applicable (party, class) pair, in a fixed order.

    The stream is seeded independently of the corpus generator so that
    adding a perturbation class does not re-roll the corpus.
    """
    rng = random.Random((seed * 1_000_003) ^ 0x5EED)
    out: list[PerturbedSubject] = []
    for cls in (classes or CLASS_ORDER):
        p = PERTURBATIONS[cls]
        for b in parties:
            r = p.fn(b.name, b, rng)
            if r is None or not r.strip():
                continue
            out.append(PerturbedSubject(cls=cls, name=r, listed_uid=b.uid,
                                        listed_name=b.name, kind=b.kind, style=b.style))
    return out
