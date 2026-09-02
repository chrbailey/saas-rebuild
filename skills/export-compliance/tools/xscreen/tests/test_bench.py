"""Benchmark harness tests.

Four things are under test here, in order of how much they matter:

1. **Determinism.** The same seed and size must produce byte-identical
   metrics. The whole point of the harness is that a reader can re-run it
   and get the README's numbers; a benchmark that drifts is marketing.
2. **Recall floors per perturbation class.** Pinned at the values measured
   on this engine minus a margin, so they trip on a regression and not on
   the next small tuning change. The measured values are recorded next to
   each pin -- when you change the matcher, re-measure and move the pin
   *with evidence*.
3. **False-positive ceilings.** Recall bought by flagging everything is not
   recall.
4. **The harness itself runs end-to-end fast** at a size small enough for
   the default suite, and the `--baseline` mode fails when it should.

Measured on engine 1.3.0 (seed 7, size 400, negatives 400, 2026-09-02).
Engine 1.1.0 values are kept in the right-hand column so the effect of the
1.2.0/1.3.0 matcher changes (compact key, apostrophes, dotted forms, extra
legal forms, acronym blocking) stays on the record:

    class                  n    >=EXACT  >=STRONG  >=WEAK   (1.1.0 >=WEAK)
    identity             400    100.0%    100.0%   100.0%   100.0%
    legal_form_swap      217     80.7%     99.1%    99.5%    97.2%
    token_reorder        145    100.0%    100.0%   100.0%   100.0%
    translit_drift       398      1.0%     77.9%    82.9%    83.2%
    diacritics_toggle    400    100.0%    100.0%   100.0%   100.0%
    typo_substitution    400      0.0%     14.8%    50.7%    53.8%
    typo_transposition   400      0.0%     66.8%    80.8%    81.8%
    typo_deletion        400      1.5%     50.0%    74.8%    75.8%
    dropped_middle        66      0.0%    100.0%   100.0%   100.0%
    truncated_name       255      5.5%    100.0%   100.0%   100.0%
    added_qualifier      400      0.0%    100.0%   100.0%   100.0%
    acronym              133      0.0%    100.0%   100.0%    61.9%
    ocr_space_insertion  398      1.5%     94.5%    95.0%    23.9%
    missing_space        400      0.0%     87.0%    88.8%     5.0%
    weak_alias            26    100.0%    100.0%   100.0%   100.0%
    punctuation_noise    400    100.0%    100.0%   100.0%   100.0%
    internal_apostrophe  400    100.0%    100.0%   100.0%    22.5%
    stacked_pair         400      0.0%     41.5%    45.2%    26.5%
    overall >=WEAK                                  86.7%    68.7%
    FP @>=WEAK 1.0%, @>=STRONG 0.25%, @EXACT 0.0%
"""

from __future__ import annotations

import functools
import json
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

from xscreen.bench.generate import NEGATIVE_CLASSES, generate_corpus
from xscreen.bench.perturb import CLASS_ORDER, PERTURBATIONS, perturb_all
from xscreen.bench.run import comparable, compare, main, run_benchmark, to_json, to_markdown
from xscreen.names import core_tokens

PIN_SEED = 7
PIN_SIZE = 400

# Floors at >=WEAK: measured value (above) minus a margin. Classes measured
# at 100% are pinned at 98% except identity, which must never miss.
RECALL_FLOORS_WEAK: dict[str, float] = {
    "identity": 1.00,             # measured 1.000
    "legal_form_swap": 0.94,      # measured 0.995
    "token_reorder": 0.98,        # measured 1.000
    "translit_drift": 0.78,       # measured 0.829
    "diacritics_toggle": 0.98,    # measured 1.000
    "typo_substitution": 0.45,    # measured 0.507
    "typo_transposition": 0.76,   # measured 0.808
    "typo_deletion": 0.70,        # measured 0.748
    "dropped_middle": 0.98,       # measured 1.000
    "truncated_name": 0.98,       # measured 1.000
    "added_qualifier": 0.98,      # measured 1.000
    "acronym": 0.98,              # measured 1.000
    "ocr_space_insertion": 0.90,  # measured 0.950
    "missing_space": 0.84,        # measured 0.888
    "weak_alias": 0.98,           # measured 1.000
    "punctuation_noise": 0.98,    # measured 1.000
    "internal_apostrophe": 0.98,  # measured 1.000
    "stacked_pair": 0.40,         # measured 0.452
}

# Floors at >=STRONG for the classes the band rules are *designed* to
# resolve without relying on the fuzzy score.
RECALL_FLOORS_STRONG: dict[str, float] = {
    "identity": 1.00,
    "token_reorder": 0.98,      # exact_reordered rule
    "dropped_middle": 0.98,     # skeleton-containment rule
    "truncated_name": 0.98,     # containment rules
    "added_qualifier": 0.98,    # containment rules
    "legal_form_swap": 0.94,    # measured 0.991 (dotted forms + Gulf/Balkan suffixes)
    "translit_drift": 0.72,     # measured 0.779
    "acronym": 0.98,            # measured 1.000 (acronym postings; dotted/spaced/noise-letter forms)
    "ocr_space_insertion": 0.90,  # measured 0.945 (compact-key rule)
    "missing_space": 0.82,      # measured 0.870 (compact-key rule)
    "internal_apostrophe": 0.98,  # measured 1.000 (inner apostrophe is elision)
}

