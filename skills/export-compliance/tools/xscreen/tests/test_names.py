import unittest

from xscreen.names import (
    core_tokens,
    fold,
    is_acronym_of,
    jaro,
    jaro_winkler,
    levenshtein,
    levenshtein_ratio,
    normalized,
    skeleton,
    token_containment,
    token_set_ratio,
)


class TestFolding(unittest.TestCase):
    def test_strips_diacritics_and_case(self):
        self.assertEqual(fold("Müller & Söhne GmbH"), "muller sohne gmbh")
        self.assertEqual(fold("ŁÓDŹ Trading"), "lodz trading")
        self.assertEqual(fold("Ærø Skibsværft"), "aero skibsvaerft")

    def test_punctuation_becomes_separation_not_deletion(self):
        # "A.B.C" must not collapse to "abc" -- that would let unrelated
        # initialisms collide with real words.
        self.assertEqual(fold("A.B.C."), "a b c")

    def test_idempotent(self):
        once = fold("Société Générale, S.A.")
        self.assertEqual(fold(once), once)

    def test_stacked_diacritic_on_an_extras_letter_folds_after_nfkd(self):
        # ǿ is ø plus an acute accent. The extras table (ø -> o) used to run
        # BEFORE NFKD, so the precomposed form never met the table and
        # "Sǿrensen" and "Sørensen" produced different keys -- they never
        # blocked together.
        self.assertEqual(fold("Sǿrensen"), fold("Sørensen"))
        self.assertEqual(fold("Sǿrensen"), "sorensen")
        self.assertEqual(fold("ǾRSTED"), "orsted")

    def test_underscore_is_a_separator_not_glue(self):
        # `\w` includes the underscore, so "ACME_TRADING" stayed one token
        # and shared nothing with "ACME TRADING".
        self.assertEqual(fold("ACME_TRADING"), "acme trading")
        self.assertEqual(core_tokens("ACME_TRADING"), core_tokens("Acme Trading"))


class TestTokens(unittest.TestCase):
    def test_corporate_suffix_stripped_from_core(self):
        self.assertEqual(core_tokens("Acme Precision LLC"), ("acme", "precision"))
        self.assertEqual(core_tokens("Acme Precision GmbH"), ("acme", "precision"))
        self.assertEqual(normalized("Acme Precision Ltd"), normalized("Acme Precision Inc"))

    def test_suffix_only_name_survives(self):
        # Stripping must never produce an empty key.
        self.assertTrue(core_tokens("Company Limited"))

    def test_loaded_organizational_nouns_are_not_suffixes(self):
        # "Alpha Fund" and "Alpha Trust" once normalized to the same key and
        # banded EXACT at 1.0 -- an automatic CONFIRMED_HIT the adjudicator
        # was forbidden to dissent from. Trust/fund/group/holding are name
        # parts, not legal wrappers.
        self.assertNotEqual(normalized("Alpha Fund"), normalized("Alpha Trust"))
        self.assertNotEqual(normalized("Wagner Group International Holdings"),
                            "wagner")
        self.assertIn("group", core_tokens("Wagner Group"))
        # True legal forms still fold together.
        self.assertEqual(normalized("Acme LLC"), normalized("Acme Ltd"))
        self.assertEqual(normalized("Northwind OAO"), normalized("Northwind JSC"))

    def test_word_equivalences(self):
        self.assertEqual(normalized("Global Technologies"), normalized("Global Technology"))
        self.assertEqual(normalized("Smith Brothers"), normalized("Smith Bros"))

    def test_noise_tokens_dropped(self):
        self.assertEqual(core_tokens("The Bank of the North"), ("bank", "north"))


