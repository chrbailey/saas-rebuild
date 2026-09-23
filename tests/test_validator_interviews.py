"""Cross-file invariants for v0.11 interview statements."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from test_validator_model_annotations import annotation


ROOT = Path(__file__).resolve().parent.parent
EXAMPLE = ROOT / "examples" / "synthetic-crm"
VALIDATOR = ROOT / "skills" / "saas-rebuild" / "tools" / "validate_artifacts.py"


def copy_example(tmp_path: Path) -> Path:
    target = tmp_path / "teardown"
    shutil.copytree(EXAMPLE, target)
    return target


def run(target: Path):
    return subprocess.run([sys.executable, str(VALIDATOR), str(target)], text=True, capture_output=True)


def read_statements(target: Path) -> list[dict]:
    return [json.loads(line) for line in (target / "interviews.jsonl").read_text().splitlines() if line.strip()]


def write_statements(target: Path, statements: list[dict]) -> None:
    (target / "interviews.jsonl").write_text("".join(json.dumps(item) + "\n" for item in statements))


def edit_statement(target: Path, statement_id: str, **updates) -> None:
    statements = read_statements(target)
    for statement in statements:
        if statement["statement_id"] == statement_id:
            statement.update(updates)
    write_statements(target, statements)


def edit_citation(target: Path, evidence_id: str, change) -> None:
    """Apply ``change`` to a citation in the inventory and in every pair copy."""

    inventory_path = target / "feature-inventory.json"
    inventory = json.loads(inventory_path.read_text())
    for feature in inventory:
        for citation in feature["evidence"]:
            if citation["evidence_id"] == evidence_id:
                change(citation)
    inventory_path.write_text(json.dumps(inventory, indent=2) + "\n")
    pairs_path = target / "pairs.jsonl"
    pairs = [json.loads(line) for line in pairs_path.read_text().splitlines() if line.strip()]
    for pair in pairs:
        for citation in pair.get("evidence", []):
            if citation["evidence_id"] == evidence_id:
                change(citation)
    pairs_path.write_text("".join(json.dumps(pair) + "\n" for pair in pairs))
    manifest_path = target / "preservation-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    for artifact in manifest["artifacts"]:
        for entry in artifact.get("files", []):
            if entry["path"] == "pairs.jsonl":
                entry["sha256"] = hashlib.sha256(pairs_path.read_bytes()).hexdigest()
                entry["bytes"] = pairs_path.stat().st_size
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")


def edit_state(target: Path, change) -> None:
    path = target / "teardown.json"
    state = json.loads(path.read_text())
    change(state)
    path.write_text(json.dumps(state, indent=2) + "\n")


def remove_interviews(target: Path) -> None:
    (target / "interviews.jsonl").unlink()
    edit_state(target, lambda state: state["artifacts"].pop("interviews"))


def test_example_statements_validate(tmp_path):
    result = run(copy_example(tmp_path))
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    ("updates", "location"),
    [
        ({"verbatim": True}, "interviews.jsonl[0]:sensitivity"),
        ({"consent": {"recorded": False, "scopes": ["teardown", "model-perception"]}}, "interviews.jsonl[0]:consent.recorded"),
        ({"linked_by": None}, "interviews.jsonl[0]:linked_by"),
        ({"respondent": {"respondent_id": "Jane Doe", "role": "service-lead", "user_group": "service"}}, "respondent.respondent_id"),
        ({"topic": "gossip"}, "interviews.jsonl[0]:topic"),
    ],
)
def test_schema_refuses_unsafe_statement_shapes(tmp_path, updates, location):
    target = copy_example(tmp_path)
    edit_statement(target, "st-int-01-01", **updates)
    result = run(target)
    assert result.returncode == 1
    assert location in result.stderr


def test_feature_link_requires_the_analyst_marker(tmp_path):
    target = copy_example(tmp_path)
    statements = read_statements(target)
    del statements[0]["linked_by"]
    write_statements(target, statements)
    result = run(target)
    assert result.returncode == 1
    assert "'linked_by' is a dependency of 'feature_id'" in result.stderr


def test_verbatim_quotes_are_allowed_when_confidential(tmp_path):
    target = copy_example(tmp_path)
    edit_state(target, lambda state: state["data_boundary"]["allowed_data_classes"].append("confidential"))
    edit_statement(target, "st-int-02-02", verbatim=True, sensitivity="confidential")
    result = run(target)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    ("statement_id", "updates", "message"),
    [
        ("st-int-01-01", {"feature_id": "missing-feature"}, "links unknown feature: missing-feature"),
        ("st-int-01-01", {"sensitivity": "internal"}, "sensitivity is outside the approved boundary"),
        ("st-int-02-02", {"text": "Mail ops-lead@example.invalid for the export."}, "email address or phone number"),
        ("st-int-02-02", {"text": "Call +1 (555) 010-4477 when the import fails."}, "email address or phone number"),
    ],
)
def test_cross_file_statement_rules(tmp_path, statement_id, updates, message):
    target = copy_example(tmp_path)
    edit_statement(target, statement_id, **updates)
    result = run(target)
    assert result.returncode == 1
    assert message in result.stderr


def test_dates_and_counts_are_not_mistaken_for_phone_numbers(tmp_path):
    target = copy_example(tmp_path)
    edit_statement(target, "st-int-02-02", text="Imported 12,000 rows on 2026-07-31 and again on 2026-08-01.")
    result = run(target)
    assert result.returncode == 0, result.stderr


def test_duplicate_statement_ids_fail(tmp_path):
    target = copy_example(tmp_path)
    statements = read_statements(target)
    write_statements(target, statements + [statements[-1]])
    result = run(target)
    assert result.returncode == 1
    assert "duplicate interview statement ids: ['st-int-02-02']" in result.stderr


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda citation: citation.pop("statement_ids"), "interview evidence ev-search-criticality must link its statement_ids"),
        (lambda citation: citation.update(statement_ids=["st-missing"]), "links unknown statements: ['st-missing']"),
    ],
)
def test_interview_citations_must_resolve_when_statements_exist(tmp_path, change, message):
    target = copy_example(tmp_path)
    edit_citation(target, "ev-search-criticality", change)
    result = run(target)
    assert result.returncode == 1
    assert message in result.stderr


def test_citation_cannot_be_less_sensitive_than_its_statements(tmp_path):
    target = copy_example(tmp_path)
    edit_state(target, lambda state: state["data_boundary"]["allowed_data_classes"].append("confidential"))
    edit_statement(target, "st-int-01-02", sensitivity="confidential")
    result = run(target)
    assert result.returncode == 1
    assert "ev-search-criticality is public but links a confidential statement" in result.stderr


def test_only_interview_citations_link_statements(tmp_path):
    target = copy_example(tmp_path)
    edit_citation(target, "ev-tax-contract", lambda citation: citation.update(statement_ids=["st-int-01-02"]))
    result = run(target)
    assert result.returncode == 1
    assert "evidence ev-tax-contract links interview statements but is not interview-plane" in result.stderr


def test_without_statements_interview_citations_are_unchanged(tmp_path):
    target = copy_example(tmp_path)
    remove_interviews(target)
    edit_citation(target, "ev-search-criticality", lambda citation: citation.pop("statement_ids"))
    result = run(target)
    assert result.returncode == 0, result.stderr


def test_statement_links_without_statements_fail(tmp_path):
    target = copy_example(tmp_path)
    remove_interviews(target)
    result = run(target)
    assert result.returncode == 1
    assert "links interview statements but interviews.jsonl is absent" in result.stderr


def test_state_pointer_must_name_the_validated_statements(tmp_path):
    target = copy_example(tmp_path)
    shutil.copy(target / "interviews.jsonl", target / "other.jsonl")
    edit_state(target, lambda state: state["artifacts"].update(interviews="other.jsonl"))
    result = run(target)
    assert result.returncode == 1
    assert "must be the validated file interviews.jsonl" in result.stderr


def write_annotation(target: Path, record: dict) -> None:
    (target / "model-annotations.jsonl").write_text(json.dumps(record) + "\n")


def test_statement_annotations_resolve_only_to_real_statements(tmp_path):
    target = copy_example(tmp_path)
    write_annotation(target, annotation(target_kind="interview-statement", target_id="st-int-01-01", question_id="I2"))
    result = run(target)
    assert result.returncode == 0, result.stderr
    write_annotation(target, annotation(target_kind="interview-statement", target_id="st-missing", question_id="I2"))
    result = run(target)
    assert result.returncode == 1
    assert "target does not resolve: interview-statement:st-missing" in result.stderr


def test_open_flag_on_a_linked_statement_blocks_drop(tmp_path):
    target = copy_example(tmp_path)
    flagged = annotation(
        target_kind="interview-statement",
        target_id="st-int-02-01",
        question_id="I2",
        effect="flag",
        calibrated_p=0.93,
        threshold_set_id="ts-test",
    )
    write_annotation(target, flagged)
    result = run(target)
    assert result.returncode == 1
    assert "social-enrichment is DROP despite an open model flag or veto on a linked interview statement" in result.stderr
    write_annotation(target, dict(flagged, effect="prioritize", calibrated_p=None, threshold_set_id=None))
    result = run(target)
    assert result.returncode == 0, result.stderr