OVERALL_FLOOR_WEAK = 0.82       # measured 0.867
FP_CEILING_WEAK = 0.06          # measured 0.010
FP_CEILING_STRONG = 0.02        # measured 0.0025
FP_CEILING_EXACT = 0.005        # measured 0.000


@functools.lru_cache(maxsize=None)
def pinned_run() -> dict:
    return run_benchmark(seed=PIN_SEED, size=PIN_SIZE)


class TestDeterminism(unittest.TestCase):
    def test_same_seed_same_metrics(self):
        a = run_benchmark(seed=11, size=120)
        b = run_benchmark(seed=11, size=120)
        self.assertEqual(to_json(comparable(a)), to_json(comparable(b)))
        # Timing is the one section allowed to differ.
        self.assertIn("timing", a)

    def test_different_seed_different_corpus(self):
        a = generate_corpus(1, 50)
        b = generate_corpus(2, 50)
        self.assertNotEqual([p.name for p in a.targets], [p.name for p in b.targets])

    def test_corpus_generation_is_deterministic(self):
        a = generate_corpus(3, 200)
        b = generate_corpus(3, 200)
        self.assertEqual([p.name for p in a.listed()], [p.name for p in b.listed()])
        self.assertEqual([n.name for n in a.negatives], [n.name for n in b.negatives])

    def test_perturbation_is_deterministic(self):
        c = generate_corpus(5, 60)
        self.assertEqual([p.name for p in perturb_all(c.targets, 5)],
                         [p.name for p in perturb_all(c.targets, 5)])

    def test_json_keys_are_sorted(self):
        js = to_json(comparable(run_benchmark(seed=1, size=20)))
        parsed = json.loads(js)
        self.assertEqual(js, json.dumps(parsed, sort_keys=True, indent=2, ensure_ascii=False) + "\n")


