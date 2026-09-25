#!/usr/bin/env python3
"""Run boundary-gated System One annotations for a teardown.

Offline mode performs no writes and no network I/O. Shadow/live/replay write
only model-annotations.jsonl and .systemone audit/cache records; they never
rewrite the evidence artifacts or record a model-owned verdict.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys
from typing import Any, Iterator, NamedTuple

TOOL_ROOT = Path(__file__).resolve().parent
if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))

from systemone.client import SystemOne  # noqa: E402
from systemone.boundary import BoundaryRefused  # noqa: E402
from systemone.limiter import BudgetGuard  # noqa: E402
from systemone.runner import Runner  # noqa: E402
from systemone.state import StateRefused, build_state  # noqa: E402


CATALOG_ROOT = TOOL_ROOT / "systemone" / "catalog"
SENSITIVITY = {"public": 0, "internal": 1, "confidential": 2, "restricted": 3}
# I1 offers at most this many candidate features; its catalog has one
# candidate-N option per slot.
CANDIDATE_SLOTS = 5
STOP_WORDS = frozenset(
    "about after all and any are before but can does each every for from has have into its "
    "just more most not only other our out over some than that the their them then there "
    "these they this those through too very was were what when where which while who why "
    "will with would you your".split()
)


def load_local_api_key() -> None:
    """Load only TYPESAFE_API_KEY from the ignored repository .env file."""

    if os.environ.get("TYPESAFE_API_KEY"):
        return
    dotenv = TOOL_ROOT.parents[2] / ".env"
    if not dotenv.is_file():
        return
    for line in dotenv.read_text(encoding="utf-8").splitlines():
        if line.startswith("TYPESAFE_API_KEY="):
            value = line.partition("=")[2].strip()
            if value:
                os.environ["TYPESAFE_API_KEY"] = value
            return


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[Any]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


class Target(NamedTuple):
    """One thing to ask about: what the model sees, and what it never sees.

    ``source`` is minimized and sent. ``context`` holds the target's declared
    fields that comparators check answers against; it stays local, so the
    model cannot echo the declared value back.
    """

    kind: str
    id: str
    source: dict[str, Any]
    data_class: str
    context: dict[str, Any]
    # Feature ids behind a candidate-slot question's options, in slot order.
    # An empty tuple means no candidate qualified, so the target is skipped.
    candidates: tuple[str, ...] | None = None


def strictest(classes: list[str], default: str) -> str:
    return max(classes or [default], key=lambda value: SENSITIVITY.get(value, 99))


def feature_targets(root: Path, boundary: dict[str, Any]) -> Iterator[Target]:
    default = (boundary.get("source_classes") or {}).get("feature-inventory.json", "restricted")
    for feature in load_json(root / "feature-inventory.json"):
        evidence = feature.get("evidence", [])
        yield Target(
            "feature",
            str(feature.get("id", "unknown")),
            {
                "name": feature.get("name"),
                "kind": feature.get("kind"),
                "nav_path": feature.get("nav_path"),
                "claims": [citation.get("claim", "") for citation in evidence],
            },
            strictest([citation.get("sensitivity", default) for citation in evidence], default),
            {"usage": feature.get("usage")},
        )


def citation_targets(root: Path, boundary: dict[str, Any]) -> Iterator[Target]:
    # evidence_class and plane stay out of the state: C2 asks the model which
    # class the text is, and the plane (telemetry, config-census) gives it away.
    default = (boundary.get("source_classes") or {}).get("feature-inventory.json", "restricted")
    seen: set[str] = set()
    for feature in load_json(root / "feature-inventory.json"):
        for citation in feature.get("evidence", []):
            evidence_id = str(citation.get("evidence_id", "unknown"))
            if evidence_id in seen:
                continue
            seen.add(evidence_id)
            yield Target(
                "citation",
                evidence_id,
                {"claim": citation.get("claim"), "source": citation.get("source")},
                citation.get("sensitivity", default),
                {"evidence_class": citation.get("evidence_class")},
            )


def edge_targets(root: Path, boundary: dict[str, Any]) -> Iterator[Target]:
    # E1's criteria read "the first named object acts on the second", so
    # `first` must be the edge's source. The edge type stays local for the
    # comparator, and node verdicts are never read.
    default = (boundary.get("source_classes") or {}).get("graph.json", "restricted")
    citations = {
        citation.get("evidence_id"): citation
        for feature in load_json(root / "feature-inventory.json")
        for citation in feature.get("evidence", [])
    }
    graph = load_json(root / "graph.json")
    labels = {node.get("id"): node.get("label") or node.get("id") for node in graph.get("nodes", [])}
    for edge in graph.get("edges", []):
        cited = [citations[evidence_id] for evidence_id in edge.get("evidence_ids", []) if evidence_id in citations]
        yield Target(
            "graph-edge",
            f"{edge.get('from')}|{edge.get('to')}|{edge.get('type')}",
            {
                "first": labels.get(edge.get("from"), edge.get("from")),
                "second": labels.get(edge.get("to"), edge.get("to")),
                "excerpt": [citation.get("claim", "") for citation in cited],
            },
            strictest([citation.get("sensitivity", default) for citation in cited], default),
            {"type": edge.get("type")},
        )


def interview_targets(root: Path, boundary: dict[str, Any]) -> Iterator[Target]:
    # Only usage statements an analyst linked to a feature, from respondents
    # who consented to model perception. Only the statement text is sent;
    # role, group, and the feature's declared usage stay local.
    usage = {feature.get("id"): feature.get("usage") for feature in load_json(root / "feature-inventory.json")}
    for statement in load_jsonl(root / "interviews.jsonl"):
        consent = statement.get("consent") or {}
        if (
            statement.get("topic") != "usage"
            or statement.get("feature_id") is None
            or consent.get("recorded") is not True
            or "model-perception" not in (consent.get("scopes") or [])
        ):
            continue
        yield Target(
            "interview-statement",
            str(statement.get("statement_id", "unknown")),
            {"statement": statement.get("text")},
            statement.get("sensitivity", "restricted"),
            {"usage": usage.get(statement.get("feature_id"))},
        )


def words(text: str) -> set[str]:
    """Lowercase letter runs of three or more, minus stop words, crudely singular."""

    found = set()
    for word in re.findall(r"[a-z]+", text.lower()):
        if len(word) < 3 or word in STOP_WORDS:
            continue
        if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
            word = word[:-1]
        found.add(word)
    return found


def select_candidates(text: str, features: list[dict[str, Any]], limit: int = CANDIDATE_SLOTS) -> list[dict[str, Any]]:
    """Deterministic candidate features for one statement, in feature-id order.

    A statement sharing no word with any feature's name or navigation path
    gets no candidates. Otherwise a small inventory is offered whole, and a
    larger one by shared-word count with ties broken by id. The result is
    sorted by id, so a candidate's slot says nothing about its rank.
    """

    statement = words(text)
    scored = [
        (len(statement & words(f"{feature.get('name', '')} {feature.get('nav_path', '')}")), str(feature.get("id")), feature)
        for feature in features
    ]
    if not any(score for score, _, _ in scored):
        return []
    if len(scored) > limit:
        scored = sorted(scored, key=lambda item: (-item[0], item[1]))[:limit]
    return [feature for _, _, feature in sorted(scored, key=lambda item: item[1])]


def matching_targets(root: Path, boundary: dict[str, Any]) -> Iterator[Target]:
    # Unlinked statements from respondents who consented to model perception.
    # Only the statement and the candidates' names and navigation paths are
    # sent; usage, verdict, criticality, and evidence would bias the match.
    inventory_class = (boundary.get("source_classes") or {}).get("feature-inventory.json", "restricted")
    features = load_json(root / "feature-inventory.json")
    for statement in load_jsonl(root / "interviews.jsonl"):
        consent = statement.get("consent") or {}
        if (
            statement.get("feature_id") is not None
            or consent.get("recorded") is not True
            or "model-perception" not in (consent.get("scopes") or [])
        ):
            continue
        chosen = select_candidates(str(statement.get("text", "")), features)
        yield Target(
            "interview-statement",
            str(statement.get("statement_id", "unknown")),
            {
                "statement": statement.get("text"),
                "candidates": [{"name": feature.get("name"), "nav_path": feature.get("nav_path")} for feature in chosen],
            },
            strictest([statement.get("sensitivity", "restricted"), inventory_class], "restricted"),
            {},
            tuple(str(feature.get("id")) for feature in chosen),
        )


# Question sets without a reader are refused rather than asked about the
# wrong kind of target.
READERS = {
    "feature-perception": feature_targets,
    "citation-checks": citation_targets,
    "graph-edges": edge_targets,
    "interviews": interview_targets,
    "interview-matching": matching_targets,
}


def target_state(target: Target, allowed: list[str]):
    return build_state(
        target.source,
        {key: target.data_class for key in target.source},
        allowed_fields=tuple(target.source),
        allowed_data_classes=allowed,
        strip_numbers=True,
    )


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("artifact_root", type=Path)
    result.add_argument("--set", dest="question_set", default="feature-perception")
    result.add_argument("--mode", choices=("offline", "shadow", "live", "replay"), default="offline")
    result.add_argument("--endpoint-id", default="typesafe-systemone")
    result.add_argument("--model", default="jev-latest")
    result.add_argument("--limit", type=int, default=None)
    result.add_argument("--max-calls", type=int, default=12)
    result.add_argument("--max-input-tokens", type=int, default=20_000)
    result.add_argument("--max-cost-usd", type=float, default=None)
    result.add_argument("--price-per-million-input-tokens", type=float, default=None)
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    root = args.artifact_root.resolve()
    teardown_path = root / "teardown.json"
    inventory_path = root / "feature-inventory.json"
    if not teardown_path.is_file() or not inventory_path.is_file():
        parser().error("artifact root must contain teardown.json and feature-inventory.json")
    if args.mode == "offline":
        print(json.dumps({
            "mode": "offline",
            "network_calls": 0,
            "artifacts_changed": False,
            "reason": "System One disabled; existing deterministic workflow is unchanged",
        }, sort_keys=True))
        return 0

    catalog_path = CATALOG_ROOT / f"{args.question_set}.json"
    if not catalog_path.is_file():
        parser().error(f"unknown question set: {args.question_set}")
    reader = READERS.get(args.question_set)
    if reader is None:
        parser().error(
            f"question set {args.question_set!r} has no target reader yet; "
            f"supported: {', '.join(sorted(READERS))}"
        )
    if not isinstance(load_json(inventory_path), list):
        parser().error("feature-inventory.json must contain an array")
    if args.question_set == "graph-edges" and not (root / "graph.json").is_file():
        parser().error("the graph-edges question set needs graph.json")
    if args.question_set in {"interviews", "interview-matching"} and not (root / "interviews.jsonl").is_file():
        parser().error(f"the {args.question_set} question set needs interviews.jsonl")

    load_local_api_key()
    catalog_doc = load_json(catalog_path)
    teardown = load_json(teardown_path)
    boundary = teardown.get("data_boundary") or {}
    allowed = list(boundary.get("allowed_data_classes") or [])
    budget = BudgetGuard(
        max_calls=args.max_calls,
        max_input_tokens=args.max_input_tokens,
        max_cost_usd=args.max_cost_usd,
        price_per_million_input_tokens=args.price_per_million_input_tokens,
    )
    runner = Runner(
        root,
        teardown,
        endpoint_id=args.endpoint_id,
        purpose=catalog_doc["purpose"],
        mode=args.mode,
        client=SystemOne(model=args.model),
        budget=budget,
    )
    targets = list(reader(root, boundary))
    selected = targets[: args.limit] if args.limit is not None else targets
    refused: list[dict[str, str]] = []
    skipped: list[dict[str, str]] = []
    for target in selected:
        if target.candidates == ():
            skipped.append({"target_id": target.id, "reason": "no feature shares a word with the statement"})
            continue
        try:
            envelope = target_state(target, allowed)
            runner.ask(
                target_kind=target.kind,
                target_id=target.id,
                state=envelope.value,
                data_classes=envelope.data_classes,
                catalog_version=catalog_doc["version"],
                catalog=catalog_doc["questions"],
                context=target.context,
                candidates=target.candidates,
            )
        except StateRefused as error:
            runner.record_refusal(
                target_kind=target.kind,
                target_id=target.id,
                data_classes=(),
                gate="state",
                reason=str(error),
            )
            refused.append({"target_id": target.id, "reason": str(error)})
        except BoundaryRefused as error:
            refused.append({"target_id": target.id, "reason": str(error)})

    annotations_path = runner.write_annotations()
    summary = runner.summary()
    output = {
        "run_id": summary.run_id,
        "mode": summary.mode,
        "calls": summary.calls,
        "cache_hits": summary.cache_hits,
        "input_tokens": summary.input_tokens,
        "output_tokens": summary.output_tokens,
        "annotations": summary.annotations,
        "refused": refused,
        "skipped": skipped,
        "calllog_head": summary.calllog_head,
        "annotations_path": annotations_path.name if annotations_path else None,
        "estimated_cost_usd": budget.estimated_cost_usd,
    }
    print(json.dumps(output, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
