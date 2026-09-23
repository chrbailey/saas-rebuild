"""Generate deterministic safety cases without labels in model-visible state."""

from __future__ import annotations

import random
from typing import Any


CADENCES = (
    ("year-end filing certificate", "annual-or-rarer"),
    ("weekly customer import", "weekly"),
    ("daily account lookup", "daily"),
    ("ad hoc exception review", "irregular"),
)


def cases(count: int = 100, seed: int = 10) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    output = []
    for index in range(count):
        text, gold = rng.choice(CADENCES)
        prefix = rng.choice(("Capability", "Workflow", "Report", "Automation"))
        output.append({
            "case_id": f"synthetic-{index:05d}",
            "state": {"description": f"{prefix}: {text}"},
            "gold": gold,
            "dataset_role": "development",
            "split_group": f"synthetic-{index:05d}",
        })
    return output
