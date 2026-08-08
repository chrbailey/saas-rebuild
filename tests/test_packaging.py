"""Every skill's committed dist/ zip must exactly mirror its source under
skills/ — same file set, byte-identical contents — so an edit to any skill
can't ship without repackaging. Parametrized over all skill directories;
__pycache__ artifacts are excluded from the comparison on both sides."""

import zipfile

import pytest

from conftest import DIST_DIR, REPO_ROOT

SKILLS = sorted(p for p in (REPO_ROOT / "skills").iterdir() if p.is_dir())


def is_artifact(path_parts):
    return "__pycache__" in path_parts or any(p.endswith(".pyc") for p in path_parts)


def zip_entries(skill_name):
    zips = sorted(DIST_DIR.glob(f"{skill_name}-*.zip"))
    assert len(zips) == 1, (
        f"expected one {skill_name} zip in dist/, found {[z.name for z in zips]}"
    )
    with zipfile.ZipFile(zips[0]) as zf:
        return {
            info.filename: zf.read(info.filename)
            for info in zf.infolist()
            if not info.is_dir() and not is_artifact(info.filename.split("/"))
        }


def source_files(skill_dir):
    return {
        f"{skill_dir.name}/" + str(p.relative_to(skill_dir)): p.read_bytes()
        for p in skill_dir.rglob("*")
        if p.is_file() and not is_artifact(p.relative_to(skill_dir).parts)
    }


@pytest.mark.parametrize("skill_dir", SKILLS, ids=lambda p: p.name)
def test_zip_file_set_matches_source(skill_dir):
    packaged, source = zip_entries(skill_dir.name), source_files(skill_dir)
    missing = sorted(set(source) - set(packaged))
    extra = sorted(set(packaged) - set(source))
    assert not missing, f"in skills/{skill_dir.name}/ but not in the dist zip (repackage): {missing}"
    assert not extra, f"in the dist zip but not in skills/{skill_dir.name}/: {extra}"


@pytest.mark.parametrize("skill_dir", SKILLS, ids=lambda p: p.name)
def test_zip_contents_byte_identical(skill_dir):
    packaged, source = zip_entries(skill_dir.name), source_files(skill_dir)
    stale = [name for name in sorted(source) if packaged.get(name) != source[name]]
    assert not stale, f"dist zip contents differ from source (repackage): {stale}"
