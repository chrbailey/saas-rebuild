#!/usr/bin/env python3
"""Print a local deterministic decision proposal and model review queue."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path

from rules.matrix import decide
from rules.raise_only import apply_raise
from rules.why import render_why


def report(root: Path) -> dict:
    features = json.loads((root / "feature-inventory.json").read_text(encoding="utf-8"))
    path = root / "model-annotations.jsonl"
    annotations = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.is_file() else []
    rows = []
    for feature in features:
        baseline = decide(feature)
        citation_ids = {citation["evidence_id"] for citation in feature.get("evidence", [])}
        related = [a for a in annotations if (a["target_kind"] == "feature" and a["target_id"] == feature["id"]) or (a["target_kind"] == "citation" and a["target_id"] in citation_ids)]
        raised = apply_raise(baseline, related)
        rows.append({
            "feature_id": feature["id"], "name": feature["name"],
            "recorded_verdict": feature.get("verdict"),
            "baseline": asdict(baseline), "proposal": asdict(raised.decision),
            "baseline_reason": render_why(baseline), "proposal_reason": render_why(raised.decision),
            "review_reasons": list(raised.review_reasons), "annotation_ids": list(raised.annotation_ids),
            "requires_human_decision": raised.decision.verdict in {None, "DROP", "DEFER"} or bool(raised.review_reasons),
        })
    return {
        "schema_version": "0.10.0", "network_calls": 0,
        "artifacts_changed": False, "features": rows,
        "other_review_items": [a for a in annotations if a["target_kind"] != "feature" and a["effect"] != "none" and a["resolution"]["status"] == "open"],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact_root", type=Path)
    args = parser.parse_args()
    print(json.dumps(report(args.artifact_root), indent=2, sort_keys=True))
