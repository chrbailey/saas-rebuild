"""Repository, plugin-manifest, skill-metadata, and public-copy contracts."""

import json
import re

import jsonschema
import yaml

from conftest import (
    MARKETPLACE_MANIFEST,
    PLUGIN_MANIFEST,
    REPO_ROOT,
    SKILL_DIR,
    repo_files,
)


ISSUE_TEMPLATE = REPO_ROOT / ".github" / "ISSUE_TEMPLATE" / "teardown-report.yml"
EVALS_PATH = SKILL_DIR / "evals" / "evals.json"


def marketplace_entry(marketplace_manifest, plugin_manifest):
    entry = next(
        (item for item in marketplace_manifest["plugins"] if item["name"] == plugin_manifest["name"]),
        None,
    )
    assert entry, f"marketplace.json has no {plugin_manifest['name']} entry"
    return entry


def test_all_json_files_parse():
    paths = repo_files("*.json")
    assert paths
    for path in paths:
        json.loads(path.read_text(encoding="utf-8"))


def test_all_json_schemas_are_valid():
    paths = repo_files("*.schema.json")
    assert len(paths) >= 5
    ids = []
    for path in paths:
        schema = json.loads(path.read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator.check_schema(schema)
        ids.append(schema["$id"])
    assert len(ids) == len(set(ids)), "JSON Schema $id values must be unique"


def test_skill_frontmatter_contract(skill_frontmatter, skill_md_text):
    assert skill_frontmatter["name"] == "saas-rebuild"
    description = skill_frontmatter["description"]
    assert description
    assert len(description) <= 1536
    assert "<" not in description and ">" not in description
    assert len(skill_md_text.splitlines()) < 500


def test_manifest_names_paths_and_descriptions(skill_frontmatter, plugin_manifest, marketplace_manifest):
    entry = marketplace_entry(marketplace_manifest, plugin_manifest)
    assert {skill_frontmatter["name"], plugin_manifest["name"], entry["name"], SKILL_DIR.name} == {"saas-rebuild"}
    assert (REPO_ROOT / plugin_manifest["skills"]).is_dir()
    for source, description in {
        "skill": skill_frontmatter["description"],
        "plugin": plugin_manifest["description"],
        "marketplace": entry["description"],
    }.items():
        assert "<" not in description and ">" not in description, source


def test_claude_manifest_shapes(plugin_manifest, marketplace_manifest):
    assert plugin_manifest["$schema"] == "https://json.schemastore.org/claude-code-plugin-manifest.json"
    assert marketplace_manifest["$schema"] == "https://json.schemastore.org/claude-code-marketplace.json"
    entry = marketplace_entry(marketplace_manifest, plugin_manifest)
    assert entry["source"] == "./"
    assert "type" not in entry, "marketplace sources use source, not type"
    assert "version" not in entry, "plugin.json is the single version source"


def test_readme_install_and_scope_claims():
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    assert "/plugin marketplace add chrbailey/saas-rebuild" in readme
    assert "/plugin install saas-rebuild@chrbailey-plugins" in readme
    assert "/saas-rebuild:saas-rebuild" in readme
    assert "not automatically a Claude skill" in readme
    assert "artifact distribution label" in readme
    assert "universal behavioral equivalence" not in readme.lower()


def test_skill_evals_have_stable_shape():
    data = json.loads(EVALS_PATH.read_text(encoding="utf-8"))
    assert data["skill_name"] == "saas-rebuild"
    assert len(data["evals"]) >= 5
    ids = [item["id"] for item in data["evals"]]
    assert len(ids) == len(set(ids))
    for item in data["evals"]:
        assert item["prompt"].strip()
        assert item["expected_output"].strip()
        assert len(item["expectations"]) >= 2
        assert isinstance(item["files"], list)


def test_issue_template_parses_and_readme_links_it():
    data = yaml.safe_load(ISSUE_TEMPLATE.read_text(encoding="utf-8"))
    assert data["name"] == "Teardown Report"
    assert isinstance(data["body"], list) and data["body"]
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    match = re.search(r"template=([A-Za-z0-9._-]+)", readme)
    assert match
    assert (REPO_ROOT / ".github" / "ISSUE_TEMPLATE" / match.group(1)).is_file()


def test_workflow_yaml_parses():
    for path in sorted((REPO_ROOT / ".github" / "workflows").glob("*.yml")):
        parsed = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert isinstance(parsed, dict)
        assert "jobs" in parsed


def test_external_actions_are_pinned_to_full_commit_shas():
    for path in sorted((REPO_ROOT / ".github" / "workflows").glob("*.yml")):
        text = path.read_text(encoding="utf-8")
        for action, ref in re.findall(r"uses:\s+([^\s@]+)@([^\s#]+)", text):
            if action.startswith("./"):
                continue
            assert re.fullmatch(r"[a-f0-9]{40}", ref), f"mutable action ref {action}@{ref} in {path.name}"


def workflow_jobs():
    for path in sorted((REPO_ROOT / ".github" / "workflows").glob("*.yml")):
        parsed = yaml.safe_load(path.read_text(encoding="utf-8"))
        for job_name, job in parsed["jobs"].items():
            yield path.name, parsed, job_name, job


def test_checkouts_never_persist_credentials():
    # Test suites and build steps execute code from the tree; a persisted
    # token in .git/config would be readable by all of it.
    checkouts = 0
    for workflow, _, job_name, job in workflow_jobs():
        for step in job["steps"]:
            if str(step.get("uses", "")).startswith("actions/checkout@"):
                checkouts += 1
                assert step.get("with", {}).get("persist-credentials") is False, (
                    f"{workflow}:{job_name} checkout persists credentials"
                )
    assert checkouts >= 3


def test_release_write_permissions_are_scoped_to_the_release_job():
    release = yaml.safe_load((REPO_ROOT / ".github" / "workflows" / "release.yml").read_text())
    assert release["permissions"] == {}, "release.yml must not grant workflow-level permissions"
    jobs = release["jobs"]
    assert set(jobs) == {"test", "release"}
    assert jobs["test"]["permissions"] == {"contents": "read"}
    assert jobs["release"]["needs"] == "test"
    assert jobs["release"]["permissions"]["contents"] == "write"
    assert jobs["release"]["permissions"]["id-token"] == "write"
    # Any job that executes the test suites runs code from the tree and must
    # hold a read-only token, whichever workflow it lives in.
    suite_jobs = 0
    for workflow, parsed, job_name, job in workflow_jobs():
        runs = " ".join(str(step.get("run", "")) for step in job["steps"])
        if "pytest" not in runs and "unittest" not in runs:
            continue
        suite_jobs += 1
        grants = {**(parsed.get("permissions") or {}), **(job.get("permissions") or {})}
        assert "write" not in grants.values(), f"{workflow}:{job_name} runs tests with a write token"
    assert suite_jobs >= 3


def codeowners_rules():
    rules = []
    for line in (REPO_ROOT / ".github" / "CODEOWNERS").read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            pattern, *owners = line.split()
            rules.append((pattern, owners))
    return rules


def covered_by(path, rules):
    return [
        owners
        for pattern, owners in rules
        if (pattern.endswith("/") and path.startswith(pattern.lstrip("/")))
        or path == pattern.lstrip("/")
    ]


def test_codeowners_covers_the_enforcement_layer():
    rules = codeowners_rules()
    maintainers = {tuple(owners) for pattern, owners in rules if pattern == "/.github/workflows/"}
    assert maintainers, "workflows have no designated owner"
    for path in (
        ".github/CODEOWNERS",
        ".github/workflows/release.yml",
        "skills/saas-rebuild/templates/pairs.schema.json",
        "skills/saas-rebuild/tools/validate_artifacts.py",
        "skills/saas-rebuild/tools/run_evals.py",
        "scripts/validate_artifacts.py",
        "scripts/package_skills.py",
        "tests/test_structure.py",
        "tests/fixtures/valid-full.json",
    ):
        assert (REPO_ROOT / path).is_file(), path
        owners = covered_by(path, rules)
        assert owners, f"{path} has no code owner"
        assert {tuple(item) for item in owners} <= maintainers, f"{path} owner differs from workflows"
