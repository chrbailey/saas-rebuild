"""Content-addressed record/replay cache."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .digest import stable_digest


class CacheMiss(KeyError):
    pass


def cache_key(endpoint: str, model: str, state: Any, questions: dict[str, Any]) -> str:
    return stable_digest({"endpoint": endpoint, "model": model, "state": state, "questions": questions})


class ResponseCache:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def _path(self, key: str) -> Path:
        if len(key) != 64 or any(character not in "0123456789abcdef" for character in key):
            raise ValueError("cache key must be a SHA-256 digest")
        return self.root / f"{key}.json"

    def get(self, key: str) -> dict[str, Any]:
        target = self._path(key)
        try:
            value = json.loads(target.read_text(encoding="utf-8"))
        except FileNotFoundError as error:
            raise CacheMiss(key) from error
        if not isinstance(value, dict) or value.get("cache_key") != key:
            raise ValueError(f"invalid cache record: {target}")
        return value

    def put(self, key: str, response: dict[str, Any]) -> Path:
        self.root.mkdir(parents=True, exist_ok=True)
        target = self._path(key)
        temporary = target.with_suffix(f".{os.getpid()}.tmp")
        record = {"cache_key": key, "response": response}
        temporary.write_text(
            json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, target)
        return target
