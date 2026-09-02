import csv
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

    def test_weak_aliases_are_parsed_and_labelled(self):
        # OFAC marks a weak aka by wrapping the name in quotation marks.
        alts = parse_ofac_alt('1001,101,"aka","""THE HAMMER""",-0-\n'
                              "1001,102,\"aka\",\"'EL MARTILLO'\",-0-\n"
                              '1001,103,"aka","REAL FORMER NAME LLC",-0-\n')
        names = alts["1001"]
        self.assertIn(("THE HAMMER", True), names)
        self.assertIn(("EL MARTILLO", True), names)
        self.assertIn(("REAL FORMER NAME LLC", False), names)

    def test_weak_aliases_reach_the_party_record(self):
        alts = parse_ofac_alt('1001,101,"aka","""THE HAMMER""",-0-\n')
        merged = merge_ofac(parse_ofac_sdn(read("SDN.raw")), alts, {})
        p = {x.native_id: x for x in merged.parties}["1001"]
        self.assertIn("THE HAMMER", p.aliases)
        self.assertIn("THE HAMMER", p.weak_aliases)

    def test_remarks_akas_are_extracted_and_screenable(self):
        # SDN remarks carry aliases the ALT file never lists
        # ("a.k.a. FARQAD GENERAL TRADING."). They were never indexed, so a
        # counterparty using exactly that trading name screened clean.
        p = {x.native_id: x for x in self.out.parties}["1002"]
        self.assertIn("FARQAD GENERAL TRADING", p.aliases)
        # Free-text extraction is low-provenance, so it must not auto-confirm.
        self.assertIn("FARQAD GENERAL TRADING", p.weak_aliases)

    def test_missing_alt_file_produces_a_warning_not_silence(self):
        out = parse_ofac_sdn(read("SDN.raw"))
        merged = merge_ofac(out, {}, {})
        self.assertTrue(any("Merged alternate names into 0" in w for w in merged.warnings))

    def test_orphan_alt_entries_surface_as_desync(self):
        out = parse_ofac_sdn(read("SDN.raw"))
        merged = merge_ofac(out, {"999999": ["GHOST ENTRY"]}, {})
        self.assertTrue(any("out of sync" in w for w in merged.warnings))

    def test_column_count_drift_warns_a_few_times_not_per_row(self):
        # A 12k-row layout change used to produce 12k warnings and bury every
        # other warning in the manifest. Throttled like the CSL ragged path.
        rows = "\n".join(f'{i},"NAME{i}","entity","PROG",,,,,,,' for i in range(50))
        out = parse_ofac_sdn(rows)
        per_row = [w for w in out.warnings if "columns, expected" in w]
        self.assertLessEqual(len(per_row), 3)
        self.assertTrue(any("in total" in w for w in out.warnings), out.warnings)
        self.assertEqual(len(out.parties), 50)

    def test_a_few_odd_rows_are_still_reported_individually(self):
        rows = '1,"A","entity","P",,,,,,,\n2,"B","entity","P",,,,,,,,\n'
        out = parse_ofac_sdn(rows)
        self.assertEqual(len([w for w in out.warnings if "columns, expected" in w]), 1)
        self.assertFalse(any("in total" in w for w in out.warnings))


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

    def test_non_sdn_labels_never_resolve_to_sdn(self):
        """Regression, and the dangerous direction.

        A substring fallback used to map any label containing "sdn" to SDN --
        which includes every "Non-SDN ..." label. A Non-SDN party would then
        inherit full blocking legal effect, telling a compliance officer to
        freeze property and file an OFAC report over what is actually a
        securities-investment restriction. UNKNOWN escalates; a wrong answer
        does not.
        """
        from xscreen.sources import resolve_csl_source

        for label in [
            "Non-SDN Menu-Based Sanctions List (NS-MBS)",
            "Non-SDN Palestinian Legislative Council (NS-PLC)",
            "Non-SDN Chinese Military-Industrial Complex Companies (NS-CMIC)",
            "Sectoral Sanctions Identifications (SSI)",
            "Some Future Non-SDN List Nobody Has Seen",
        ]:
            self.assertNotEqual(resolve_csl_source(label), "SDN", label)

    def test_unrecognized_labels_return_unknown_not_a_guess(self):
        from xscreen.sources import resolve_csl_source

        for label in ["Ministry of Widgets Watchlist", "Entity Listing v2", "", "sdn-ish"]:
            self.assertEqual(resolve_csl_source(label), "UNKNOWN", label)

    def test_exact_labels_still_resolve(self):
        from xscreen.sources import resolve_csl_source

        self.assertEqual(resolve_csl_source("SDN"), "SDN")
        self.assertEqual(
            resolve_csl_source("Entity List (EL) - Bureau of Industry and Security"), "EL")
        self.assertEqual(
            resolve_csl_source("  Unverified List (UVL) - Bureau of Industry and Security  "),
            "UVL", "whitespace normalization regressed")

    def test_missing_name_column_refuses_rather_than_guesses(self):
        out = parse_csl("foo,bar\n1,2\n")
        self.assertEqual(out.parties, [])
        self.assertTrue(any("no recognizable name column" in w for w in out.warnings))

    def test_live_label_renderings_resolve_through_key_normalization(self):
        """The lookup docstring promised punctuation-insensitive keys while
        the code only lowercased, so a label differing from the table by a
        dash rendering or a dropped parenthesis resolved UNKNOWN and
        escalated every row on that list."""
        from xscreen.sources import resolve_csl_source

        for label, code in [
            ("Non-SDN Menu-Based Sanctions List (NS-MBS List) - Treasury Department", "NONSDN"),
            ("Non–SDN Menu–Based Sanctions List (NS–MBS List) — Treasury Department",
             "NONSDN"),
            ("Entity List (EL) – Bureau of Industry and Security", "EL"),
            ("Denied Persons List (DPL) -- Bureau of Industry and Security", "DPL"),
            ("Foreign Sanctions Evaders (FSE) - Treasury Department", "FSE"),
        ]:
            self.assertEqual(resolve_csl_source(label), code, label)

    def test_key_normalization_is_not_a_substring_fallback(self):
        # Whole-label equality only. The post-mortem in sources.py explains
        # why a partial match here is the dangerous direction.
        from xscreen.sources import resolve_csl_source

        for label in ["SDN List", "SDN - Treasury Department",
                      "Non-SDN Menu-Based Sanctions List (NS-MBS)", "Entity List Extended"]:
            self.assertEqual(resolve_csl_source(label), "UNKNOWN", label)

    def test_no_two_map_keys_collide_after_normalization(self):
        from xscreen.sources import CSL_SOURCE_MAP, _source_key

        seen: dict[str, str] = {}
        for k, v in CSL_SOURCE_MAP.items():
            self.assertEqual(seen.setdefault(_source_key(k), v), v, k)


