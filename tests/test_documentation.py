"""Documentation links and high-risk public statements stay reviewable."""

import re
import subprocess
import sys

import yaml

from conftest import REPO_ROOT, repo_files

README = REPO_ROOT / "README.md"
EXAMPLE = REPO_ROOT / "examples" / "synthetic-crm"
ISSUE_TEMPLATES = REPO_ROOT / ".github" / "ISSUE_TEMPLATE"


def test_relative_markdown_links_resolve():
    missing = []
    for path in repo_files("*.md"):
        for target in re.findall(r"\]\(([^)]+)\)", path.read_text(encoding="utf-8")):
            target = target.split("#", 1)[0].split("?", 1)[0]
            if not target or re.match(r"^[a-z]+:", target):
                continue
            if not (path.parent / target).exists():
                missing.append(f"{path.relative_to(REPO_ROOT)} -> {target}")
    assert not missing, f"broken relative Markdown links: {missing}"


def test_retired_overclaims_do_not_return():
    paths = [
        README,
        REPO_ROOT / "skills" / "saas-rebuild" / "SKILL.md",
        REPO_ROOT / "skills" / "saas-rebuild" / "references" / "extraction-playbook.md",
    ]
    text = "\n".join(path.read_text(encoding="utf-8") for path in paths).lower()
    retired = [
        "raw tenant data never leaves",
        "empty table = unused module",
        "0.3%-populated custom field = abandoned experiment",
        "the delta from vanilla is the requirements list",
        "behavioral equivalence on historical data is the only proof",
    ]
    assert not [claim for claim in retired if claim in text]


def test_readme_leads_with_value_quickstart_and_output():
    """A newcomer meets the pitch, a zero-access quickstart, and a real
    output excerpt before any rigor section."""
    headings = [
        line[3:].strip()
        for line in README.read_text(encoding="utf-8").splitlines()
        if line.startswith("## ")
    ]
    first_three = headings[:3]
    assert first_three[0].lower().startswith("five-minute quickstart"), first_three
    assert first_three[1].lower().startswith("what a teardown produces"), first_three
    assert "The 60-second model" in headings
    assert headings.index("The 60-second model") > headings.index(first_three[1])
    for kept in (
        "Proof surfaces",
        "Pipeline",
        "Data boundary and responsible use",
        "Reference rebuild: export compliance",
        "Historical public report",
        "Research lineage",
        "Contributing and security",
    ):
        assert kept in headings, kept


def test_readme_artifact_table_names_files_the_example_ships():
    """Every artifact the README says a teardown produces is present in the
    worked example, so the promise is demonstrated rather than asserted."""
    text = README.read_text(encoding="utf-8")
    section = text.split("## What a teardown produces", 1)[1].split("\n## ", 1)[0]
    names = re.findall(r"^\| `([A-Za-z_./-]+\.(?:json|jsonl|md))` \|", section, re.MULTILINE)
    assert len(names) >= 9, names
    missing = [name for name in names if not (EXAMPLE / name).is_file()]
    assert not missing, f"README promises artifacts the example does not ship: {missing}"


def test_readme_quickstart_shows_the_validator_output_it_gets():
    text = README.read_text(encoding="utf-8")
    quoted = re.search(r"^artifact validation passed \([^)]*\)$", text, re.MULTILINE)
    assert quoted, "README should quote the validator's success line verbatim"
    result = subprocess.run(
        [sys.executable, "skills/saas-rebuild/tools/validate_artifacts.py", "examples/synthetic-crm"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    assert quoted.group(0) in result.stdout + result.stderr


def test_readme_keeps_migration_note_and_responsible_use():
    text = README.read_text(encoding="utf-8")
    assert "docs/migration-v0.7.md" in text
    assert "Use this only on software and data you are authorized to administer" in text
    assert "artifact distribution label" in text


def test_issue_templates_parse_and_are_linked_from_readme():
    templates = sorted(ISSUE_TEMPLATES.glob("*.yml"))
    assert {path.name for path in templates} >= {
        "teardown-report.yml",
        "recipe-verification.yml",
        "screening-discrepancy.yml",
    }
    readme = README.read_text(encoding="utf-8")
    corpus_readme = (REPO_ROOT / "skills" / "saas-rebuild" / "corpus" / "README.md").read_text(encoding="utf-8")
    for path in templates:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert data["name"].strip() and data["description"].strip(), path.name
        assert isinstance(data["body"], list) and data["body"], path.name
        ids = [block.get("id") for block in data["body"] if block.get("id")]
        assert len(ids) == len(set(ids)), f"{path.name}: duplicate field ids"
        checkboxes = [block for block in data["body"] if block["type"] == "checkboxes"]
        assert checkboxes, f"{path.name}: no sanitization/confirmation checkbox"
    for name in ("teardown-report.yml", "recipe-verification.yml"):
        assert f"template={name}" in readme, name
    assert "template=recipe-verification.yml" in corpus_readme

    recipe_form = yaml.safe_load((ISSUE_TEMPLATES / "recipe-verification.yml").read_text(encoding="utf-8"))
    ids = {block.get("id") for block in recipe_form["body"]}
    assert {"app", "routes-tried", "worked", "failed", "docs-links", "date"} <= ids
