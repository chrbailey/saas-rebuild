"""Contract, safety, and offline-equivalence tests for optional Jev support."""

from __future__ import annotations

import ast
import copy
import hashlib
import json
from pathlib import Path
import random
import subprocess
import sys
import urllib.error

import jsonschema
import pytest


ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "skills" / "saas-rebuild" / "tools"
SYSTEMONE = TOOLS / "systemone"
sys.path.insert(0, str(TOOLS))

from rules.matrix import Decision, decide  # noqa: E402
from rules.raise_only import apply_raise  # noqa: E402
from systemone.audit import AuditLog  # noqa: E402
from systemone.boundary import BoundaryRefused, open_ticket  # noqa: E402
from systemone.cache import CacheMiss, ResponseCache, cache_key  # noqa: E402
from systemone.calibrate import CalibrationRefused, IsotonicModel, fit_isotonic, sprt  # noqa: E402
from systemone.client import ENDPOINT, SystemOne  # noqa: E402
from systemone.fake import FakeSystemOne, FakeTransport  # noqa: E402
from systemone.limiter import BudgetGuard, LimitExceeded  # noqa: E402
from systemone.questions import Choice, Noul, Score, question_hash, to_wire  # noqa: E402
from systemone.runner import CalibratedThreshold, Runner, ThresholdSet  # noqa: E402
from systemone.state import StateRefused, build_state  # noqa: E402
from systemone.transport import post_json  # noqa: E402


def example_state() -> dict:
    return json.loads((ROOT / "examples" / "synthetic-crm" / "teardown.json").read_text())


def file_hashes(root: Path) -> dict[str, str]:
    return {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in root.rglob("*")
        if path.is_file()
    }


def test_exact_wire_contract_and_all_answer_types():
    body = {
        "model": "jev-contract-test",
        "answers": {
            "c": {"type": "choice", "choice": "a", "probabilities": {"a": 0.8, "b": 0.2}, "confidence": 0.8},
            "s": {"type": "score", "score": 1.4, "probabilities": {"0": 0.1, "1": 0.4, "2": 0.5}, "confidence": 0.7, "legend": {"0": "low", "1": "mid", "2": "high"}},
            "n": {"type": "noul", "noul": 0.75},
        },
        "usage": {"input_tokens": 91, "output_tokens": 17},
    }
    transport = FakeTransport([(body, {"x-request-id": "req-1"})])
    client = SystemOne(api_key="test-only", transport=transport)
    result = client.ask(
        {"claim": "bounded text"},
        {
            "c": Choice("pick", {"a": "A", "b": "B"}),
            "s": Score("rate", ["low", "mid", "high"]),
            "n": Noul("true or false"),
        },
    )
    assert transport.calls[0]["url"] == ENDPOINT
    assert transport.calls[0]["headers"]["authorization"] == "[REDACTED]"
    assert set(transport.calls[0]["payload"]) == {"state", "model", "questions"}
    assert result.answers["c"].value == "a"
    assert result.answers["s"].value == 1.4
    assert result.answers["n"].confidence is None
    assert result.usage == {"input_tokens": 91, "output_tokens": 17}


def test_pinned_live_feature_fixture_parses_against_catalog():
    fixture = json.loads((ROOT / "tests" / "fixtures" / "systemone" / "jev-1.13.0-feature-perception.json").read_text())
    catalog = json.loads((SYSTEMONE / "catalog" / "feature-perception.json").read_text())
    client = FakeSystemOne([(fixture, {})])
    response = client.ask({"name": "synthetic customer search"}, {key: item["question"] for key, item in catalog["questions"].items()})
    assert response.model == "jev-1.13.0"
    assert response.usage == {"input_tokens": 925, "output_tokens": 301}
    assert set(response.answers) == set(catalog["questions"])


