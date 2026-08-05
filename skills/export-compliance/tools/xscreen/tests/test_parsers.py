import unittest
from pathlib import Path

from xscreen.normalize import (
    dedupe,
    merge_ofac,
    parse_bis_dpl,
    parse_csl,
    parse_ofac_add,
    parse_ofac_alt,
    parse_ofac_sdn,
)
from xscreen.models import ListedParty

FIX = Path(__file__).parent / "fixtures"


def read(name: str) -> str:
    return (FIX / name).read_text(encoding="utf-8")


class TestOFAC(unittest.TestCase):
    def setUp(self):
        self.out = parse_ofac_sdn(read("SDN.raw"))

    def test_parses_all_rows(self):
        self.assertEqual(len(self.out.parties), 6)
        self.assertEqual(self.out.skipped_rows, 0)

    def test_null_sentinel_becomes_empty(self):
        p = {x.native_id: x for x in self.out.parties}["1001"]
        self.assertEqual(p.name, "NORTHWIND HEAVY MACHINERY OAO")
        # "-0- " with trailing space in the fixture must still normalize away.
        self.assertNotIn("-0-", " ".join(p.programs))

    def test_party_types(self):
        by = {x.native_id: x for x in self.out.parties}
        self.assertEqual(by["1001"].party_type, "entity")
        self.assertEqual(by["1003"].party_type, "individual")
        self.assertEqual(by["1005"].party_type, "vessel")

    def test_programs_split(self):
        by = {x.native_id: x for x in self.out.parties}
        self.assertIn("UKRAINE-EO13662", by["1001"].programs)

    def test_alias_merge_is_the_recall_path(self):
        alts = parse_ofac_alt(read("SDN_ALT.raw"))
        adds = parse_ofac_add(read("SDN_ADD.raw"))
        merged = merge_ofac(self.out, alts, adds)
        by = {x.native_id: x for x in merged.parties}
        self.assertIn("NORTHWIND HEAVY MACHINERY JSC", by["1001"].aliases)
        self.assertIn("NORDVIND TYAZHELOE MASHINOSTROENIE", by["1001"].aliases)
        self.assertTrue(any("Moscow" in a for a in by["1001"].addresses))
        self.assertIn("Russia", by["1001"].countries)

    def test_missing_alt_file_produces_a_warning_not_silence(self):
        out = parse_ofac_sdn(read("SDN.raw"))
        merged = merge_ofac(out, {}, {})
        self.assertTrue(any("Merged alternate names into 0" in w for w in merged.warnings))

    def test_orphan_alt_entries_surface_as_desync(self):
        out = parse_ofac_sdn(read("SDN.raw"))
        merged = merge_ofac(out, {"999999": ["GHOST ENTRY"]}, {})
        self.assertTrue(any("out of sync" in w for w in merged.warnings))


class TestCSL(unittest.TestCase):
    def setUp(self):
        self.out = parse_csl(read("CSL.raw"))

    def test_source_codes_resolved(self):
        codes = {p.source for p in self.out.parties}
        self.assertIn("EL", codes)
        self.assertIn("UVL", codes)
        self.assertIn("MEU", codes)
        self.assertIn("DTC", codes)
        self.assertIn("NONSDN", codes)

    def test_unknown_source_is_flagged_not_absorbed(self):
        unknown = [p for p in self.out.parties if p.source == "UNKNOWN"]
        self.assertEqual(len(unknown), 1)
        self.assertTrue(any("does not recognize" in w for w in self.out.warnings))

    def test_aliases_split_on_semicolon(self):
        el = [p for p in self.out.parties if p.native_id == "EL-9001"][0]
        self.assertIn("HSRI", el.aliases)
        self.assertIn("HELIOS SEMICONDUCTOR RES INST", el.aliases)

    def test_license_fields_preserved_in_remarks(self):
        el = [p for p in self.out.parties if p.native_id == "EL-9001"][0]
        self.assertIn("Presumption of denial", el.remarks)

    def test_subset_filter(self):
        only_uvl = parse_csl(read("CSL.raw"), source_filter="UVL")
        self.assertTrue(only_uvl.parties)
        self.assertEqual({p.source for p in only_uvl.parties}, {"UVL"})

    def test_unmapped_columns_reported(self):
        # Every column in the fixture is mapped; adding one must surface.
        text = read("CSL.raw").replace("id,source", "id,brand_new_column,source", 1)
        text = text.replace("d1,\"Entity", "d1,X,\"Entity")
        out = parse_csl(text)
        self.assertIn("brand_new_column", out.unmapped_columns)

    def test_missing_name_column_refuses_rather_than_guesses(self):
        out = parse_csl("foo,bar\n1,2\n")
        self.assertEqual(out.parties, [])
        self.assertTrue(any("no recognizable name column" in w for w in out.warnings))


class TestDPL(unittest.TestCase):
    def test_tab_delimited_with_dates(self):
        out = parse_bis_dpl(read("DPL.raw"))
        self.assertEqual(len(out.parties), 2)
        by = {p.name: p for p in out.parties}
        self.assertEqual(by["CASCADE AVIONICS SUPPLY INC"].expiration_date, "2031-02-01")
        self.assertEqual(by["MERIDIAN PARTS EXPORT GMBH"].expiration_date, "2023-06-15")
        self.assertEqual(by["CASCADE AVIONICS SUPPLY INC"].federal_register, "89 FR 8123")


class TestDedupe(unittest.TestCase):
    def test_merges_alias_sets_rather_than_dropping(self):
        a = ListedParty(uid="SDN:1", source="SDN", native_id="1", name="ACME",
                        aliases=["A"], countries=["RU"])
        b = ListedParty(uid="SDN:1", source="SDN", native_id="1", name="ACME",
                        aliases=["B"], addresses=["X"], remarks="hello")
        merged = dedupe([a, b])
        self.assertEqual(len(merged), 1)
        self.assertEqual(sorted(merged[0].aliases), ["A", "B"])
        self.assertEqual(merged[0].addresses, ["X"])
        self.assertEqual(merged[0].remarks, "hello")

    def test_case_insensitive_alias_dedupe(self):
        a = ListedParty(uid="SDN:1", source="SDN", native_id="1", name="ACME", aliases=["Acme Co"])
        b = ListedParty(uid="SDN:1", source="SDN", native_id="1", name="ACME", aliases=["ACME CO"])
        self.assertEqual(len(dedupe([a, b])[0].aliases), 1)


class TestAllNames(unittest.TestCase):
    def test_primary_plus_aliases_deduped_order_preserved(self):
        p = ListedParty(uid="x", source="SDN", native_id="1", name="Acme",
                        aliases=["ACME", "Acme Corp", ""])
        self.assertEqual(p.all_names(), ["Acme", "Acme Corp"])


if __name__ == "__main__":
    unittest.main()
