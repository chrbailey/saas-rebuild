"""Set-specific, classified input jobs and local target registries."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any

from .boundary import DATA_CLASSES
from .state import StateEnvelope, build_state


SETS = {
    "feature-perception": ("feature", ("name", "kind", "nav_path", "claims")),
    "citation-checks": ("citation", ("claim", "scope", "source_text")),
    "graph-edges": ("graph-edge", ("source_label", "target_label", "script_body", "deployment_text")),
    "process-mining": ("event-signature", ("description", "control", "activity_labels")),
    "sanitization": ("pair", ("input", "output")),
    "replay-residuals": ("replay-residual", ("difference", "registered_divergences", "legacy_notes")),
    "interviews": ("interview-statement", ("statement", "candidate_features")),
}


def load_registry(root: Path) -> list[dict[str, Any]]:
    path = root / "model-inputs.jsonl"
    if not path.is_file():
        return []
    records = []
    seen = set()
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict) or set(row) - {
            "question_set", "target_id", "fields", "field_classes",
            "contains_phi", "contains_eu_personal_data",
        }:
            raise ValueError(f"model-inputs.jsonl:{number}: invalid record fields")
        name, target = row.get("question_set"), row.get("target_id")
        if not isinstance(name, str) or name not in SETS or not isinstance(target, str) or not target:
            raise ValueError(f"model-inputs.jsonl:{number}: invalid question set or target")
        if not isinstance(row.get("fields"), dict) or not row["fields"] or set(row["fields"]) - set(SETS[name][1]):
            raise ValueError(f"model-inputs.jsonl:{number}: fields do not match question set")
        if not isinstance(row.get("field_classes"), dict) or any(c not in DATA_CLASSES for c in row["field_classes"].values()):
            raise ValueError(f"model-inputs.jsonl:{number}: invalid field classifications")
        if any(type(row.get(flag, False)) is not bool for flag in ("contains_phi", "contains_eu_personal_data")):
            raise ValueError(f"model-inputs.jsonl:{number}: privacy flags must be booleans")
        key = (name, target)
        if key in seen:
            raise ValueError(f"model-inputs.jsonl:{number}: duplicate target")
        seen.add(key)
        records.append(row)
    return records


def _class(*values: str) -> str:
    if any(value not in DATA_CLASSES for value in values):
        raise ValueError("unknown source classification")
    return max(values, key=DATA_CLASSES.index)


@dataclass(frozen=True)
class Job:
    kind: str
    target_id: str
    fields: dict[str, Any]
    classes: dict[str, str]
    allowed_fields: tuple[str, ...]
    contains_phi: bool = False
    contains_eu_personal_data: bool = False
    context: dict[str, Any] = field(default_factory=dict)

    def envelope(self, allowed: list[str]) -> StateEnvelope:
        return build_state(self.fields, self.classes, allowed_fields=self.allowed_fields, allowed_data_classes=allowed)


def feature_job(feature: dict[str, Any], source_class: str) -> Job:
    sensitivity = _class(source_class, *(citation.get("sensitivity", "restricted") for citation in feature.get("evidence", [])))
    fields = {key: feature.get(key) for key in ("name", "kind", "nav_path")}
    fields["claims"] = [citation.get("claim", "") for citation in feature.get("evidence", [])]
    return Job("feature", feature["id"], fields, {key: sensitivity for key in fields}, SETS["feature-perception"][1], context={"usage": feature.get("usage")})


def jobs(root: Path, teardown: dict[str, Any], name: str) -> list[Job]:
    if name not in SETS:
        raise ValueError("unknown question set")
    features = json.loads((root / "feature-inventory.json").read_text(encoding="utf-8"))
    if not isinstance(features, list):
        raise ValueError("feature-inventory.json must contain an array")
    classes = teardown.get("data_boundary", {}).get("source_classes", {})
    if name == "feature-perception":
        return [feature_job(feature, classes.get("feature-inventory.json", "restricted")) for feature in features]

    targets: dict[str, dict[str, Any]] = {}
    if name == "citation-checks":
        targets = {citation["evidence_id"]: citation for feature in features for citation in feature.get("evidence", [])}
    elif name == "graph-edges":
        graph = json.loads((root / "graph.json").read_text(encoding="utf-8"))
        targets = {f"{edge['from']}|{edge['to']}|{edge['type']}": edge for edge in graph["edges"]}
    elif name == "sanitization":
        targets = {pair["pair_id"]: pair for line in (root / "pairs.jsonl").read_text(encoding="utf-8").splitlines() if line.strip() for pair in [json.loads(line)]}

    result = []
    for row in load_registry(root):
        if row["question_set"] != name:
            continue
        target_id = row["target_id"]
        if name in {"citation-checks", "graph-edges", "sanitization"} and target_id not in targets:
            raise ValueError(f"{name} target does not resolve: {target_id}")
        if name == "sanitization" and targets[target_id]["dataset_role"] == "holdout-eval":
            raise ValueError("holdout-eval pairs cannot be sent for model assistance")
        fields = dict(row["fields"])
        if name == "citation-checks":
            if not fields.get("source_text"):
                raise ValueError("citation checks require actual source_text")
            fields["claim"] = targets[target_id]["claim"]
        if name == "sanitization":
            pair = targets[target_id]
            fields = {"input": pair["input"], "output": pair["output"]}
        floor = classes.get("model-inputs.jsonl", "restricted")
        if name == "citation-checks":
            floor = _class(floor, classes.get("feature-inventory.json", "restricted"), targets[target_id]["sensitivity"])
        if name == "sanitization":
            floor = _class(floor, classes.get("pairs.jsonl", "restricted"), *(c["sensitivity"] for c in pair.get("evidence", [])))
        if name == "graph-edges":
            evidence = {c["evidence_id"]: c for feature in features for c in feature.get("evidence", [])}
            floor = _class(floor, classes.get("graph.json", "restricted"), *(evidence.get(eid, {}).get("sensitivity", "restricted") for eid in targets[target_id].get("evidence_ids", [])))
        field_classes = {key: _class(floor, row["field_classes"].get(key, "restricted")) for key in fields}
        if name == "citation-checks":
            field_classes["claim"] = floor  # Copied from classified inventory, not a user field.
        context = {}
        if name == "citation-checks":
            context = {"evidence_class": targets[target_id].get("evidence_class")}
        if name == "graph-edges":
            context = {"type": targets[target_id].get("type")}
        result.append(Job(SETS[name][0], target_id, fields, field_classes, SETS[name][1], row.get("contains_phi", False), row.get("contains_eu_personal_data", False), context))
    if not result:
        raise ValueError(f"{name} requires classified {name} records in model-inputs.jsonl")
    return result
