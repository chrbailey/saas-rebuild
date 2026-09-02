#!/usr/bin/env python3
"""Validate, print, and partially check the saas-rebuild eval specification.

`evals/evals.json` is a set of fresh-session cases in the skill-creator
format: `{"skill_name": ..., "evals": [{"id", "prompt", "expected_output",
"files", "expectations", ...}]}`. This command has no third-party
dependency and does three things:

  run_evals.py                      validate the file's structure, print
                                    every case for a reviewer, exit 0/1
  run_evals.py --case 5             print one case
  run_evals.py --check DIR --case 5 run case 5's declared machine checks
                                    against a teardown output directory

What is and is not automatable
------------------------------
The file's *structure* is fully machine-checkable and this command checks
it: skill name parity with SKILL.md, unique integer ids, non-empty prompt
and expected output, attached files that exist, at least two expectations,
and a closed vocabulary for machine checks.

A case's `expectations` describe model behavior in prose (a refusal, a
distinction drawn, a claim kept bounded). Grading them requires a human or
an LLM grader reading the transcript. This command prints them; it never
grades them and never reports a case as "passed".

Where an expected outcome leaves a structural trace in the output
directory, the case declares `machine_checks` and `--check` runs exactly
those. Vocabulary:

  {"check": "validate-artifacts"}
      DIR passes tools/validate_artifacts.py (a subprocess; that tool needs
      jsonschema, and a missing dependency is a failed check, not a skip).
  {"check": "json-field", "file": "teardown.json",
   "path": "app.methodology", "equals": "document-based"}
      A dotted key path in a JSON object file equals a value.
  {"check": "feature", "where": {...}, "expect": {...}}
      At least one entry in feature-inventory.json matches every `where`
      field and every matching entry satisfies every `expect` field. A
      `where` value that is a list matches any of its members.
  {"check": "no-feature", "where": {...}}
      No entry in feature-inventory.json matches every `where` field.
  {"check": "pair-roles", "roles": [...]}
      pairs.jsonl contains every listed dataset_role and no split_group
      spans more than one role.

Passing machine checks are necessary, never sufficient: an output can
satisfy every check and still fail the case on its prose expectations.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import textwrap
from typing import Any

SKILL_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_EVALS = SKILL_ROOT / "evals" / "evals.json"
SKILL_MD = SKILL_ROOT / "SKILL.md"
VALIDATOR = SKILL_ROOT / "tools" / "validate_artifacts.py"

CASE_FIELDS = {"id", "prompt", "expected_output", "files", "expectations", "machine_checks"}
REQUIRED_CASE_FIELDS = CASE_FIELDS - {"machine_checks"}
MIN_EXPECTATIONS = 2
CHECK_FIELDS = {
    "validate-artifacts": set(),
    "json-field": {"file", "path", "equals"},
    "feature": {"where", "expect"},
    "no-feature": {"where"},
    "pair-roles": {"roles"},
}


def skill_name_from_frontmatter(path: Path) -> str | None:
    """The `name:` line of SKILL.md's YAML frontmatter, without a YAML parser."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    if not lines or lines[0].strip() != "---":
        return None
    for line in lines[1:]:
        if line.strip() == "---":
            break
        key, separator, value = line.partition(":")
        if separator and key.strip() == "name":
            return value.strip().strip("'\"")
    return None


