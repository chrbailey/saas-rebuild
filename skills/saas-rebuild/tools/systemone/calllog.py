"""Privacy-minimized, hash-chained call records."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .audit import AuditLog
from .client import Response
from .digest import stable_digest


class CallLog:
    def __init__(self, path: Path) -> None:
        self.audit = AuditLog(path)

    def record(
        self,
        *,
        run_id: str,
        endpoint_id: str,
        purpose: str,
        model_requested: str,
        state: Any,
        questions: dict[str, Any],
        data_classes: tuple[str, ...],
        response: Response,
        cache_key: str,
    ) -> dict[str, Any]:
        details = {
            "run_id": run_id,
            "endpoint_id": endpoint_id,
            "purpose": purpose,
            "model_requested": model_requested,
            "model_returned": response.model,
            "state_sha256": stable_digest(state),
            "questions_sha256": stable_digest(questions),
            "question_ids": sorted(questions),
            "data_classes": list(data_classes),
            "usage": response.usage,
            "request_id": response.request_id,
            "latency_ms": response.latency_ms,
            "cache_key": cache_key,
        }
        return self.audit.append("jev.call", details)

    def refused(
        self,
        *,
        run_id: str,
        endpoint_id: str,
        purpose: str,
        target_kind: str,
        target_id: str,
        data_classes: tuple[str, ...],
        gate: str,
        reason: str,
    ) -> dict[str, Any]:
        """Record a content-free fail-closed gate result."""

        return self.audit.append("jev.gate.refused", {
            "run_id": run_id,
            "endpoint_id": endpoint_id,
            "purpose": purpose,
            "target_kind": target_kind,
            "target_id": target_id,
            "data_classes": list(data_classes),
            "gate": gate,
            "reason": reason,
        })

    def verify(self) -> tuple[bool, list[str]]:
        return self.audit.verify()

    def head(self) -> tuple[int, str]:
        return self.audit.head()
