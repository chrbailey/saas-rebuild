#!/usr/bin/env python3
"""Build byte-reproducible skill archives and their SHA-256 manifest.

Archives use ZIP_STORED, sorted paths, fixed timestamps, and normalized Unix
permissions. The result is deliberately a little larger than a deflated zip;
in exchange, identical source bytes produce identical archives across Python
and zlib versions. Archives are release outputs and are not committed.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
import sys
import zipfile


ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = ROOT / "skills"
VERSIONS_FILE = ROOT / "skill-versions.json"
DEFAULT_DIST = ROOT / "dist"
ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)


def source_files(skill_dir: Path) -> list[Path]:
    files: list[Path] = []
    for path in skill_dir.rglob("*"):
        if path.is_symlink():
            raise ValueError(f"refusing to package symlink: {path}")
        if (
            path.is_file()
            and "__pycache__" not in path.parts
            and path.suffix != ".pyc"
        ):
            files.append(path)
    return sorted(files)


def archive_bytes(skill_name: str, skill_dir: Path) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_STORED) as archive:
        for path in source_files(skill_dir):
            relative = path.relative_to(skill_dir).as_posix()
            info = zipfile.ZipInfo(f"{skill_name}/{relative}", ZIP_TIMESTAMP)
            info.create_system = 3
            mode = 0o755 if path.stat().st_mode & 0o111 else 0o644
            info.external_attr = mode << 16
            info.compress_type = zipfile.ZIP_STORED
            archive.writestr(info, path.read_bytes())
    return buffer.getvalue()


def expected_outputs() -> dict[str, bytes]:
    versions = json.loads(VERSIONS_FILE.read_text(encoding="utf-8"))
    actual_skills = {p.name for p in SKILLS_DIR.iterdir() if p.is_dir()}
    declared_skills = set(versions)
    if actual_skills != declared_skills:
        missing = sorted(actual_skills - declared_skills)
        stale = sorted(declared_skills - actual_skills)
        raise ValueError(
            f"skill-versions.json mismatch; missing={missing}, stale={stale}"
        )

    outputs: dict[str, bytes] = {}
    for skill_name in sorted(versions):
        version = versions[skill_name]
        outputs[f"{skill_name}-{version}.zip"] = archive_bytes(
            skill_name, SKILLS_DIR / skill_name
        )

    checksum_lines = [
        f"{hashlib.sha256(data).hexdigest()}  {name}"
        for name, data in sorted(outputs.items())
    ]
    outputs["SHA256SUMS"] = ("\n".join(checksum_lines) + "\n").encode("ascii")
    return outputs


def check(outputs: dict[str, bytes]) -> int:
    """Verify a fresh in-memory build, its source parity, and its checksums."""

    failures: list[str] = []
    second_build = expected_outputs()
    if outputs != second_build:
        failures.append("two independent in-memory builds differ")

    checksum_lines = outputs["SHA256SUMS"].decode("ascii").splitlines()
    checksums = dict(line.split("  ", 1)[::-1] for line in checksum_lines)

    for skill_name, version in json.loads(
        VERSIONS_FILE.read_text(encoding="utf-8")
    ).items():
        archive_name = f"{skill_name}-{version}.zip"
        archive_data = outputs[archive_name]
        if checksums.get(archive_name) != hashlib.sha256(archive_data).hexdigest():
            failures.append(f"{archive_name}: SHA256SUMS mismatch")

        expected_entries: dict[str, bytes] = {}
        for path in source_files(SKILLS_DIR / skill_name):
            relative = path.relative_to(SKILLS_DIR / skill_name).as_posix()
            expected_entries[f"{skill_name}/{relative}"] = path.read_bytes()

        with zipfile.ZipFile(io.BytesIO(archive_data)) as archive:
            infos = [info for info in archive.infolist() if not info.is_dir()]
            actual_entries = {
                info.filename: archive.read(info.filename)
                for info in infos
            }
            if actual_entries != expected_entries:
                failures.append(f"{archive_name}: archive/source mismatch")
            if [info.filename for info in infos] != sorted(actual_entries):
                failures.append(f"{archive_name}: noncanonical entry order")
            for info in infos:
                if info.date_time != ZIP_TIMESTAMP:
                    failures.append(f"{archive_name}: noncanonical timestamp")
                if info.compress_type != zipfile.ZIP_STORED:
                    failures.append(f"{archive_name}: noncanonical compression")
                if info.create_system != 3:
                    failures.append(f"{archive_name}: noncanonical source system")
                if (info.external_attr >> 16) & 0o777 not in {0o644, 0o755}:
                    failures.append(f"{archive_name}: noncanonical permissions")

    if failures:
        print("\n".join(failures), file=sys.stderr)
        return 1
    print(
        f"fresh package builds, source parity, and checksums verified "
        f"({len(outputs) - 1} archives)"
    )
    return 0


def write(dist_dir: Path, outputs: dict[str, bytes]) -> int:
    dist_dir.mkdir(parents=True, exist_ok=True)
    expected_names = set(outputs)
    unexpected = sorted(
        path.name for path in dist_dir.glob("*.zip") if path.name not in expected_names
    )
    if unexpected:
        raise ValueError(
            "output directory contains unexpected ZIPs; use an empty directory: "
            f"{unexpected}"
        )
    for name, data in outputs.items():
        (dist_dir / name).write_bytes(data)
    print(f"wrote {len(outputs) - 1} archives and SHA256SUMS to {dist_dir}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify fresh builds without writing release artifacts",
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_DIST)
    args = parser.parse_args()
    outputs = expected_outputs()
    return check(outputs) if args.check else write(args.output_dir, outputs)


if __name__ == "__main__":
    raise SystemExit(main())
