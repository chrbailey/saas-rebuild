"""The rendered Markdown in examples/synthetic-crm is derived from its JSON.

These tests pin the derived facts (feature ids, verdicts, reasons, evidence
ids, counts, byte sizes, digests) so the human-readable artifacts cannot drift
from the machine artifacts they claim to render. They do not test prose.
"""

import json
import re

from conftest import REPO_ROOT

EXAMPLE = REPO_ROOT / "examples" / "synthetic-crm"
VERDICTS = ("KEEP", "SIMPLIFY", "DROP", "DEFER")


def load_json(name):
    return json.loads((EXAMPLE / name).read_text(encoding="utf-8"))


def markdown_tables(text):
    """Yield (header cells, list of row cell lists) for every pipe table."""
    lines = text.splitlines()
    index = 0
    while index < len(lines) - 1:
        header, divider = lines[index], lines[index + 1]
        if header.startswith("|") and re.fullmatch(r"\|(\s*:?-+:?\s*\|)+", divider.strip()):
            rows = []
            index += 2
            while index < len(lines) and lines[index].startswith("|"):
                rows.append([cell.strip() for cell in lines[index].strip().strip("|").split("|")])
                index += 1
            yield [cell.strip() for cell in header.strip().strip("|").split("|")], rows
        else:
            index += 1


def verdict_table(path):
    """The one table whose header has Feature, Verdict, Why, and Evidence."""
    text = path.read_text(encoding="utf-8")
    matches = [
        (header, rows)
        for header, rows in markdown_tables(text)
        if {"Feature", "Verdict", "Why", "Evidence"} <= set(header)
    ]
    assert len(matches) == 1, f"{path.name}: expected exactly one verdict table"
    header, rows = matches[0]
    return [dict(zip(header, row)) for row in rows]


def codes(cell):
    return re.findall(r"`([^`]+)`", cell)


def expected_verdict_rows():
    return {
        feature["id"]: {
            "verdict": feature["verdict"],
            "usage": feature["usage"],
            "criticality": feature["criticality"],
            "replaceability": feature["replaceability"],
            "why": feature["why"],
            "evidence": [citation["evidence_id"] for citation in feature["evidence"]],
        }
        for feature in load_json("feature-inventory.json")
    }


def assert_rows_match_inventory(rows, expected, *, exact_set):
    seen = {}
    for row in rows:
        (feature_id,) = codes(row["Feature"])
        assert feature_id in expected, f"unknown feature {feature_id}"
        assert feature_id not in seen, f"duplicate row {feature_id}"
        seen[feature_id] = row
        want = expected[feature_id]
        assert row["Verdict"] == want["verdict"], feature_id
        assert row["Why"] == want["why"], feature_id
        assert codes(row["Evidence"]) == want["evidence"], feature_id
        for column in ("Usage", "Criticality", "Replaceability"):
            if column in row:
                assert row[column] == want[column.lower()], (feature_id, column)
    if exact_set:
        assert set(seen) == set(expected)
    return seen


def test_usage_analysis_verdict_table_matches_feature_inventory():
    rows = verdict_table(EXAMPLE / "usage-analysis.md")
    expected = expected_verdict_rows()
    seen = assert_rows_match_inventory(rows, expected, exact_set=True)
    order = [row["Verdict"] for row in seen.values()]
    assert order == sorted(order, key=VERDICTS.index), "rows are grouped KEEP, SIMPLIFY, DROP, DEFER"


def test_usage_analysis_counts_and_decisions_match_json():
    text = (EXAMPLE / "usage-analysis.md").read_text(encoding="utf-8")
    features = load_json("feature-inventory.json")
    counts = " / ".join(
        f"{verdict} {sum(1 for feature in features if feature['verdict'] == verdict)}"
        for verdict in VERDICTS
    )
    assert f"Verdict counts: {counts}." in text

    decisions = {decision["id"]: decision for decision in load_json("teardown.json")["decisions"]}
    tables = [rows for header, rows in markdown_tables(text) if header[0] == "Decision"]
    assert len(tables) == 1
    rendered = {codes(row[0])[0]: row for row in tables[0]}
    assert set(rendered) == set(decisions)
    for decision_id, row in rendered.items():
        decision = decisions[decision_id]
        assert row[1] == decision["made_at"]
        assert row[2] == decision["decision"]
        assert row[3] == decision["reason"]
        assert codes(row[4]) == decision["evidence_ids"]


def test_readme_verdict_excerpt_is_a_faithful_subset():
    rows = verdict_table(REPO_ROOT / "README.md")
    assert rows, "README should show a real excerpt of the verdict table"
    assert_rows_match_inventory(rows, expected_verdict_rows(), exact_set=False)


