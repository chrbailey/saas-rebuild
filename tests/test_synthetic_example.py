"""Validate the worked example across schemas and artifact boundaries."""

import csv
import hashlib
import json
import shutil
import subprocess
import sys

import jsonschema

from conftest import REPO_ROOT, SKILL_DIR


EXAMPLE = REPO_ROOT / "examples" / "synthetic-crm"
TEMPLATES = SKILL_DIR / "templates"


def load_json(name):
    return json.loads((EXAMPLE / name).read_text(encoding="utf-8"))


def load_schema(name):
    return json.loads((TEMPLATES / name).read_text(encoding="utf-8"))


def pairs():
    return [
        json.loads(line)
        for line in (EXAMPLE / "pairs.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_every_example_artifact_passes_its_schema():
    feature_schema = load_schema("feature-inventory.schema.json")
    pair_schema = load_schema("pairs.schema.json")
    validators = {
        "teardown.json": load_schema("teardown-state.schema.json"),
        "graph.json": load_schema("dependency-graph.schema.json"),
        "preservation-manifest.json": load_schema("preservation-manifest.schema.json"),
    }
    for feature in load_json("feature-inventory.json"):
        jsonschema.Draft202012Validator(feature_schema).validate(feature)
    for pair in pairs():
        jsonschema.Draft202012Validator(pair_schema).validate(pair)
    for artifact, schema in validators.items():
        jsonschema.Draft202012Validator(schema).validate(load_json(artifact))


def test_state_references_exist_and_example_is_explicitly_synthetic():
    state = load_json("teardown.json")
    assert state["status"] == "complete"
    for relative in state["artifacts"].values():
        assert (EXAMPLE / relative).is_file(), relative
    readme = (EXAMPLE / "README.md").read_text(encoding="utf-8").lower()
    assert "fictional" in readme and "not evidence from a customer" in readme


def test_feature_evidence_ids_are_unique_and_graph_resolves_them():
    features = load_json("feature-inventory.json")
    evidence_ids = [
        citation["evidence_id"]
        for feature in features
        for citation in feature.get("evidence", [])
    ]
    assert len(evidence_ids) == len(set(evidence_ids))

    graph = load_json("graph.json")
    node_ids = {node["id"] for node in graph["nodes"]}
    for edge in graph["edges"]:
        assert edge["from"] in node_ids and edge["to"] in node_ids
        assert set(edge["evidence_ids"]) <= set(evidence_ids)


def test_graph_process_coverage_and_verdicts_match_inventory():
    features = {feature["id"]: feature for feature in load_json("feature-inventory.json")}
    graph = load_json("graph.json")
    nodes = {node["id"]: node for node in graph["nodes"]}
    supports = {
        (edge["from"], edge["to"])
        for edge in graph["edges"]
        if edge["type"] == "supports"
    }
    for feature_id, feature in features.items():
        assert nodes[feature_id]["verdict"] == feature["verdict"]
        for process in feature.get("business_processes", []):
            assert nodes[process]["type"] == "business-process"
            assert (feature_id, process) in supports


def test_absence_conclusions_respect_evidence_horizon():
    features = load_json("feature-inventory.json")
    never = [feature for feature in features if feature.get("usage") == "never"]
    assert never
    for feature in never:
        assert any(
            citation["evidence_class"] == "runtime"
            and citation["coverage"]["kind"] == "all-time"
            and "usage" in citation["supports"]
            for citation in feature["evidence"]
        )
    annual = next(feature for feature in features if feature["id"] == "annual-tax-certificate")
    assert annual["usage"] == "unknown" and annual["verdict"] == "DEFER"


def test_pair_lineages_do_not_cross_dataset_roles():
    roles_by_group = {}
    for pair in pairs():
        roles_by_group.setdefault(pair["split_group"], set()).add(pair["dataset_role"])
    assert all(len(roles) == 1 for roles in roles_by_group.values())
    holdouts = [pair for pair in pairs() if pair["dataset_role"] == "holdout-eval"]
    assert holdouts
    assert all(pair["label_authority"] != "analyst" for pair in holdouts)


def test_preservation_files_exist_with_exact_size_and_digest():
    manifest = load_json("preservation-manifest.json")
    pair_count = len(pairs())
    for artifact in manifest["artifacts"]:
        if artifact["status"] != "exported":
            assert "gap" in artifact
            continue
        for file_entry in artifact["files"]:
            path = (EXAMPLE / file_entry["path"]).resolve()
            path.relative_to(EXAMPLE.resolve())
            data = path.read_bytes()
            assert len(data) == file_entry["bytes"]
            assert hashlib.sha256(data).hexdigest() == file_entry["sha256"]
        if artifact["id"] == "behavioral-cases":
            assert artifact["record_count"] == pair_count


def test_preserved_csv_counts_match_manifest():
    manifest = load_json("preservation-manifest.json")
    counts = {artifact["id"]: artifact.get("record_count") for artifact in manifest["artifacts"]}
    with (EXAMPLE / "exports" / "customers.csv").open(newline="", encoding="utf-8") as handle:
        assert sum(1 for _ in csv.DictReader(handle)) == counts["customer-records"]
    with (EXAMPLE / "audit" / "events.csv").open(newline="", encoding="utf-8") as handle:
        assert sum(1 for _ in csv.DictReader(handle)) == counts["audit-events"]


def test_repository_validator_accepts_example():
    subprocess.run(
        [sys.executable, "scripts/validate_artifacts.py", str(EXAMPLE)],
        cwd=REPO_ROOT,
        check=True,
    )


def run_validator(path):
    return subprocess.run(
        [sys.executable, "scripts/validate_artifacts.py", str(path)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )


def test_repository_validator_rejects_cross_role_lineage_leak(tmp_path):
    target = tmp_path / "teardown"
    shutil.copytree(EXAMPLE, target)
    values = [json.loads(line) for line in (target / "pairs.jsonl").read_text().splitlines()]
    values[2]["split_group"] = values[3]["split_group"]
    (target / "pairs.jsonl").write_text(
        "\n".join(json.dumps(value, separators=(",", ":")) for value in values) + "\n",
        encoding="utf-8",
    )
    result = run_validator(target)
    assert result.returncode == 1
    assert "split_group appears in multiple dataset roles" in result.stderr


def test_repository_validator_rejects_preservation_digest_mismatch(tmp_path):
    target = tmp_path / "teardown"
    shutil.copytree(EXAMPLE, target)
    manifest_path = target / "preservation-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["artifacts"][0]["files"][0]["sha256"] = "0" * 64
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    result = run_validator(target)
    assert result.returncode == 1
    assert "preserved file digest mismatch" in result.stderr
