"""The eval specification validates and its runner behaves as documented:
dry mode prints and exits 0, check mode runs only declared machine checks
and fails closed."""

from copy import deepcopy
import importlib.util
import json
import subprocess
import sys

import pytest

from conftest import REPO_ROOT, SKILL_DIR

RUNNER = SKILL_DIR / "tools" / "run_evals.py"
EVALS = SKILL_DIR / "evals" / "evals.json"
EXAMPLE = REPO_ROOT / "examples" / "synthetic-crm"


@pytest.fixture(scope="module")
def runner():
    spec = importlib.util.spec_from_file_location("run_evals", RUNNER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def spec():
    return json.loads(EVALS.read_text(encoding="utf-8"))


def run(*args):
    return subprocess.run(
        [sys.executable, str(RUNNER), *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )


def test_runner_has_no_third_party_imports():
    # Dry mode must work on a bare interpreter; the validator subprocess is
    # the only place a dependency may enter, and it fails closed if missing.
    import re

    text = RUNNER.read_text(encoding="utf-8")
    assert not re.findall(r"^\s*(?:import|from)\s+(?:jsonschema|yaml|pytest)\b", text, re.MULTILINE)


def test_spec_validates(runner, spec):
    assert runner.structure_errors(spec, EVALS) == []


def test_dry_mode_prints_every_case_and_exits_zero(spec):
    result = run()
    assert result.returncode == 0, result.stderr
    for case in spec["evals"]:
        assert f"Case {case['id']}" in result.stdout
        for expectation in case["expectations"]:
            assert expectation.split()[0] in result.stdout
    assert "not graded" in result.stdout


@pytest.mark.parametrize(
    "mutate,message",
    [
        (lambda s: s.update(skill_name="other"), "skill_name must be 'saas-rebuild'"),
        (lambda s: s["evals"][1].update(id=1), "duplicate id 1"),
        (lambda s: s["evals"][0].update(prompt=" "), "prompt must be a non-empty string"),
        (lambda s: s["evals"][0].update(expectations=["only one"]), "expectations must be at least 2"),
        (lambda s: s["evals"][0].update(files=["missing.txt"]), "attached file does not exist"),
        (lambda s: s["evals"][0].update(surprise=1), "unexpected fields ['surprise']"),
        (
            lambda s: s["evals"][0]["machine_checks"].append({"check": "grade-prose"}),
            "check must be one of",
        ),
        (
            lambda s: s["evals"][0]["machine_checks"].append({"check": "feature", "where": {}}),
            "feature takes exactly ['expect', 'where']",
        ),
    ],
    ids=[
        "wrong-skill-name",
        "duplicate-id",
        "blank-prompt",
        "too-few-expectations",
        "missing-file",
        "unexpected-field",
        "unknown-check",
        "malformed-check",
    ],
)
def test_structural_errors_are_reported(runner, spec, mutate, message):
    mutated = deepcopy(spec)
    mutate(mutated)
    reported = runner.structure_errors(mutated, EVALS)
    assert any(message in error for error in reported), reported


def test_invalid_spec_fails_dry_mode(tmp_path, spec):
    spec["evals"][0]["machine_checks"].append({"check": "grade-prose"})
    broken = tmp_path / "evals.json"
    broken.write_text(json.dumps(spec), encoding="utf-8")
    result = run("--evals", str(broken))
    assert result.returncode == 1
    assert "eval spec invalid" in result.stderr


def test_check_mode_passes_declared_checks_against_the_example():
    result = run("--case", "5", "--check", str(EXAMPLE))
    assert result.returncode == 0, result.stderr
    assert "prose expectations still need a grader" in result.stdout


def test_check_mode_fails_closed_on_an_empty_directory(tmp_path):
    result = run("--case", "5", "--check", str(tmp_path))
    assert result.returncode == 1
    assert "FAIL" in result.stdout


def test_check_mode_refuses_to_pass_a_case_without_machine_checks():
    result = run("--case", "2", "--check", str(EXAMPLE))
    assert result.returncode == 1
    assert "declares no machine checks" in result.stderr


def test_feature_checks_read_the_inventory(runner):
    assert runner.run_check({"check": "no-feature", "where": {"usage": "never"}}, EXAMPLE)
    assert runner.run_check(
        {"check": "feature", "where": {"usage": "unknown"}, "expect": {"verdict": "DEFER"}}, EXAMPLE
    ) is None
    assert runner.run_check(
        {"check": "feature", "where": {"usage": "unknown"}, "expect": {"verdict": "KEEP"}}, EXAMPLE
    )
    assert runner.run_check({"check": "no-feature", "where": {"usage": ["rare"]}}, EXAMPLE) is None