class TestSkeleton(unittest.TestCase):
    def test_transliteration_variants_share_a_skeleton(self):
        for a, b in [
            ("Mohammed", "Muhammad"),
            ("Yusuf", "Yousef"),
            ("Abdullah", "Abdulah"),
            ("Vasiliy", "Vasily"),
        ]:
            self.assertEqual(skeleton(a), skeleton(b), f"{a} vs {b}")

    def test_slavic_ov_off_family(self):
        self.assertEqual(skeleton("Petrov"), skeleton("Petroff"))

    def test_qaf_family_unites(self):
        # Qadhafi/Gaddafi/Kaddafi all render the same Arabic qāf. The digraph
        # table had no q/g/k fold, so the three skeletons were qdf/gdf/kdf and
        # the most famous transliteration family in OFAC history was a
        # complete blocking miss.
        self.assertEqual(skeleton("Qadhafi"), skeleton("Gaddafi"))
        self.assertEqual(skeleton("Qadhafi"), skeleton("Kaddafi"))
        self.assertEqual(skeleton("Qasemi"), skeleton("Ghasemi"))

    def test_tch_folds_with_ch(self):
        self.assertEqual(skeleton("Tchernov"), skeleton("Chernov"))

    def test_distinct_names_do_not_collide(self):
        self.assertNotEqual(skeleton("Petrov"), skeleton("Ivanov"))
        self.assertNotEqual(skeleton("Northwind"), skeleton("Southwind"))


class TestSimilarity(unittest.TestCase):
    def test_jaro_reference_values(self):
        self.assertAlmostEqual(jaro("martha", "marhta"), 0.9444, places=3)
        self.assertAlmostEqual(jaro("dixon", "dicksonx"), 0.7667, places=3)

    def test_jaro_winkler_reference_values(self):
        self.assertAlmostEqual(jaro_winkler("martha", "marhta"), 0.9611, places=3)
        self.assertAlmostEqual(jaro_winkler("dixon", "dicksonx"), 0.8133, places=3)

    def test_bounds(self):
        self.assertEqual(jaro_winkler("acme", "acme"), 1.0)
        self.assertEqual(jaro_winkler("", "acme"), 0.0)
        self.assertEqual(jaro_winkler("", ""), 1.0)

    def test_symmetry(self):
        for a, b in [("northwind", "nordvind"), ("acme corp", "acme"), ("ab", "ba")]:
            self.assertAlmostEqual(jaro_winkler(a, b), jaro_winkler(b, a), places=9)

    def test_levenshtein(self):
        self.assertEqual(levenshtein("kitten", "sitting"), 3)
        self.assertEqual(levenshtein("", "abc"), 3)
        self.assertEqual(levenshtein("abc", "abc"), 0)

    def test_levenshtein_cap_short_circuits_without_wrong_answer(self):
        # Capped calls may return cap+1, but never a value below the truth.
        self.assertGreaterEqual(levenshtein("kitten", "sitting", cap=1), 2)
        self.assertEqual(levenshtein("kitten", "sitting", cap=10), 3)

    def test_levenshtein_ratio_bounds(self):
        self.assertEqual(levenshtein_ratio("abc", "abc"), 1.0)
        self.assertEqual(levenshtein_ratio("", ""), 1.0)

    def test_token_metrics(self):
        a, b = ("acme", "precision"), ("acme", "precision", "machining")
        self.assertAlmostEqual(token_set_ratio(a, b), 2 / 3)
        self.assertEqual(token_containment(a, b), 1.0)
        self.assertEqual(token_set_ratio((), b), 0.0)


class TestAcronym(unittest.TestCase):
    def test_detects_initialism(self):
        self.assertTrue(is_acronym_of("ZPI", core_tokens("Zenith Precision Instruments")))
        self.assertTrue(is_acronym_of("Z.P.I.", core_tokens("Zenith Precision Instruments")))

    def test_rejects_non_initialism(self):
        self.assertFalse(is_acronym_of("ZEN", core_tokens("Zenith Precision Instruments")))
        self.assertFalse(is_acronym_of("A", core_tokens("Acme Corp")))

    def test_two_letter_initials_are_noise_not_acronyms(self):
        # On a real list "GE" would initial-match half the two-token names.
        self.assertFalse(is_acronym_of("GE", core_tokens("General Electric")))


class TestDeterminism(unittest.TestCase):
    def test_repeated_calls_identical(self):
        name = "Sociedad Anónima Müller & Søhne Ltd."
        first = (fold(name), core_tokens(name), skeleton(name), normalized(name))
        for _ in range(5):
            self.assertEqual(
                (fold(name), core_tokens(name), skeleton(name), normalized(name)), first
            )


if __name__ == "__main__":
    unittest.main()
