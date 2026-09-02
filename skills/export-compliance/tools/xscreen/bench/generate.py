"""Seeded synthetic corpus generator.

Every name here is *composed* from syllable pools at generation time. No
pool contains the name of a real sanctioned person, company or vessel, and
no pool is derived from a government list. Composed names can coincide with
real words by chance (a two-syllable pinyin surname is unavoidably a real
surname); that coincidence is not a reference to any real listed party.

Determinism: everything is drawn from one `random.Random(seed)` in a fixed
order, so the same seed and size produce the same corpus on any machine and
any Python version that keeps `random.Random`'s sequence stable (it has
since 3.2).

Vocabulary structure, because the benchmark's negatives depend on it:

* **Distinctive tokens** are the composed ones -- a surname, a company's
  proper name, a vessel's name. Each party records its own. A true negative
  is a name that shares *no* distinctive token with anything in the index.
* **Generic tokens** are drawn from small fixed pools -- given names,
  industry words ("Precision", "Machinery"), the words every trading company
  uses ("International", "Group"), legal forms. Sharing these across parties
  is the point: it is what makes blocking and the discriminating-token rule
  earn their keep.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from ..models import ListedParty
from ..names import core_tokens, fold

STYLES: tuple[str, ...] = ("latin", "cyrillic", "arabic", "cjk")
KINDS: tuple[str, ...] = ("entity", "individual", "vessel")

# ---------------------------------------------------------------------------
# Syllable and word pools
# ---------------------------------------------------------------------------

LATIN_SYL = (
    "bel", "mar", "ton", "vic", "ren", "dor", "las", "quin", "hal", "ver",
    "mon", "tra", "sel", "ber", "cas", "wen", "fal", "gri", "lor", "pen",
    "rud", "sta", "thal", "ost", "brin", "cor", "dun", "elm", "fen", "gal",
)
LATIN_END = (
    "ford", "wick", "stone", "field", "hurst", "mere", "worth", "by", "ley",
    "bach", "gard", "holm", "vale", "son", "man", "berg", "dorf", "ton",
)
LATIN_GIVEN_A = ("Al", "Ber", "Cor", "Dan", "El", "Fre", "Ger", "Hen", "Il", "Jor",
                 "Kas", "Lu", "Mar", "Nor", "Os", "Pat", "Ro", "Sil", "Ta", "Vi")
LATIN_GIVEN_B = ("an", "ic", "dric", "mund", "nard", "win", "ren", "mo", "sen",
                 "ton", "vin", "lio", "rik", "ina", "ela", "ora", "ette", "ika")

CYR_SYL = (
    "vol", "kor", "pet", "ros", "nov", "mal", "zhu", "kri", "bel", "gor",
    "sta", "tar", "lut", "mir", "sok", "dub", "yer", "chai", "shche", "kly",
    "bor", "sev", "tru", "vish", "gla", "kho", "zhe", "tsy", "shu", "ryb",
)
CYR_SUR_END = ("ov", "ev", "in", "sky", "enko", "ich", "uk", "tsev", "ykh")
CYR_GIVEN = (
    "Vasili", "Dmitri", "Nikolai", "Sergei", "Andrei", "Aleksei", "Mikhail",
    "Oleg", "Yevgeni", "Konstantin", "Pavel", "Igor", "Boris", "Grigori",
    "Yuri", "Anatoli", "Viktor", "Ruslan", "Timur", "Arkadi",
)
CYR_ENTITY_WORDS = (
    "Zavod", "Mashinostroitelny", "Nauchno-Proizvodstvenny", "Obedinenie",
    "Tekhnika", "Priborostroenie", "Kombinat", "Sudostroitelny", "Elektro",
    "Radiozavod", "Avia", "Metallurgichesky",
)

AR_G_PRE = ("Sa", "Ha", "Kha", "Ra", "Ja", "Fa", "Na", "Ta", "Mu", "Ba", "Wa",
            "Za", "Qa", "Ma", "Da", "Gha", "Sha")
AR_G_MID = ("li", "hi", "ri", "di", "mi", "bi", "zi", "si", "ni", "wi", "ki",
            "fi", "ji", "yi")
AR_G_END = ("m", "d", "r", "l", "f", "q", "n", "b", "h", "s", "z")
AR_SUR_STEM = (
    "Har", "Qud", "Sham", "Naj", "Tab", "Mas", "Zub", "Rash", "Kar", "Bad",
    "Faw", "Ghan", "Hus", "Jab", "Khal", "Lat", "Muk", "Nas", "Qas", "Sab",
)
AR_SUR_END = ("bi", "di", "ri", "wi", "ni", "si", "mi", "qi", "li", "zi")
AR_ENTITY_WORDS = (
    "General Trading", "Trading", "Contracting", "Industrial", "Commercial",
    "Shipping", "Engineering", "Import Export", "Petroleum Services",
    "Electronics",
)

PY_INIT = ("zh", "ch", "sh", "x", "q", "j", "l", "w", "h", "g", "d", "t", "b",
           "p", "m", "f", "k", "n", "r", "y", "z", "c", "s")
PY_FIN = ("ang", "eng", "ing", "ong", "an", "en", "in", "un", "ao", "ou", "ai",
          "ei", "ia", "iao", "ian", "uan", "uo", "ue", "i", "u", "a", "e", "o")
CJK_ENTITY_WORDS = (
    "Electronics", "Technology", "Precision Instruments", "Optoelectronics",
    "Machinery", "Aviation Industry", "Microelectronics", "Materials",
    "Semiconductor", "Automation", "Communication Equipment", "Photonics",
)

ENTITY_WORDS = (
    "Precision", "Machinery", "Marine", "Optics", "Logistics", "Petrochemical",
    "Aerospace", "Instruments", "Metallurgical", "Shipping", "Electronics",
    "Engineering", "Aviation", "Microwave", "Semiconductor", "Textile",
    "Pharmaceutical", "Automation", "Radar", "Composite",
)

# The words that every second trading company carries. Decoys are built from
# these so the list has the same "Trading International Group" density a real
# one does.
COMMON_WORDS = (
    "Trading", "International", "Group", "Holdings", "General", "Industries",
    "Company", "Technology", "Enterprises", "Development", "Services", "Global",
    "Investment", "Commercial",
)

VESSEL_WORDS = (
    "Aurora", "Meridian", "Sapphire", "Horizon", "Pioneer", "Voyager",
    "Tempest", "Harmony", "Corsair", "Emerald", "Glacier", "Monsoon",
    "Zenith", "Pelican", "Kestrel", "Tundra", "Sirocco", "Marlin", "Osprey",
    "Beacon",
)

# Weak-alias vocabulary: generic descriptors of the kind OFAC records in
# quotation marks. Deliberately ambiguous -- that is what a weak aka is.
WEAK_NOUNS = ("Engineer", "Doctor", "Professor", "Captain", "Chemist",
              "Broker", "Accountant", "Elder", "Tall One", "Merchant",
              "Pilot", "Teacher")

# Legal forms per style. Some are in the engine's CORPORATE_SUFFIXES set and
# some (FZE, FZCO, WLL, EOOD, OU) deliberately are not: a real ERP carries
# forms the engine has never heard of, and the benchmark should say what that
# costs rather than hide it.
LEGAL_FORMS: dict[str, tuple[str, ...]] = {
    "latin": ("LLC", "Ltd", "Inc", "GmbH", "SA", "BV", "Corp", "S.A.", "Pte Ltd",
              "Limited", "AG", "Sarl", "S.p.A.", "d.o.o.", "EOOD", "OU", "A.S."),
    "cyrillic": ("OAO", "ZAO", "OOO", "PAO", "AO", "JSC", "FGUP", "PJSC", "OJSC"),
    "arabic": ("LLC", "FZE", "FZCO", "Co.", "WLL", "Est.", "L.L.C.", "Ltd", "SAL"),
    "cjk": ("Co., Ltd.", "Co Ltd", "Limited", "Corporation", "Group Co., Ltd.",
            "Kabushiki Kaisha", "Sdn Bhd", "Inc.", "Ltd."),
}

QUALIFIERS_ENTITY = ("Division", "Branch", "Export Department", "Dubai Branch",
                     "Overseas", "Services", "Group", "Trading", "Logistics Unit")
TITLES_INDIVIDUAL = ("Mr.", "Dr.", "Eng.", "Haji", "Capt.", "Prof.", "Mrs.")
PREFIXES_VESSEL = ("MV", "M/V", "MT", "M/T", "MSC")

DIACRITIC_MAP: dict[str, tuple[str, ...]] = {
    "a": ("á", "ä", "à", "ã"), "e": ("é", "è", "ë"), "i": ("í", "ï"),
    "o": ("ó", "ö", "ø", "õ"), "u": ("ú", "ü"), "c": ("ç", "č"), "s": ("š", "ş"),
    "z": ("ž",), "n": ("ñ",), "g": ("ğ",),
}


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class BenchParty:
    """A listed party plus the generation facts the harness needs later."""

    party: ListedParty
    kind: str                      # entity | individual | vessel
    style: str                     # latin | cyrillic | arabic | cjk
    role: str                      # target | decoy
    base: str                      # name without legal form
    legal_form: str = ""           # exact suffix string appended, or ""
    distinctive: tuple[str, ...] = ()   # folded distinctive tokens
    parts: dict[str, str] = field(default_factory=dict)  # individuals: given/middle/surname
    surname_first: bool = False    # cjk individuals as published

    @property
    def uid(self) -> str:
        return self.party.uid

    @property
    def name(self) -> str:
        return self.party.name


@dataclass
class Negative:
    """A subject that must not match anything in the index."""

    name: str
    cls: str        # unrelated | near_miss_common_words | near_miss_shared_name_part | near_miss_shared_industry
    style: str
    kind: str
    # The listed party this near-miss was shaped after, for the report.
    shaped_after: str = ""


@dataclass
class Corpus:
    seed: int
    size: int
    targets: list[BenchParty]
    decoys: list[BenchParty]
    negatives: list[Negative]

    def listed(self) -> list[ListedParty]:
        return [b.party for b in self.targets] + [b.party for b in self.decoys]

    def distinctive_vocab(self) -> set[str]:
        out: set[str] = set()
        for b in self.targets + self.decoys:
            out.update(b.distinctive)
        return out


# ---------------------------------------------------------------------------
# Composition helpers
# ---------------------------------------------------------------------------

def _cap(s: str) -> str:
    return s[:1].upper() + s[1:]


def _latin_word(rng: random.Random) -> str:
    n = rng.choice((2, 2, 3))
    return _cap("".join(rng.choice(LATIN_SYL) for _ in range(n - 1)) + rng.choice(LATIN_END)) \
        if rng.random() < 0.6 else _cap("".join(rng.choice(LATIN_SYL) for _ in range(n)))


def _latin_given(rng: random.Random) -> str:
    return rng.choice(LATIN_GIVEN_A) + rng.choice(LATIN_GIVEN_B)


def _maybe_diacritic(word: str, rng: random.Random, p: float) -> str:
    if rng.random() >= p:
        return word
    positions = [i for i, ch in enumerate(word.lower()) if ch in DIACRITIC_MAP and i > 0]
    if not positions:
        return word
    i = rng.choice(positions)
    repl = rng.choice(DIACRITIC_MAP[word[i].lower()])
    return word[:i] + repl + word[i + 1:]


def _cyr_word(rng: random.Random) -> str:
    return _cap("".join(rng.choice(CYR_SYL) for _ in range(rng.choice((2, 2, 3)))))


def _cyr_surname(rng: random.Random) -> str:
    stem = "".join(rng.choice(CYR_SYL) for _ in range(rng.choice((1, 2, 2))))
    return _cap(stem + rng.choice(CYR_SUR_END))


def _ar_given(rng: random.Random) -> str:
    return rng.choice(AR_G_PRE) + rng.choice(AR_G_MID) + rng.choice(AR_G_END)


def _ar_surname(rng: random.Random) -> str:
    stem = rng.choice(AR_SUR_STEM) + rng.choice(AR_G_MID)
    r = rng.random()
    if r < 0.5:
        return "al-" + stem + rng.choice(AR_SUR_END)
    if r < 0.75:
        return stem + rng.choice(AR_SUR_END)
    return "al-" + stem


def _py_syl(rng: random.Random) -> str:
    return rng.choice(PY_INIT) + rng.choice(PY_FIN)


def _cjk_surname(rng: random.Random) -> str:
    return _cap(_py_syl(rng))


def _cjk_given(rng: random.Random) -> str:
    return _cap(_py_syl(rng) + _py_syl(rng))


def _cjk_place(rng: random.Random) -> str:
    return _cap(_py_syl(rng) + _py_syl(rng))


def _legal_form(style: str, rng: random.Random) -> str:
    return rng.choice(LEGAL_FORMS[style])


# ---------------------------------------------------------------------------
# Party builders
# ---------------------------------------------------------------------------

def _make_individual(style: str, rng: random.Random) -> tuple[str, dict[str, str], tuple[str, ...], bool]:
    """Return (name, parts, distinctive tokens, surname_first)."""
    if style == "latin":
        given = _latin_given(rng)
        middle = _latin_given(rng) if rng.random() < 0.4 else ""
        surname = _maybe_diacritic(_latin_word(rng), rng, 0.15)
        parts = {"given": given, "middle": middle, "surname": surname}
        name = " ".join(x for x in (given, middle, surname) if x)
        return name, parts, (fold(surname),), False
    if style == "cyrillic":
        given = rng.choice(CYR_GIVEN)
        base = rng.choice(CYR_GIVEN)
        patronymic = base + ("evich" if base.endswith("i") else "ovich")
        if base.endswith("i"):
            patronymic = base[:-1] + "evich"
        middle = patronymic if rng.random() < 0.8 else ""
        surname = _cyr_surname(rng)
        parts = {"given": given, "middle": middle, "surname": surname}
        name = " ".join(x for x in (given, middle, surname) if x)
        return name, parts, (fold(surname),), False
    if style == "arabic":
        given = _ar_given(rng)
        middle = ("bin " + _ar_given(rng)) if rng.random() < 0.5 else ""
        surname = _ar_surname(rng)
        parts = {"given": given, "middle": middle, "surname": surname}
        name = " ".join(x for x in (given, middle, surname) if x)
        # "al-harbi" folds to "al harbi"; "al" is a noise token, so the
        # distinctive part is the stem.
        distinctive = tuple(t for t in core_tokens(surname))
        return name, parts, distinctive, False
    # cjk: surname first as published, given name is the distinctive part
    surname = _cjk_surname(rng)
    given = _cjk_given(rng)
    parts = {"given": given, "middle": "", "surname": surname}
    name = f"{surname} {given}"
    return name, parts, (fold(given),), True


def _make_entity_base(style: str, rng: random.Random) -> tuple[str, tuple[str, ...]]:
    """Return (base name without legal form, distinctive tokens)."""
    if style == "latin":
        d = _maybe_diacritic(_latin_word(rng), rng, 0.1)
        words = rng.sample(ENTITY_WORDS, rng.choice((1, 2, 2)))
        if rng.random() < 0.3:
            words.append(rng.choice(COMMON_WORDS))
        return f"{d} {' '.join(words)}", (fold(d),)
    if style == "cyrillic":
        d = _cyr_word(rng)
        r = rng.random()
        if r < 0.4:
            base = f"{d} {rng.choice(CYR_ENTITY_WORDS)}"
        elif r < 0.7:
            base = f"{rng.choice(CYR_ENTITY_WORDS)} {d}"
        else:
            base = f"{d} {rng.choice(ENTITY_WORDS)} {rng.choice(ENTITY_WORDS)}"
        return base, tuple(core_tokens(d))
    if style == "arabic":
        d = rng.choice(AR_SUR_STEM) + rng.choice(AR_G_MID) + rng.choice(AR_G_END)
        r = rng.random()
        if r < 0.4:
            base = f"Al-{d} {rng.choice(AR_ENTITY_WORDS)}"
        elif r < 0.7:
            base = f"{d} {rng.choice(AR_ENTITY_WORDS)}"
        else:
            base = f"Sharikat {d} {rng.choice(AR_ENTITY_WORDS)}"
        return base, (fold(d),)
    # cjk
    place = _cjk_place(rng)
    d = _cap(_py_syl(rng) + _py_syl(rng))
    words = rng.choice(CJK_ENTITY_WORDS)
    if rng.random() < 0.5:
        base = f"{place} {d} {words}"
        return base, (fold(d), fold(place))
    base = f"{d} {words}"
    return base, (fold(d),)


def _make_vessel(rng: random.Random) -> tuple[str, tuple[str, ...]]:
    d = _latin_word(rng)
    r = rng.random()
    if r < 0.4:
        name = f"{rng.choice(VESSEL_WORDS)} {d}"
    elif r < 0.7:
        name = f"{d} {rng.choice(VESSEL_WORDS)}"
    else:
        name = f"{d} {rng.choice(VESSEL_WORDS)} {rng.randint(1, 12)}"
    return name.upper(), (fold(d),)


def _weak_alias(style: str, rng: random.Random) -> str:
    if style == "arabic":
        return "Abu " + _ar_given(rng)
    return "The " + rng.choice(WEAK_NOUNS)


def _party(uid: str, name: str, kind: str, aliases: list[str] | None = None,
           weak: list[str] | None = None) -> ListedParty:
    return ListedParty(
        uid=uid, source="SDN", native_id=uid.split(":", 1)[1], name=name,
        party_type=kind,  # type: ignore[arg-type]
        aliases=list(aliases or []), weak_aliases=list(weak or []),
        countries=[], programs=["BENCH"],
    )


def _make_target(i: int, rng: random.Random) -> BenchParty:
    r = rng.random()
    kind = "entity" if r < 0.55 else ("individual" if r < 0.90 else "vessel")
    uid = f"SDN:B{i:05d}"
    if kind == "vessel":
        name, distinctive = _make_vessel(rng)
        return BenchParty(party=_party(uid, name, kind), kind=kind, style="latin",
                          role="target", base=name, distinctive=distinctive)
    style = rng.choice(STYLES)
    if kind == "individual":
        name, parts, distinctive, sf = _make_individual(style, rng)
        weak = [_weak_alias(style, rng)] if rng.random() < 0.2 else []
        return BenchParty(party=_party(uid, name, kind, aliases=weak, weak=weak),
                          kind=kind, style=style, role="target", base=name,
                          distinctive=distinctive, parts=parts, surname_first=sf)
    base, distinctive = _make_entity_base(style, rng)
    form = _legal_form(style, rng) if rng.random() < 0.8 else ""
    name = f"{base} {form}".strip()
    return BenchParty(party=_party(uid, name, kind), kind=kind, style=style,
                      role="target", base=base, legal_form=form, distinctive=distinctive)


def _fresh_distinctive(style: str, rng: random.Random, taken: set[str]) -> str:
    """A composed token whose folded form is not in `taken`."""
    for _ in range(200):
        if style == "latin":
            w = _latin_word(rng)
        elif style == "cyrillic":
            w = _cyr_word(rng)
        elif style == "arabic":
            w = _cap(rng.choice(AR_SUR_STEM) + rng.choice(AR_G_MID) + rng.choice(AR_G_END))
        else:
            w = _cap(_py_syl(rng) + _py_syl(rng))
        if fold(w) not in taken:
            return w
    raise RuntimeError("could not compose a fresh distinctive token; enlarge the pools")


def _make_decoy(i: int, rng: random.Random, targets: list[BenchParty],
                taken: set[str]) -> BenchParty:
    uid = f"SDN:D{i:05d}"
    style = rng.choice(STYLES)
    commons = rng.sample(COMMON_WORDS, 2)
    sibling = rng.random() < 0.25 and targets
    if sibling:
        # A sibling shares a target's distinctive token: the "subsidiary with
        # the same trade name" pattern. Different party, same rare word.
        src = rng.choice(targets)
        d = src.base.split()[0] if src.kind != "individual" else src.parts["surname"]
        distinctive = tuple(core_tokens(d))
    else:
        d = _fresh_distinctive(style, rng, taken)
        distinctive = (fold(d),)
        taken.add(fold(d))
    r = rng.random()
    if r < 0.5:
        base = f"{d} {commons[0]} {commons[1]}"
    elif r < 0.8:
        base = f"{commons[0]} {commons[1]} {d}"
    else:
        base = f"{d} {rng.choice(ENTITY_WORDS)} {commons[0]}"
    form = _legal_form(style, rng) if rng.random() < 0.7 else ""
    name = f"{base} {form}".strip()
    return BenchParty(party=_party(uid, name, "entity"), kind="entity", style=style,
                      role="decoy", base=base, legal_form=form, distinctive=distinctive)


# ---------------------------------------------------------------------------
# Negatives
# ---------------------------------------------------------------------------

NEGATIVE_CLASSES: tuple[str, ...] = (
    "unrelated",
    "near_miss_common_words",
    "near_miss_shared_name_part",
    "near_miss_shared_industry",
)


def _unrelated(rng: random.Random, taken: set[str]) -> Negative:
    for _ in range(200):
        r = rng.random()
        kind = "entity" if r < 0.55 else ("individual" if r < 0.90 else "vessel")
        if kind == "vessel":
            name, distinctive = _make_vessel(rng)
            style = "latin"
        else:
            style = rng.choice(STYLES)
            if kind == "individual":
                name, _, distinctive, _ = _make_individual(style, rng)
            else:
                base, distinctive = _make_entity_base(style, rng)
                form = _legal_form(style, rng) if rng.random() < 0.8 else ""
                name = f"{base} {form}".strip()
        if not any(t in taken for t in distinctive):
            return Negative(name=name, cls="unrelated", style=style, kind=kind)
    raise RuntimeError("could not compose an unrelated negative")


def _near_common(rng: random.Random, taken: set[str], pool: list[BenchParty]) -> Negative:
    src = rng.choice(pool)
    distinct = set(src.distinctive)
    generic = [t for t in src.base.split() if not (set(core_tokens(t)) & distinct)
               and fold(t) in {fold(w) for w in COMMON_WORDS}]
    if not generic:
        generic = list(rng.sample(COMMON_WORDS, 2))
    d = _fresh_distinctive(src.style, rng, taken)
    form = _legal_form(src.style, rng) if rng.random() < 0.7 else ""
    name = f"{d} {' '.join(generic)} {form}".strip()
    return Negative(name=name, cls="near_miss_common_words", style=src.style,
                    kind="entity", shaped_after=src.name)


def _near_name_part(rng: random.Random, taken: set[str], individuals: list[BenchParty]) -> Negative:
    src = rng.choice(individuals)
    p = src.parts
    if src.style == "cjk":
        # Same surname (one syllable, shared by many), fresh given name.
        given = _fresh_distinctive("cjk", rng, taken)
        name = f"{p['surname']} {given}"
    else:
        if src.style == "latin":
            surname = _fresh_distinctive("latin", rng, taken)
        elif src.style == "cyrillic":
            surname = _fresh_distinctive("cyrillic", rng, taken)
        else:
            surname = "al-" + _fresh_distinctive("arabic", rng, taken)
        name = " ".join(x for x in (p["given"], p["middle"], surname) if x)
    return Negative(name=name, cls="near_miss_shared_name_part", style=src.style,
                    kind="individual", shaped_after=src.name)


def _near_industry(rng: random.Random, taken: set[str], entities: list[BenchParty]) -> Negative:
    src = rng.choice(entities)
    # Compare on core tokens, not the folded word: "Al-Ghanzid" folds to
    # "al ghanzid", and matching on that whole string kept the distinctive
    # token in what was supposed to be a negative.
    distinct = set(src.distinctive)
    rest = [t for t in src.base.split() if not (set(core_tokens(t)) & distinct)]
    d = _fresh_distinctive(src.style, rng, taken)
    if src.style == "arabic" and src.base.startswith("Al-"):
        d = "Al-" + d
    form = _legal_form(src.style, rng) if rng.random() < 0.7 else ""
    name = f"{d} {' '.join(rest)} {form}".strip() if rest else f"{d} {rng.choice(ENTITY_WORDS)} {form}".strip()
    return Negative(name=name, cls="near_miss_shared_industry", style=src.style,
                    kind="entity", shaped_after=src.name)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def generate_corpus(seed: int, size: int, negatives: int | None = None,
                    decoy_ratio: float = 0.3) -> Corpus:
    """Build a corpus of `size` listed targets plus decoys and negatives.

    `negatives` defaults to `size`. Decoys are `decoy_ratio * size` extra
    listed parties made of generic words around one distinctive token.
    """
    if size < 1:
        raise ValueError("size must be >= 1")
    rng = random.Random(seed)
    n_neg = size if negatives is None else negatives

    targets = [_make_target(i, rng) for i in range(size)]
    taken: set[str] = set()
    for b in targets:
        taken.update(b.distinctive)
    decoys = [_make_decoy(i, rng, targets, taken) for i in range(int(size * decoy_ratio))]
    for b in decoys:
        taken.update(b.distinctive)

    individuals = [b for b in targets if b.kind == "individual"]
    entities = [b for b in targets if b.kind == "entity"]
    pool = targets + decoys
    negs: list[Negative] = []
    for i in range(n_neg):
        r = rng.random()
        # A builder guarantees its *own* composed token is fresh, but a
        # generic part it keeps -- a one-syllable CJK surname, a given name
        # -- can coincide with a composed token somewhere in the index
        # ("Ki"+"an" is also the surname "Kian"). The negative contract is
        # "shares no distinctive token with anything listed", so check the
        # whole name and redraw when it fails.
        for _ in range(50):
            if r < 0.4 or not pool:
                n = _unrelated(rng, taken)
            elif r < 0.6:
                n = _near_common(rng, taken, pool)
            elif r < 0.8 and individuals:
                n = _near_name_part(rng, taken, individuals)
            elif entities:
                n = _near_industry(rng, taken, entities)
            else:
                n = _unrelated(rng, taken)
            if not (set(core_tokens(n.name)) & taken):
                break
        else:
            raise RuntimeError("could not compose a negative free of listed tokens")
        negs.append(n)
    return Corpus(seed=seed, size=size, targets=targets, decoys=decoys, negatives=negs)
