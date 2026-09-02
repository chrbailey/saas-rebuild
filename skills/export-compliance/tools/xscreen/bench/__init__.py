"""Reproducible recall / precision benchmark for the xscreen matcher.

Commercial screening vendors publish recall figures that nobody outside the
vendor can reproduce. This package exists so that every number the project
states about its matcher comes with a command anyone can run:

    cd skills/export-compliance/tools
    python3 -m xscreen.bench.run --seed 7 --size 5000

Three modules, standard library only:

* `generate`  -- a seeded synthetic corpus: listed parties in four
                 transliteration styles, decoys that share generic tokens,
                 and true-negative subjects that share *no* distinctive
                 token with anything in the list.
* `perturb`   -- the taxonomy of ways an ERP counterparty record mangles a
                 listed name (typos, transliteration drift, dropped
                 patronymic, acronyms, OCR spacing ...). Each is a pure
                 function labelled with its class.
* `run`       -- builds the index, screens every perturbed positive and
                 every negative, and reports recall per class per band,
                 false-positive rate, candidate volume and timing, as JSON
                 (stable key order) and Markdown. A `--baseline` mode diffs
                 two runs and fails when any class regresses.

What this benchmark measures is the matcher's behaviour on *synthetic*
names under *documented* perturbations. It says nothing about recall on a
real government list against a real book of business -- see
`references/benchmark.md` for the full list of what it does not claim.
"""

from .generate import Corpus, generate_corpus
from .perturb import PERTURBATIONS, PerturbedSubject, perturb_all

# `run_benchmark` lives in `xscreen.bench.run`; it is not re-exported here so
# that `python3 -m xscreen.bench.run` does not import the module twice.
__all__ = [
    "Corpus",
    "PERTURBATIONS",
    "PerturbedSubject",
    "generate_corpus",
    "perturb_all",
]