def is_nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def structure_errors(spec: Any, evals_path: Path) -> list[str]:
    errors: list[str] = []
    if not isinstance(spec, dict):
        return ["top level must be an object"]
    unexpected = sorted(set(spec) - {"skill_name", "evals"})
    if unexpected:
        errors.append(f"unexpected top-level fields: {unexpected}")
    expected_name = skill_name_from_frontmatter(SKILL_MD)
    if spec.get("skill_name") != expected_name:
        errors.append(f"skill_name must be {expected_name!r}, got {spec.get('skill_name')!r}")
    cases = spec.get("evals")
    if not isinstance(cases, list) or not cases:
        return errors + ["evals must be a non-empty array"]

    seen_ids: set[Any] = set()
    for index, case in enumerate(cases):
        label = f"evals[{index}]"
        if not isinstance(case, dict):
            errors.append(f"{label}: must be an object")
            continue
        missing = sorted(REQUIRED_CASE_FIELDS - set(case))
        if missing:
            errors.append(f"{label}: missing fields {missing}")
        unexpected = sorted(set(case) - CASE_FIELDS)
        if unexpected:
            errors.append(f"{label}: unexpected fields {unexpected}")
        case_id = case.get("id")
        if not isinstance(case_id, int) or isinstance(case_id, bool):
            errors.append(f"{label}: id must be an integer")
        elif case_id in seen_ids:
            errors.append(f"{label}: duplicate id {case_id}")
        else:
            seen_ids.add(case_id)
        for field in ("prompt", "expected_output"):
            if field in case and not is_nonempty_string(case[field]):
                errors.append(f"{label}: {field} must be a non-empty string")
        files = case.get("files", [])
        if not isinstance(files, list):
            errors.append(f"{label}: files must be an array")
        else:
            for item in files:
                if not is_nonempty_string(item):
                    errors.append(f"{label}: files entries must be non-empty strings")
                elif not (evals_path.parent / item).is_file():
                    errors.append(f"{label}: attached file does not exist: {item}")
        expectations = case.get("expectations", [])
        if (
            not isinstance(expectations, list)
            or len(expectations) < MIN_EXPECTATIONS
            or not all(is_nonempty_string(item) for item in expectations)
        ):
            errors.append(
                f"{label}: expectations must be at least {MIN_EXPECTATIONS} non-empty strings"
            )
        errors.extend(f"{label}: {error}" for error in check_errors(case.get("machine_checks", [])))
    return errors


def check_errors(checks: Any) -> list[str]:
    if not isinstance(checks, list):
        return ["machine_checks must be an array"]
    errors: list[str] = []
    for index, check in enumerate(checks):
        label = f"machine_checks[{index}]"
        if not isinstance(check, dict) or check.get("check") not in CHECK_FIELDS:
            errors.append(f"{label}: check must be one of {sorted(CHECK_FIELDS)}")
            continue
        fields = CHECK_FIELDS[check["check"]]
        actual = set(check) - {"check"}
        if actual != fields:
            errors.append(f"{label}: {check['check']} takes exactly {sorted(fields)}")
            continue
        for field in ("where", "expect"):
            if field in check and (not isinstance(check[field], dict) or not check[field]):
                errors.append(f"{label}: {field} must be a non-empty object")
        if check["check"] == "pair-roles" and (
            not isinstance(check["roles"], list)
            or not check["roles"]
            or not all(is_nonempty_string(role) for role in check["roles"])
        ):
            errors.append(f"{label}: roles must be a non-empty array of strings")
        if check["check"] == "json-field" and not (
            is_nonempty_string(check["file"]) and is_nonempty_string(check["path"])
        ):
            errors.append(f"{label}: file and path must be non-empty strings")
    return errors


def describe_check(check: dict[str, Any]) -> str:
    kind = check["check"]
    if kind == "validate-artifacts":
        return "the directory passes validate_artifacts.py"
    if kind == "json-field":
        return f"{check['file']}: {check['path']} == {json.dumps(check['equals'])}"
    if kind == "feature":
        return f"some feature matching {json.dumps(check['where'])} has {json.dumps(check['expect'])}"
    if kind == "no-feature":
        return f"no feature matches {json.dumps(check['where'])}"
    return f"pairs.jsonl covers dataset roles {check['roles']} with no split_group spanning roles"


def print_case(case: dict[str, Any], out=sys.stdout) -> None:
    def block(title: str, text: str) -> None:
        print(f"  {title}", file=out)
        print(textwrap.indent(textwrap.fill(text, width=76), "    "), file=out)

    print(f"Case {case['id']}", file=out)
    block("Prompt:", case["prompt"])
    block("Expected output:", case["expected_output"])
    if case.get("files"):
        print(f"  Files: {', '.join(case['files'])}", file=out)
    print("  Expectations (human or LLM graded):", file=out)
    for item in case["expectations"]:
        print(
            textwrap.fill(item, width=76, initial_indent="    - ", subsequent_indent="      "),
            file=out,
        )
    checks = case.get("machine_checks", [])
    if checks:
        print("  Machine checks (--check DIR):", file=out)
        for check in checks:
            print(f"    - {describe_check(check)}", file=out)
    else:
        print("  Machine checks: none; this case is graded on the transcript only.", file=out)
    print(file=out)


