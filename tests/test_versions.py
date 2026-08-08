"""One version source per skill and correctly named generated archives."""

import json
import re
import subprocess
import sys

from conftest import REPO_ROOT


SEMVER = r"\d+\.\d+\.\d+"
VERSIONS_PATH = REPO_ROOT / "skill-versions.json"


def test_declared_versions_are_complete_and_semver(plugin_manifest):
    versions = json.loads(VERSIONS_PATH.read_text())
    skills = {path.name for path in (REPO_ROOT / "skills").iterdir() if path.is_dir()}
    assert set(versions) == skills
    assert all(re.fullmatch(SEMVER, version) for version in versions.values())
    assert plugin_manifest["version"] == versions["saas-rebuild"]


def test_generated_zips_match_declared_versions(tmp_path):
    subprocess.run(
        [sys.executable, "scripts/package_skills.py", "--output-dir", str(tmp_path)],
        cwd=REPO_ROOT,
        check=True,
    )
    versions = json.loads(VERSIONS_PATH.read_text())
    expected = {f"{name}-{version}.zip" for name, version in versions.items()}
    actual = {path.name for path in tmp_path.glob("*.zip")}
    assert actual == expected


def test_saas_contract_versions_match_skill_version():
    versions = json.loads(VERSIONS_PATH.read_text())
    expected = versions["saas-rebuild"]
    for path in sorted((REPO_ROOT / "skills" / "saas-rebuild" / "templates").glob("*.schema.json")):
        schema = json.loads(path.read_text())
        assert schema["properties"]["schema_version"]["const"] == expected, path.name


def test_each_generated_zip_name_maps_to_a_real_skill(tmp_path):
    subprocess.run(
        [sys.executable, "scripts/package_skills.py", "--output-dir", str(tmp_path)],
        cwd=REPO_ROOT,
        check=True,
    )
    for path in tmp_path.glob("*.zip"):
        match = re.fullmatch(rf"([a-z0-9-]+)-({SEMVER})\.zip", path.name)
        assert match
        assert (REPO_ROOT / "skills" / match.group(1)).is_dir()
