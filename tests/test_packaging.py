"""Release archives are complete, byte-reproducible, and checksummed."""

import hashlib
import subprocess
import sys
import zipfile

import pytest

from conftest import REPO_ROOT
from scripts.package_skills import source_files as packaged_source_files


SKILLS = sorted(path for path in (REPO_ROOT / "skills").iterdir() if path.is_dir())
FIXED_TIMESTAMP = (1980, 1, 1, 0, 0, 0)


def is_artifact(parts):
    return "__pycache__" in parts or any(part.endswith(".pyc") for part in parts)


@pytest.fixture(scope="module")
def built_dist(tmp_path_factory):
    target = tmp_path_factory.mktemp("release-dist")
    subprocess.run(
        [sys.executable, "scripts/package_skills.py", "--output-dir", str(target)],
        cwd=REPO_ROOT,
        check=True,
    )
    return target


def one_zip(dist_dir, skill_name):
    matches = sorted(dist_dir.glob(f"{skill_name}-*.zip"))
    assert len(matches) == 1
    return matches[0]


def zip_entries(path):
    with zipfile.ZipFile(path) as archive:
        return {
            info.filename: archive.read(info.filename)
            for info in archive.infolist()
            if not info.is_dir() and not is_artifact(info.filename.split("/"))
        }


def source_files(skill_dir):
    return {
        f"{skill_dir.name}/{path.relative_to(skill_dir).as_posix()}": path.read_bytes()
        for path in skill_dir.rglob("*")
        if path.is_file() and not is_artifact(path.relative_to(skill_dir).parts)
    }


@pytest.mark.parametrize("skill_dir", SKILLS, ids=lambda path: path.name)
def test_archive_exactly_matches_source(built_dist, skill_dir):
    assert zip_entries(one_zip(built_dist, skill_dir.name)) == source_files(skill_dir)


@pytest.mark.parametrize("skill_dir", SKILLS, ids=lambda path: path.name)
def test_archive_metadata_is_reproducible(built_dist, skill_dir):
    with zipfile.ZipFile(one_zip(built_dist, skill_dir.name)) as archive:
        names = [info.filename for info in archive.infolist() if not info.is_dir()]
        assert names == sorted(names)
        for info in archive.infolist():
            if info.is_dir():
                continue
            assert info.date_time == FIXED_TIMESTAMP
            assert info.compress_type == zipfile.ZIP_STORED
            assert info.create_system == 3
            assert (info.external_attr >> 16) & 0o777 in {0o644, 0o755}


def test_sha256_manifest_matches_archives(built_dist):
    entries = {}
    for line in (built_dist / "SHA256SUMS").read_text(encoding="ascii").splitlines():
        digest, name = line.split("  ", 1)
        entries[name] = digest
    zips = sorted(built_dist.glob("*.zip"))
    assert set(entries) == {path.name for path in zips}
    for path in zips:
        assert entries[path.name] == hashlib.sha256(path.read_bytes()).hexdigest()


def test_packager_check_mode_passes():
    subprocess.run(
        [sys.executable, "scripts/package_skills.py", "--check"],
        cwd=REPO_ROOT,
        check=True,
    )


def test_release_outputs_are_not_committed():
    dist = REPO_ROOT / "dist"
    assert not list(dist.glob("*.zip"))
    assert not (dist / "SHA256SUMS").exists()


def test_packager_rejects_symlinks(tmp_path):
    target = tmp_path / "target.txt"
    target.write_text("content")
    (tmp_path / "alias.txt").symlink_to(target)
    with pytest.raises(ValueError, match="refusing to package symlink"):
        packaged_source_files(tmp_path)


def test_packager_preserves_unrelated_archives(tmp_path):
    unrelated = tmp_path / "unrelated.zip"
    unrelated.write_bytes(b"keep me")
    result = subprocess.run(
        [sys.executable, "scripts/package_skills.py", "--output-dir", str(tmp_path)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert unrelated.read_bytes() == b"keep me"


def test_two_independent_builds_are_identical(tmp_path):
    first = tmp_path / "first"
    second = tmp_path / "second"
    for target in (first, second):
        subprocess.run(
            [sys.executable, "scripts/package_skills.py", "--output-dir", str(target)],
            cwd=REPO_ROOT,
            check=True,
        )
    assert {path.name: path.read_bytes() for path in first.iterdir()} == {
        path.name: path.read_bytes() for path in second.iterdir()
    }