# --- --check ---------------------------------------------------------------


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def matches(entry: dict[str, Any], where: dict[str, Any]) -> bool:
    for field, wanted in where.items():
        actual = entry.get(field)
        if isinstance(wanted, list):
            if actual not in wanted:
                return False
        elif actual != wanted:
            return False
    return True


def run_check(check: dict[str, Any], output_dir: Path) -> str | None:
    """Return None on success, otherwise a one-line failure reason."""
    kind = check["check"]
    try:
        if kind == "validate-artifacts":
            result = subprocess.run(
                [sys.executable, str(VALIDATOR), str(output_dir)],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                tail = (result.stderr or result.stdout).strip().splitlines()[-1:]
                return f"validate_artifacts.py exited {result.returncode}: {' '.join(tail)}"
            return None
        if kind == "json-field":
            value: Any = load_json(output_dir / check["file"])
            for key in check["path"].split("."):
                if not isinstance(value, dict) or key not in value:
                    return f"{check['file']}: no field {check['path']}"
                value = value[key]
            if value != check["equals"]:
                return f"{check['file']}: {check['path']} is {json.dumps(value)}"
            return None
        if kind in {"feature", "no-feature"}:
            features = load_json(output_dir / "feature-inventory.json")
            if not isinstance(features, list):
                return "feature-inventory.json is not an array"
            matching = [f for f in features if isinstance(f, dict) and matches(f, check["where"])]
            if kind == "no-feature":
                if matching:
                    return f"features match {json.dumps(check['where'])}: {[f.get('id') for f in matching]}"
                return None
            if not matching:
                return f"no feature matches {json.dumps(check['where'])}"
            failing = [f.get("id") for f in matching if not matches(f, check["expect"])]
            if failing:
                return f"features lack {json.dumps(check['expect'])}: {failing}"
            return None
        roles_by_group: dict[str, set[str]] = {}
        present: set[str] = set()
        for line in (output_dir / "pairs.jsonl").read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            pair = json.loads(line)
            present.add(pair.get("dataset_role"))
            roles_by_group.setdefault(pair.get("split_group"), set()).add(pair.get("dataset_role"))
        missing = sorted(set(check["roles"]) - present)
        if missing:
            return f"pairs.jsonl has no pairs in roles {missing}"
        leaks = sorted(group for group, roles in roles_by_group.items() if len(roles) > 1)
        if leaks:
            return f"split_group spans several roles: {leaks}"
        return None
    except (OSError, json.JSONDecodeError) as error:
        return f"{error}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--evals", type=Path, default=DEFAULT_EVALS, help="eval spec to read")
    parser.add_argument("--case", type=int, help="restrict to one case id")
    parser.add_argument("--check", type=Path, metavar="DIR", help="run the case's machine checks against DIR")
    args = parser.parse_args(argv)

    try:
        spec = load_json(args.evals)
    except (OSError, json.JSONDecodeError) as error:
        print(f"ERROR: {args.evals}: {error}", file=sys.stderr)
        return 1
    errors = structure_errors(spec, args.evals)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        print(f"eval spec invalid ({len(errors)} errors)", file=sys.stderr)
        return 1

    cases = spec["evals"]
    if args.case is not None:
        cases = [case for case in cases if case["id"] == args.case]
        if not cases:
            print(f"ERROR: no case with id {args.case}", file=sys.stderr)
            return 1

    if args.check is None:
        print(f"{spec['skill_name']} evals: {len(spec['evals'])} cases in {args.evals}\n")
        for case in cases:
            print_case(case)
        print("Structure valid. Prose expectations are not graded by this command.")
        return 0

    if args.case is None:
        parser.error("--check requires --case")
    if not args.check.is_dir():
        parser.error(f"not a directory: {args.check}")
    case = cases[0]
    checks = case.get("machine_checks", [])
    if not checks:
        print(f"case {case['id']} declares no machine checks; grade the transcript.", file=sys.stderr)
        return 1
    failures = 0
    for check in checks:
        reason = run_check(check, args.check)
        status = "ok  " if reason is None else "FAIL"
        print(f"{status} {describe_check(check)}" + (f" -- {reason}" if reason else ""))
        failures += reason is not None
    if failures:
        print(f"case {case['id']}: {failures} of {len(checks)} machine checks failed", file=sys.stderr)
        return 1
    print(
        f"case {case['id']}: all {len(checks)} machine checks passed; "
        "prose expectations still need a grader"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
