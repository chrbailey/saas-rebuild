"""Append-only, hash-chained audit log.

Export compliance recordkeeping is not optional: EAR 762.6 requires five
years from the date of export (or of the transaction), and OFAC 501.601
requires five years for records relating to blocked or rejected transactions.
An auditor will ask two things -- what did you screen, and can you prove the
record has not been edited since.

The chain answers the second. Each entry stores the SHA-256 of the previous
entry, so altering any historical line invalidates every hash after it.
Deleting a line breaks the sequence numbers. This is tamper-*evident*, not
tamper-proof: a determined insider with write access can recompute the whole
chain. For tamper-resistance, ship the daily head hash somewhere the operator
cannot rewrite -- `xscreen audit head` prints it for exactly that purpose.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

GENESIS = "0" * 64
RETENTION_YEARS = 5


def _hash_entry(entry: dict[str, Any]) -> str:
    body = {k: v for k, v in entry.items() if k != "hash"}
    blob = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


@dataclass
class AuditLog:
    path: Path

    def __post_init__(self) -> None:
        self.path = Path(self.path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    # -- reading ---------------------------------------------------------

    def entries(self) -> Iterator[dict[str, Any]]:
        if not self.path.exists():
            return iter(())
        def _gen() -> Iterator[dict[str, Any]]:
            with self.path.open(encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if line:
                        yield json.loads(line)
        return _gen()

    def head(self) -> tuple[int, str]:
        """(sequence, hash) of the last entry, or (0, GENESIS) when empty."""
        seq, h = 0, GENESIS
        for e in self.entries():
            seq, h = e.get("seq", seq), e.get("hash", h)
        return seq, h

    # -- writing ---------------------------------------------------------

    def append(self, event: str, payload: dict[str, Any], actor: str | None = None) -> dict[str, Any]:
        seq, prev = self.head()
        entry: dict[str, Any] = {
            "seq": seq + 1,
            "ts": datetime.now(timezone.utc).isoformat(),
            "actor": actor or os.environ.get("XSCREEN_ACTOR") or os.environ.get("USER") or "unknown",
            "event": event,
            "payload": payload,
            "prev_hash": prev,
        }
        entry["hash"] = _hash_entry(entry)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        return entry

    # -- verification ----------------------------------------------------

    def verify(self) -> tuple[bool, list[str]]:
        """Walk the chain. Returns (intact, problems)."""
        problems: list[str] = []
        prev_hash = GENESIS
        expected_seq = 1
        count = 0
        for e in self.entries():
            count += 1
            if e.get("seq") != expected_seq:
                problems.append(
                    f"entry {count}: sequence is {e.get('seq')}, expected "
                    f"{expected_seq} -- an entry was deleted or reordered"
                )
            if e.get("prev_hash") != prev_hash:
                problems.append(
                    f"seq {e.get('seq')}: prev_hash does not match the previous "
                    "entry's hash -- history was rewritten at or before this point"
                )
            recomputed = _hash_entry(e)
            if e.get("hash") != recomputed:
                problems.append(
                    f"seq {e.get('seq')}: content hash mismatch -- this entry's "
                    "payload was modified after it was written"
                )
            prev_hash = e.get("hash", prev_hash)
            expected_seq = (e.get("seq") or expected_seq) + 1
        if count == 0:
            problems.append("audit log is empty")
        return (not problems), problems

    def retention_floor(self, now: datetime | None = None) -> str:
        """ISO date before which entries may lawfully be purged."""
        now = now or datetime.now(timezone.utc)
        return now.replace(year=now.year - RETENTION_YEARS).date().isoformat()
