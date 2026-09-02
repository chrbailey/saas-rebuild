import json
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = REPO_ROOT / "skills" / "saas-rebuild"
PLUGIN_MANIFEST = REPO_ROOT / ".claude-plugin" / "plugin.json"
MARKETPLACE_MANIFEST = REPO_ROOT / ".claude-plugin" / "marketplace.json"
FEATURE_SCHEMA = SKILL_DIR / "templates" / "feature-inventory.schema.json"
SKILL_MD = SKILL_DIR / "SKILL.md"
DIST_DIR = REPO_ROOT / "dist"
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"

# Directories that can sit inside a checkout but are never repository content:
# git internals, agent worktrees, virtualenvs, caches. A repo-wide rglob that
# descended into them found a second copy of every schema (duplicate $id) and
# every JSON file a venv ships, so contract tests failed on a perfectly good
# tree. Walk the repository, not the workstation.
SKIP_DIRS = frozenset({
    ".git", ".claude", ".venv", "venv", ".pytest_cache", "__pycache__",
    "node_modules", ".mypy_cache", ".ruff_cache", "dist",
})


def repo_files(pattern: str) -> list[Path]:
    """Sorted repository files matching `pattern`, skipping SKIP_DIRS."""
    return sorted(
        p for p in REPO_ROOT.rglob(pattern)
        if p.is_file() and not (set(p.relative_to(REPO_ROOT).parts[:-1]) & SKIP_DIRS)
    )


@pytest.fixture(scope="session")
def repo_root():
    return REPO_ROOT


@pytest.fixture(scope="session")
def plugin_manifest():
    return json.loads(PLUGIN_MANIFEST.read_text())


@pytest.fixture(scope="session")
def marketplace_manifest():
    return json.loads(MARKETPLACE_MANIFEST.read_text())


@pytest.fixture(scope="session")
def feature_schema():
    return json.loads(FEATURE_SCHEMA.read_text())


@pytest.fixture(scope="session")
def skill_md_text():
    return SKILL_MD.read_text()


@pytest.fixture(scope="session")
def skill_frontmatter(skill_md_text):
    """The YAML frontmatter block of SKILL.md, parsed."""
    import yaml

    match = re.match(r"\A---\n(.*?)\n---\n", skill_md_text, re.DOTALL)
    assert match, "SKILL.md must start with a --- delimited YAML frontmatter block"
    return yaml.safe_load(match.group(1))
