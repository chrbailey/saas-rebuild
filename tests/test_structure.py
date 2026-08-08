"""Structural validation of the machine-read files: manifests, SKILL.md
frontmatter, and the issue template."""

import json

import yaml

from conftest import (
    FEATURE_SCHEMA,
    MARKETPLACE_MANIFEST,
    PLUGIN_MANIFEST,
    REPO_ROOT,
    SKILL_DIR,
)

ISSUE_TEMPLATE = REPO_ROOT / ".github" / "ISSUE_TEMPLATE" / "teardown-report.yml"


def test_json_files_parse():
    for path in (PLUGIN_MANIFEST, MARKETPLACE_MANIFEST, FEATURE_SCHEMA):
        json.loads(path.read_text())


def test_skill_frontmatter_required_keys(skill_frontmatter):
    assert skill_frontmatter.get("name"), "SKILL.md frontmatter needs a name"
    assert skill_frontmatter.get("description"), "SKILL.md frontmatter needs a description"


def marketplace_entry(marketplace_manifest, plugin_manifest):
    entry = next(
        (p for p in marketplace_manifest["plugins"] if p["name"] == plugin_manifest["name"]),
        None,
    )
    assert entry, f"marketplace.json has no entry named {plugin_manifest['name']}"
    return entry


def test_no_angle_brackets_in_descriptions(skill_frontmatter, plugin_manifest, marketplace_manifest):
    # The Claude for Work workspace uploader rejects skill descriptions
    # containing angle brackets (documented in SKILL.md's org-deployment
    # section), so keep them out of every description field.
    descriptions = {
        "SKILL.md frontmatter": skill_frontmatter["description"],
        "plugin.json": plugin_manifest["description"],
        "marketplace.json": marketplace_entry(marketplace_manifest, plugin_manifest)["description"],
    }
    for source, text in descriptions.items():
        assert "<" not in text and ">" not in text, f"angle bracket in {source} description"


def test_names_agree_everywhere(skill_frontmatter, plugin_manifest, marketplace_manifest):
    names = {
        skill_frontmatter["name"],
        plugin_manifest["name"],
        marketplace_entry(marketplace_manifest, plugin_manifest)["name"],
        SKILL_DIR.name,
    }
    assert names == {"saas-rebuild"}, f"name mismatch across manifests: {names}"


def test_plugin_skills_path_exists(plugin_manifest):
    skills_path = REPO_ROOT / plugin_manifest["skills"]
    assert skills_path.is_dir(), f"plugin.json skills path missing: {plugin_manifest['skills']}"


def test_issue_template_parses():
    data = yaml.safe_load(ISSUE_TEMPLATE.read_text())
    assert data["name"] == "Teardown Report"
    assert isinstance(data["body"], list) and data["body"]
