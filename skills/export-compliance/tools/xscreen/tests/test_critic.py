import unittest

from xscreen.critic import CriticReview, review, route, run_loop
from xscreen.llm import BackendError
from xscreen.models import Candidate, ScreeningResult, SubjectParty
from xscreen.tests.test_guardrails import FakeBackend


def make_case(band="STRONG") -> ScreeningResult:
    r = ScreeningResult(subject=SubjectParty(ref="C-1", name="Acme Precision").to_dict())
    r.candidates = [Candidate(listed_uid="SDN:1", listed_name="ACME PRECISION LLC",
                              listed_source="SDN", score=0.93, band=band,
                              listed_party={"name": "ACME PRECISION LLC"}).to_dict()]
    r.adjudications = [{"listed_uid": "SDN:1", "verdict": "DIFFERENT_PARTY",
                        "confidence": 0.8, "rationale": "different country",
                        "discriminating_evidence": [], "model": "fake", "guardrail_override": ""}]
    r.disposition = "REVIEW"
    return r


def critic_payload(verdict="PASS", risk=0.1, findings=None, summary="ok"):
    return {"verdict": verdict, "risk_score": risk,
            "findings": findings or [], "summary": summary}


class TestCriticIndependence(unittest.TestCase):
    def test_critic_never_sees_the_adjudicator_prompt(self):
        from xscreen.adjudicate import SYSTEM_PROMPT as WORKER_PROMPT
        be = FakeBackend(critic_payload())
        review(make_case(), be)
        _, user = be.calls[0]
        self.assertNotIn(WORKER_PROMPT[:200], user)
        self.assertIn("<case_under_review>", user)

    def test_critic_receives_evidence_and_conclusions(self):
        be = FakeBackend(critic_payload())
        review(make_case(), be)
        _, user = be.calls[0]
        for key in ("deterministic_candidates", "adjudications_under_review",
                    "rule_flags", "proposed_disposition"):
            self.assertIn(key, user)

    def test_critic_prompt_is_biased_toward_false_negatives(self):
        from xscreen.critic import CRITIC_SYSTEM
        self.assertIn("dismissed too easily", CRITIC_SYSTEM)
        self.assertIn("strict-liability", CRITIC_SYSTEM)


class TestCriticFailClosed(unittest.TestCase):
    def test_backend_error_is_fail_not_pass(self):
        rev = review(make_case(), FakeBackend(raises=BackendError("timeout")))
        self.assertEqual(rev.verdict, "FAIL")
        self.assertEqual(rev.risk_score, 1.0)
        self.assertIn("timeout", rev.infra_error)

    def test_unrecognized_verdict_is_fail(self):
        rev = review(make_case(), FakeBackend(critic_payload(verdict="LOOKS_GOOD")))
        self.assertEqual(rev.verdict, "FAIL")
        self.assertTrue(rev.infra_error)

    def test_unparseable_risk_score_is_fail(self):
        rev = review(make_case(), FakeBackend({"verdict": "PASS", "risk_score": "low"}))
        self.assertEqual(rev.verdict, "FAIL")

    def test_bad_severity_is_coerced_upward_not_downward(self):
        rev = review(make_case(), FakeBackend(critic_payload(
            findings=[{"listed_uid": "SDN:1", "severity": "trivial",
                       "category": "x", "finding": "y", "suggested_action": "z"}])))
        self.assertEqual(rev.findings[0]["severity"], "major")

    def test_risk_score_is_clamped(self):
        rev = review(make_case(), FakeBackend(critic_payload(risk=42)))
        self.assertEqual(rev.risk_score, 1.0)


