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

Output of `python3 -m xscreen.bench.run --seed 7 --size 5000`, engine 1.1.0,
tuning digest `2003aab90f44`, corpus digest `829e1ed9d5fc`, run 2026-09-02.
Index: 5000 targets + 1500 decoys = 6854 entries. 70,625 perturbed positives
and 5,000 negatives screened.

### Recall by perturbation class

| class | n | >=EXACT | >=STRONG | >=WEAK | missed | at blocking | at scoring |
|---|---:|---:|---:|---:|---:|---:|---:|
| identity | 5000 | 100.0% | 100.0% | 100.0% | 0 | 0 | 0 |
| legal_form_swap | 2737 | 61.8% | 93.0% | 97.0% | 82 | 0 | 82 |
| token_reorder | 1771 | 100.0% | 100.0% | 100.0% | 0 | 0 | 0 |
| translit_drift | 4985 | 0.9% | 79.0% | 84.5% | 770 | 6 | 764 |
| diacritics_toggle | 5000 | 100.0% | 100.0% | 100.0% | 0 | 0 | 0 |
| typo_substitution | 5000 | 0.2% | 15.6% | 54.6% | 2272 | 9 | 2263 |
| typo_transposition | 4998 | 0.0% | 64.8% | 81.0% | 952 | 1 | 951 |
| typo_deletion | 5000 | 0.8% | 49.8% | 73.8% | 1309 | 3 | 1306 |
| dropped_middle | 731 | 0.0% | 100.0% | 100.0% | 0 | 0 | 0 |
| truncated_name | 3229 | 0.2% | 100.0% | 100.0% | 0 | 0 | 0 |
| added_qualifier | 5000 | 0.0% | 100.0% | 100.0% | 0 | 0 | 0 |
| acronym | 1838 | 0.0% | 66.3% | 66.3% | 619 | 619 | 0 |
| ocr_space_insertion | 4982 | 1.7% | 6.4% | 21.5% | 3912 | 7 | 3905 |
| missing_space | 5000 | 0.0% | 0.4% | 3.9% | 4804 | 2127 | 2677 |
| weak_alias | 354 | 100.0% | 100.0% | 100.0% | 0 | 0 | 0 |
| punctuation_noise | 5000 | 100.0% | 100.0% | 100.0% | 0 | 0 | 0 |
| internal_apostrophe | 5000 | 0.0% | 5.2% | 20.9% | 3957 | 8 | 3949 |
| stacked_pair | 5000 | 0.1% | 23.0% | 26.3% | 3686 | 749 | 2937 |
| **overall (micro)** | 70625 | 26.9% | 59.5% | 68.3% | | | |

Macro-averaged recall at >=WEAK across classes (identity excluded): **72.3%**.

### False-positive rate on negatives

| negative class | n | FP @>=WEAK | FP @>=STRONG | FP @EXACT |
|---|---:|---:|---:|---:|
| unrelated | 1978 | 4.1% | 1.7% | 0.0% |
| near_miss_common_words | 966 | 5.2% | 3.4% | 0.0% |
| near_miss_shared_name_part | 1027 | 11.7% | 1.7% | 0.0% |
| near_miss_shared_industry | 1029 | 9.0% | 2.8% | 0.0% |
| **overall** | 5000 | 6.9% | 2.2% | 0.0% |

### Candidates per subject

| subjects | mean | p50 | p90 | p99 | max | 0 | 1 | 2-5 | 6-20 | 21+ |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| positives | 1.066 | 1 | 1 | 10 | 97 | 21978 | 44697 | 3013 | 331 | 606 |
| negatives | 0.176 | 0 | 0 | 3 | 122 | 4656 | 254 | 72 | 15 | 3 |

The 21+ bucket is almost entirely `weak_alias` subjects: "The Engineer" is
the weak aka of dozens of generated individuals, and every one of them is
returned EXACT. That is correct behaviour for a weak alias and the reason
weak-alias hits are barred from auto-confirming.

### Timing

One core, index build 0.27 s; 75,625 subjects in 170 s; per subject mean
2.3 ms, p50 1.0 ms, p95 7.9 ms, max 148 ms. Not part of the determinism
contract; it is in the JSON under `timing` and stripped for comparison.

## Known weaknesses, from the per-class results

Read these before tuning anything. They are ordered by how much recall is on
the table.

1. **A name with two tokens cannot survive an edit in one of them.**
   `typo_substitution` is 54.6% at >=WEAK, `typo_deletion` 73.8%,
   `typo_transposition` 81.0%; on vessels (typically two tokens) substitution
   is 33%. Nearly every miss is at *scoring*, not blocking: with one of two
   tokens changed, token-set (Jaccard 1/3) and containment (1/2) -- 40% of
   the weight -- collapse, and Jaro-Winkler plus Levenshtein on a
   14-character string cannot lift a 0.74 over the 0.78 floor.
   `Bockor Elektro OAO` does not find `Borkor Elektro OAO`. Longer names
   (three or more tokens) survive because the untouched tokens carry them.
   This is the single largest recall gap in the engine and a weights
   question, not a blocking one.

