"""The release version appears in three hand-edited places; they must agree."""

import re

from conftest import DIST_DIR


def zip_version():
    zips = sorted(DIST_DIR.glob("*.zip"))
    assert len(zips) == 1, f"expected exactly one zip in dist/, found {[z.name for z in zips]}"
    match = re.fullmatch(r"saas-rebuild-(\d+\.\d+\.\d+)\.zip", zips[0].name)
    assert match, f"dist zip name not in saas-rebuild-X.Y.Z.zip form: {zips[0].name}"
    return match.group(1)


def test_versions_in_sync(plugin_manifest, marketplace_manifest):
    versions = {
        "plugin.json": plugin_manifest["version"],
        "marketplace.json": marketplace_manifest["plugins"][0]["version"],
        "dist zip filename": zip_version(),
    }
    assert len(set(versions.values())) == 1, f"version drift: {versions}"


def test_version_is_semver(plugin_manifest):
    assert re.fullmatch(r"\d+\.\d+\.\d+", plugin_manifest["version"])
