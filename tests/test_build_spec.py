"""The portable rebuild spec is assembled from evidence, never from judgment."""

import importlib.util
import json
import shutil

import jsonschema
import pytest

from conftest import REPO_ROOT, SKILL_DIR


EXAMPLE = REPO_ROOT / "examples" / "synthetic-crm"
SCHEMA = json.loads((SKILL_DIR / "templates" / "rebuild-spec.schema.json").read_text())


def load_builder():
    spec = importlib.util.spec_from_file_location("build_spec", SKILL_DIR / "tools" / "build_spec.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def run_dir(tmp_path):
    for name in ("teardown.json", "autopilot.json", "feature-inventory.json",
                 "preservation-manifest.json", "pairs.jsonl"):
        shutil.copy(EXAMPLE / name, tmp_path / name)
    return tmp_path


def test_example_spec_matches_schema_and_accounts_for_every_feature(run_dir):
    spec = load_builder().build(run_dir)
    jsonschema.Draft202012Validator(SCHEMA).validate(spec)
    features = json.loads((run_dir / "feature-inventory.json").read_text())
    placed = [x["id"] for key in ("build", "do_not_build", "undecided") for x in spec[key]]
    assert sorted(placed) == sorted(f["id"] for f in features)


def test_unknown_usage_is_never_excluded_and_never_built(run_dir):
    features = [
        {"id": "a", "name": "A", "usage": "unknown", "verdict": "DEFER", "why": "w",
         "observed_signals": {"empty_state": True}, "evidence": []},
        {"id": "b", "name": "B", "usage": "unknown", "evidence": []},
        {"id": "c", "name": "C", "usage": "rare", "evidence": []},  # claims use, cites nothing
    ]
    (run_dir / "feature-inventory.json").write_text(json.dumps(features))
    spec = load_builder().build(run_dir)
    assert spec["build"] == [] and spec["do_not_build"] == []
    assert {u["id"]: u["state"] for u in spec["undecided"]} == {
        "a": "empty-so-far", "b": "not-checked", "c": "not-checked"}


def test_only_system_of_record_replay_pairs_become_tests(run_dir):
    pairs = [json.loads(line) for line in (run_dir / "pairs.jsonl").read_text().splitlines() if line.strip()]
    expected = [p["pair_id"] for p in pairs
                if p["pair_type"] == "replay" and p["label_authority"] == "system-of-record"]
    spec = load_builder().build(run_dir)
    assert [t["id"] for t in spec["acceptance_tests"]] == expected


def test_non_admin_run_and_missing_history_are_stated_as_limits(run_dir):
    data = json.loads((run_dir / "autopilot.json").read_text())
    data["access_level"] = "view-only"
    (run_dir / "autopilot.json").write_text(json.dumps(data))
    (run_dir / "pairs.jsonl").write_text("")
    spec = load_builder().build(run_dir)
    text = " ".join(spec["limits"])
    assert "non-admin" in text and "No recorded history" in text


def test_command_writes_json_and_html(run_dir, monkeypatch):
    builder = load_builder()
    monkeypatch.setattr("sys.argv", ["build_spec.py", str(run_dir)])
    assert builder.main() == 0
    jsonschema.Draft202012Validator(SCHEMA).validate(json.loads((run_dir / "rebuild-spec.json").read_text()))
    assert "<!doctype html>" in (run_dir / "rebuild-spec.html").read_text()


def test_document_evidence_can_place_a_feature_but_is_named_as_a_limit(run_dir):
    cite = {"evidence_id": "ev-1", "claim": "Trained as a daily procedure.", "source": "manual",
            "evidence_class": "structure", "plane": "document", "supports": ["usage", "verdict"]}
    features = [
        {"id": "a", "name": "A", "usage": "rare", "evidence": [cite]},
        {"id": "b", "name": "B", "usage": "never", "why": "Licensed, never switched on.", "evidence": [cite]},
        {"id": "c", "name": "C", "usage": "rare", "evidence": [dict(cite, supports=["verdict"])]},
    ]
    (run_dir / "feature-inventory.json").write_text(json.dumps(features))
    spec = load_builder().build(run_dir)
    jsonschema.Draft202012Validator(SCHEMA).validate(spec)
    assert [x["id"] for x in spec["build"]] == ["a"]
    assert [x["id"] for x in spec["do_not_build"]] == ["b"]
    assert [x["id"] for x in spec["undecided"]] == ["c"]
    assert any("Built from documents" in limit for limit in spec["limits"])
