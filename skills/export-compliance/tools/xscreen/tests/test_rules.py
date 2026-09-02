import unittest
from datetime import date

from xscreen.models import Candidate, ScreeningResult, SubjectParty
from xscreen.rules import (
    classification_rules,
    destination_rules,
    end_use_rules,
    evaluate,
    list_hit_rules,
    load_policy,
    provisional_disposition,
)


def ids(flags) -> set[str]:
    return {f.rule_id for f in flags}


class TestDestination(unittest.TestCase):
    def setUp(self):
        self.p = load_policy()

    def test_comprehensive_embargo(self):
        f = destination_rules(SubjectParty(ref="t", name="X", destination_country="Iran"), self.p)
        self.assertIn("DEST.COMPREHENSIVE", ids(f))
        self.assertEqual([x.severity for x in f if x.rule_id == "DEST.COMPREHENSIVE"], ["prohibitive"])

    def test_iso_and_free_text_resolve_the_same(self):
        a = ids(destination_rules(SubjectParty(ref="t", name="X", destination_country="IR"), self.p))
        b = ids(destination_rules(SubjectParty(ref="t", name="X", destination_country="iran"), self.p))
        self.assertEqual(a, b)

    def test_extensive_is_not_prohibitive(self):
        f = destination_rules(SubjectParty(ref="t", name="X", destination_country="Russia"), self.p)
        self.assertIn("DEST.EXTENSIVE", ids(f))
        self.assertNotIn("DEST.COMPREHENSIVE", ids(f))

    def test_region_embargo_fires_on_address_not_country(self):
        subj = SubjectParty(ref="t", name="X", destination_country="Ukraine",
                            address="Ulitsa Lenina 4, Sevastopol, Crimea")
        f = destination_rules(subj, self.p)
        self.assertIn("DEST.REGION", ids(f))

    def test_ukraine_alone_is_not_embargoed(self):
        f = destination_rules(
            SubjectParty(ref="t", name="X", destination_country="Ukraine", address="Kyiv"), self.p)
        self.assertNotIn("DEST.REGION", ids(f))

    def test_transshipment_watch_is_diligence_not_prohibition(self):
        f = destination_rules(
            SubjectParty(ref="t", name="X", destination_country="United Arab Emirates"), self.p)
        flag = [x for x in f if x.rule_id == "DEST.TRANSSHIP"][0]
        self.assertEqual(flag.severity, "diligence")

    def test_unknown_two_letter_code_does_not_pass_through_silently(self):
        """Regression, false-clear direction.

        `resolve_country` used to return any two-character string as a valid
        ISO2 code. It then matched no policy entry, produced no destination
        flag at all, and the case reached CLEAR with exit code 0 -- while the
        party-file schema promised an unresolvable value would raise
        DEST.UNRESOLVED. A shipping gate keyed on exit 0 would have released
        it.
        """
        for bogus in ("XX", "ZZ", "QQ", "J1"):
            f = destination_rules(
                SubjectParty(ref="t", name="X", destination_country=bogus), self.p)
            self.assertIn("DEST.UNRESOLVED", ids(f), f"{bogus} resolved silently")

    def test_a_real_but_unlisted_code_is_not_silently_clear(self):
        # KH is a genuine ISO code with no entry in the shipped policy file.
        # It must produce *something* while the file is unattested.
        f = destination_rules(
            SubjectParty(ref="t", name="X", destination_country="KH"), self.p)
        self.assertTrue(f, "a resolvable but unlisted destination produced no flag at all")

    def test_no_policy_entry_flag_disappears_once_attested(self):
        from dataclasses import replace
        attested = replace(self.p, verified_by="someone", verified_on="2026-01-15")
        f = destination_rules(
            SubjectParty(ref="t", name="X", destination_country="CA"), attested)
        self.assertNotIn("DEST.NO_POLICY_ENTRY", ids(f))

    def test_missing_destination_is_flagged(self):
        self.assertIn("DEST.MISSING", ids(destination_rules(SubjectParty(ref="t", name="X"), self.p)))

    def test_iso_official_renderings_resolve_to_the_embargo(self):
        """ERP master data emits the ISO 3166 'official' forms and alpha-3
        codes. They used to fall out as DEST.UNRESOLVED -- a diligence flag
        -- on comprehensively embargoed destinations."""
        for dest in ["Iran, Islamic Republic of", "IRAN (ISLAMIC REPUBLIC OF)",
                     "Iran, Islamic Rep.", "IRN", "Korea, Democratic People's Republic of",
                     "PRK", "Syrian Arab Republic", "SYR", "Cuba", "CUB", "Republic of Cuba"]:
            f = ids(destination_rules(SubjectParty(ref="t", name="X", destination_country=dest), self.p))
            self.assertIn("DEST.COMPREHENSIVE", f, dest)
            self.assertNotIn("DEST.UNRESOLVED", f, dest)

    def test_plain_names_alpha3_codes_and_rotated_forms_resolve(self):
        for dest, iso in [("Germany", "DE"), ("DEU", "DE"), ("Viet Nam", "VN"),
                          ("Russian Fed.", "RU"), ("Russian Federation", "RU"),
                          ("Congo, Democratic Republic of the", "CD"),
                          ("Taiwan, Province of China", "TW"), ("The Netherlands", "NL"),
                          ("Bolivia (Plurinational State of)", "BO"),
                          ("Hong Kong SAR, China", "HK"), ("Burma (Myanmar)", "MM")]:
            self.assertEqual(self.p.resolve_country(dest), iso, dest)

    def test_ambiguous_or_bogus_values_still_do_not_resolve(self):
        # Bare "Korea" is ambiguous between KR and KP; resolving it to the
        # unrestricted one would be a false clear. Unknown alpha-3 codes and
        # made-up names stay unresolved.
        for dest in ["Korea", "XXX", "ZZZ", "Narnia"]:
            self.assertEqual(self.p.resolve_country(dest), "", dest)
            self.assertIn("DEST.UNRESOLVED", ids(destination_rules(
                SubjectParty(ref="t", name="X", destination_country=dest), self.p)), dest)

    def test_unverified_policy_is_marked_on_every_flag(self):
        f = destination_rules(SubjectParty(ref="t", name="X", destination_country="Cuba"), self.p)
        # The shipped policy file is unattested by design.
        self.assertTrue(all(x.unverified_policy for x in f))
        self.assertTrue(all(x.policy_as_of for x in f))


