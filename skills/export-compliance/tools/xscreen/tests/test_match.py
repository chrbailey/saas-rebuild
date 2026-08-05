import unittest
from pathlib import Path

from xscreen.match import ListIndex, assign_band, score_pair, screen_name
from xscreen.models import ListedParty, SubjectParty
from xscreen.normalize import merge_ofac, parse_csl, parse_ofac_add, parse_ofac_alt, parse_ofac_sdn

FIX = Path(__file__).parent / "fixtures"


def build_index() -> ListIndex:
    sdn = parse_ofac_sdn((FIX / "SDN.raw").read_text(encoding="utf-8"))
    sdn = merge_ofac(
        sdn,
        parse_ofac_alt((FIX / "SDN_ALT.raw").read_text(encoding="utf-8")),
        parse_ofac_add((FIX / "SDN_ADD.raw").read_text(encoding="utf-8")),
    )
    csl = parse_csl((FIX / "CSL.raw").read_text(encoding="utf-8"))
    idx = ListIndex()
    idx.add_all(sdn.parties)
    idx.add_all(csl.parties)
    return idx.build()


def bands(idx: ListIndex, name: str, **kw) -> dict[str, str]:
    subj = SubjectParty(ref="t", name=name, **kw)
    return {c.listed_uid: c.band for c in screen_name(subj, idx)}


class TestRecall(unittest.TestCase):
    """Every case here is a hit a naive exact-match screen would miss."""

    def setUp(self):
        self.idx = build_index()

    def test_exact_match(self):
        self.assertEqual(bands(self.idx, "NORTHWIND HEAVY MACHINERY OAO")["SDN:1001"], "EXACT")

    def test_corporate_form_swap_is_exact_after_normalization(self):
        # OAO vs JSC vs no suffix -- all the same party.
        for variant in ["Northwind Heavy Machinery", "Northwind Heavy Machinery JSC",
                        "Northwind Heavy Machinery, LLC"]:
            self.assertEqual(bands(self.idx, variant).get("SDN:1001"), "EXACT", variant)

    def test_transliteration_alias(self):
        b = bands(self.idx, "Nordvind Tyazheloe Mashinostroenie")
        self.assertEqual(b.get("SDN:1001"), "EXACT")

    def test_individual_name_reordered_and_respelled(self):
        # List: "PETROV, Vasiliy Ivanovich"; invoice: "Vasily Ivanovic Petrov"
        b = bands(self.idx, "Vasily Ivanovic Petrov")
        self.assertIn(b.get("SDN:1003"), ("EXACT", "STRONG"))

    def test_acronym_resolves(self):
        b = bands(self.idx, "ZPI")
        self.assertEqual(b.get("SDN:1004"), "EXACT")

    def test_shortened_trade_name_contained(self):
        b = bands(self.idx, "Al Farqad Trading")
        self.assertIn(b.get("SDN:1002"), ("EXACT", "STRONG"))

    def test_punctuation_and_case_noise(self):
        b = bands(self.idx, "al-farqad  TRADING company.")
        self.assertIn(b.get("SDN:1002"), ("EXACT", "STRONG"))

    def test_entity_list_alias_hit(self):
        b = bands(self.idx, "HSRI")
        self.assertIn(b.get("EL:EL-9001"), ("EXACT", "STRONG"))

    def test_subject_supplied_alias_is_screened(self):
        subj = SubjectParty(ref="t", name="Completely Unrelated Holdings",
                            aliases=["Zenith Precision Instruments Ltd"])
        got = {c.listed_uid: c.band for c in screen_name(subj, self.idx)}
        self.assertIn(got.get("SDN:1004"), ("EXACT", "STRONG"))


class TestPrecisionGuards(unittest.TestCase):
    def setUp(self):
        self.idx = build_index()

    def test_unrelated_name_does_not_match(self):
        self.assertEqual(bands(self.idx, "Sunny Day Bakery LLC"), {})

    def test_short_names_require_exact(self):
        # "SU" is in the fixture list. A different two-letter string must not
        # fuzzy-match it.
        self.assertNotIn("SDN:1006", bands(self.idx, "SA"))
        self.assertNotIn("SDN:1006", bands(self.idx, "SUN"))
        self.assertEqual(bands(self.idx, "SU").get("SDN:1006"), "EXACT")

    def test_generic_word_alone_does_not_pull_everything(self):
        # "Trading" and "Company" appear across the list; a name made only of
        # generic words must not match a specific listed party strongly.
        got = bands(self.idx, "Trading Company")
        self.assertNotIn("EXACT", got.values())

    def test_country_mismatch_does_not_demote(self):
        # Listed in RU; subject claims Germany. Still an exact name hit.
        b = bands(self.idx, "Northwind Heavy Machinery OAO", country="Germany")
        self.assertEqual(b.get("SDN:1001"), "EXACT")

    def test_country_signal_is_recorded(self):
        subj = SubjectParty(ref="t", name="Northwind Heavy Machinery OAO", country="Germany")
        cand = [c for c in screen_name(subj, self.idx) if c.listed_uid == "SDN:1001"][0]
        self.assertEqual(cand.signals["country_evidence"], "differs")


