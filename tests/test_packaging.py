"""The committed saas-rebuild zip in dist/ must exactly mirror
skills/saas-rebuild/ — same file set, byte-identical contents — so an
edit to the skill source can't ship without repackaging. (Other skills
in this repo package their own zips; this suite covers saas-rebuild.)"""

import zipfile

from conftest import DIST_DIR, SKILL_DIR

ZIP_PREFIX = "saas-rebuild/"


def zip_entries():
    zips = sorted(DIST_DIR.glob("saas-rebuild-*.zip"))
    assert len(zips) == 1, f"expected one saas-rebuild zip in dist/, found {[z.name for z in zips]}"
    with zipfile.ZipFile(zips[0]) as zf:
        return {
            info.filename: zf.read(info.filename)
            for info in zf.infolist()
            if not info.is_dir()
        }


def source_files():
    return {
        ZIP_PREFIX + str(p.relative_to(SKILL_DIR)): p.read_bytes()
        for p in SKILL_DIR.rglob("*")
        if p.is_file()
    }


def test_zip_file_set_matches_source():
    packaged, source = zip_entries(), source_files()
    missing = sorted(set(source) - set(packaged))
    extra = sorted(set(packaged) - set(source))
    assert not missing, f"in skills/saas-rebuild/ but not in the dist zip (repackage): {missing}"
    assert not extra, f"in the dist zip but not in skills/saas-rebuild/: {extra}"


def test_zip_contents_byte_identical():
    packaged, source = zip_entries(), source_files()
    stale = [name for name in sorted(source) if packaged.get(name) != source[name]]
    assert not stale, f"dist zip contents differ from source (repackage): {stale}"