class TestListEffects(unittest.TestCase):
    def _cand(self, source: str, band: str = "EXACT", **lp) -> Candidate:
        return Candidate(
            listed_uid=f"{source}:1", listed_name="TEST PARTY", listed_source=source,
            score=1.0, band=band, listed_party={"party_type": "entity", **lp},
        )

    def test_sdn_is_prohibitive_and_triggers_ownership_analysis(self):
        f = list_hit_rules([self._cand("SDN")], date(2026, 1, 1))
        self.assertIn("LIST.SDN", ids(f))
        self.assertIn("LIST.SDN50", ids(f))

    def test_individual_sdn_does_not_trigger_ownership_rule(self):
        f = list_hit_rules([self._cand("SDN", party_type="individual")], date(2026, 1, 1))
        self.assertNotIn("LIST.SDN50", ids(f))

    def test_uvl_is_diligence_not_prohibition(self):
        f = list_hit_rules([self._cand("UVL")], date(2026, 1, 1))
        self.assertEqual([x.severity for x in f if x.rule_id == "LIST.UVL"], ["diligence"])

    def test_nonsdn_is_licence_level_not_blocking(self):
        f = list_hit_rules([self._cand("NONSDN", programs=["SSI"])], date(2026, 1, 1))
        flag = [x for x in f if x.rule_id == "LIST.NONSDN"][0]
        self.assertEqual(flag.severity, "license")
        self.assertIn("NOT a blocking designation", flag.detail)

    def test_fse_is_prohibitive_not_licence_level(self):
        """Foreign Sanctions Evaders fell through to the Non-SDN rule as
        'generally NOT a blocking designation' at licence severity. EO 13608
        prohibits U.S. persons from all transactions or dealings with the
        listed person -- for a shipment decision, the prohibitive outcome."""
        f = list_hit_rules([self._cand("FSE")], date(2026, 1, 1))
        flag = [x for x in f if x.rule_id == "LIST.FSE"][0]
        self.assertEqual(flag.severity, "prohibitive")
        self.assertIn("13608", flag.basis)
        self.assertNotIn("LIST.NONSDN", ids(f))

    def test_fse_program_tag_inside_the_nonsdn_file_is_prohibitive(self):
        # OFAC's consolidated Non-SDN file carries FSE parties as NONSDN rows
        # tagged FSE-IR / FSE-SY.
        f = list_hit_rules([self._cand("NONSDN", programs=["FSE-IR"])], date(2026, 1, 1))
        self.assertIn("LIST.FSE", ids(f))
        self.assertNotIn("LIST.NONSDN", ids(f))

    def test_other_nonsdn_programs_keep_the_licence_nuance(self):
        for program in ("SSI", "CAPTA", "NS-CMIC", "UKRAINE-EO13662"):
            f = list_hit_rules([self._cand("NONSDN", programs=[program])], date(2026, 1, 1))
            self.assertIn("LIST.NONSDN", ids(f), program)
            self.assertNotIn("LIST.FSE", ids(f), program)

    def test_fse_source_has_a_recorded_legal_effect(self):
        from xscreen.sources import legal_effect_for
        self.assertNotIn("UNKNOWN LIST", legal_effect_for("FSE"))

    def test_entity_list_points_back_at_the_entry(self):
        f = list_hit_rules([self._cand("EL")], date(2026, 1, 1))
        self.assertIn("Read the actual Entity List entry",
                      [x.action_required for x in f if x.rule_id == "LIST.ENTITY"][0])

    def test_expired_denial_order_is_informational(self):
        c = self._cand("DPL")
        c.listed_party.update({"effective_date": "2018-06-15", "expiration_date": "2023-06-15"})
        f = list_hit_rules([c], date(2026, 1, 1))
        flag = [x for x in f if x.rule_id == "LIST.DPL"][0]
        self.assertEqual(flag.severity, "informational")
        self.assertIn("expired", flag.detail)

    def test_active_denial_order_is_prohibitive(self):
        c = self._cand("DPL")
        c.listed_party.update({"effective_date": "2024-02-01", "expiration_date": "2031-02-01"})
        f = list_hit_rules([c], date(2026, 1, 1))
        self.assertEqual([x.severity for x in f if x.rule_id == "LIST.DPL"], ["prohibitive"])

    def test_order_not_yet_effective(self):
        c = self._cand("DPL")
        c.listed_party.update({"effective_date": "2030-01-01", "expiration_date": ""})
        f = list_hit_rules([c], date(2026, 1, 1))
        self.assertIn("not effective until", [x.detail for x in f if x.rule_id == "LIST.DPL"][0])

    def test_undated_order_is_assumed_in_force(self):
        f = list_hit_rules([self._cand("DPL")], date(2026, 1, 1))
        self.assertEqual([x.severity for x in f if x.rule_id == "LIST.DPL"], ["prohibitive"])

    def test_unknown_source_escalates_rather_than_guessing(self):
        f = list_hit_rules([self._cand("UNKNOWN")], date(2026, 1, 1))
        self.assertIn("LIST.UNKNOWN_SOURCE", ids(f))

    def test_none_band_produces_no_flags(self):
        self.assertEqual(list_hit_rules([self._cand("SDN", band="NONE")], date(2026, 1, 1)), [])


