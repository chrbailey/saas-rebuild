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


class TestTokens(unittest.TestCase):
    def test_corporate_suffix_stripped_from_core(self):
        self.assertEqual(core_tokens("Acme Precision LLC"), ("acme", "precision"))
        self.assertEqual(core_tokens("Acme Precision GmbH"), ("acme", "precision"))
        self.assertEqual(normalized("Acme Precision Ltd"), normalized("Acme Precision Inc"))

    def test_suffix_only_name_survives(self):
        # Stripping must never produce an empty key.
        self.assertTrue(core_tokens("Holding Group"))

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
