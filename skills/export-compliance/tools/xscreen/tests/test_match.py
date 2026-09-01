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


class TestSingleTokenContainment(unittest.TestCase):
    """Regression: a shortened single-token trade name was a COMPLETE miss.

    `Gazprom` against `Gazprom Neft` had containment 1.0 and skeleton
    containment 1.0, but the two-token floor blocked both bypass rules and the
    residual score sat below the WEAK floor -- so nothing was reported at all,
    on exactly the case the containment metric exists to catch.
    """

    def _index(self, *names: str) -> ListIndex:
        idx = ListIndex()
        for i, n in enumerate(names):
            idx.add(ListedParty(uid=f"SDN:{i}", source="SDN", native_id=str(i), name=n))
        return idx.build()

    def test_shortened_trade_name_is_found(self):
        for short, full in [
            ("Gazprom", "Gazprom Neft"),
            ("Rosneft", "Rosneft Trading SA"),
            ("Acme", "Acme Precision Machining Corp"),
            ("Wagner", "Wagner Group PMC"),
        ]:
            idx = self._index(full)
            got = bands(idx, short)
            self.assertIn(got.get("SDN:0"), ("EXACT", "STRONG"),
                          f"{short!r} did not find {full!r}: {got}")

    def test_generic_word_does_not_fire_the_same_rule(self):
        # "Trading" is contained in every one of these, but it discriminates
        # nothing, so containment alone must not band it.
        idx = self._index(*[f"Company{i} Trading Corp" for i in range(60)])
        got = bands(idx, "Trading")
        self.assertEqual(got, {}, f"a generic single word matched: {got}")

    def test_discriminating_flag_reflects_token_rarity(self):
        from xscreen.match import discriminating
        from xscreen.names import core_tokens
        idx = self._index(*[f"Company{i} Trading Corp" for i in range(60)],
                          "Gazprom Neft")
        self.assertTrue(discriminating(idx, core_tokens("Gazprom"), core_tokens("Gazprom Neft")))
        self.assertFalse(discriminating(idx, core_tokens("Trading"),
                                        core_tokens("Company1 Trading Corp")))


class TestBlockingDisclosure(unittest.TestCase):
    """Regression: when truncation dropped the ONLY candidate, the per-candidate
    disclosure had nothing to attach to and the caller saw a clean empty result."""

    def test_truncation_is_reported_even_with_no_surviving_candidates(self):
        from xscreen import match as m
        idx = ListIndex()
        for i in range(60):
            idx.add(ListedParty(uid=f"SDN:{i}", source="SDN", native_id=str(i),
                                name=f"Quarrying Zeppelin Number{i}"))
        idx.build()
        original = m.MAX_BLOCK_ENTRIES
        m.MAX_BLOCK_ENTRIES = 1
        try:
            diags: dict = {}
            screen_name(SubjectParty(ref="t", name="Quarrying Zeppelin Widgetry"),
                        idx, diagnostics=diags)
            self.assertIn("blocking_truncated_tokens", diags,
                          "a bounded search was not disclosed to the caller")
        finally:
            m.MAX_BLOCK_ENTRIES = original

    def test_no_truncation_means_no_diagnostic_noise(self):
        idx = build_index()
        diags: dict = {}
        screen_name(SubjectParty(ref="t", name="Northwind Heavy Machinery OAO"),
                    idx, diagnostics=diags)
        self.assertEqual(diags, {})


class TestAcronymReachability(unittest.TestCase):
    """The acronym band rule must fire through the real pipeline.

    Blocking is token- and skeleton-based, and an initialism shares neither
    with its expansion -- so screen_name("IRGC") returned zero candidates
    against a list carrying only the expanded name, and the acronym rule was
    dead code except when the list itself carried the acronym as an alias
    (i.e. when it was already an exact match). The short-name gate also
    preceded the acronym rule, eating every 3-letter initialism.
    """

    @staticmethod
    def _idx(*names):
        idx = ListIndex()
        for i, n in enumerate(names, 1):
            idx.add(ListedParty(uid=f"SDN:{i}", source="SDN", native_id=str(i), name=n))
        return idx.build()

    def test_initialism_query_finds_the_expanded_listing(self):
        b = bands(self._idx("ISLAMIC REVOLUTIONARY GUARD CORPS"), "IRGC")
        self.assertEqual(b.get("SDN:1"), "STRONG")

    def test_three_letter_initialism_survives_the_short_name_gate(self):
        b = bands(self._idx("Kuznetsov Machine Zavod"), "KMZ")
        self.assertEqual(b.get("SDN:1"), "STRONG")

    def test_expanded_query_finds_a_listed_acronym(self):
        b = bands(self._idx("KMZ"), "Kuznetsov Machine Zavod")
        self.assertEqual(b.get("SDN:1"), "STRONG")

    def test_two_letter_initials_do_not_band(self):
        self.assertEqual(bands(self._idx("General Electric"), "GE"), {})