def test_question_bounds_are_enforced():
    with pytest.raises(ValueError):
        to_wire(Choice("pick", {"only": "one"}))
    with pytest.raises(ValueError):
        to_wire(Score("rate", ["only one"]))
    with pytest.raises(ValueError):
        to_wire(Noul("", None))


def test_transport_retries_retry_after(monkeypatch):
    calls = []
    sleeps = []

    class Response:
        headers = {"X-Request-ID": "retry-ok"}

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return b'{"ok":true}'

    def urlopen(*args, **kwargs):
        calls.append((args, kwargs))
        if len(calls) == 1:
            raise urllib.error.HTTPError(ENDPOINT, 429, "limited", {"Retry-After": "2"}, None)
        return Response()

    monkeypatch.setattr("urllib.request.urlopen", urlopen)
    body, headers = post_json(ENDPOINT, {"authorization": "Bearer test"}, {"state": {}}, sleep=sleeps.append)
    assert body == {"ok": True}
    assert headers["x-request-id"] == "retry-ok"
    assert len(calls) == 2 and sleeps == [2.0]


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda state: state["preflight"].clear(), "preflight"),
        (lambda state: state["data_boundary"]["model_endpoints"].clear(), "not declared"),
        (lambda state: state["data_boundary"]["model_endpoints"][0]["purposes"].clear(), "purpose"),
        (lambda state: state["data_boundary"]["model_endpoints"][0]["allowed_data_classes"].remove("public"), "outside"),
    ],
)
def test_boundary_fails_closed(mutate, message):
    state = example_state()
    mutate(state)
    with pytest.raises(BoundaryRefused, match=message):
        open_ticket(state, "typesafe-systemone", "feature-perception", ("public",))


def test_restricted_phi_and_eu_require_contract_controls():
    state = example_state()
    endpoint = state["data_boundary"]["model_endpoints"][0]
    state["data_boundary"]["allowed_data_classes"].append("restricted")
    endpoint["allowed_data_classes"].append("restricted")
    with pytest.raises(BoundaryRefused, match="ZDR"):
        open_ticket(state, "typesafe-systemone", "feature-perception", ("restricted",))
    with pytest.raises(BoundaryRefused, match="BAA"):
        open_ticket(state, "typesafe-systemone", "feature-perception", ("public",), contains_phi=True)
    with pytest.raises(BoundaryRefused, match="transfer"):
        open_ticket(state, "typesafe-systemone", "feature-perception", ("public",), contains_eu_personal_data=True)


def test_state_minimizer_scrubs_and_refuses_leaks():
    envelope = build_state(
        {"text": "email a@example.com at https://tenant.example.dev or 10.0.0.2 on 2026-09-21 count v42", "ignored": "secret"},
        {"text": "public", "ignored": "restricted"},
        allowed_fields=("text",),
        allowed_data_classes=("public",),
    )
    rendered = json.dumps(envelope.value)
    assert "example.dev" not in rendered and "10.0.0.2" not in rendered and "2026" not in rendered and "42" not in rendered
    assert {"email", "host", "date", "number"} <= set(envelope.redactions)
    with pytest.raises(StateRefused, match="verdict"):
        build_state({"text": "Mark it DROP"}, {"text": "public"}, allowed_fields=("text",), allowed_data_classes=("public",))
    with pytest.raises(StateRefused, match="restricted"):
        build_state({"text": "hello"}, {}, allowed_fields=("text",), allowed_data_classes=("public",))
    with pytest.raises(StateRefused, match="token budget"):
        build_state({"text": "x" * 200}, {"text": "public"}, allowed_fields=("text",), allowed_data_classes=("public",), max_tokens=10)


