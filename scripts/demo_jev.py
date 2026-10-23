#!/usr/bin/env python3
"""Run the Jev workflow locally against a recorded synthetic response; no network."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "skills" / "saas-rebuild" / "tools"
sys.path.insert(0, str(TOOLS))

from jev_report import report
from jev_run import feature_state
from systemone.fake import FakeSystemOne
from systemone.limiter import BudgetGuard
from systemone.runner import Runner


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="New directory for the copied example and demo outputs")
    args = parser.parse_args()
    if args.output.exists():
        parser.error("output directory already exists; choose a new path")
    shutil.copytree(ROOT / "examples" / "synthetic-crm", args.output)
    before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in args.output.glob("*.json*")}
    teardown = json.loads((args.output / "teardown.json").read_text())
    feature = json.loads((args.output / "feature-inventory.json").read_text())[0]
    catalog = json.loads((TOOLS / "systemone" / "catalog" / "feature-perception.json").read_text())
    fixture = json.loads((ROOT / "tests" / "fixtures" / "systemone" / "jev-1.13.0-feature-perception.json").read_text())
    envelope = feature_state(feature, "public", ["public"])
    request = dict(target_kind="feature", target_id=feature["id"], state=envelope.value, data_classes=envelope.data_classes, catalog_version=catalog["version"], catalog=catalog["questions"])
    shadow = Runner(args.output, teardown, endpoint_id="typesafe-systemone", purpose=catalog["purpose"], mode="shadow", client=FakeSystemOne([(fixture, {})]), budget=BudgetGuard(1, 20_000))
    original = shadow.ask(**request)
    shadow.write_annotations()
    replay = Runner(args.output, teardown, endpoint_id="typesafe-systemone", purpose=catalog["purpose"], mode="replay", client=FakeSystemOne([]), budget=BudgetGuard(0, 0))
    if replay.ask(**request) != original:
        raise RuntimeError("replay changed the recorded annotations")
    replay.write_annotations()
    for name, digest in before.items():
        if hashlib.sha256((args.output / name).read_bytes()).hexdigest() != digest:
            raise RuntimeError(f"demo changed source evidence: {name}")
    (args.output / "jev-review.json").write_text(json.dumps(report(args.output), indent=2) + "\n")
    output = {"network_calls": 0, "cost_usd": 0, "source_evidence_unchanged": True, "audit_chain_valid": shadow.calllog.verify()[0], "replay_exact": True, "simulated_run": asdict(shadow.summary()), "replay": asdict(replay.summary()), "review_report": str((args.output / "jev-review.json").resolve())}
    print(json.dumps(output, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
