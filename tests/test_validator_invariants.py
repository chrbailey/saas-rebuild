"""Cross-artifact invariants the validator must reject, one mutation each.

Every case copies the synthetic example, applies a single mutation that
JSON Schema alone cannot see, and asserts the validator fails with a message
naming the offending object. Mutations to pairs.jsonl re-hash the
preservation manifest so only the mutation under test can fail.
"""

import hashlib
import json
import shutil
import subprocess
import sys

import pytest

from conftest import REPO_ROOT

EXAMPLE = REPO_ROOT / "examples" / "synthetic-crm"


def read_json(target, name):
    return json.loads((target / name).read_text(encoding="utf-8"))


def write_json(target, name, value):
    (target / name).write_text(json.dumps(value), encoding="utf-8")


def read_pairs(target):
    return [
        json.loads(line)
        for line in (target / "pairs.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def write_pairs(target, pairs):
    data = ("\n".join(json.dumps(pair, separators=(",", ":")) for pair in pairs) + "\n").encode()
    (target / "pairs.jsonl").write_bytes(data)
    manifest = read_json(target, "preservation-manifest.json")
    for artifact in manifest["artifacts"]:
        for entry in artifact.get("files", []):
            if entry["path"] == "pairs.jsonl":
                entry["sha256"] = hashlib.sha256(data).hexdigest()
                entry["bytes"] = len(data)
    write_json(target, "preservation-manifest.json", manifest)


def corpus_artifact(manifest):
    return next(item for item in manifest["artifacts"] if item["category"] == "replay-corpus")


def run_validator(path):
    return subprocess.run(
        [sys.executable, "scripts/validate_artifacts.py", str(path)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )


# --- pair citations must be copies of registered evidence ------------------


def pair_cites_unknown_evidence(target):
    pairs = read_pairs(target)
    pairs[1]["evidence"][0]["evidence_id"] = "ev-does-not-exist"
    write_pairs(target, pairs)


def pair_citation_has_unknown_parent(target):
    pairs = read_pairs(target)
    pairs[1]["evidence"][0]["derived_from"] = ["ev-phantom-parent"]
    write_pairs(target, pairs)


def pair_citation_contradicts_coverage(target):
    pairs = read_pairs(target)
    pairs[1]["evidence"][0]["coverage"] = {"kind": "all-time"}
    write_pairs(target, pairs)


def pair_citation_contradicts_claim(target):
    pairs = read_pairs(target)
    pairs[1]["evidence"][0]["claim"] = "Certificates were generated weekly."
    write_pairs(target, pairs)


def pair_citation_contradicts_class(target):
    pairs = read_pairs(target)
    pairs[3]["evidence"][0]["evidence_class"] = "runtime"
    write_pairs(target, pairs)


def pair_citation_contradicts_supports(target):
    pairs = read_pairs(target)
    pairs[3]["evidence"][0]["supports"] = ["usage"]
    write_pairs(target, pairs)


# --- preservation paths compare by resolved path, not spelling -------------


def dot_slash_evades_record_count(target):
    manifest = read_json(target, "preservation-manifest.json")
    corpus = corpus_artifact(manifest)
    corpus["files"][0]["path"] = "./pairs.jsonl"
    corpus["record_count"] = 99
    write_json(target, "preservation-manifest.json", manifest)


def dot_slash_evades_duplicate_check(target):
    manifest = read_json(target, "preservation-manifest.json")
    corpus = corpus_artifact(manifest)
    manifest["artifacts"].append(
        {
            **corpus,
            "id": "behavioral-cases-again",
            "files": [{**corpus["files"][0], "path": "./pairs.jsonl"}],
        }
    )
    write_json(target, "preservation-manifest.json", manifest)


def missing_record_count_on_replay_corpus(target):
    manifest = read_json(target, "preservation-manifest.json")
    corpus_artifact(manifest).pop("record_count")
    write_json(target, "preservation-manifest.json", manifest)


# --- graph verdicts mirror the inventory in both directions ---------------


def node_verdict_without_feature_verdict(target):
    features = read_json(target, "feature-inventory.json")
    feature = next(item for item in features if item["id"] == "annual-tax-certificate")
    feature.pop("verdict")
    feature.pop("why")
    write_json(target, "feature-inventory.json", features)


def feature_verdict_without_node_verdict(target):
    graph = read_json(target, "graph.json")
    next(node for node in graph["nodes"] if node["id"] == "customer-search").pop("verdict")
    write_json(target, "graph.json", graph)


def feature_node_without_inventory_entry(target):
    graph = read_json(target, "graph.json")
    graph["nodes"].append({"id": "ghost", "type": "feature", "label": "Ghost", "verdict": "KEEP"})
    write_json(target, "graph.json", graph)


# --- teardown.json references resolve ---------------------------------------


def decision_cites_unknown_evidence(target):
    state = read_json(target, "teardown.json")
    state["decisions"][0]["evidence_ids"] = ["ev-nope"]
    write_json(target, "teardown.json", state)


def state_declares_a_different_pairs_file(target):
    (target / "other.jsonl").write_text("", encoding="utf-8")
    state = read_json(target, "teardown.json")
    state["artifacts"]["pairs"] = "other.jsonl"
    write_json(target, "teardown.json", state)


CASES = [
    (pair_cites_unknown_evidence, "pair pair-judgment-tax cites unknown evidence: ev-does-not-exist"),
    (
        pair_citation_has_unknown_parent,
        "pair pair-judgment-tax citation ev-tax-window has unknown derivation parents: ['ev-phantom-parent']",
    ),
    (
        pair_citation_contradicts_coverage,
        "pair pair-judgment-tax citation ev-tax-window differs from its feature-inventory definition in: ['coverage']",
    ),
    (
        pair_citation_contradicts_claim,
        "pair pair-judgment-tax citation ev-tax-window differs from its feature-inventory definition in: ['claim']",
    ),
    (
        pair_citation_contradicts_class,
        "pair pair-design-search citation ev-search-criticality differs from its feature-inventory definition in: ['evidence_class']",
    ),
    (
        pair_citation_contradicts_supports,
        "pair pair-design-search citation ev-search-criticality differs from its feature-inventory definition in: ['supports']",
    ),
    (dot_slash_evades_record_count, "replay-corpus record_count does not match pairs.jsonl"),
    (
        dot_slash_evades_duplicate_check,
        "preserved file appears in multiple artifacts: pairs.jsonl (listed as ['pairs.jsonl', './pairs.jsonl'])",
    ),
    (missing_record_count_on_replay_corpus, "replay-corpus record_count does not match pairs.jsonl"),
    (
        node_verdict_without_feature_verdict,
        "verdict mismatch for annual-tax-certificate: inventory=None graph=DEFER",
    ),
    (feature_verdict_without_node_verdict, "verdict mismatch for customer-search: inventory=KEEP graph=None"),
    (feature_node_without_inventory_entry, "graph feature node has no inventory entry: ghost"),
    (decision_cites_unknown_evidence, "teardown decision decision-hybrid-target has unknown evidence: ['ev-nope']"),
    (
        state_declares_a_different_pairs_file,
        "state artifact pairs must be the validated file pairs.jsonl, not other.jsonl",
    ),
]


@pytest.mark.parametrize("mutate,message", CASES, ids=[mutate.__name__ for mutate, _ in CASES])
def test_validator_rejects_mutation(tmp_path, mutate, message):
    target = tmp_path / "teardown"
    shutil.copytree(EXAMPLE, target)
    mutate(target)
    result = run_validator(target)
    assert result.returncode == 1, result.stdout + result.stderr
    assert message in result.stderr, result.stderr


def test_pair_citation_identical_to_inventory_is_accepted(tmp_path):
    # Re-serializing the untouched pairs proves the copy check compares
    # values, not bytes, and that the manifest re-hash helper is sound.
    target = tmp_path / "teardown"
    shutil.copytree(EXAMPLE, target)
    write_pairs(target, read_pairs(target))
    result = run_validator(target)
    assert result.returncode == 0, result.stderr


def test_example_pair_citations_are_exact_copies():
    # The example must model the rule: every pair citation is byte-for-byte
    # the inventory's definition, so a reader can diff them.
    definitions = {
        citation["evidence_id"]: citation
        for feature in read_json(EXAMPLE, "feature-inventory.json")
        for citation in feature["evidence"]
    }
    cited = [citation for pair in read_pairs(EXAMPLE) for citation in pair.get("evidence", [])]
    assert cited
    for citation in cited:
        assert citation == definitions[citation["evidence_id"]]