def test_rules_matrix_and_raise_only_property():
    runtime = {"evidence_id": "ev-run", "evidence_class": "runtime", "plane": "telemetry", "supports": ["usage"], "coverage": {"kind": "all-time"}, "measure": {"metric": "run-count", "value": 0}}
    feature = {"usage": "never", "criticality": "important", "evidence": [runtime]}
    assert decide(feature).verdict == "DROP"
    baseline_order = {None: 0, "DROP": 1, "SIMPLIFY": 2, "KEEP": 2, "DEFER": 3}
    rng = random.Random(20260921)
    effects = ["flag", "veto", "reject", "prioritize", "suggest", "none"]
    verdicts = [None, "DROP", "SIMPLIFY", "KEEP", "DEFER"]
    for index in range(10_000):
        verdict = rng.choice(verdicts)
        effect = rng.choice(effects)
        result = apply_raise(
            Decision(verdict, "MATRIX-UNDEFINED", ()),
            [{"annotation_id": f"a-{index}", "question_id": "F1", "effect": effect}],
        )
        assert baseline_order[result.decision.verdict] >= baseline_order[verdict]
        assert result.decision.verdict != "DROP" or verdict == "DROP"
    unchanged = apply_raise(Decision("KEEP", "MATRIX-RUNTIME-CRITICAL", ("ev",)), [])
    assert unchanged.decision == Decision("KEEP", "MATRIX-RUNTIME-CRITICAL", ("ev",))


def test_cache_calllog_runner_and_replay(tmp_path):
    catalog = {"F2": {"question": {"type": "noul", "instructions": "Is this regulated?"}, "authority": "veto", "consumer": "rules.raise_only", "gold": None}}
    response = ({"model": "jev-test", "answers": {"F2": {"type": "noul", "noul": 0.9}}, "usage": {"input_tokens": 20, "output_tokens": 3}}, {"x-request-id": "req"})
    client = FakeSystemOne([response])
    runner = Runner(tmp_path, example_state(), endpoint_id="typesafe-systemone", purpose="feature-perception", mode="shadow", client=client, budget=BudgetGuard(1, 100))
    annotations = runner.ask(target_kind="feature", target_id="customer-search", state={"name": "search"}, data_classes=("public",), catalog_version="1", catalog=catalog)
    assert annotations[0]["effect"] == "none"
    assert client.fake_transport.calls
    assert runner.calllog.verify() == (True, [])
    assert '"name":"search"' not in (tmp_path / ".systemone" / "calls.jsonl").read_text()
    call_schema = json.loads((SYSTEMONE / "schemas" / "calllog.schema.json").read_text())
    call_entry = json.loads((tmp_path / ".systemone" / "calls.jsonl").read_text().splitlines()[0])
    jsonschema.validate(call_entry, call_schema)
    replay_client = FakeSystemOne([])
    replay = Runner(tmp_path, example_state(), endpoint_id="typesafe-systemone", purpose="feature-perception", mode="replay", client=replay_client, budget=BudgetGuard(0, 0))
    replayed = replay.ask(target_kind="feature", target_id="customer-search", state={"name": "search"}, data_classes=("public",), catalog_version="1", catalog=catalog)
    assert replay.cache_hits == 1 and not replay_client.fake_transport.calls
    assert replayed[0]["answer"] == annotations[0]["answer"]


def test_cache_miss_tamper_and_budget_guards(tmp_path):
    cache = ResponseCache(tmp_path / "cache")
    key = cache_key(ENDPOINT, "jev", {"a": 1}, {"q": {"type": "noul"}})
    with pytest.raises(CacheMiss):
        cache.get(key)
    path = cache.put(key, {"model": "jev"})
    path.write_text('{"cache_key":"wrong","response":{}}\n')
    with pytest.raises(ValueError, match="invalid cache"):
        cache.get(key)
    budget = BudgetGuard(1, 10)
    budget.reserve(10)
    budget.record(10)
    with pytest.raises(LimitExceeded):
        budget.reserve(1)
    with pytest.raises(LimitExceeded, match="verified price"):
        BudgetGuard(1, 100, max_cost_usd=5).reserve(10)


