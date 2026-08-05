"""Regressions for the defects an adversarial safety review found.

Each test here corresponds to a demonstrated exploit. They are grouped by the
property the exploit broke rather than by module, because the property is what
has to keep holding when someone refactors.
"""

import json
import os
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from xscreen.audit import AuditLog
from xscreen.fetch import corpus_check, load_manifest, refresh, staleness_check
from xscreen.models import Candidate, ListedParty, ScreeningResult, SubjectParty

FIX = Path(__file__).parent / "fixtures"
FULL = ("CSL", "SDN", "SDN_ALT", "SDN_ADD", "NONSDN", "DPL")


class CorpusCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.data = self.tmp / "lists"
        self.data.mkdir(parents=True)
        for f in FIX.glob("*.raw"):
            shutil.copy(f, self.data / f.name)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


class TestCorpusCoverage(CorpusCase):
    """`xscreen refresh --sources DPL` rebuilt parties.jsonl from that one
    list. The manifest reported fresh and not degraded, and the next screen
    exited 0 on an OFAC-blocked party."""

    def test_full_refresh_is_healthy(self):
        m = refresh(self.data, FULL, offline=True)
        self.assertFalse(m.degraded, m.degraded_reason)
        self.assertTrue(staleness_check(m)[0])

    def test_narrow_refresh_is_degraded(self):
        m = refresh(self.data, ("DPL",), offline=True)
        self.assertTrue(m.degraded)
        self.assertIn("omits", m.degraded_reason)

    def test_narrow_refresh_is_refused_at_screening_time(self):
        refresh(self.data, ("DPL",), offline=True)
        ok, msg = corpus_check(load_manifest(self.data))
        self.assertFalse(ok)
        self.assertIn("does not cover", msg)

    def test_completeness_is_not_an_age_question(self):
        """Coverage must live outside staleness_check, because --allow-stale
        suppresses everything staleness_check returns."""
        refresh(self.data, ("DPL",), offline=True)
        m = load_manifest(self.data)
        self.assertFalse(corpus_check(m)[0])
        # Freshly written, so age alone is fine -- the two checks are orthogonal.
        self.assertTrue(staleness_check(m)[0], "coverage leaked back into the age check")

    def test_allow_stale_cannot_bypass_an_incomplete_corpus(self):
        """Regression for the P1 review finding.

        `--allow-stale` exists so an operator can deliberately re-screen a
        historical snapshot they know is old but *whole*. It must not also
        wave through a corpus missing entire lists: a party listed only on an
        omitted list would come back CLEAR.
        """
        from xscreen.pipeline import parse_party_file, run

        refresh(self.data, ("DPL",), offline=True)
        subjects, _ = parse_party_file("name\nNorthwind Heavy Machinery OAO\n")
        audit = self.tmp / "audit.jsonl"

        for allow_stale in (False, True):
            with self.assertRaises(RuntimeError, msg=f"allow_stale={allow_stale}") as ctx:
                run(subjects, self.data, audit, use_llm=False, use_critic=False,
                    allow_stale=allow_stale)
            self.assertIn("does not cover", str(ctx.exception),
                          f"allow_stale={allow_stale} bypassed the coverage refusal")

    def test_allow_stale_still_works_for_a_complete_but_old_corpus(self):
        """The override must keep functioning for what it was built for."""
        from xscreen.pipeline import parse_party_file, run

        refresh(self.data, FULL, offline=True)
        p = self.data / "manifest.json"
        man = json.loads(p.read_text())
        for f in man["files"]:
            if f.get("fetched_at"):
                f["fetched_at"] = "2023-01-01T00:00:00+00:00"
        p.write_text(json.dumps(man))

        subjects, _ = parse_party_file("name\nSunny Day Bakery\n")
        audit = self.tmp / "audit2.jsonl"
        with self.assertRaises(RuntimeError):
            run(subjects, self.data, audit, use_llm=False, use_critic=False)
        results, summary = run(subjects, self.data, audit, use_llm=False,
                               use_critic=False, allow_stale=True)
        self.assertEqual(len(results), 1)

    def test_coverage_is_recorded_on_the_manifest(self):
        m = refresh(self.data, FULL, offline=True)
        self.assertIn("SDN", m.covered_sources)
        self.assertIn("NONSDN", m.covered_sources)


