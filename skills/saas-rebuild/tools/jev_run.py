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
import sys
from typing import Any

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


def feature_state(feature: dict[str, Any], default_class: str, allowed: list[str]):
    claims = [citation.get("claim", "") for citation in feature.get("evidence", [])]
    declared = [citation.get("sensitivity", default_class) for citation in feature.get("evidence", [])]
    data_class = max(declared or [default_class], key=lambda value: SENSITIVITY.get(value, 99))
    source = {
        "name": feature.get("name"),
        "kind": feature.get("kind"),
        "nav_path": feature.get("nav_path"),
        "claims": claims,
    }
    field_classes = {key: data_class for key in source}
    return build_state(
        source,
        field_classes,
        allowed_fields=("name", "kind", "nav_path", "claims"),
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

    load_local_api_key()

    catalog_path = CATALOG_ROOT / f"{args.question_set}.json"
    if not catalog_path.is_file():
        parser().error(f"unknown question set: {args.question_set}")
    catalog_doc = load_json(catalog_path)
    teardown = load_json(teardown_path)
    features = load_json(inventory_path)
    if not isinstance(features, list):
        parser().error("feature-inventory.json must contain an array")

    boundary = teardown.get("data_boundary") or {}
    allowed = list(boundary.get("allowed_data_classes") or [])
    default_class = (boundary.get("source_classes") or {}).get("feature-inventory.json", "restricted")
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
    selected = features[: args.limit] if args.limit is not None else features
    refused: list[dict[str, str]] = []
    for feature in selected:
        try:
            envelope = feature_state(feature, default_class, allowed)
            runner.ask(
                target_kind="feature",
                target_id=feature["id"],
                state=envelope.value,
                data_classes=envelope.data_classes,
                catalog_version=catalog_doc["version"],
                catalog=catalog_doc["questions"],
            )
        except StateRefused as error:
            runner.record_refusal(
                target_kind="feature",
                target_id=str(feature.get("id", "unknown")),
                data_classes=(),
                gate="state",
                reason=str(error),
            )
            refused.append({"target_id": str(feature.get("id", "unknown")), "reason": str(error)})
        except BoundaryRefused as error:
            refused.append({"target_id": str(feature.get("id", "unknown")), "reason": str(error)})

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
        "calllog_head": summary.calllog_head,
        "annotations_path": annotations_path.name if annotations_path else None,
        "estimated_cost_usd": budget.estimated_cost_usd,
    }
    print(json.dumps(output, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