def test_audit_chain_detects_tampering(tmp_path):
    log = AuditLog(tmp_path / "audit.jsonl")
    log.append("one", {"safe": True})
    log.append("two", {"safe": True})
    assert log.verify() == (True, [])
    lines = (tmp_path / "audit.jsonl").read_text().splitlines()
    record = json.loads(lines[0])
    record["payload"]["safe"] = False
    lines[0] = json.dumps(record)
    (tmp_path / "audit.jsonl").write_text("\n".join(lines) + "\n")
    assert not log.verify()[0]


def test_calibration_refuses_holdout_and_model_assisted_gold():
    base = {"probability": 0.8, "label": True, "dataset_role": "regression", "split_group": "g1", "gold_source": "system-of-record", "model_assist": False}
    assert fit_isotonic([base]).predict(0.8) == 1.0
    for change in ({"dataset_role": "holdout-eval"}, {"model_assist": True}, {"gold_source": "analyst"}):
        with pytest.raises(CalibrationRefused):
            fit_isotonic([{**base, **change}])
    with pytest.raises(CalibrationRefused, match="span roles"):
        fit_isotonic([base, {**base, "dataset_role": "development"}])
    assert sprt([False] * 100, acceptable_rate=0.05, unacceptable_rate=0.20).decision == "accept"
    assert sprt([True] * 20, acceptable_rate=0.05, unacceptable_rate=0.20).decision == "demote"


def test_catalogs_validate_and_questions_compile():
    schema = json.loads((SYSTEMONE / "schemas" / "catalog.schema.json").read_text())
    catalogs = list((SYSTEMONE / "catalog").glob("*.json"))
    assert {path.stem for path in catalogs} >= {"feature-perception", "sanitization", "replay-residuals"}
    for path in catalogs:
        catalog = json.loads(path.read_text())
        jsonschema.validate(catalog, schema)
        for item in catalog["questions"].values():
            assert to_wire(item["question"])["type"] in {"choice", "score", "noul"}
            assert item["consumer"]


FEATURE_CATALOG = json.loads((SYSTEMONE / "catalog" / "feature-perception.json").read_text())
PINNED_RESPONSE = json.loads((ROOT / "tests" / "fixtures" / "systemone" / "jev-1.13.0-feature-perception.json").read_text())
ANNOTATION_SCHEMA = json.loads((ROOT / "skills" / "saas-rebuild" / "templates" / "model-annotations.schema.json").read_text())


def run_once(tmp_path, mode, catalog, body, thresholds=None):
    runner = Runner(tmp_path, example_state(), endpoint_id="typesafe-systemone", purpose="feature-perception", mode=mode, client=FakeSystemOne([(body, {})]), budget=BudgetGuard(1, 10_000))
    records = runner.ask(target_kind="feature", target_id="customer-search", state={"name": "synthetic customer search"}, data_classes=("public",), catalog_version="1", catalog=catalog, thresholds=thresholds)
    for record in records:
        jsonschema.validate(record, ANNOTATION_SCHEMA)
    return runner, {record["question_id"]: record for record in records}


def noul_item(authority):
    return {"question": {"type": "noul", "instructions": "Is this regulated?"}, "authority": authority, "consumer": "rules.raise_only", "gold": None}


def noul_body(value):
    return {"model": "jev-test", "answers": {"Q": {"type": "noul", "noul": value}}, "usage": {"input_tokens": 10, "output_tokens": 1}}


def test_pinned_live_answers_only_raise_where_the_answer_says_so(tmp_path):
    """The one real Jev response: F2 answered 0.24 ("no regulated obligation").

    Uncalibrated, nothing may veto; a negative answer must not even prioritize.
    """

    _, records = run_once(tmp_path, "live", FEATURE_CATALOG["questions"], PINNED_RESPONSE)
    effects = {question_id: record["effect"] for question_id, record in records.items()}
    assert effects == {
        "F1": "none",      # intraday: the rare-cadence trigger holds 0.06
        "F2": "none",      # 0.24: no regulated obligation
        "F3": "none",      # 0.12: no external integration
        "F4": "none",      # 0.12: no workaround
        "F5": "suggest",   # an untriggered choice only offers its answer
        "F6": "suggest",
        "F7": "none",      # "hard" holds 0.46, below the routing cutoff
        "F8": "none",      # 0.06: not a test or demo label
    }
    assert not {"veto", "flag", "reject"} & set(effects.values())
    assert all(record["calibrated_p"] is None and record["threshold_set_id"] is None for record in records.values())