class TestHarnessRuns(unittest.TestCase):
    def test_end_to_end_small_is_fast(self):
        t = time.perf_counter()
        r = run_benchmark(seed=3, size=120)
        elapsed = time.perf_counter() - t
        self.assertLess(elapsed, 8.0, f"size-120 benchmark took {elapsed:.1f}s")
        self.assertEqual(r["corpus"]["targets"], 120)
        self.assertGreater(r["corpus"]["positives_screened"], 120 * 10)
        self.assertEqual(set(r["recall"]["by_class"]), set(CLASS_ORDER))
        self.assertEqual(set(r["false_positives"]["by_class"]), set(NEGATIVE_CLASSES))
        md = to_markdown(r)
        self.assertIn("| identity |", md)
        self.assertIn("### False-positive rate", md)

    def test_every_class_applies_to_some_party(self):
        c = generate_corpus(7, 200)
        classes = {p.cls for p in perturb_all(c.targets, 7)}
        self.assertEqual(classes, set(CLASS_ORDER))

    def test_perturbations_change_the_name_except_identity(self):
        c = generate_corpus(9, 150)
        for p in perturb_all(c.targets, 9):
            if p.cls == "identity":
                self.assertEqual(p.name, p.listed_name)
            else:
                self.assertNotEqual(p.name, p.listed_name, f"{p.cls} returned the input unchanged")

    def test_each_perturbation_is_a_pure_function(self):
        import random
        c = generate_corpus(4, 40)
        for cls, p in PERTURBATIONS.items():
            for b in c.targets:
                r1 = p.fn(b.name, b, random.Random(99))
                r2 = p.fn(b.name, b, random.Random(99))
                self.assertEqual(r1, r2, f"{cls} is not deterministic for {b.name!r}")

    def test_negatives_share_no_distinctive_token_with_the_index(self):
        c = generate_corpus(7, 300)
        vocab = c.distinctive_vocab()
        listed_norms = {" ".join(core_tokens(p.name)) for p in c.listed()}
        for n in c.negatives:
            toks = set(core_tokens(n.name))
            self.assertFalse(toks & vocab, f"negative {n.name!r} ({n.cls}) shares {toks & vocab}")
            self.assertNotIn(" ".join(core_tokens(n.name)), listed_norms)

    def test_decoys_are_built_from_generic_words(self):
        from xscreen.bench.generate import COMMON_WORDS, ENTITY_WORDS
        # Through core_tokens, because "Trading" and "International" carry
        # word equivalences (trade, intl) that a bare fold does not apply.
        generic: set[str] = set()
        for w in COMMON_WORDS + ENTITY_WORDS:
            generic.update(core_tokens(w))
        c = generate_corpus(7, 200)
        for d in c.decoys:
            toks = set(core_tokens(d.base))
            self.assertTrue(toks & generic, d.name)

    def test_module_is_runnable_as_a_command(self):
        tools = Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "r.json"
            proc = subprocess.run(
                [sys.executable, "-m", "xscreen.bench.run", "--seed", "7", "--size", "30",
                 "--json", str(out), "--quiet"],
                cwd=tools, capture_output=True, text=True, timeout=120,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertNotIn("RuntimeWarning", proc.stderr)
            data = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(data["benchmark"]["seed"], 7)
            self.assertEqual(data["benchmark"]["size"], 30)


class TestRecallFloors(unittest.TestCase):
    """Regression tripwires. See the module docstring for the measurements."""

    def test_per_class_recall_at_weak(self):
        by_class = pinned_run()["recall"]["by_class"]
        self.assertEqual(set(by_class), set(RECALL_FLOORS_WEAK), "class set changed; re-pin")
        failures = []
        for cls, floor in RECALL_FLOORS_WEAK.items():
            got = by_class[cls]["recall_weak"]
            if got < floor:
                failures.append(f"{cls}: {got:.3f} < floor {floor:.2f}")
        self.assertFalse(failures, "recall regressed at >=WEAK:\n  " + "\n  ".join(failures))

    def test_per_class_recall_at_strong(self):
        by_class = pinned_run()["recall"]["by_class"]
        failures = []
        for cls, floor in RECALL_FLOORS_STRONG.items():
            got = by_class[cls]["recall_strong"]
            if got < floor:
                failures.append(f"{cls}: {got:.3f} < floor {floor:.2f}")
        self.assertFalse(failures, "recall regressed at >=STRONG:\n  " + "\n  ".join(failures))

    def test_overall_recall(self):
        self.assertGreaterEqual(pinned_run()["recall"]["overall"]["recall_weak"], OVERALL_FLOOR_WEAK)

    def test_identity_is_always_exact(self):
        r = pinned_run()["recall"]["by_class"]["identity"]
        self.assertEqual(r["recall_exact"], 1.0)
        self.assertEqual(r["missed"], 0)


class TestFalsePositiveCeilings(unittest.TestCase):
    def test_overall_fp_rate(self):
        fp = pinned_run()["false_positives"]["overall"]
        self.assertLessEqual(fp["fp_rate_weak"], FP_CEILING_WEAK, fp)
        self.assertLessEqual(fp["fp_rate_strong"], FP_CEILING_STRONG, fp)
        self.assertLessEqual(fp["fp_rate_exact"], FP_CEILING_EXACT, fp)

    def test_unrelated_names_almost_never_flag(self):
        fp = pinned_run()["false_positives"]["by_class"]["unrelated"]
        self.assertLessEqual(fp["fp_rate_weak"], 0.03, fp)   # measured 0.006
        self.assertEqual(fp["fp_strong"], 0, fp)


class TestBaselineCompare(unittest.TestCase):
    def _result(self):
        return run_benchmark(seed=2, size=60)

    def test_identical_runs_pass(self):
        r = self._result()
        report, code = compare(r, r, tolerance=0.01)
        self.assertEqual(code, 0, report)
        self.assertIn("OK", report)

    def test_regression_beyond_tolerance_fails(self):
        cur = self._result()
        base = json.loads(to_json(cur))
        base["recall"]["by_class"]["typo_deletion"]["recall_weak"] += 0.10
        report, code = compare(cur, base, tolerance=0.01)
        self.assertEqual(code, 1, report)
        self.assertIn("typo_deletion", report)
        self.assertIn("REGRESSED", report)

    def test_regression_within_tolerance_passes(self):
        cur = self._result()
        base = json.loads(to_json(cur))
        base["recall"]["by_class"]["typo_deletion"]["recall_weak"] += 0.005
        _, code = compare(cur, base, tolerance=0.01)
        self.assertEqual(code, 0)

    def test_missing_class_is_a_regression(self):
        cur = self._result()
        base = json.loads(to_json(cur))
        base["recall"]["by_class"]["phantom_class"] = dict(base["recall"]["by_class"]["identity"])
        _, code = compare(cur, base)
        self.assertEqual(code, 1)

    def test_mismatched_configuration_is_not_compared(self):
        cur = self._result()
        base = json.loads(to_json(cur))
        base["benchmark"]["size"] = 61
        report, code = compare(cur, base)
        self.assertEqual(code, 2)
        self.assertIn("NOT COMPARABLE", report)

    def test_cli_baseline_exit_codes(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td) / "base.json"
            self.assertEqual(main(["--seed", "2", "--size", "40", "--json", str(base), "--quiet"]), 0)
            self.assertEqual(main(["--seed", "2", "--size", "40", "--baseline", str(base), "--quiet"]), 0)
            data = json.loads(base.read_text(encoding="utf-8"))
            data["recall"]["by_class"]["translit_drift"]["recall_weak"] = 1.0
            base.write_text(json.dumps(data), encoding="utf-8")
            self.assertEqual(main(["--seed", "2", "--size", "40", "--baseline", str(base), "--quiet"]), 1)


if __name__ == "__main__":
    unittest.main()
