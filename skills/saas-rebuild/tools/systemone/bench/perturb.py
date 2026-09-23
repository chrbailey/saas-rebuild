"""Deterministic text perturbations for consistency checks."""

from __future__ import annotations


def variants(text: str) -> list[str]:
    normalized = " ".join(text.split())
    return [
        normalized,
        normalized.replace("Capability:", "Named capability:"),
        f"The tenant documentation describes this as {normalized.lower()}",
    ]
