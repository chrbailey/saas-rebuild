"""The documented v0.10 -> v0.11 artifact migration is complete and necessary.

Bumping schema_version changes file bytes, and two contracts are bound to
bytes: the scorecard's success-profile digest and the preservation manifest's
file digests. These tests pin that a version bump alone fails and that the
steps in docs/migration-v0.11.md produce a valid teardown.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE = ROOT / "examples" / "synthetic-crm"
VALIDATOR = ROOT / "skills" / "saas-rebuild" / "tools" / "validate_artifacts.py"
ARTIFACTS = [
    "teardown.json",
    "feature-inventory.json",
    "pairs.jsonl",
    "graph.json",
    "preservation-manifest.json",
    "success-profile.json",
    "evaluation-scorecard.json",
]


def set_version(root: Path, old: str, new: str) -> None:
    for name in ARTIFACTS:
        path = root / name
        text = path.read_text(encoding="utf-8")
        path.write_text(
            text.replace(f'"schema_version": "{old}"', f'"schema_version": "{new}"')
            .replace(f'"schema_version":"{old}"', f'"schema_version":"{new}"'),
            encoding="utf-8",
        )


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rebind_benchmark(root: Path) -> tuple[str, str]:
    path = root / "evaluation-scorecard.json"
    scorecard = json.loads(path.read_text())
    old = scorecard["benchmark"]["sha256"]
    scorecard["benchmark"]["sha256"] = sha256(root / "success-profile.json")
    path.write_text(json.dumps(scorecard, indent=2) + "\n")
    return old, scorecard["benchmark"]["sha256"]


def rehash_preserved(root: Path) -> None:
    path = root / "preservation-manifest.json"
    manifest = json.loads(path.read_text())
    for artifact in manifest["artifacts"]:
        for entry in artifact.get("files", []):
            preserved = root / entry["path"]
            if preserved.is_file():
                entry["sha256"] = sha256(preserved)
                entry["bytes"] = preserved.stat().st_size
    path.write_text(json.dumps(manifest, indent=2) + "\n")


def validate(root: Path) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(VALIDATOR), str(root)], text=True, capture_output=True)


def strip_interviews(root: Path) -> None:
    """Remove the v0.11-only interview statements and their citation links."""

    (root / "interviews.jsonl").unlink()
    for name, link in (
        ("feature-inventory.json", ',\n        "statement_ids": ["st-int-01-02"]'),
        ("pairs.jsonl", ',"statement_ids":["st-int-01-02"]'),
        ("teardown.json", '\n    "interviews": "interviews.jsonl",'),
    ):
        path = root / name
        text = path.read_text(encoding="utf-8")
        assert link in text, name
        path.write_text(text.replace(link, ""), encoding="utf-8")


def v010_teardown(tmp_path: Path) -> Path:
    """A self-consistent v0.10 artifact set built from the worked example."""

    root = tmp_path / "teardown"
    shutil.copytree(EXAMPLE, root)
    strip_interviews(root)
    set_version(root, "0.11.0", "0.10.0")
    rebind_benchmark(root)
    rehash_preserved(root)
    return root


def migrate(root: Path) -> None:
    """The steps docs/migration-v0.11.md describes, in order."""

    set_version(root, "0.10.0", "0.11.0")
    old, new = rebind_benchmark(root)
    state_path = root / "teardown.json"
    state = json.loads(state_path.read_text())
    state["decisions"].append({
        "id": "benchmark-revision-v0-11",
        "made_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "decision": f"Re-bound success-profile.json digest {old} -> {new}",
        "reason": "schema_version bump 0.10.0 -> 0.11.0 only; no criterion, weight, or target changed",
        "evidence_ids": [],
    })
    state_path.write_text(json.dumps(state, indent=2) + "\n")
    rehash_preserved(root)


def test_version_bump_alone_breaks_byte_bound_contracts(tmp_path):
    root = v010_teardown(tmp_path)
    set_version(root, "0.10.0", "0.11.0")
    result = validate(root)
    assert result.returncode == 1
    assert "benchmark digest does not match" in result.stderr
    assert "preserved file digest mismatch" in result.stderr


def test_interview_statements_stay_optional(tmp_path):
    # A v0.11 teardown with no interviews.jsonl needs no new content.
    root = v010_teardown(tmp_path)
    set_version(root, "0.10.0", "0.11.0")
    rebind_benchmark(root)
    rehash_preserved(root)
    assert validate(root).returncode == 0


def test_documented_migration_produces_a_valid_v011_teardown(tmp_path):
    root = v010_teardown(tmp_path)
    migrate(root)
    result = validate(root)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(("doc", "script"), [("migration-v0.10.md", "migrate_v010.py"), ("migration-v0.11.md", "migrate_v011.py")])
def test_migration_doc_names_every_byte_bound_step(doc, script):
    text = (ROOT / "docs" / doc).read_text()
    for phrase in ("schema_version", "benchmark", "sha256", "decisions", "preservation-manifest.json", script):
        assert phrase in text, phrase


@pytest.mark.parametrize("script", ["migrate_v010.py", "migrate_v011.py"])
def test_repository_migration_refuses_to_run_again(script):
    watched = [*(ROOT / "skills" / "saas-rebuild" / "templates").glob("*.json"), ROOT / "skill-versions.json"]
    before = {path: path.read_bytes() for path in watched}
    result = subprocess.run([sys.executable, str(ROOT / "scripts" / script)], text=True, capture_output=True)
    assert result.returncode == 1
    assert "already been applied" in result.stderr
    assert {path: path.read_bytes() for path in before} == before
