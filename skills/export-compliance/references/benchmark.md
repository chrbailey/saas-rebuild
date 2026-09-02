# Matcher Benchmark

Every recall figure this project states about its matcher comes from a
command you can run yourself. This document says what that command measures,
what it deliberately does not measure, and what the current numbers are.

```
cd skills/export-compliance/tools
python3 -m xscreen.bench.run --seed 7 --size 5000
```

Standard library only. About three minutes on one core at size 5000; about
three seconds at `--size 400`, which is what the test suite pins.

## What it measures

A **synthetic** list of `--size` parties -- entities, individuals and vessels,
with names composed from syllable pools in four transliteration styles (Latin,
romanized Cyrillic, romanized Arabic, romanized CJK) -- plus 30% decoy parties
built from the words every trading company shares ("International", "Group",
"General Trading"). Every name is generated from a `random.Random(seed)`;
the same seed and size give the same corpus on any machine.

For each listed party the harness applies every applicable **perturbation** --
a documented way an ERP counterparty record mangles a listed name -- and
screens the result against the index. Recall for a class is the fraction of
those subjects for which the true party came back at or above a band
(EXACT / STRONG / WEAK). The classes:

| class | the record it imitates |
|---|---|
| identity | verbatim copy of the listed name (harness sanity check; must be 100% EXACT) |
| legal_form_swap | LLC on the list, GmbH / FZE / Co., Ltd. on the invoice |
| token_reorder | "Surname, Given Patronymic" vs "Given Patronymic Surname"; CJK surname-first vs Western order |
| translit_drift | kh/q/g, ch/tch, sh/sch, -ov/-off, vowel drift between transliteration systems |
| diacritics_toggle | accents the list carries and the ERP strips, or vice versa |
| typo_substitution / typo_transposition / typo_deletion | one interior-character error |
| dropped_middle | individual without middle name or patronymic |
| truncated_name | entity or vessel with its last name word dropped |
| added_qualifier | "... Dubai Branch", "Mr. ...", "MV ..." |
| acronym | initialism of a 3+ token entity name (RRM / R.R.M. / R R M) |
| ocr_space_insertion | OCR splits a token: "Velm ora" |
| missing_space | two tokens run together: "VelmoraPrecision" |
| weak_alias | the record carries only the party's generic weak aka ("The Engineer", "Abu ...") |
| punctuation_noise | commas, hyphens, quotes, parentheses, trailing dots, slashes |
| internal_apostrophe | apostrophe inside a token: Sa'id, O'Brien |
| stacked_pair | two of the above applied in sequence |

Each miss is attributed to the stage that lost it: **blocking** (the true
party was never pulled into scoring -- no weight change can recover it) or
**scoring** (it was scored and fell below the WEAK floor -- a weights or
threshold question).