class TestTransliterationRecall(unittest.TestCase):
    """Consonant families the skeleton claimed to unite but did not."""

    @staticmethod
    def _idx(name):
        idx = ListIndex()
        idx.add(ListedParty(uid="SDN:1", source="SDN", native_id="1", name=name))
        return idx.build()

    def test_qaf_family_is_found(self):
        for q in ("Muammar Gaddafi", "Muammar Kaddafi", "Muammar Qaddafi"):
            b = bands(self._idx("QADHAFI, Muammar"), q)
            self.assertIn("SDN:1", b, q)

    def test_tch_variant_is_found(self):
        self.assertIn("SDN:1", bands(self._idx("CHERNOV, Andrei"), "Andrey Tchernov"))

    def test_q_gh_variant_is_found(self):
        self.assertIn("SDN:1",
                      bands(self._idx("MOHAMMAD REZA GHASEMI"), "Muhammed Riza Qasemi"))


class TestSuffixInflation(unittest.TestCase):
    """'Alpha Fund' vs 'Alpha Trust' banded EXACT at score 1.0 because
    trust/fund/group/holding were stripped as corporate suffixes. EXACT means
    an automatic CONFIRMED_HIT the adjudicator is forbidden to dissent from,
    so a one-shared-word coincidence became an uncontestable hit."""

    def test_fund_vs_trust_is_not_a_hit(self):
        idx = ListIndex()
        idx.add(ListedParty(uid="SDN:1", source="SDN", native_id="1", name="Alpha Trust"))
        self.assertNotEqual(bands(idx.build(), "Alpha Fund").get("SDN:1"), "EXACT")

    def test_rare_name_inside_a_loaded_qualifier_still_hits(self):
        # Recall must survive the fix: a listed "Wagner" inside subject
        # "Wagner Group" is still caught by discriminating containment.
        idx = ListIndex()
        idx.add(ListedParty(uid="SDN:1", source="SDN", native_id="1", name="WAGNER"))
        idx.add(ListedParty(uid="SDN:2", source="SDN", native_id="2", name="Beacon Optics"))
        b = bands(idx.build(), "Wagner Group")
        self.assertEqual(b.get("SDN:1"), "STRONG")


class TestWeakAliases(unittest.TestCase):
    def _screen(self, subject_name):
        p = ListedParty(uid="SDN:9", source="SDN", native_id="9",
                        name="IVANOV, Igor Petrovich",
                        aliases=["THE PROFESSOR"], weak_aliases=["THE PROFESSOR"])
        idx = ListIndex()
        idx.add(p)
        return screen_name(SubjectParty(ref="t", name=subject_name), idx.build())

    def test_weak_alias_hit_is_labelled(self):
        cands = self._screen("The Professor")
        self.assertEqual(cands[0].band, "EXACT")
        self.assertTrue(cands[0].signals.get("weak_alias"))

    def test_primary_name_hit_is_not_labelled(self):
        cands = self._screen("Ivanov, Igor Petrovich")
        self.assertEqual(cands[0].band, "EXACT")
        self.assertNotIn("weak_alias", cands[0].signals)

    def test_weak_alias_exact_floors_at_review_not_confirmed(self):
        from xscreen.models import ScreeningResult
        from xscreen.rules import provisional_disposition
        cands = self._screen("The Professor")
        r = ScreeningResult(subject={"ref": "t", "name": "The Professor"},
                            candidates=[c.to_dict() for c in cands])
        disp, reason = provisional_disposition(r)
        self.assertEqual(disp, "REVIEW")
        self.assertIn("weak alias", reason)

    def test_primary_exact_still_auto_confirms(self):
        from xscreen.models import ScreeningResult
        from xscreen.rules import provisional_disposition
        cands = self._screen("Ivanov, Igor Petrovich")
        r = ScreeningResult(subject={"ref": "t", "name": "Ivanov, Igor Petrovich"},
                            candidates=[c.to_dict() for c in cands])
        self.assertEqual(provisional_disposition(r)[0], "CONFIRMED_HIT")


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