class TestEndUse(unittest.TestCase):
    def test_proliferation_keywords_trigger_inquiry(self):
        f = end_use_rules(SubjectParty(ref="t", name="X", item_description="vacuum pump",
                                       end_use="uranium enrichment research"))
        self.assertIn("USE.NUCLEAR", ids(f))

    def test_keyword_hit_is_labelled_as_a_signal_not_a_finding(self):
        f = end_use_rules(SubjectParty(ref="t", name="X", end_use="missile test stand"))
        flag = [x for x in f if x.rule_id == "USE.MISSILE"][0]
        self.assertIn("not a classification", flag.detail)

    def test_kyc_reluctance_flag(self):
        f = end_use_rules(SubjectParty(ref="t", name="X", item_description="parts",
                                       end_use="Customer declined to provide end use"))
        self.assertIn("KYC.RELUCTANT_END_USE", ids(f))

    def test_intermediary_role(self):
        f = end_use_rules(SubjectParty(ref="t", name="X", role="freight forwarder",
                                       item_description="pumps"))
        self.assertIn("KYC.INTERMEDIARY", ids(f))

    def test_missing_end_use_is_itself_a_flag(self):
        self.assertIn("USE.MISSING", ids(end_use_rules(SubjectParty(ref="t", name="X"))))


