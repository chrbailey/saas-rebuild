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
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

try:
    import fcntl
except ImportError:  # Windows
    fcntl = None  # type: ignore[assignment]

try:
    import msvcrt
except ImportError:  # POSIX
    msvcrt = None  # type: ignore[assignment]

GENESIS = "0" * 64
RETENTION_YEARS = 5

# Seconds to wait for the append lock before giving up.
LOCK_TIMEOUT_S = 30


class AuditLockError(RuntimeError):
    """Could not acquire the append lock. Never write without it."""


def _hash_entry(entry: dict[str, Any]) -> str:
    body = {k: v for k, v in entry.items() if k != "hash"}
    blob = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


@contextmanager
def _exclusive(lock_path: Path) -> Iterator[None]:
    """Cross-process exclusive lock around the read-head/append sequence.

    Appending is read-then-write: read the previous entry's hash, compute this
    entry's hash from it, append. Two processes interleaving there both read
    the same predecessor and both claim it, which forks the chain -- and a
    forked chain is indistinguishable from a tampered one on `verify()`. That
    matters more here than the usual lost-update concern, because the whole
    evidentiary value of this file is that a broken chain means somebody
    edited history.

    The deployment model makes this a live risk, not a theoretical one: three
    named operator roles plus scheduled runs that can overlap a manual one.

    A separate `.lock` file is used rather than locking the log itself so the
    lock survives the log being rotated or replaced, and so readers never
    contend with writers.
    """
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fh = open(lock_path, "a+b")
    try:
        if fcntl is not None:
            import time
            deadline = time.monotonic() + LOCK_TIMEOUT_S
            while True:
                try:
                    fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except OSError:
                    if time.monotonic() >= deadline:
                        raise AuditLockError(
                            f"Could not acquire the audit lock at {lock_path} within "
                            f"{LOCK_TIMEOUT_S}s. Another screening run is writing. "
                            "Nothing was recorded; re-run rather than proceeding."
                        ) from None
                    time.sleep(0.05)
        elif msvcrt is not None:
            import time
            deadline = time.monotonic() + LOCK_TIMEOUT_S
            while True:
                try:
                    fh.seek(0)
                    msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError:
                    if time.monotonic() >= deadline:
                        raise AuditLockError(
                            f"Could not acquire the audit lock at {lock_path} within "
                            f"{LOCK_TIMEOUT_S}s. Another screening run is writing."
                        ) from None
                    time.sleep(0.05)
        yield
    finally:
        try:
            if fcntl is not None:
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
            elif msvcrt is not None:
                fh.seek(0)
                msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
        except OSError:
            pass
        fh.close()


@dataclass
class AuditLog:
    path: Path

    def __post_init__(self) -> None:
        self.path = Path(self.path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    # -- reading ---------------------------------------------------------

    def entries(self) -> Iterator[dict[str, Any]]:
        """Yield entries, marking unparseable lines rather than raising.

        A partial write -- disk full, SIGKILL mid-fsync, a stray line from
        some other tool -- used to make the log permanently unreadable AND
        unwritable, because `append` reads the head first. One truncated line
        could therefore block every future screening run, with no recovery
        short of hand-editing the evidence file.
        """
        if not self.path.exists():
            return iter(())

        def _gen() -> Iterator[dict[str, Any]]:
            with self.path.open(encoding="utf-8") as fh:
                for lineno, line in enumerate(fh, 1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError as e:
                        yield {"__corrupt__": True, "lineno": lineno, "error": str(e),
                               "raw": line[:200]}
                        continue
                    if isinstance(obj, dict):
                        yield obj
                    else:
                        yield {"__corrupt__": True, "lineno": lineno,
                               "error": f"line is a {type(obj).__name__}, not an object",
                               "raw": line[:200]}
        return _gen()

    def head(self) -> tuple[int, str]:
        """(sequence, hash) of the last well-formed entry, or (0, GENESIS)."""
        seq, h = 0, GENESIS
        for e in self.entries():
            if e.get("__corrupt__"):
                continue
            seq, h = e.get("seq", seq), e.get("hash", h)
        return seq, h

    # -- tamper marker ---------------------------------------------------

    @property
    def head_marker_path(self) -> Path:
        return self.path.parent / "HEAD"

    def _write_head_marker(self, seq: int, digest: str) -> None:
        """Persist the expected chain length beside the log.

        `verify()` walks forward from GENESIS, so a valid *prefix* verifies
        clean -- an operator who dislikes today's hits could delete the
        trailing lines and the chain would still report INTACT. Recording the
        expected head gives truncation something to contradict. Make this file
        root-owned in a real deployment: an attacker who has to edit two files
        in agreement is doing something much more deliberate than `truncate`.
        """
        self.head_marker_path.write_text(
            json.dumps({"seq": seq, "hash": digest}, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def _read_head_marker(self) -> dict[str, Any] | None:
        try:
            return json.loads(self.head_marker_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            return None

    # -- writing ---------------------------------------------------------

    @property
    def lock_path(self) -> Path:
        return self.path.with_suffix(self.path.suffix + ".lock")

    def append(self, event: str, payload: dict[str, Any], actor: str | None = None) -> dict[str, Any]:
        """Append one entry. Serialized across processes and threads.

        The read-head/hash/write sequence happens entirely inside the lock;
        see `_exclusive` for why an interleaved append is worse than a lost
        update here.
        """
        with _exclusive(self.lock_path):
            seq, prev = self.head()
            entry: dict[str, Any] = {
                "seq": seq + 1,
                "ts": datetime.now(timezone.utc).isoformat(),
                "actor": actor or os.environ.get("XSCREEN_ACTOR")
                or os.environ.get("USER") or "unknown",
                "event": event,
                "payload": payload,
                "prev_hash": prev,
            }
            entry["hash"] = _hash_entry(entry)
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")
                fh.flush()
                os.fsync(fh.fileno())
            self._write_head_marker(entry["seq"], entry["hash"])
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
            if e.get("__corrupt__"):
                problems.append(
                    f"line {e.get('lineno')}: unreadable entry ({e.get('error')}). "
                    "A partial write or foreign line is present; the chain cannot "
                    "be verified across it."
                )
                continue
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

        # Compare against the recorded head. Forward verification alone cannot
        # see a truncated tail, because a valid prefix is still a valid chain.
        marker = self._read_head_marker()
        seq, digest = self.head()
        if marker is None:
            if count:
                problems.append(
                    "no HEAD marker beside the log, so truncation of the most "
                    "recent entries cannot be ruled out. Entries written by this "
                    "version maintain one."
                )
        else:
            if marker.get("seq", 0) > seq:
                problems.append(
                    f"the log ends at entry {seq} but the HEAD marker records "
                    f"{marker.get('seq')} -- {marker.get('seq', 0) - seq} entry(ies) "
                    "have been removed from the end"
                )
            elif marker.get("seq") == seq and marker.get("hash") != digest:
                problems.append(
                    "the final entry's hash does not match the HEAD marker -- the "
                    "last entry was replaced"
                )
        return (not problems), problems

    def retention_floor(self, now: datetime | None = None) -> str:
        """ISO date before which entries may lawfully be purged."""
        now = now or datetime.now(timezone.utc)
        return now.replace(year=now.year - RETENTION_YEARS).date().isoformat()