class TestRalphRouting(unittest.TestCase):
    def test_pass_low_risk_commits(self):
        self.assertEqual(route(CriticReview("PASS", 0.1), 0).action, "COMMIT")

    def test_pass_but_high_risk_retries(self):
        self.assertEqual(route(CriticReview("PASS", 0.45), 0).action, "RETRY")

    def test_conditional_pass_below_half_commits(self):
        self.assertEqual(route(CriticReview("CONDITIONAL_PASS", 0.4), 0).action, "COMMIT")

    def test_conditional_pass_above_half_retries(self):
        self.assertEqual(route(CriticReview("CONDITIONAL_PASS", 0.6), 0).action, "RETRY")

    def test_critical_finding_blocks_commit_even_at_low_risk(self):
        rev = CriticReview("PASS", 0.05, findings=[{"severity": "critical", "finding": "missed hit"}])
        self.assertEqual(route(rev, 0).action, "RETRY")

    def test_fail_retries_until_the_cap_then_escalates(self):
        rev = CriticReview("FAIL", 0.9)
        self.assertEqual(route(rev, 0).action, "RETRY")
        self.assertEqual(route(rev, 2).action, "RETRY")
        self.assertEqual(route(rev, 3).action, "ESCALATE")

    def test_infra_error_retries_then_escalates_but_never_commits(self):
        rev = CriticReview("FAIL", 1.0, infra_error="boom")
        self.assertEqual(route(rev, 0).action, "RETRY")
        self.assertEqual(route(rev, 3).action, "ESCALATE")

    def test_retry_brief_carries_the_findings(self):
        rev = CriticReview("FAIL", 0.8, findings=[
            {"listed_uid": "SDN:1", "severity": "critical", "finding": "address is weak evidence",
             "suggested_action": "check the identifiers"}])
        brief = route(rev, 0).retry_brief
        self.assertIn("KNOWN_ISSUES", brief)
        self.assertIn("address is weak evidence", brief)
        self.assertIn("check the identifiers", brief)

    def test_retry_brief_orders_critical_first(self):
        rev = CriticReview("FAIL", 0.8, findings=[
            {"listed_uid": "a", "severity": "minor", "finding": "m", "suggested_action": ""},
            {"listed_uid": "b", "severity": "critical", "finding": "c", "suggested_action": ""}])
        brief = route(rev, 0).retry_brief
        self.assertLess(brief.index("[critical]"), brief.index("[minor]"))


class TestLoop(unittest.TestCase):
    def test_commit_on_first_pass_runs_the_worker_once(self):
        calls = []

        def adjudicate(result, brief):
            calls.append(brief)
            return result

        _, reviews, rt = run_loop(make_case(), adjudicate, FakeBackend(critic_payload()))
        self.assertEqual(rt.action, "COMMIT")
        self.assertEqual(len(calls), 1)
        self.assertEqual(len(reviews), 1)

    def test_persistent_failure_escalates_and_marks_the_case(self):
        def adjudicate(result, brief):
            return result

        result, reviews, rt = run_loop(
            make_case(), adjudicate, FakeBackend(critic_payload(verdict="FAIL", risk=0.9)))
        self.assertEqual(rt.action, "ESCALATE")
        self.assertEqual(len(reviews), 4)   # initial attempt plus three retries
        self.assertEqual(result.disposition, "ESCALATE")
        self.assertTrue(result.requires_human)

    def test_retry_brief_reaches_the_worker(self):
        seen = []

        def adjudicate(result, brief):
            seen.append(brief)
            return result

        run_loop(make_case(), adjudicate,
                 FakeBackend(critic_payload(verdict="FAIL", risk=0.9, findings=[
                     {"listed_uid": "SDN:1", "severity": "major",
                      "finding": "weak basis", "suggested_action": "recheck"}])))
        self.assertEqual(seen[0], "")
        self.assertIn("weak basis", seen[1])

    def test_findings_from_every_round_are_retained(self):
        def adjudicate(result, brief):
            return result

        result, _, _ = run_loop(make_case(), adjudicate, FakeBackend(critic_payload(
            verdict="FAIL", risk=0.9,
            findings=[{"listed_uid": "SDN:1", "severity": "major", "finding": "f",
                       "suggested_action": "a"}])))
        self.assertEqual(len(result.critic_findings), 4)
        self.assertEqual({f["review_index"] for f in result.critic_findings}, {0, 1, 2, 3})


if __name__ == "__main__":
    unittest.main()