@pytest.mark.parametrize("authority", ["veto", "flag", "reject"])
def test_uncalibrated_high_authority_only_routes_affirmative_answers(tmp_path, authority):
    catalog = {"Q": noul_item(authority)}
    assert run_once(tmp_path / "yes", "live", catalog, noul_body(0.9))[1]["Q"]["effect"] == "prioritize"
    assert run_once(tmp_path / "no", "live", catalog, noul_body(0.1))[1]["Q"]["effect"] == "none"


def test_calibrated_threshold_compares_the_answer_not_its_existence(tmp_path):
    catalog = {"Q": noul_item("veto")}
    model = IsotonicModel((0.5, 1.0), (0.1, 0.95))
    thresholds = ThresholdSet("ts-2026-09", {"Q": CalibratedThreshold(question_hash(catalog["Q"]["question"]), model, 0.9)})

    _, above = run_once(tmp_path / "above", "live", catalog, noul_body(0.8), thresholds)
    assert above["Q"]["effect"] == "veto"
    assert above["Q"]["calibrated_p"] == 0.95 and above["Q"]["threshold_set_id"] == "ts-2026-09"

    _, below = run_once(tmp_path / "below", "live", catalog, noul_body(0.3), thresholds)
    assert below["Q"]["effect"] == "none"
    assert below["Q"]["calibrated_p"] == 0.1


def test_threshold_fitted_on_other_question_text_does_not_apply(tmp_path):
    catalog = {"Q": noul_item("veto")}
    stale = ThresholdSet("ts-old", {"Q": CalibratedThreshold("0" * 64, IsotonicModel((1.0,), (1.0,)), 0.5)})
    _, records = run_once(tmp_path, "live", catalog, noul_body(0.9), stale)
    assert records["Q"]["effect"] == "prioritize"
    assert records["Q"]["calibrated_p"] is None and records["Q"]["threshold_set_id"] is None


def test_choice_triggers_decide_what_the_authority_acts_on(tmp_path):
    f1 = FEATURE_CATALOG["questions"]["F1"]
    body = {"model": "jev-test", "answers": {"F1": {"type": "choice", "choice": "annual-or-rarer", "probabilities": {"intraday": 0.0, "daily": 0.0, "weekly": 0.0, "monthly": 0.05, "quarterly": 0.15, "annual-or-rarer": 0.75, "irregular": 0.05}, "confidence": 0.8}}, "usage": {"input_tokens": 10, "output_tokens": 1}}
    thresholds = ThresholdSet("ts-f1", {"F1": CalibratedThreshold(question_hash(f1["question"]), IsotonicModel((1.0,), (0.97,)), 0.9)})
    _, records = run_once(tmp_path / "rare", "live", {"F1": f1}, body, thresholds)
    assert records["F1"]["effect"] == "veto"

    untriggered = {**f1}
    untriggered.pop("trigger")
    _, records = run_once(tmp_path / "untriggered", "live", {"F1": untriggered}, body, thresholds)
    assert records["F1"]["effect"] == "none"


def test_catalog_triggers_name_real_options_and_inert_questions_are_known():
    inert = set()
    for path in (SYSTEMONE / "catalog").glob("*.json"):
        for question_id, item in json.loads(path.read_text())["questions"].items():
            question = item["question"]
            if "trigger" in item:
                assert question["type"] == "choice", question_id
                assert set(item["trigger"]) <= set(question["criteria"]), question_id
            elif question["type"] != "noul" and item["authority"] != "suggest":
                inert.add(question_id)
    # These compare an answer against target-specific evidence (the cited
    # class, the declared edge direction, observed runtime), so no fixed
    # trigger fits. They stay inert until their set-specific comparators exist.
    assert inert == {"C2", "E1", "I2"}


