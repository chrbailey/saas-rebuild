"""Scale guard.

A screening engine that is correct but takes six hours to run a book of
business does not get run, and a control that does not get run is not a
control. This test is deliberately small enough to stay in the default suite;
it exists to catch an order-of-magnitude regression, not to benchmark.

The low-diversity corpus is adversarial on purpose: every listed name is drawn
from a tiny vocabulary, so token blocking has almost nothing to discriminate
on. Real list data is far kinder. If this case stays bounded, the real one
will.
"""

import random
import time
import unittest

from xscreen.match import ListIndex, screen_name
from xscreen.models import ListedParty, SubjectParty

WORDS_LOW = [f"Name{i}" for i in range(20)]
MID = ["Precision", "Heavy", "Marine", "Optics", "Trading", "Machinery"]
SUF = ["LLC", "Ltd", "GmbH", "OAO", "JSC", "Inc"]

# Generous ceiling: the measured figure on a modest core is ~30 ms even on the
# adversarial corpus. This trips only on a real regression, not on a slow CI
# machine.
MAX_MS_PER_SUBJECT = 250


def build(n: int, vocab: list[str], seed: int = 7) -> tuple[ListIndex, random.Random]:
    rng = random.Random(seed)
    idx = ListIndex()
    idx.add_all([
        ListedParty(uid=f"SDN:{i}", source="SDN", native_id=str(i),
                    name=f"{rng.choice(vocab)} {rng.choice(MID)} {rng.choice(SUF)}",
                    countries=["RU"])
        for i in range(n)
    ])
    return idx.build(), rng


class TestScale(unittest.TestCase):
    def test_adversarial_low_diversity_corpus_stays_bounded(self):
        idx, rng = build(8000, WORDS_LOW)
        subjects = [
            SubjectParty(ref=str(i), country="Germany",
                         name=f"{rng.choice(WORDS_LOW)} {rng.choice(MID)} {rng.choice(SUF)}")
            for i in range(40)
        ]
        t = time.time()
        for s in subjects:
            screen_name(s, idx)
        ms = (time.time() - t) / len(subjects) * 1000
        self.assertLess(ms, MAX_MS_PER_SUBJECT,
                        f"{ms:.0f} ms/subject on an 8k adversarial list -- "
                        "blocking or scoring has regressed")

    def test_realistic_diversity_is_much_faster(self):
        vocab = [f"Distinct{i}" for i in range(4000)]
        idx, rng = build(8000, vocab)
        subjects = [
            SubjectParty(ref=str(i), country="Germany",
                         name=f"{rng.choice(vocab)} {rng.choice(MID)} {rng.choice(SUF)}")
            for i in range(40)
        ]
        t = time.time()
        for s in subjects:
            screen_name(s, idx)
        ms = (time.time() - t) / len(subjects) * 1000
        self.assertLess(ms, MAX_MS_PER_SUBJECT)

    def test_index_build_is_linear_enough(self):
        t = time.time()
        build(8000, WORDS_LOW)
        self.assertLess(time.time() - t, 30.0)


if __name__ == "__main__":
    unittest.main()
