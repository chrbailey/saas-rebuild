# Matching Methodology

How `xscreen` decides that a counterparty might be a listed party, why it is
deterministic, and what it costs you when you tune it.

## Why no model in the scoring path

Three reasons, in order of how much they matter.

1. **Reproducibility is the audit product.** A screening decision has to be
   reconstructible five years later from the inputs and the list snapshot
   hash. A sampled model cannot promise that; a pure function can.
2. **Recall is measurable and tunable.** Thresholds are numbers with test
   cases behind them. "The model seemed to think they were different" is not a
   control an auditor can evaluate.
3. **Cost and scale.** ~20,000 listed parties against a 10,000-party book is
   200 million comparisons. Blocking plus cheap metrics does it in minutes on
   one core with no API bill and no counterparty names leaving the host.

The model earns its place one stage later, where the question stops being
string similarity and starts being identity.

## Pipeline

```
name -> fold -> tokens -> core tokens -> {normalized, sorted, skeleton}
                                              |
                            inverted index (token + skeleton postings)
                                              |
                         blocking (rarest token first, capped)
                                              |
                    five signals -> weighted score -> band rules
```

### Normalization

**Fold.** Unicode NFKD, strip combining marks, casefold, punctuation to
whitespace, collapse runs. Note punctuation becomes *separation*, not deletion:
"A.B.C." folds to `a b c`, not `abc`, so initialisms cannot collide with real
words. Extra mappings cover characters NFKD leaves alone (ø, đ, ł, æ, ß, þ).

**Tokens.** Word-level equivalences (`company`→`co`, `technologies`→`tech`,
`brothers`→`bros`) and noise removal (`the`, `of`, `and`, romance articles).

**Core tokens.** Legal-form suffixes stripped — some 90 of them across
jurisdictions (LLC, Ltd, GmbH, OAO, ZAO, PJSC, KK, Sdn Bhd, doo, kft…). "Acme
Precision LLC" and "Acme Precision GmbH" produce the same key, which is right:
the legal form carries almost no discriminating power but wrecks edit distance.
Stripping never empties a name — an entity genuinely called "Holding Group"
keeps its tokens.

**Skeleton.** Consonant skeleton for transliteration drift. Slavic surname
endings normalize first (`-off`/`-ov`/`-ew`/`-ev` → `ov`), then digraphs fold
(`kh`→`k`, `ph`→`f`, `sch`→`s`), then doubled letters collapse, then non-
initial vowels drop. `Mohammed`/`Muhammad`, `Yusuf`/`Yousef`, `Petrov`/`Petroff`
converge. `Petrov`/`Ivanov` and `Northwind`/`Southwind` do not.

### Blocking

An inverted index over every name and alias of every listed party, plus a
skeleton index. Query tokens expand **rarest first**, capped at
`MAX_BLOCK_ENTRIES`.

The safety argument for capping at all: an exact match shares *every* token
with the query, so it necessarily appears in the postings of the query's rarest
token. Expanding rarest-first therefore cannot lose an exact match wherever the
cap falls. What the cap costs is recall on partial matches through very common
tokens — and when it bites, every candidate carries
`blocking_truncated_tokens` naming exactly what was not expanded.

### Signals and weights

| Signal | Weight | What it catches |
|---|---|---|
| Jaro-Winkler | 0.35 | Typos, minor spelling drift; prefix-weighted |
| Token set (Jaccard) | 0.20 | Shared words regardless of order |
| Token containment | 0.20 | Shortened trade names, added qualifiers |
| Levenshtein ratio | 0.15 | Character-level edits |
| Skeleton | 0.10 | Transliteration; dropped name parts via containment |

Jaro-Winkler and Levenshtein are each computed twice — once on the ordered
normalized string and once on the token-sorted string — and the better result
is kept. Without that, "PETROV, Vasiliy Ivanovich" and "Vasiliy Ivanovich
Petrov" score like unrelated strings.

Weights sum to 1.0. Changing any of them changes every historical score, so
bump `SCHEMA_VERSION` in `models.py` at the same time or your audit trail
starts comparing incomparable numbers.

### Bands

Rule-based, first match wins:

1. `exact_normalized` → **EXACT**
2. `exact_reordered` (same token multiset, different order) → **EXACT**
3. Either name under 4 folded characters → **NONE** (exact only)
4. Acronym relationship resolves → **STRONG**
5. Full token containment plus skeleton equality → **STRONG**
6. Full skeleton containment with ≥2 skeleton tokens → **STRONG**
7. score ≥ 0.90 → **STRONG**; ≥ 0.78 → **WEAK**; else **NONE**

Rule 6 is the dropped-name-part case: "Vasiliy Petroff" against "PETROV,
Vasiliy Ivanovich". Every skeleton token of the shorter name is present in the
longer one. The two-token floor stops generic single words from firing it.

### The early exit, and why it is provable

Set-based signals are computed first; the string metrics are the expensive
part. If

```
w_jw*1 + w_ts*ts + w_cont*cont + w_lev*1 + w_skel*skel_containment  <  WEAK_FLOOR
```

the pair cannot band on score, because both string metrics are bounded by 1.0.
But three band rules bypass the score entirely, so each independently
suppresses the exit: an acronym relationship, full token containment, or full
skeleton containment with two or more tokens.

That last condition is not decoration. The first version of this optimization
omitted it, and the brute-force equivalence test in `test_match.py` caught it
immediately: full skeleton containment contributes only 0.10 to the ceiling but
is worth STRONG on its own, so "PETROV, Vasily Ivanovic" against "PETROV,
Vasiliy Ivanovich" silently dropped from STRONG to NONE. The test scores every
fixture pair with and without the exit and asserts the bands agree. Keep it.

Measured effect: ~21 ms per subject against a 25,000-name index, so a
10,000-party book screens in roughly 3.5 minutes on one core.

**That figure covers the deterministic layer only** — blocking, scoring,
banding and the rules engine. It says nothing about wall-clock for a run with
adjudication enabled, which is dominated by model latency: cases are processed
sequentially, and each case with a candidate costs one adjudication plus one
critic call, up to three retries each. On a book where most parties are clear
this barely matters, because a party with no candidate never reaches a model.
On a book with hundreds of hits it dominates completely. Size the run by the
number of *candidates*, not the number of parties.

## Deliberate non-behaviours

**Geography never demotes a band.** A German-addressed subject can absolutely
be the SDN listed at a Moscow address — list addresses are sparse and often
historical. `country_evidence` (`agrees` / `differs` / `insufficient`) is
recorded for the adjudicator and is never allowed to clear a name hit.

**Short names match only exactly.** Fuzzy-matching 2–3 character strings
generates noise that buries real hits.

**No score is a clear.** A subject with any candidate above the review floor
cannot reach CLEAR, whatever the model says downstream.

## Tuning, and its asymmetry

The floors are set for recall. Before moving them:

1. **Measure on your own diff**, ideally against a parallel run of the
   incumbent tool. Both tools draw the fuzzy line differently; the disagreements
   are the data.
2. **Raising `WEAK_FLOOR` trades a cheap error for an expensive one.** Fewer
   rows to read, more chance of a missed hit under strict liability.
3. **Prefer fixing normalization to raising thresholds.** If a class of false
   positives comes from an unhandled corporate suffix, add the suffix. That
   fixes the cause without costing recall anywhere else.
4. **Record every change**: the value, the date, the evidence, the person. A
   threshold nobody can justify is a finding in your next audit.

## Known limitations

- **Non-Latin scripts.** Names are folded to Latin; native-script Chinese,
  Arabic, Cyrillic and Japanese names in a customer master will not match Latin
  list entries. Transliterate on the way in.
- **Phonetic matching is skeleton-based, not Soundex/Metaphone.** Those are
  tuned for English and mislead on transliterated Arabic and Chinese names.
  The skeleton is cruder and less English-biased.
- **Individual names are harder than entities.** Patronymics, honorifics,
  maternal surnames and name order vary by culture. Expect more UNCERTAIN
  adjudications on individuals; that is the system working.
- **Vessels and aircraft** are matched on name only. IMO numbers and call signs
  are captured but not used as match keys.
- **No fuzzy address matching.** Addresses inform the adjudicator; they do not
  generate candidates.
