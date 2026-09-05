"""The locked benchmark and scorecard must remain reproducible cross-file contracts."""

import json
import hashlib
import shutil
import subprocess
import sys

import jsonschema
import pytest

from conftest import REPO_ROOT, SKILL_DIR


EXAMPLE = REPO_ROOT / "examples" / "synthetic-crm"


def read_json(target, name):
    return json.loads((target / name).read_text(encoding="utf-8"))


def write_json(target, name, value):
    (target / name).write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def run_validator(path):
    return subprocess.run(
        [sys.executable, "scripts/validate_artifacts.py", str(path)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )


@pytest.mark.parametrize("name", ["success-profile", "evaluation-scorecard"])
def test_new_contract_schemas_accept_the_worked_example(name):
    schema = read_json(SKILL_DIR / "templates", f"{name}.schema.json")
    value = read_json(EXAMPLE, f"{name}.json")
    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.Draft202012Validator(schema).validate(value)


def stale_benchmark_digest(target):
    scorecard = read_json(target, "evaluation-scorecard.json")
    scorecard["benchmark"]["sha256"] = "0" * 64
    write_json(target, "evaluation-scorecard.json", scorecard)


def missing_criterion(target):
    scorecard = read_json(target, "evaluation-scorecard.json")
    scorecard["entries"].pop()
    write_json(target, "evaluation-scorecard.json", scorecard)


def duplicate_criterion(target):
    scorecard = read_json(target, "evaluation-scorecard.json")
    scorecard["entries"].append(scorecard["entries"][0])
    write_json(target, "evaluation-scorecard.json", scorecard)


def unknown_evidence(target):
    scorecard = read_json(target, "evaluation-scorecard.json")
    scorecard["entries"][0]["evidence_ids"] = ["ev-not-real"]
    write_json(target, "evaluation-scorecard.json", scorecard)


def missing_required_evidence_class(target):
    scorecard = read_json(target, "evaluation-scorecard.json")
    scorecard["entries"][0]["evidence_ids"] = ["ev-search-runtime"]
    write_json(target, "evaluation-scorecard.json", scorecard)


def inflated_weighted_score(target):
    scorecard = read_json(target, "evaluation-scorecard.json")
    scorecard["summary"]["weighted_score"] = 99.0
    write_json(target, "evaluation-scorecard.json", scorecard)


def false_pass_gate(target):
    scorecard = read_json(target, "evaluation-scorecard.json")
    scorecard["summary"]["gate_status"] = "pass"
    write_json(target, "evaluation-scorecard.json", scorecard)


def unknown_masks_known_failure(target):
    scorecard = read_json(target, "evaluation-scorecard.json")
    scorecard["summary"]["gate_status"] = "blocked"
    write_json(target, "evaluation-scorecard.json", scorecard)


def unknown_must_does_not_block(target):
    profile = read_json(target, "success-profile.json")
    next(item for item in profile["criteria"] if item["id"] == "weekly-customer-ingest")[
        "priority"
    ] = "should"
    write_json(target, "success-profile.json", profile)
    scorecard = read_json(target, "evaluation-scorecard.json")
    scorecard["benchmark"]["sha256"] = hashlib.sha256(
        (target / "success-profile.json").read_bytes()
    ).hexdigest()
    scorecard["summary"]["must_gaps"] = ["annual-tax-compliance"]
    # Leave the old fail status in place; with only an unknown must, blocked is required.
    write_json(target, "evaluation-scorecard.json", scorecard)


CASES = [
    (stale_benchmark_digest, "benchmark digest does not match"),
    (missing_criterion, "is missing criteria"),
    (duplicate_criterion, "duplicate evaluation-scorecard criterion ids"),
    (unknown_evidence, "has unknown evidence"),
    (missing_required_evidence_class, "lacks required evidence classes"),
    (inflated_weighted_score, "summary weighted_score"),
    (false_pass_gate, "summary gate_status"),
    (unknown_masks_known_failure, "summary gate_status is 'blocked', expected 'fail'"),
    (unknown_must_does_not_block, "summary gate_status is 'fail', expected 'blocked'"),
]


@pytest.mark.parametrize("mutate,message", CASES, ids=[fn.__name__ for fn, _ in CASES])
def test_validator_rejects_scorecard_mutations(tmp_path, mutate, message):
    target = tmp_path / "teardown"
    shutil.copytree(EXAMPLE, target)
    mutate(target)
    result = run_validator(target)
    assert result.returncode == 1, result.stdout + result.stderr
    assert message in result.stderr
