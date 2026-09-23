"""Cross-file invariants for v0.10 model annotations."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parent.parent
EXAMPLE = ROOT / "examples" / "synthetic-crm"
VALIDATOR = ROOT / "skills" / "saas-rebuild" / "tools" / "validate_artifacts.py"


def annotation(**updates):
    value = {
        "schema_version": "0.11.0",
        "annotation_id": "ann-test",
        "run_id": "jev-test",
        "target_kind": "feature",
        "target_id": "customer-search",
        "endpoint_id": "typesafe-systemone",
        "sent_data_classes": ["public"],
        "question_id": "F2",
        "question_hash": "0" * 64,
        "catalog_version": "1",
        "model_returned": "jev-test",
        "answer": {"type": "noul", "value": 0.8, "probabilities": None, "confidence": None, "legend": None},
        "calibrated_p": None,
        "threshold_set_id": None,
        "effect": "none",
        "resolution": {"status": "open", "resolved_by": None, "resolved_at": None, "calllog_seq": 1},
        "created_at": "2026-09-21T12:00:00Z",
    }
    value.update(updates)
    return value


def prepare(tmp_path: Path, record: dict) -> Path:
    target = tmp_path / "teardown"
    shutil.copytree(EXAMPLE, target)
    state_path = target / "teardown.json"
    state = json.loads(state_path.read_text())
    state["artifacts"]["model_annotations"] = "model-annotations.jsonl"
    state_path.write_text(json.dumps(state, indent=2) + "\n")
    (target / "model-annotations.jsonl").write_text(json.dumps(record) + "\n")
    return target


def run(target: Path):
    return subprocess.run([sys.executable, str(VALIDATOR), str(target)], text=True, capture_output=True)


def test_valid_model_annotation_resolves(tmp_path):
    result = run(prepare(tmp_path, annotation()))
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    ("record", "message"),
    [
        (annotation(endpoint_id="undeclared"), "unknown endpoint"),
        (annotation(sent_data_classes=["restricted"]), "unapproved data classes"),
        (annotation(target_id="missing-feature"), "target does not resolve"),
        (
            annotation(target_id="social-enrichment", effect="veto", calibrated_p=0.95, threshold_set_id="ts-test"),
            "DROP despite an open model flag or veto",
        ),
        (annotation(effect="veto"), "calibrated_p: None is not of type 'number'"),
        (annotation(calibrated_p=0.5), "threshold_set_id: None is not of type 'string'"),
    ],
)
def test_invalid_model_annotation_fails_closed(tmp_path, record, message):
    result = run(prepare(tmp_path, record))
    assert result.returncode == 1
    assert message in result.stderr


def test_undeclared_annotation_file_is_still_enforced(tmp_path):
    """jev_run never edits teardown.json, so a present annotation file must be
    validated whether or not it is declared; ignoring it would hide a veto."""

    target = prepare(tmp_path, annotation(target_id="social-enrichment", effect="veto", calibrated_p=0.95, threshold_set_id="ts-test"))
    state_path = target / "teardown.json"
    state = json.loads(state_path.read_text())
    del state["artifacts"]["model_annotations"]
    state_path.write_text(json.dumps(state, indent=2) + "\n")
    result = run(target)
    assert result.returncode == 1
    assert "DROP despite an open model flag or veto" in result.stderr


def test_annotations_declared_elsewhere_are_refused(tmp_path):
    target = prepare(tmp_path, annotation())
    (target / "model-annotations.jsonl").rename(target / "other.jsonl")
    state_path = target / "teardown.json"
    state = json.loads(state_path.read_text())
    state["artifacts"]["model_annotations"] = "other.jsonl"
    state_path.write_text(json.dumps(state, indent=2) + "\n")
    result = run(target)
    assert result.returncode == 1
    assert "must be the validated file model-annotations.jsonl" in result.stderr


@pytest.mark.parametrize(
    ("declaration", "message"),
    [
        (None, "PHI is present or undeclared, without a BAA in force"),
        ({"phi": "unknown", "eu_personal_data": "no"}, "PHI is present or undeclared, without a BAA in force"),
        ({"phi": "no", "eu_personal_data": "yes"}, "EU personal data is present or undeclared, without a transfer mechanism"),
    ],
)
def test_annotations_require_regulated_data_coverage(tmp_path, declaration, message):
    target = prepare(tmp_path, annotation())
    state_path = target / "teardown.json"
    state = json.loads(state_path.read_text())
    if declaration is None:
        del state["data_boundary"]["regulated_data"]
    else:
        state["data_boundary"]["regulated_data"] = declaration
    state_path.write_text(json.dumps(state, indent=2) + "\n")
    result = run(target)
    assert result.returncode == 1
    assert message in result.stderr