class TestIdentityDiscriminators(unittest.TestCase):
    """The adjudication playbook names date and place of birth as among the
    few facts that genuinely distinguish two similarly named individuals.
    They were being reported as unmapped columns and dropped before the
    adjudicator ever saw them."""

    HEADER = ("_id,source,entity_number,type,programs,name,title,addresses,"
              "alt_names,dates_of_birth,places_of_birth,nationalities,ids,remarks\n")
    ROW = ('d1,"Specially Designated Nationals (SDN) - Treasury Department",'
           'SDN-1,Individual,SDGT,"PETROV, Vasiliy",Director General,Moscow,'
           '"PETROFF, V",14 Mar 1968,"Leningrad, USSR",Russia,'
           '"Passport 71234567",Linked to X\n')

    def test_dob_and_pob_reach_the_record(self):
        out = parse_csl(self.HEADER + self.ROW)
        ids = out.parties[0].ids
        self.assertIn("DOB: 14 Mar 1968", ids)
        self.assertIn("POB: Leningrad, USSR", ids)

    def test_native_identifiers_are_preserved_alongside(self):
        out = parse_csl(self.HEADER + self.ROW)
        self.assertIn("Passport 71234567", out.parties[0].ids)

    def test_they_are_no_longer_reported_as_unmapped(self):
        out = parse_csl(self.HEADER + self.ROW)
        for col in ("dates_of_birth", "places_of_birth", "title"):
            self.assertNotIn(col, out.unmapped_columns)

    def test_absent_columns_are_simply_skipped(self):
        # Adding aliases must be safe on a file that does not have them.
        out = parse_csl("id,source,name\nd1,SDN,Acme\n")
        self.assertEqual(out.parties[0].ids, [])

    def test_vessel_identifiers_are_captured(self):
        text = ("id,source,name,type,call_sign,vessel_flag,vessel_owner\n"
                "d1,SDN,MV ARCTIC DAWN,Vessel,J8B2199,Panama,ARCTIC DAWN SHIPPING\n")
        ids = parse_csl(text).parties[0].ids
        self.assertIn("call sign: J8B2199", ids)
        self.assertIn("vessel flag: Panama", ids)