class TestStalenessCannotBeTouched(CorpusCase):
    """Freshness came from st_mtime, so `touch lists/*.raw` turned a
    three-year-old snapshot into a "0.0 days old" one with stale_override
    false in the audit log -- a one-line bypass that looked clean."""

    def _backdate(self, iso: str) -> None:
        p = self.data / "manifest.json"
        man = json.loads(p.read_text())
        for f in man["files"]:
            if f.get("fetched_at"):
                f["fetched_at"] = iso
        p.write_text(json.dumps(man))

    def test_touch_does_not_reset_freshness(self):
        refresh(self.data, FULL, offline=True)
        self._backdate("2023-01-01T00:00:00+00:00")
        self.assertFalse(staleness_check(load_manifest(self.data))[0])

        for f in self.data.glob("*.raw"):
            os.utime(f, None)
        m = refresh(self.data, FULL, offline=True)
        ok, msg = staleness_check(m)
        self.assertFalse(ok, "touching the files reset the recorded fetch time")
        self.assertIn("days old", msg)

    def test_changed_content_gets_a_new_fetch_time(self):
        # Carrying forward is keyed on sha256, so genuinely new data must not
        # inherit the old timestamp.
        refresh(self.data, FULL, offline=True)
        self._backdate("2023-01-01T00:00:00+00:00")
        (self.data / "DPL.raw").write_text(
            (self.data / "DPL.raw").read_text() + "NEWPARTY\t\t\t\t\t\t\t\t\t\t\t\n")
        m = refresh(self.data, FULL, offline=True)
        dpl = [f for f in m.files if f["code"] == "DPL"][0]
        self.assertNotEqual(dpl["fetched_at"], "2023-01-01T00:00:00+00:00")

    def test_future_timestamps_are_not_eternally_fresh(self):
        refresh(self.data, FULL, offline=True)
        self._backdate((datetime.now(timezone.utc) + timedelta(days=900)).isoformat())
        ok, msg = staleness_check(load_manifest(self.data))
        self.assertFalse(ok, "a future timestamp read as fresh forever")
        self.assertIn("future", msg)