class TestScoring(unittest.TestCase):
    def test_score_bounded(self):
        idx = build_index()
        for entry in idx.entries:
            s, _ = score_pair("Acme Precision Machining", entry)
            self.assertGreaterEqual(s, 0.0)
            self.assertLessEqual(s, 1.0)

    def test_band_ordering_is_monotonic_in_score(self):
        idx = build_index()
        entry = [e for e in idx.entries if e.uid == "SDN:1001"][0]
        prev_rank = 4
        order = {"EXACT": 3, "STRONG": 2, "WEAK": 1, "NONE": 0}
        for name in ["Northwind Heavy Machinery OAO", "Northwind Heavy Machinry",
                     "Northwind Machinery", "Southgate Bakery Supplies"]:
            s, sig = score_pair(name, entry)
            rank = order[assign_band(s, sig, name, entry)]
            self.assertLessEqual(rank, prev_rank, name)
            prev_rank = rank


class TestDeterminism(unittest.TestCase):
    def test_same_input_same_output_including_order(self):
        idx = build_index()
        subj = SubjectParty(ref="t", name="Zenith Precision Instruments Limited",
                            country="Hong Kong")
        runs = [[(c.listed_uid, c.band, c.score) for c in screen_name(subj, idx)]
                for _ in range(5)]
        for r in runs[1:]:
            self.assertEqual(r, runs[0])

    def test_index_insertion_order_does_not_change_results(self):
        parties = [
            ListedParty(uid=f"SDN:{i}", source="SDN", native_id=str(i), name=n)
            for i, n in enumerate(
                ["Acme Precision Ltd", "Beacon Optics Inc", "Cormorant Shipping AG"], 1)
        ]
        a, b = ListIndex(), ListIndex()
        a.add_all(parties)
        b.add_all(list(reversed(parties)))
        subj = SubjectParty(ref="t", name="Acme Precision")
        self.assertEqual(
            [(c.listed_uid, c.band, c.score) for c in screen_name(subj, a.build())],
            [(c.listed_uid, c.band, c.score) for c in screen_name(subj, b.build())],
        )


class TestBlocking(unittest.TestCase):
    def test_blocking_does_not_lose_a_true_exact_match(self):
        """The safety property: whatever blocking discards must not contain
        a name that would have scored EXACT."""
        idx = build_index()
        for i, entry in enumerate(idx.entries):
            blocked = idx.block(entry.listed_name)
            self.assertIn(
                i, blocked.entries,
                f"blocking dropped an exact self-match for {entry.listed_name!r}",
            )

    def test_rarest_token_is_always_expanded_first(self):
        """The cap's safety rests on this: the rarest token never gets cut."""
        from xscreen.match import MAX_BLOCK_ENTRIES
        idx = ListIndex()
        # One rare name plus many sharing a common token.
        idx.add(ListedParty(uid="SDN:rare", source="SDN", native_id="r",
                            name="Xylophone Quarrying Zeppelin"))
        for i in range(50):
            idx.add(ListedParty(uid=f"SDN:{i}", source="SDN", native_id=str(i),
                                name=f"Quarrying Holdings Number{i}"))
        idx.build()
        blocked = idx.block("Xylophone Quarrying Zeppelin")
        self.assertIn(0, blocked.entries)

    def test_truncation_is_disclosed_on_the_candidates(self):
        from xscreen import match as m
        idx = ListIndex()
        for i in range(60):
            idx.add(ListedParty(uid=f"SDN:{i}", source="SDN", native_id=str(i),
                                name=f"Quarrying Zeppelin Number{i}"))
        idx.build()
        original = m.MAX_BLOCK_ENTRIES
        m.MAX_BLOCK_ENTRIES = 5
        try:
            blocked = idx.block("Quarrying Zeppelin Number3")
            self.assertTrue(blocked.truncated_tokens)
        finally:
            m.MAX_BLOCK_ENTRIES = original

    def test_empty_query_is_safe(self):
        idx = build_index()
        self.assertEqual(idx.block("").entries, set())
        self.assertEqual(idx.block("!!!").entries, set())
        self.assertEqual(screen_name(SubjectParty(ref="t", name="???"), idx), [])

    def test_early_exit_is_behaviour_preserving(self):
        """Brute force: the optimization must never change a band.

        Every fixture name is scored against every indexed name twice -- once
        with the early exit and once without -- and the bands must agree. This
        is the proof that the performance work did not quietly cost recall.
        """
        from xscreen.match import assign_band, score_pair
        idx = build_index()
        probes = [e.listed_name for e in idx.entries] + [
            "Sunny Day Bakery LLC", "Quarry Holdings", "Zebra Fund",
            "Vasiliy Petroff", "ZPI", "Northwind", "Trading Company",
            "Al Farqad", "Helios Semiconductor", "SU", "Boreal Optics Mfg Co",
        ]
        compared = 0
        for entry in idx.entries:
            for name in probes:
                fast_score, fast_sig = score_pair(name, entry, early_exit=True)
                slow_score, slow_sig = score_pair(name, entry, early_exit=False)
                self.assertEqual(
                    assign_band(fast_score, fast_sig, name, entry),
                    assign_band(slow_score, slow_sig, name, entry),
                    f"early exit changed the band for {name!r} vs {entry.listed_name!r}",
                )
                compared += 1
        self.assertGreater(compared, 300)

    def test_early_exit_only_fires_below_the_band_ceiling(self):
        from xscreen.match import WEAK_FLOOR, score_pair
        idx = build_index()
        fired = 0
        for entry in idx.entries:
            for name in ["Sunny Day Bakery LLC", "Zebra Fund", "Quarry Holdings"]:
                _, sig = score_pair(name, entry)
                if "below_band_ceiling" in sig:
                    fired += 1
                    self.assertLess(sig["below_band_ceiling"], WEAK_FLOOR)
        self.assertGreater(fired, 0, "early exit never fired; the test proves nothing")


if __name__ == "__main__":
    unittest.main()