class TestPositionalDrift(unittest.TestCase):
    """The OFAC flat files are positionally defined, so a column-count check
    cannot detect a same-width reorder. A misaligned parse builds names out of
    the wrong field and every screen against that snapshot is worthless."""

    def test_clean_file_produces_no_drift_warning(self):
        out = parse_ofac_sdn(read("SDN.raw"))
        self.assertFalse([w for w in out.warnings if "COLUMN REORDER" in w])

    def test_reordered_columns_are_detected(self):
        rows = []
        for line in read("SDN.raw").splitlines():
            parts = next(csv.reader([line]))
            if len(parts) >= 4:
                # Swap the type and program columns: same width, wrong meaning.
                parts[2], parts[3] = parts[3], parts[2]
            rows.append(",".join(f'"{p}"' for p in parts))
        out = parse_ofac_sdn("\n".join(rows))
        self.assertTrue([w for w in out.warnings if "COLUMN REORDER" in w],
                        f"a column swap went undetected: {out.warnings}")

    def test_small_files_do_not_trigger_a_false_alarm(self):
        out = parse_ofac_sdn('1,"ACME","weird","PROG",,,,,,,,\n')
        self.assertFalse([w for w in out.warnings if "COLUMN REORDER" in w])


class TestRaggedRows(unittest.TestCase):
    """Regression: one stray delimiter in a government file crashed the whole
    refresh with AttributeError, instead of producing a warning."""

    def test_extra_field_does_not_crash_the_parse(self):
        text = read("CSL.raw").replace(
            'https://example.invalid/el,', 'https://example.invalid/el,STRAY,EXTRA,')
        out = parse_csl(text)   # must not raise
        self.assertTrue(out.parties, "a ragged row wiped out the whole parse")

    def test_extra_field_is_reported_not_silently_absorbed(self):
        text = read("CSL.raw").replace(
            'https://example.invalid/el,', 'https://example.invalid/el,STRAY,EXTRA,')
        out = parse_csl(text)
        self.assertTrue(any("ragged" in w for w in out.warnings),
                        f"no ragged-row warning: {out.warnings}")

    def test_short_row_does_not_crash(self):
        lines = read("CSL.raw").splitlines()
        lines.append("d7,Some List")   # far fewer fields than the header
        out = parse_csl("\n".join(lines))
        self.assertTrue(any("ragged" in w for w in out.warnings))

    def test_raw_snapshot_excludes_the_restkey(self):
        from xscreen.normalize import _safe_raw
        row = {"a": "1", None: ["x", "y"], "b": None, "c": "  "}
        self.assertEqual(_safe_raw(row), {"a": "1"})

    def test_many_ragged_rows_do_not_produce_one_warning_each(self):
        header = read("CSL.raw").splitlines()[0]
        rows = [header] + [f"d{i},Entity List,EL-{i},Entity,,Name{i},,,,,,,,,,,,STRAY"
                           for i in range(50)]
        out = parse_csl("\n".join(rows))
        self.assertLessEqual(len([w for w in out.warnings if "ragged" in w]), 5)
        self.assertTrue(any("in total" in w for w in out.warnings))