def test_shadow_and_replay_never_mint_effects(tmp_path):
    catalog = FEATURE_CATALOG["questions"]
    shadow, records = run_once(tmp_path, "shadow", catalog, PINNED_RESPONSE)
    assert {record["effect"] for record in records.values()} == {"none"}
    written = shadow.write_annotations()
    before = written.read_bytes()

    replay = Runner(tmp_path, example_state(), endpoint_id="typesafe-systemone", purpose="feature-perception", mode="replay", client=FakeSystemOne([]), budget=BudgetGuard(0, 0))
    replayed = replay.ask(target_kind="feature", target_id="customer-search", state={"name": "synthetic customer search"}, data_classes=("public",), catalog_version="1", catalog=catalog)
    assert {record["effect"] for record in replayed} == {"none"}
    assert [record["answer"] for record in replayed] == [records[key]["answer"] for key in catalog]
    assert replay.write_annotations() is None
    assert written.read_bytes() == before


@pytest.mark.parametrize("effect", ["veto", "flag", "reject"])
def test_annotation_schema_refuses_uncalibrated_high_authority(tmp_path, effect):
    _, records = run_once(tmp_path, "live", {"Q": noul_item("veto")}, noul_body(0.9))
    record = {**records["Q"], "effect": effect}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(record, ANNOTATION_SCHEMA)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({**records["Q"], "calibrated_p": 0.5}, ANNOTATION_SCHEMA)
    jsonschema.validate({**record, "calibrated_p": 0.95, "threshold_set_id": "ts-1"}, ANNOTATION_SCHEMA)


def test_refusal_events_validate_and_stay_content_free(tmp_path):
    call_schema = json.loads((SYSTEMONE / "schemas" / "calllog.schema.json").read_text())
    runner, _ = run_once(tmp_path, "shadow", {"Q": noul_item("veto")}, noul_body(0.9))
    with pytest.raises(BoundaryRefused):
        runner.ask(target_kind="feature", target_id="customer-search", state={"name": "secret tenant text"}, data_classes=("restricted",), catalog_version="1", catalog={"Q": noul_item("veto")})
    # jev_run logs a state-gate refusal before any data class is known.
    runner.record_refusal(target_kind="feature", target_id="customer-search", data_classes=(), gate="state", reason="no approved fields remain after minimization")

    log = (tmp_path / ".systemone" / "calls.jsonl").read_text()
    entries = [json.loads(line) for line in log.splitlines()]
    assert [entry["event"] for entry in entries] == ["jev.call", "jev.gate.refused", "jev.gate.refused"]
    assert [entry["payload"].get("gate") for entry in entries[1:]] == ["boundary", "state"]
    for entry in entries:
        jsonschema.validate(entry, call_schema)
    assert runner.calllog.verify() == (True, [])
    assert "secret tenant text" not in log

    # A refusal payload cannot pose as a call, nor a call as a refusal.
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({**entries[1], "event": "jev.call"}, call_schema)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({**entries[0], "event": "jev.gate.refused"}, call_schema)


def regulated_teardown(declaration, **endpoint_updates):
    state = example_state()
    boundary = state["data_boundary"]
    if declaration is None:
        boundary.pop("regulated_data", None)
    else:
        boundary["regulated_data"] = declaration
    boundary["model_endpoints"][0].update(endpoint_updates)
    return state


