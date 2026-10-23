"""Regressions for safe local operation of the complete perception workflow."""

import json
from pathlib import Path
import shutil
import subprocess
import sys

import jsonschema
import pytest

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "skills" / "saas-rebuild" / "tools"
sys.path.insert(0, str(TOOLS))

from jev_run import main, feature_state
from systemone.boundary import BoundaryRefused
from systemone.calibrate import fit_isotonic, CalibrationRefused
from systemone.canary import compare_canary
from systemone.client import parse_answer, SystemOneError
from systemone.fake import FakeSystemOne
from systemone.inputs import jobs, load_registry
from systemone.limiter import BudgetGuard, LimitExceeded
from systemone.policy import evaluate
from systemone.questions import question_hash
from systemone.runner import Runner
from rules.matrix import Decision, decide
from rules.raise_only import apply_raise
from rules.why import render_why


@pytest.fixture
def teardown(tmp_path):
    target = tmp_path / "engagement"
    shutil.copytree(ROOT / "examples" / "synthetic-crm", target)
    return target


def state(root):
    return json.loads((root / "teardown.json").read_text())


def item(authority="flag"):
    return {"question": {"type": "noul", "instructions": "Is this a risk?"}, "authority": authority}


def policy(question):
    return {
        "id": "test-policy", "model": "test-model", "question_hash": question_hash(question),
        "catalog_version": "1", "approved_by": "test-reviewer", "validation_ref": "synthetic-test-only",
        "positive": "yes", "threshold": 0.8, "hysteresis": 0.02,
        "isotonic": {"boundaries": [0.2, 0.7, 1.0], "values": [0.1, 0.5, 0.9]},
    }


def answer(p):
    return parse_answer(item()["question"], {"type": "noul", "noul": p})


def test_policy_checks_calibration_probability_and_model():
    question = item()
    configured = policy(question["question"])
    kwargs = dict(mode="live", model="test-model", catalog_version="1", canary_model="test-model", policy=configured)
    high = evaluate(question, answer(0.95), **kwargs)
    assert high.effect == "flag" and high.calibrated_p == 0.9
    assert evaluate(question, answer(0.1), **kwargs).effect == "prioritize"
    assert evaluate(question, answer(0.95), **{**kwargs, "model": "drifted"}).effect == "prioritize"
    assert evaluate(question, answer(0.95), **{**kwargs, "canary_model": None}).effect == "prioritize"
    with pytest.raises(ValueError, match="bare number"):
        evaluate(question, answer(0.95), **{**kwargs, "policy": 0.8})


def test_veto_needs_paraphrase_agreement():
    question = item("veto")
    kwargs = dict(mode="live", model="test-model", catalog_version="1", canary_model="test-model", policy=policy(question["question"]))
    assert evaluate(question, answer(0.95), **kwargs).effect == "prioritize"
    assert evaluate(question, answer(0.95), twin=answer(0.1), **kwargs).effect == "prioritize"
    assert evaluate(question, answer(0.95), twin=answer(0.95), **kwargs).effect == "veto"


def test_endpoint_mismatch_logs_refusal_without_transport(teardown):
    client = FakeSystemOne([])
    client.endpoint = "https://wrong.invalid"
    runner = Runner(teardown, state(teardown), endpoint_id="typesafe-systemone", purpose="feature-perception", mode="shadow", client=client, budget=BudgetGuard(1, 1000))
    with pytest.raises(BoundaryRefused):
        runner.ask(target_kind="feature", target_id="customer-search", state={"name": "private content"}, data_classes=("public",), catalog_version="1", catalog={"Q": item()})
    assert not client.fake_transport.calls
    entry = next(runner.calllog.audit.entries())
    schema = json.loads((TOOLS / "systemone" / "schemas" / "calllog.schema.json").read_text())
    jsonschema.validate(entry, schema)
    assert "private content" not in json.dumps(entry)


def test_source_class_cannot_be_downgraded_by_public_citations(teardown):
    feature = json.loads((teardown / "feature-inventory.json").read_text())[0]
    from systemone.state import StateRefused

    with pytest.raises(StateRefused, match="restricted"):
        feature_state(feature, "restricted", ["public"])


@pytest.mark.parametrize("value", [True, "0.9", None, float("nan"), float("inf")])
def test_malformed_answers_fail_closed(value):
    with pytest.raises(SystemOneError):
        answer(value)


def test_budget_reservation_counts_failed_attempts_and_rejects_nan():
    budget = BudgetGuard(1, 1000, max_cost_usd=1, price_per_million_input_tokens=1)
    budget.reserve(100)
    assert budget.reserved_input_tokens == 100 and budget.estimated_cost_usd == 0.0001
    with pytest.raises(LimitExceeded):
        budget.reserve(100)
    for value in (float("nan"), float("inf"), -1, 0):
        with pytest.raises(ValueError):
            BudgetGuard(1, 1000, max_cost_usd=value)