class TestDPL(unittest.TestCase):
    def test_tab_delimited_with_dates(self):
        out = parse_bis_dpl(read("DPL.raw"))
        self.assertEqual(len(out.parties), 2)
        by = {p.name: p for p in out.parties}
        self.assertEqual(by["CASCADE AVIONICS SUPPLY INC"].expiration_date, "2031-02-01")
        self.assertEqual(by["MERIDIAN PARTS EXPORT GMBH"].expiration_date, "2023-06-15")
        self.assertEqual(by["CASCADE AVIONICS SUPPLY INC"].federal_register, "89 FR 8123")

    def test_uids_are_content_derived_not_positional(self):
        """Regression: the uid was the row ordinal, so every insertion BIS
        made shifted every uid below it and a case keyed on DPL:417 in March
        referred to a different person in April."""
        text = read("DPL.raw")
        before = {p.name: p.uid for p in parse_bis_dpl(text).parties}
        lines = text.splitlines()
        new_row = ("NEWLY DENIED PERSON\t1 Main St\tReno\tNV\tUnited States\t89501\t"
                   "2026-03-01\t2031-03-01\tY\t2026-03-02\tDenial of export privileges\t91 FR 1")
        after = {p.name: p.uid for p in parse_bis_dpl("\n".join([lines[0], new_row, *lines[1:]])).parties}
        for name, uid in before.items():
            self.assertEqual(after[name], uid, name)
        self.assertNotIn("DPL:0", before.values())

    def test_uid_tracks_the_order_not_the_row(self):
        text = read("DPL.raw")
        a = {p.name: p.uid for p in parse_bis_dpl(text).parties}
        b = {p.name: p.uid for p in parse_bis_dpl(text.replace("89 FR 8123", "90 FR 1")).parties}
        self.assertNotEqual(a["CASCADE AVIONICS SUPPLY INC"], b["CASCADE AVIONICS SUPPLY INC"])
        self.assertEqual(a["MERIDIAN PARTS EXPORT GMBH"], b["MERIDIAN PARTS EXPORT GMBH"])

    def test_uid_keeps_the_source_native_id_contract(self):
        for p in parse_bis_dpl(read("DPL.raw")).parties:
            self.assertEqual(p.uid, f"DPL:{p.native_id}")


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

    def test_programs_ids_and_party_type_survive_the_merge(self):
        # Regression: only aliases, addresses and countries were merged; the
        # first record's programs, ids and party type silently won, so load
        # order decided whether the adjudicator saw a date of birth and
        # whether the program tag that changes the legal effect survived.
        a = ListedParty(uid="SDN:1", source="SDN", native_id="1", name="ACME",
                        party_type="unknown", programs=["IRAN"], ids=["POB: Tehran"])
        b = ListedParty(uid="SDN:1", source="SDN", native_id="1", name="ACME",
                        party_type="entity", programs=["FSE-IR", "iran"], ids=["DOB: 1970"],
                        effective_date="2024-01-01")
        m = dedupe([a, b])[0]
        self.assertEqual(m.party_type, "entity")
        self.assertEqual(m.programs, ["IRAN", "FSE-IR"])
        self.assertEqual(sorted(m.ids), ["DOB: 1970", "POB: Tehran"])
        self.assertEqual(m.effective_date, "2024-01-01")

    def test_known_party_type_is_not_overwritten_by_unknown(self):
        a = ListedParty(uid="SDN:1", source="SDN", native_id="1", name="X", party_type="individual")
        b = ListedParty(uid="SDN:1", source="SDN", native_id="1", name="X", party_type="unknown")
        self.assertEqual(dedupe([a, b])[0].party_type, "individual")
        self.assertEqual(dedupe([b, a])[0].party_type, "individual")


class TestAllNames(unittest.TestCase):
    def test_primary_plus_aliases_deduped_order_preserved(self):
        p = ListedParty(uid="x", source="SDN", native_id="1", name="Acme",
                        aliases=["ACME", "Acme Corp", ""])
        self.assertEqual(p.all_names(), ["Acme", "Acme Corp"])


if __name__ == "__main__":
    unittest.main()
