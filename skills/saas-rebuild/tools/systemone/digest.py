"""Canonical SHA-256 helpers for System One records."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def stable_digest(payload: Any) -> str:
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()