2. **No character-level blocking, so a missing space is a complete miss.**
   `missing_space` is 3.9%: `BorkorElektro` shares no token and no skeleton
   token with `Borkor Elektro`, so blocking never pulls the party in (2127
   of 4804 misses at blocking), and when a second token does pull it in the
   score is ~0.5. `ocr_space_insertion` (21.5%) is the mirror image: the
   split token matches nothing and the fragments hurt Jaccard. OCR'd bills of
   lading and pasted-from-PDF customer masters do exactly this.

3. **Internal apostrophes split the token** (`internal_apostrophe` 20.9%).
   `fold()` turns every punctuation mark into a space -- correct for
   "A.B.C." -- so `Sa'id` becomes the tokens `sa` and `id` and never
   matches `Said`. Arabic ayn/hamza (Sa'id, Qa'ida, Mu'assasat), Irish and
   Italian surnames (O'Brien, D'Angelo) are all written this way in real
   records. Engine finding, see below.

4. **Dotted and spaced initialisms never reach the acronym rule**
   (`acronym` 66.3%, every miss at blocking). `RRM` bands STRONG against
   "Roschai Radar Machinery", but `R.R.M.` and `R R M` return zero
   candidates: `block()` consults the acronym postings only for a token of
   three or more letters, and the dotted form folds to three one-letter
   tokens. The scoring rule (`is_acronym_of`) would accept them if blocking
   let them through. Engine finding, see below.

5. **Legal forms the engine does not know are name tokens.**
   `legal_form_swap` misses (3%) are all Gulf and Balkan forms absent from
   `CORPORATE_SUFFIXES` -- FZE, FZCO, WLL, SAL, Est., EOOD, OÜ -- on
   two-word names: `Al-Mukrir Contracting EOOD` does not find
   `Al-Mukrir Contracting FZE`. Arabic-style entities are at 88% versus
   ~100% for the other styles for this reason alone. A vocabulary fix.

6. **Dotted legal forms tokenize to single letters** -- the reason
   `legal_form_swap` is only 61.8% EXACT when `Ltd`→`LLC` is EXACT.
   `L.L.C.` folds to `l l c`, `S.p.A.` to `s p`, and those letters stay in
   the token stream as if they were name words. It costs a band on the true
   match (`Alpha Precision S.A.` is STRONG, not EXACT, against
   `Alpha Precision LLC`) and it *creates* false positives: two unrelated
   "... General Trading L.L.C." companies band WEAK on the shared `l l c`,
   and the same pair spelled "LLC" does not. Engine finding, see below.

7. **Transliteration drift that touches both tokens of a two-token name**
   is lost (`translit_drift` 84.5%; Cyrillic 79%, Arabic 80%). Same
   mechanism as (1). Single-token drift is caught by the skeleton at STRONG;
   two changes at once (`Burkor Ilektro`) are not. Note also that the
   skeleton keeps a leading vowel, so `Elektro`/`Ilektro` and
   `Osama`/`Usama`-shaped pairs have different skeletons.

8. **Stacking two perturbations** (`stacked_pair` 26.3%) mostly inherits
   the failures above; it is reported so a fix to one class can be checked
   for its effect on combinations.

On the precision side: the 2.2% STRONG false-positive rate on negatives is
almost entirely the consonant skeleton being coarse on vowel-heavy pinyin and
on the g/kh/q family -- `Zhiaxu` and `Jaoxue` both skeletonize to `jks`,
`Galfen` and `Khalfin` to `klfn` -- so a fresh name that happens to share a
skeleton with a listed one and shares its industry words bands STRONG through
skeleton containment. That is the documented recall-first trade-off of the
skeleton; the benchmark just puts a number on its cost. The 11.7% WEAK rate on
`near_miss_shared_name_part` is two of three tokens genuinely shared (same
given name and patronymic), which an analyst would likely want to see.

## Engine findings (reported, not fixed here)

Each reproduces in three lines against `ListIndex` / `screen_name`.

1. **Dotted or spaced initialisms are unreachable through blocking.**
   Index `Roschai Radar Machinery PJSC`; screen `RRM` → STRONG; screen
   `R.R.M.` or `R R M` → no candidates. `match.ListIndex.block()` only looks
   up `_acronym_postings` for tokens of length >= 3 and looks the subject's
   own initials up in `_token_postings` rather than `_acronym_postings`.
2. **An internal apostrophe splits a token.** Index `Said al-Harbi`; screen
   `Sa'id al-Harbi` → no candidates (ceiling 0.70, early exit). `names.fold`
   maps every non-word character to a space; an apostrophe between two
   letters should be deleted instead.
3. **Dotted legal forms leave single-letter tokens in the name.**
   `core_tokens("Alpha Precision L.L.C.")` is `('alpha','precision','l','l','c')`.
   Consequences above (weakness 6). Either strip legal forms before folding
   punctuation or fold single-letter tokens out of the suffix position.
4. **Gulf / Balkan legal forms missing from `CORPORATE_SUFFIXES`:** FZE,
   FZCO, FZ-LLC, WLL, SAL, Est., EOOD, OÜ (folds to `ou`).

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