class TestAuditTruncation(unittest.TestCase):
    """verify() walked forward from GENESIS, so a valid *prefix* verified
    clean -- an operator could delete today's hits from the tail and the chain
    still reported INTACT."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "audit.jsonl"
        self.log = AuditLog(self.path)
        for i in range(6):
            self.log.append("case.screened", {"ref": f"C-{i}"}, actor="t")

    def tearDown(self):
        self.tmp.cleanup()

    def test_intact_chain_verifies(self):
        ok, problems = self.log.verify()
        self.assertTrue(ok, problems)

    def test_tail_truncation_is_detected(self):
        lines = self.path.read_text().splitlines()
        self.path.write_text("\n".join(lines[:-3]) + "\n")
        ok, problems = self.log.verify()
        self.assertFalse(ok, "deleting the last three entries went unnoticed")
        self.assertTrue(any("removed from the end" in p for p in problems))

    def test_replacing_the_final_entry_is_detected(self):
        lines = self.path.read_text().splitlines()
        e = json.loads(lines[-1])
        e["payload"] = {"ref": "different"}
        from xscreen.audit import _hash_entry
        e["hash"] = _hash_entry(e)
        lines[-1] = json.dumps(e, ensure_ascii=False, sort_keys=True)
        self.path.write_text("\n".join(lines) + "\n")
        ok, problems = self.log.verify()
        self.assertFalse(ok)

    def test_a_corrupt_line_does_not_brick_the_log(self):
        """One partial write used to make the log permanently unreadable AND
        unwritable, blocking every future screening run."""
        with self.path.open("a") as fh:
            fh.write('{"seq": 7, "ts": "truncated mid-w\n')
        ok, problems = self.log.verify()
        self.assertFalse(ok)
        self.assertTrue(any("unreadable entry" in p for p in problems))
        # And appends must still work rather than raising.
        entry = self.log.append("run.end", {"after": "corruption"})
        self.assertEqual(entry["seq"], 7)

    def test_head_survives_a_corrupt_line(self):
        with self.path.open("a") as fh:
            fh.write("not json at all\n")
        seq, digest = self.log.head()
        self.assertEqual(seq, 6)
        self.assertEqual(len(digest), 64)


class TestRetryCannotDowngrade(unittest.TestCase):
    """Each retry replaced the adjudications wholesale, so a worker that said
    SAME_PARTY (BLOCKED) and then flipped to DIFFERENT_PARTY (REVIEW) after an
    unrelated critic objection quietly downgraded the case -- and the CLI exit
    code with it, 3 to 2."""

    def _case(self) -> ScreeningResult:
        r = ScreeningResult(subject=SubjectParty(ref="C-1", name="Acme").to_dict())
        r.candidates = [Candidate(listed_uid="SDN:1", listed_name="ACME",
                                  listed_source="SDN", score=1.0, band="EXACT").to_dict()]
        r.rule_flags = [{"rule_id": "LIST.SDN", "severity": "prohibitive", "title": "",
                         "basis": "", "detail": "", "action_required": ""}]
        return r

    def test_a_reversal_across_passes_escalates(self):
        from xscreen.critic import run_loop
        from xscreen.tests.test_critic import critic_payload
        from xscreen.tests.test_guardrails import FakeBackend

        attempts = {"n": 0}

        def adjudicate(result, brief):
            attempts["n"] += 1
            result.disposition = "BLOCKED" if attempts["n"] == 1 else "REVIEW"
            return result

        # Critic fails the first pass, passes the (weakened) second.
        class Alternating:
            name = "fake:alternating"

            def __init__(self):
                self.calls = 0

            def complete_json(self, system, user, max_tokens=2000):
                self.calls += 1
                if self.calls == 1:
                    return critic_payload(verdict="FAIL", risk=0.9)
                return critic_payload()

        result, reviews, route = run_loop(self._case(), adjudicate, Alternating())
        self.assertEqual(route.action, "ESCALATE")
        self.assertEqual(result.disposition, "BLOCKED",
                         "the loop accepted a weaker conclusion from a later pass")
        self.assertTrue(result.requires_human)

    def test_a_stable_conclusion_still_commits(self):
        from xscreen.critic import run_loop
        from xscreen.tests.test_critic import critic_payload
        from xscreen.tests.test_guardrails import FakeBackend

        def adjudicate(result, brief):
            result.disposition = "BLOCKED"
            return result

        result, _, route = run_loop(self._case(), adjudicate, FakeBackend(critic_payload()))
        self.assertEqual(route.action, "COMMIT")
        self.assertEqual(result.disposition, "BLOCKED")


class TestNonBackendErrorsDoNotAbortTheRun(unittest.TestCase):
    """`Backend` is a Protocol; a custom transport raising TimeoutError used to
    abort the whole run mid-file, leaving results unwritten and the audit log
    holding a run.start with no run.end."""

    def _result(self) -> ScreeningResult:
        r = ScreeningResult(subject=SubjectParty(ref="C-1", name="Acme").to_dict())
        r.candidates = [Candidate(listed_uid="SDN:1", listed_name="ACME",
                                  listed_source="SDN", score=0.95, band="STRONG").to_dict()]
        return r

    def test_arbitrary_exception_becomes_uncertain(self):
        from xscreen.adjudicate import adjudicate_result

        class Exploding:
            name = "fake:boom"

            def complete_json(self, system, user, max_tokens=2000):
                raise TimeoutError("upstream went away")

        r = adjudicate_result(self._result(), Exploding())
        self.assertEqual(r.adjudications[0]["verdict"], "UNCERTAIN")
        self.assertIn("TimeoutError", r.adjudications[0]["rationale"])

    def test_critic_survives_an_arbitrary_exception(self):
        from xscreen.critic import review

        class Exploding:
            name = "fake:boom"

            def complete_json(self, system, user, max_tokens=2000):
                raise KeyError("nope")

        rev = review(self._result(), Exploding())
        self.assertEqual(rev.verdict, "FAIL")
        self.assertIn("KeyError", rev.infra_error)

    def test_top_level_array_is_a_backend_error_not_a_crash(self):
        from xscreen.llm import BackendError, extract_json

        for payload in ('[{"listed_uid": "x"}]', "123", "null", '"a string"'):
            with self.assertRaises(BackendError, msg=payload):
                extract_json(payload)


class TestClosedSetViolationEscalates(unittest.TestCase):
    def test_discarded_marker_reaches_the_disposition(self):
        from xscreen.adjudicate import adjudicate_result, resolve_disposition
        from xscreen.tests.test_guardrails import FakeBackend, make_result

        payload = {"adjudications": [
            {"listed_uid": "SDN:1001", "verdict": "DIFFERENT_PARTY", "confidence": 0.9,
             "rationale": "x", "discriminating_evidence": []},
            {"listed_uid": "SDN:INVENTED", "verdict": "SAME_PARTY", "confidence": 0.9,
             "rationale": "y", "discriminating_evidence": []},
        ]}
        r = resolve_disposition(adjudicate_result(make_result(), FakeBackend(payload)))
        self.assertEqual(r.disposition, "ESCALATE")
        self.assertTrue(r.requires_human)


class TestHostileInputIsBounded(unittest.TestCase):
    """A 13 KB counterparty name -- comfortably inside the csv field limit --
    cost minutes per row, so a hostile or corrupt name field could wedge the
    nightly screening job indefinitely. Given the gate semantics, an unbounded
    run is functionally a bypass."""

    def test_over_long_names_are_truncated_and_disclosed(self):
        import csv
        import io

        from xscreen.pipeline import MAX_NAME_CHARS, parse_party_file

        buf = io.StringIO()
        w = csv.writer(buf, lineterminator="\n")
        w.writerow(["ref", "name"])
        w.writerow(["bad", "Northwind " + ("Padding " * 2000)])
        subjects, warnings = parse_party_file(buf.getvalue())
        self.assertEqual(len(subjects[0].name), MAX_NAME_CHARS)
        self.assertTrue(any("truncated" in x for x in warnings),
                        "truncation was silent")

    def test_alias_count_is_bounded_and_disclosed(self):
        import csv
        import io

        from xscreen.pipeline import MAX_ALIASES, parse_party_file

        buf = io.StringIO()
        w = csv.writer(buf, lineterminator="\n")
        w.writerow(["ref", "name", "aka"])
        w.writerow(["bad", "Acme", ";".join(f"Alias{i}" for i in range(500))])
        subjects, warnings = parse_party_file(buf.getvalue())
        self.assertEqual(len(subjects[0].aliases), MAX_ALIASES)
        self.assertTrue(any("only the first" in x for x in warnings))

    def test_capping_the_edit_distance_never_changes_a_band(self):
        """The cap is only sound if a capped distance cannot alter a verdict."""
        from xscreen import match as m
        from xscreen.match import ListIndex, assign_band, score_pair

        idx = ListIndex()
        for name in ["Northwind Heavy Machinery OAO", "Gazprom Neft",
                     "Acme Precision Machining Corp", "Sunny Day Bakery LLC",
                     "PETROV, Vasiliy Ivanovich", "Zenith Precision Instruments"]:
            idx.add(ListedParty(uid=f"SDN:{name[:4]}", source="SDN",
                                native_id=name[:4], name=name))
        idx.build()

        probes = [e.listed_name for e in idx.entries] + [
            "Northwind Heavy Machinry", "Gazprom", "Acme", "Vasiliy Petroff",
            "Zenith Precision", "Completely Unrelated Holdings AG",
        ]
        def bands() -> dict:
            out = {}
            for e in idx.entries:
                for n in probes:
                    score, signals = score_pair(n, e, early_exit=False)
                    out[(n, e.listed_name)] = assign_band(score, signals, n, e)
            return out

        capped = bands()
        real = m.levenshtein_ratio
        try:
            # Force the uncapped path and recompute every band.
            m.levenshtein_ratio = lambda a, b, floor=0.0: real(a, b, 0.0)
            uncapped = bands()
        finally:
            m.levenshtein_ratio = real

        self.assertEqual(capped, uncapped,
                         "the edit-distance cap changed a band assignment")
        self.assertGreater(len(capped), 40)


class TestReportEscaping(unittest.TestCase):
    def test_markup_in_a_counterparty_name_is_neutralized(self):
        from xscreen.report import markdown_report

        r = ScreeningResult(
            subject={"ref": "X-1", "name": '<img src=x onerror="alert(1)">'},
            disposition="REVIEW", disposition_reason="test")
        md = markdown_report([r], {"dispositions": {"REVIEW": 1}})
        self.assertNotIn("<img", md)
        self.assertIn("&lt;img", md)


if __name__ == "__main__":
    unittest.main()


class TestOfflineBackendIsRecognized(unittest.TestCase):
    """Regression for the P2 review finding.

    `get_backend()` returns the offline sentinel rather than raising when
    nothing is configured, so a caller catching only BackendError carried it
    into the pipeline. Every case then burned four failing adjudications and
    four failing critic passes before landing on ESCALATE, instead of the
    documented deterministic human-review path.
    """

    def test_default_environment_yields_the_offline_sentinel(self):
        from xscreen.llm import get_backend, is_offline

        saved = {k: os.environ.pop(k, None)
                 for k in ("XSCREEN_BACKEND", "XSCREEN_LLM_BASE_URL",
                           "XSCREEN_LLM_MODEL", "ANTHROPIC_API_KEY")}
        try:
            self.assertTrue(is_offline(get_backend()))
        finally:
            for k, v in saved.items():
                if v is not None:
                    os.environ[k] = v

    def test_is_offline_recognizes_none_and_name(self):
        from xscreen.llm import OfflineBackend, is_offline

        self.assertTrue(is_offline(None))
        self.assertTrue(is_offline(OfflineBackend()))

        class Custom:
            name = "offline"

        self.assertTrue(is_offline(Custom()), "a backend advertising offline was not recognized")

    def test_a_real_backend_is_not_offline(self):
        from xscreen.llm import is_offline
        from xscreen.tests.test_guardrails import FakeBackend

        self.assertFalse(is_offline(FakeBackend()))

    def test_cli_disables_model_stages_when_unconfigured(self):
        """The whole point: an unconfigured install must not enter the loop."""
        import io
        import shutil
        import contextlib
        from xscreen.cli import main

        tmp = Path(tempfile.mkdtemp())
        try:
            data = tmp / "lists"
            data.mkdir(parents=True)
            for f in FIX.glob("*.raw"):
                shutil.copy(f, data / f.name)
            refresh(data, FULL, offline=True)

            saved = {k: os.environ.pop(k, None)
                     for k in ("XSCREEN_BACKEND", "XSCREEN_LLM_BASE_URL",
                               "XSCREEN_LLM_MODEL", "ANTHROPIC_API_KEY")}
            err = io.StringIO()
            try:
                with contextlib.redirect_stderr(err):
                    code = main(["--home", str(tmp), "screen",
                                 str(FIX / "parties.csv"), "--as-of", "2026-01-15",
                                 "--out", str(tmp / "run")])
            finally:
                for k, v in saved.items():
                    if v is not None:
                        os.environ[k] = v

            self.assertIn("No model backend configured", err.getvalue())
            self.assertEqual(code, 2, "expected human-review exit, not an escalation storm")

            import csv as _csv
            rows = list(_csv.DictReader((tmp / "run" / "dispositions.csv").open()))
            self.assertNotIn("ESCALATE", {r["disposition"] for r in rows},
                             "unconfigured install produced ESCALATE cases")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