@pytest.mark.parametrize(
    ("declaration", "endpoint_updates", "message"),
    [
        (None, {}, "PHI requires a BAA in force"),
        ({"phi": "unknown", "eu_personal_data": "no"}, {}, "PHI requires a BAA in force"),
        ({"phi": "yes", "eu_personal_data": "no"}, {}, "PHI requires a BAA in force"),
        ({"phi": "no", "eu_personal_data": "unknown"}, {}, "EU personal data requires a recorded transfer mechanism"),
        ({"phi": "no", "eu_personal_data": "yes"}, {}, "EU personal data requires a recorded transfer mechanism"),
    ],
)
def test_runner_engages_phi_and_eu_gates_failing_closed(tmp_path, declaration, endpoint_updates, message):
    client = FakeSystemOne([])
    runner = Runner(tmp_path, regulated_teardown(declaration, **endpoint_updates), endpoint_id="typesafe-systemone", purpose="feature-perception", mode="live", client=client, budget=BudgetGuard(1, 10_000))
    with pytest.raises(BoundaryRefused, match=message):
        runner.ask(target_kind="feature", target_id="customer-search", state={"name": "x"}, data_classes=("public",), catalog_version="1", catalog={"Q": noul_item("veto")})
    assert not client.fake_transport.calls
    entry = json.loads((tmp_path / ".systemone" / "calls.jsonl").read_text().splitlines()[-1])
    assert entry["event"] == "jev.gate.refused" and message in entry["payload"]["reason"]


def test_runner_calls_once_regulated_data_is_covered(tmp_path):
    covered = regulated_teardown(
        {"phi": "yes", "eu_personal_data": "yes"},
        baa={"status": "in-force", "ref": "baa-2026"},
        transfer_mechanism="EU SCCs 2021/914",
    )
    runner = Runner(tmp_path, covered, endpoint_id="typesafe-systemone", purpose="feature-perception", mode="shadow", client=FakeSystemOne([(noul_body(0.9), {})]), budget=BudgetGuard(1, 10_000))
    records = runner.ask(target_kind="feature", target_id="customer-search", state={"name": "x"}, data_classes=("public",), catalog_version="1", catalog={"Q": noul_item("veto")})
    assert records[0]["effect"] == "none"


def test_runner_refuses_a_client_aimed_at_another_endpoint(tmp_path):
    client = FakeSystemOne([])
    client.endpoint = "https://example.invalid/v1/systemone"
    runner = Runner(tmp_path, example_state(), endpoint_id="typesafe-systemone", purpose="feature-perception", mode="live", client=client, budget=BudgetGuard(1, 10_000))
    with pytest.raises(BoundaryRefused, match="differs from the approved endpoint"):
        runner.ask(target_kind="feature", target_id="customer-search", state={"name": "x"}, data_classes=("public",), catalog_version="1", catalog={"Q": noul_item("veto")})
    assert not client.fake_transport.calls


def test_systemone_runtime_has_no_third_party_imports():
    standard = set(sys.stdlib_module_names)
    local = {path.stem for path in SYSTEMONE.glob("*.py")} | {"systemone"}
    for path in SYSTEMONE.rglob("*.py"):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots = {alias.name.split(".")[0] for alias in node.names}
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                roots = {node.module.split(".")[0]}
            else:
                continue
            assert roots <= standard | local, f"third-party import in {path}: {roots - standard - local}"


def test_shared_audit_implementation_stays_byte_identical():
    source = ROOT / "skills" / "export-compliance" / "tools" / "xscreen" / "audit.py"
    assert (SYSTEMONE / "audit.py").read_bytes() == source.read_bytes()


def test_offline_mode_is_byte_equivalent(tmp_path):
    source = ROOT / "examples" / "synthetic-crm"
    target = tmp_path / "teardown"
    import shutil

    shutil.copytree(source, target)
    before = file_hashes(target)
    result = subprocess.run(
        [sys.executable, str(TOOLS / "jev_run.py"), "--mode", "offline", str(target)],
        text=True,
        capture_output=True,
        check=True,
    )
    assert json.loads(result.stdout)["network_calls"] == 0
    assert file_hashes(target) == before