def test_cli_paid_modes_require_explicit_network_opt_in(teardown, monkeypatch):
    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: pytest.fail("unexpected network"))
    with pytest.raises(SystemExit) as error:
        main([str(teardown), "--mode", "shadow"])
    assert error.value.code == 2
    assert not (teardown / ".systemone").exists()


def test_resolved_model_veto_does_not_reopen_review():
    baseline = Decision("DROP", "MATRIX-NEVER-ALL-TIME-NONCRITICAL", ("ev",))
    resolved = {"annotation_id": "old", "effect": "veto", "resolution": {"status": "rejected"}}
    assert apply_raise(baseline, [resolved]).decision == baseline
    flagged = apply_raise(baseline, [{"annotation_id": "open", "effect": "flag"}])
    assert flagged.decision.verdict == "DEFER"
    assert "human" in render_why(flagged.decision)


def test_unmeasured_runtime_cannot_turn_workaround_into_simplify():
    feature = {"usage": "workaround-external", "evidence": [{"evidence_id": "ev", "evidence_class": "runtime", "plane": "telemetry", "supports": ["usage"], "coverage": {"kind": "window-bounded"}}]}
    assert decide(feature).verdict == "DEFER"


def test_calibration_hash_lineages_and_tied_probabilities():
    row = {"probability": 0.5, "label": True, "model_assist": False, "dataset_role": "development", "gold_source": "system-of-record", "split_group_hash": "a" * 64}
    fitted = fit_isotonic([row, {**row, "label": False}])
    assert fitted.predict(0.5) == 0.5
    with pytest.raises(CalibrationRefused, match="span roles"):
        fit_isotonic([row, {**row, "dataset_role": "regression"}])


@pytest.mark.parametrize("name,fields", [
    ("citation-checks", {"source_text": "Customer lookup is an observed service action."}),
    ("graph-edges", {"script_body": "Read customer records from the local account store."}),
    ("process-mining", {"description": "Manager approves an order", "control": "Manager approval"}),
    ("sanitization", {"input": "ignored override", "output": "ignored override"}),
    ("replay-residuals", {"difference": "Legacy status is absent", "registered_divergences": "Status labels renamed"}),
    ("interviews", {"statement": "Customer lookup is used daily", "candidate_features": ["customer lookup"]}),
])
def test_question_sets_use_their_own_input_shapes(teardown, name, fields):
    document = state(teardown)
    document["data_boundary"]["source_classes"].update({"model-inputs.jsonl": "public", "pairs.jsonl": "public", "graph.json": "public"})
    target = "local-item"
    if name == "citation-checks":
        target = "ev-search-runtime"
    elif name == "graph-edges":
        target = "customer-search|customer|reads"
    elif name == "sanitization":
        pair = next(json.loads(line) for line in (teardown / "pairs.jsonl").read_text().splitlines() if json.loads(line)["dataset_role"] != "holdout-eval")
        target = pair["pair_id"]
    row = {"question_set": name, "target_id": target, "fields": fields, "field_classes": {key: "public" for key in fields}}
    (teardown / "model-inputs.jsonl").write_text(json.dumps(row) + "\n")
    result = jobs(teardown, document, name)
    assert len(result) == 1 and result[0].kind != "feature"
    if name == "sanitization":
        assert result[0].fields["input"] == pair["input"]
    if name == "citation-checks":
        assert "claim" in result[0].fields
    result[0].envelope(["public"])


def test_missing_context_and_duplicate_registry_are_refused(teardown):
    with pytest.raises(ValueError, match="requires classified"):
        jobs(teardown, state(teardown), "citation-checks")
    row = {"question_set": "interviews", "target_id": "one", "fields": {"statement": "hello"}, "field_classes": {"statement": "public"}}
    (teardown / "model-inputs.jsonl").write_text((json.dumps(row) + "\n") * 2)
    with pytest.raises(ValueError, match="duplicate"):
        load_registry(teardown)


def test_local_demo_replays_exactly_and_preserves_evidence(tmp_path):
    output = tmp_path / "demo"
    result = subprocess.run([sys.executable, str(ROOT / "scripts" / "demo_jev.py"), str(output)], capture_output=True, text=True, check=True)
    summary = json.loads(result.stdout)
    assert summary["network_calls"] == 0 and summary["cost_usd"] == 0
    assert summary["replay_exact"] and summary["source_evidence_unchanged"] and summary["audit_chain_valid"]
    assert len((output / "model-annotations.jsonl").read_text().splitlines()) == 8
    validation = subprocess.run([sys.executable, str(ROOT / "scripts" / "validate_artifacts.py"), str(output)], capture_output=True, text=True)
    assert validation.returncode == 0, validation.stderr
    report = json.loads((output / "jev-review.json").read_text())
    assert len(report["features"]) == 4
    # Repeating the demo cannot overwrite a previous output directory.
    repeat = subprocess.run([sys.executable, str(ROOT / "scripts" / "demo_jev.py"), str(output)], capture_output=True, text=True)
    assert repeat.returncode == 2