class TestClassification(unittest.TestCase):
    def test_missing_eccn(self):
        self.assertIn("CLASS.MISSING", ids(classification_rules(SubjectParty(ref="t", name="X"))))

    def test_ear99_still_warns_about_destination_and_end_use(self):
        f = classification_rules(SubjectParty(ref="t", name="X", eccn="EAR99"))
        self.assertIn("CLASS.EAR99", ids(f))

    def test_valid_eccn_formats_accepted(self):
        for eccn in ["3A001", "5A002", "5A002.a.1", "9E003"]:
            self.assertEqual(ids(classification_rules(SubjectParty(ref="t", name="X", eccn=eccn))),
                             set(), eccn)

    def test_malformed_eccn_flagged(self):
        for eccn in ["3X001", "ABC", "30001"]:
            self.assertIn("CLASS.MALFORMED",
                          ids(classification_rules(SubjectParty(ref="t", name="X", eccn=eccn))), eccn)

    def test_valid_prefix_with_garbage_suffix_is_flagged(self):
        # Regression: the suffix separator used to be optional while trailing
        # alphanumerics were still allowed, so a mistyped ECCN that happened
        # to start with a valid pattern passed as well-formed and the operator
        # never got the prompt to correct it.
        for eccn in ["3A0011", "3A001XYZ", "3A001abcdef", "5A002a1"]:
            self.assertIn("CLASS.MALFORMED",
                          ids(classification_rules(SubjectParty(ref="t", name="X", eccn=eccn))),
                          eccn)


class TestProvisionalDisposition(unittest.TestCase):
    def _result(self, band=None, severity=None) -> ScreeningResult:
        r = ScreeningResult(subject=SubjectParty(ref="t", name="X").to_dict())
        if band:
            r.candidates = [Candidate(listed_uid="SDN:1", listed_name="X", listed_source="SDN",
                                      score=1.0, band=band).to_dict()]
        if severity:
            r.rule_flags = [{"rule_id": "R", "severity": severity, "title": "", "basis": "",
                             "detail": "", "action_required": ""}]
        return r

    def test_exact_is_a_confirmed_hit_before_any_model_runs(self):
        d, _ = provisional_disposition(self._result(band="EXACT"))
        self.assertEqual(d, "CONFIRMED_HIT")

    def test_strong_and_weak_route_to_review(self):
        self.assertEqual(provisional_disposition(self._result(band="STRONG"))[0], "REVIEW")
        self.assertEqual(provisional_disposition(self._result(band="WEAK"))[0], "REVIEW")

    def test_prohibitive_rule_without_a_name_hit_still_reviews(self):
        self.assertEqual(provisional_disposition(self._result(severity="prohibitive"))[0], "REVIEW")

    def test_informational_only_is_clear(self):
        self.assertEqual(provisional_disposition(self._result(severity="informational"))[0], "CLEAR")

    def test_nothing_at_all_is_clear(self):
        self.assertEqual(provisional_disposition(self._result())[0], "CLEAR")


class TestEvaluateIntegration(unittest.TestCase):
    def test_all_rule_families_run(self):
        subj = SubjectParty(ref="t", name="X", destination_country="Iran", role="broker",
                            item_description="centrifuge parts", eccn="")
        cand = Candidate(listed_uid="SDN:1", listed_name="X", listed_source="SDN",
                         score=1.0, band="EXACT", listed_party={"party_type": "entity"})
        got = ids(evaluate(subj, [cand], as_of=date(2026, 1, 1)))
        for expected in ("LIST.SDN", "LIST.SDN50", "DEST.COMPREHENSIVE", "DEST.ITAR126",
                         "USE.NUCLEAR", "KYC.INTERMEDIARY", "CLASS.MISSING"):
            self.assertIn(expected, got)


if __name__ == "__main__":
    unittest.main()