def test_inventory_lists_every_feature_citation_and_edge():
    text = (EXAMPLE / "inventory.md").read_text(encoding="utf-8")
    features = load_json("feature-inventory.json")
    graph = load_json("graph.json")
    tables = {header[0]: (header, rows) for header, rows in markdown_tables(text)}

    header, rows = tables["Feature"]
    assert [codes(row[0])[-1] for row in rows] == [feature["id"] for feature in features]
    for row, feature in zip(rows, features):
        record = dict(zip(header, row))
        assert record["Nav path"] == feature["nav_path"]
        assert record["Kind"] == feature["kind"]
        assert codes(record["Entities"]) == feature["data_entities"]
        assert codes(record["Actions"]) == feature["actions"]
        assert record["Usage"] == feature["usage"]
        count = feature["observed_signals"]["record_count"]
        assert f"record_count {'null' if count is None else count}" in record["Observed signals"]
    assert f"## Features ({len(features)})" in text

    header, rows = tables["Evidence id"]
    citations = [(feature["id"], citation) for feature in features for citation in feature["evidence"]]
    assert f"## Evidence register ({len(citations)} citations)" in text
    assert len(rows) == len(citations)
    for row, (feature_id, citation) in zip(rows, citations):
        record = dict(zip(header, row))
        assert codes(record["Evidence id"]) == [citation["evidence_id"]]
        assert codes(record["Feature"]) == [feature_id]
        assert record["Class / plane"] == f"{citation['evidence_class']} / {citation['plane']}"
        assert record["Confidence"] == citation["confidence"]
        assert record["Supports"] == ", ".join(citation["supports"])
        assert record["Claim"] == citation["claim"]
        coverage = citation["coverage"]
        assert record["Coverage"].startswith(coverage["kind"])
        for bound in ("start", "end"):
            if coverage.get(bound):
                assert coverage[bound] in record["Coverage"]

    header, rows = tables["From"]
    assert f"## Edges ({len(graph['edges'])})" in text
    assert len(rows) == len(graph["edges"])
    for row, edge in zip(rows, graph["edges"]):
        record = dict(zip(header, row))
        assert codes(record["From"]) == [edge["from"]]
        assert record["Type"] == edge["type"]
        assert codes(record["To"]) == [edge["to"]]
        assert record["Runtime status"] == edge["runtime_status"]
        assert codes(record["Evidence"]) == edge["evidence_ids"]

    header, rows = tables["Node"]
    non_features = [node for node in graph["nodes"] if node["type"] != "feature"]
    assert [codes(row[0])[0] for row in rows] == [node["id"] for node in non_features]


def test_extraction_runbook_matches_state_manifest_and_files():
    text = (EXAMPLE / "extraction-runbook.md").read_text(encoding="utf-8")
    state = load_json("teardown.json")
    manifest = load_json("preservation-manifest.json")
    tables = {header[0]: (header, rows) for header, rows in markdown_tables(text)}

    header, rows = tables["Entity"]
    assert len(rows) == len(state["extraction"])
    for row, entry in zip(rows, state["extraction"]):
        record = dict(zip(header, row))
        assert codes(record["Entity"]) == [entry["entity"]]
        assert record["Route"] == entry["route"]
        assert record["Status"] == entry["status"]
        assert record["Notes"] == entry.get("notes", "")
        assert f"### `{entry['entity']}`" in text

    header, rows = tables["Artifact"]
    expected = []
    for artifact in manifest["artifacts"]:
        if artifact["status"] == "exported":
            for file_entry in artifact["files"]:
                expected.append((artifact, file_entry))
        else:
            expected.append((artifact, None))
    assert len(rows) == len(expected)
    for row, (artifact, file_entry) in zip(rows, expected):
        record = dict(zip(header, row))
        assert codes(record["Artifact"]) == [artifact["id"]]
        assert record["Category"] == artifact["category"]
        assert record["Status"] == artifact["status"]
        assert record["Route"] == artifact["route"]
        if file_entry is None:
            assert record["Records"] == f"gap: {artifact['gap']['reason']}"
            continue
        assert codes(record["File"]) == [file_entry["path"]]
        assert record["Bytes"] == str(file_entry["bytes"])
        assert codes(record["SHA-256"]) == [file_entry["sha256"]]
        count = artifact.get("record_count")
        assert record["Records"] == ("null" if count is None else str(count))

    for relative in ("exports/customers.csv", "audit/events.csv"):
        columns = (EXAMPLE / relative).read_text(encoding="utf-8").splitlines()[0].split(",")
        rendered = "Expected fields: " + ", ".join(f"`{column}`" for column in columns) + "."
        assert rendered in text, relative
