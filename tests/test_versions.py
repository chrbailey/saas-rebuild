"""Version consistency. The plugin version (plugin.json ↔ marketplace.json)
is hand-edited in two places and must agree. Skill zips in dist/ are
versioned per skill, independently of the plugin version, but each must be
semver-named after a skill directory that actually exists."""

import re

from conftest import DIST_DIR, REPO_ROOT

SEMVER = r"\d+\.\d+\.\d+"


def test_plugin_and_marketplace_versions_in_sync(plugin_manifest, marketplace_manifest):
    entry = next(
        (p for p in marketplace_manifest["plugins"] if p["name"] == plugin_manifest["name"]),
        None,
    )
    assert entry, f"marketplace.json has no entry named {plugin_manifest['name']}"
    assert entry["version"] == plugin_manifest["version"], (
        f"version drift: plugin.json {plugin_manifest['version']} "
        f"vs marketplace.json {entry['version']}"
    )


def test_plugin_version_is_semver(plugin_manifest):
    assert re.fullmatch(SEMVER, plugin_manifest["version"])


def test_dist_zips_are_semver_named_after_real_skills():
    zips = sorted(DIST_DIR.glob("*.zip"))
    assert zips, "expected at least one packaged skill zip in dist/"
    for z in zips:
        match = re.fullmatch(rf"([a-z0-9-]+)-({SEMVER})\.zip", z.name)
        assert match, f"dist zip name not in <skill>-X.Y.Z.zip form: {z.name}"
        skill_dir = REPO_ROOT / "skills" / match.group(1)
        assert skill_dir.is_dir(), f"{z.name} names no skill directory: skills/{match.group(1)}"


def test_one_zip_per_skill():
    by_skill = {}
    for z in DIST_DIR.glob("*.zip"):
        match = re.fullmatch(rf"([a-z0-9-]+)-{SEMVER}\.zip", z.name)
        if match:
            by_skill.setdefault(match.group(1), []).append(z.name)
    stale = {k: v for k, v in by_skill.items() if len(v) > 1}
    assert not stale, f"multiple zip versions for the same skill in dist/: {stale}"