It also screens `--size` **true negatives** -- names that share no distinctive
token with anything in the index -- and reports how often they come back at
each band. Four negative classes: `unrelated` (nothing in common but generic
words), `near_miss_common_words` (a fresh name around the same "Trading
International" words as a listed party), `near_miss_shared_name_part`
(same given name and patronymic, different surname), and
`near_miss_shared_industry` (same industry words, different proper name).

Also reported: candidates returned per subject (a recall figure bought with
40 candidates per row is not a recall figure) and wall-clock per subject.

## What it does NOT measure

- **Real-world recall.** The corpus is synthetic. No real sanctioned name is
  in any pool, and the distribution of name shapes, token frequencies and
  alias counts is a guess at reality, not a sample of it. A number here is a
  statement about the matcher's behaviour under a *named* perturbation, not a
  prediction of what fraction of OFAC hits a customer file will surface.
- **List aliases.** Listed parties carry only a primary name (and a weak
  alias for 20% of individuals). Real lists carry several transliteration
  variants per party, which raises recall on `translit_drift` and
  `token_reorder` in practice. The benchmark measures the engine, not the
  list's generosity.
- **Adjudication.** Nothing after `match.py`. The LLM adjudicator and the
  critic loop are out of scope; this is candidate generation only.
- **Ground truth for ambiguous negatives.** A negative one edit away from a
  listed name is not included, because whether it *should* match is a policy
  question rather than a measurement.

The pinned floors in `tests/test_bench.py` are regression tripwires, not
targets. When you change the matcher, re-run, read the per-class deltas
(`--baseline previous.json` prints them and exits non-zero on a regression
beyond `--tolerance`), and move the pins with the evidence in the commit.

## Current scorecard

Output of `python3 -m xscreen.bench.run --seed 7 --size 5000`, engine 1.3.0,
tuning digest `3bfa807b9d74`, corpus digest `829e1ed9d5fc`, run 2026-09-02.
Index: 5000 targets + 1500 decoys = 6854 entries. 70,455 perturbed positives
and 5,000 negatives screened. (The positive count differs from the 1.1.0 run
below because the generator derives perturbations from the engine's own
tokenization, which changed.)

### Recall by perturbation class

| class | n | >=EXACT | >=STRONG | >=WEAK | missed | at blocking | at scoring |
|---|---:|---:|---:|---:|---:|---:|---:|
| identity | 5000 | 100.0% | 100.0% | 100.0% | 0 | 0 | 0 |
| legal_form_swap | 2737 | 81.4% | 99.5% | 99.7% | 7 | 0 | 7 |
| token_reorder | 1771 | 100.0% | 100.0% | 100.0% | 0 | 0 | 0 |
| translit_drift | 4985 | 0.8% | 79.4% | 84.0% | 797 | 8 | 789 |
| diacritics_toggle | 5000 | 100.0% | 100.0% | 100.0% | 0 | 0 | 0 |
| typo_substitution | 5000 | 0.2% | 16.0% | 51.7% | 2415 | 11 | 2404 |
| typo_transposition | 4998 | 0.0% | 65.2% | 79.4% | 1030 | 3 | 1027 |
| typo_deletion | 5000 | 0.8% | 50.4% | 72.2% | 1392 | 4 | 1388 |
| dropped_middle | 731 | 0.0% | 100.0% | 100.0% | 0 | 0 | 0 |
| truncated_name | 3229 | 6.0% | 100.0% | 100.0% | 0 | 0 | 0 |
| added_qualifier | 5000 | 0.0% | 100.0% | 100.0% | 0 | 0 | 0 |
| acronym | 1668 | 0.0% | 99.9% | 99.9% | 1 | 1 | 0 |
| ocr_space_insertion | 4982 | 2.0% | 93.9% | 94.9% | 252 | 1 | 251 |
| missing_space | 5000 | 0.0% | 87.8% | 89.2% | 538 | 152 | 386 |
| weak_alias | 354 | 100.0% | 100.0% | 100.0% | 0 | 0 | 0 |
| punctuation_noise | 5000 | 100.0% | 100.0% | 100.0% | 0 | 0 | 0 |
| internal_apostrophe | 5000 | 100.0% | 100.0% | 100.0% | 0 | 0 | 0 |
| stacked_pair | 5000 | 0.2% | 37.3% | 40.3% | 2985 | 739 | 2246 |
| **overall (micro)** | 70455 | 35.1% | 80.8% | 86.6% | | | |

Macro-averaged recall at >=WEAK across classes (identity excluded): **88.9%**.

Macro-averaged recall at >=WEAK across classes (identity excluded): **88.9%**.

### False-positive rate on negatives

| negative class | n | FP @>=WEAK | FP @>=STRONG | FP @EXACT |
|---|---:|---:|---:|---:|
| unrelated | 1978 | 2.9% | 1.8% | 0.0% |
| near_miss_common_words | 966 | 5.3% | 4.5% | 0.0% |
| near_miss_shared_name_part | 1027 | 11.5% | 1.6% | 0.0% |
| near_miss_shared_industry | 1029 | 6.8% | 2.8% | 0.0% |
| **overall** | 5000 | 5.9% | 2.5% | 0.0% |

### Candidates per subject

| subjects | mean | p50 | p90 | p99 | max | 0 | 1 | 2-5 | 6-20 | 21+ |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| positives | 1.268 | 1 | 1 | 16 | 49 | 9321 | 56834 | 3219 | 489 | 592 |
| negatives | 0.084 | 0 | 0 | 1 | 25 | 4703 | 265 | 28 | 3 | 1 |

The 21+ bucket is almost entirely `weak_alias` subjects: "The Engineer" is
the weak aka of dozens of generated individuals, and every one of them is
returned EXACT. That is correct behaviour for a weak alias and the reason
weak-alias hits are barred from auto-confirming.

### Timing

One core, index build 0.30 s; 75,455 subjects in 179 s; per subject mean
2.4 ms, p50 0.9 ms, p95 8.6 ms, max 158 ms. Not part of the determinism
contract; it is in the JSON under `timing` and stripped for comparison.

### What changed between engine versions

The harness was written against engine 1.1.0 and the first scorecard it
produced named the four defects fixed in 1.2.0 and 1.3.0. Same seed and
size; >=WEAK recall per class:

| class | 1.1.0 | 1.2.0 | 1.3.0 | what moved it |
|---|---:|---:|---:|---|
| missing_space | 3.9% | 89.6% | 89.2% | compact (whitespace-stripped) blocking key and band rule |
| ocr_space_insertion | 21.5% | 94.8% | 94.9% | same |
| internal_apostrophe | 20.9% | 94.9% | 100.0% | compact key, then inner apostrophe folded as elision (EXACT) |
| acronym | 66.3% | 66.3% | 99.9% | dotted/spaced initialisms and noise-letter initials reach blocking |
| legal_form_swap | 97.0% | 97.0% | 99.7% | dotted legal forms rejoin; Gulf/Balkan/Baltic forms added |
| stacked_pair | 26.3% | 40.3% | 40.3% | inherits the above |
| typo_substitution | 54.6% | 54.8% | 51.7% | unchanged mechanism; class membership shifted with tokenization |
| **macro (ex. identity)** | **72.3%** | **86.9%** | **88.9%** | |
| FP @>=WEAK / @>=STRONG | 6.9% / 2.2% | 6.9% / 2.3% | 5.9% / 2.5% | dotted-LLC false positives gone; skeleton collisions unchanged |

## Known weaknesses, from the per-class results

Read these before tuning anything. They are ordered by how much recall is on
the table.

1. **A name with two tokens cannot survive an edit in one of them.**
   `typo_substitution` is 51.7% at >=WEAK, `typo_deletion` 72.2%,
   `typo_transposition` 79.4%; on vessels (typically two tokens) substitution
   is worst. Nearly every miss is at *scoring*, not blocking: with one of two
   tokens changed, token-set (Jaccard 1/3) and containment (1/2) -- 40% of
   the weight -- collapse, and Jaro-Winkler plus Levenshtein on a
   14-character string cannot lift a 0.74 over the 0.78 floor.
   `Bockor Elektro OAO` does not find `Borkor Elektro OAO`. Longer names
   (three or more tokens) survive because the untouched tokens carry them.
   This is the single largest recall gap in the engine and a weights
   question, not a blocking one.

2. **Transliteration drift that touches both tokens of a two-token name**
   is lost (`translit_drift` 84.0%; Cyrillic and Arabic lowest). Same
   mechanism as (1). Single-token drift is caught by the skeleton at STRONG;
   two changes at once (`Burkor Ilektro`) are not. Note also that the
   skeleton keeps a leading vowel, so `Elektro`/`Ilektro` and
   `Osama`/`Usama`-shaped pairs have different skeletons.

3. **A missing space still loses ~11%** (`missing_space` 89.2%): the
   compact key catches equality, but a squashed name that also carries a
   second edit, or whose squashed form is under `COMPACT_MIN_CHARS`, has no
   character-level blocking to fall back on. 152 of the 538 misses are at
   blocking.

4. **Stacking two perturbations** (`stacked_pair` 40.3%) mostly inherits
   (1) and (2); it is reported so a fix to one class can be checked for its
   effect on combinations.

On the precision side: the 2.5% STRONG false-positive rate on negatives is
almost entirely the consonant skeleton being coarse on vowel-heavy pinyin and
on the g/kh/q family -- `Zhiaxu` and `Jaoxue` both skeletonize to `jks`,
`Galfen` and `Khalfin` to `klfn` -- so a fresh name that happens to share a
skeleton with a listed one and shares its industry words bands STRONG through
skeleton containment. That is the documented recall-first trade-off of the
skeleton; the benchmark just puts a number on its cost. The 11.5% WEAK rate on
`near_miss_shared_name_part` is two of three tokens genuinely shared (same
given name and patronymic), which an analyst would likely want to see.

## Engine findings the benchmark surfaced (fixed)

Each was reported by the first run of this harness and fixed with a
regression test in `tests/test_match.py` / `tests/test_names.py`:

1. **Dotted or spaced initialisms were unreachable through blocking**
   (`R.R.M.`, `R R M` → no candidates; `RRM` → STRONG). `block()` now looks
   an all-single-letter query up as its joined initialism, taken from the
   folded letters so that `a` and `e` -- noise tokens elsewhere -- survive.
2. **An internal apostrophe split the token** (`Sa'id` → `sa id`, ceiling
   0.70, early exit). `fold()` deletes an apostrophe between two letters.
3. **Dotted legal forms left single-letter tokens in the name**
   (`L.L.C.` → `l l c`), costing a band on true matches and creating false
   positives between unrelated dotted-LLC companies. A run of single letters
   that spells a known suffix is rejoined at the token layer; `A.B.C.` still
   stays separate letters.
4. **Gulf, GCC, Balkan, Baltic and French legal forms** (FZE, FZCO, WLL,
   EOOD, UAB, SIA, SASU, EURL ...) were name tokens; they are suffixes now.

## Reading a baseline diff

```
python3 -m xscreen.bench.run --seed 7 --size 5000 --json before.json --quiet
# ... change the matcher ...
python3 -m xscreen.bench.run --seed 7 --size 5000 --baseline before.json --tolerance 0.01
```

The comparison table lists every class with its >=WEAK recall before and
after, the delta in percentage points, and the >=STRONG delta alongside.
Exit 1 if any class (or the overall figure) lost more than the tolerance;
exit 2 if the two runs used a different seed, size or negative count and
are not comparable at all. A rise in the false-positive rate is printed as a
warning, not a failure -- recall is the gate, by design, but the number is
there so the trade you made is on the record.
