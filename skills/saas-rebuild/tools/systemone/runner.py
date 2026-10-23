"""Boundary-gated, cached System One execution and annotation writing."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import uuid
from typing import Any, Mapping

from .boundary import BoundaryRefused, BoundaryTicket, open_ticket, regulated_data
from .audit import _exclusive
from .cache import CacheMiss, ResponseCache
from .canary import CanaryResult
from .calllog import CallLog
from .client import Answer, Response, SystemOne, estimate_request_tokens, reserve_request_tokens
from .digest import stable_digest
from .limiter import BudgetGuard, RateLimiter
from .policy import evaluate
from .signals import CalibratedThreshold, ThresholdSet
from .questions import question_hash, to_wire


@dataclass(frozen=True)
class RunSummary:
    run_id: str
    mode: str
    calls: int
    cache_hits: int
    input_tokens: int
    output_tokens: int
    annotations: int
    calllog_head: str | None


def _answer_value(answer: Answer) -> Any:
    return {
        "type": answer.type,
        "value": answer.value,
        "probabilities": answer.probabilities,
        "confidence": answer.confidence,
        "legend": answer.legend,
    }


class Runner:
    def __init__(
        self,
        artifact_root: Path,
        teardown: dict[str, Any],
        *,
        endpoint_id: str,
        purpose: str,
        mode: str,
        client: SystemOne,
        budget: BudgetGuard,
        limiter: RateLimiter | None = None,
        canary: CanaryResult | None = None,
    ) -> None:
        if mode not in {"shadow", "live", "replay"}:
            raise ValueError("Runner mode must be shadow, live, or replay")
        self.artifact_root = Path(artifact_root)
        self.teardown = teardown
        self.endpoint_id = endpoint_id
        self.purpose = purpose
        self.mode = mode
        self.client = client
        self.budget = budget
        self.limiter = limiter or RateLimiter()
        self.canary = canary
        self.cache = ResponseCache(self.artifact_root / ".systemone" / "cache")
        self.calllog = CallLog(self.artifact_root / ".systemone" / "calls.jsonl")
        self.run_id = f"jev-{uuid.uuid4().hex[:16]}"
        self.annotations: list[dict[str, Any]] = []
        self.cache_hits = 0
        self.output_tokens = 0

    def ask(
        self,
        *,
        target_kind: str,
        target_id: str,
        state: Any,
        data_classes: tuple[str, ...],
        catalog_version: str,
        catalog: Mapping[str, dict[str, Any]],
        thresholds: Mapping[str, dict[str, Any]] | ThresholdSet | None = None,
        context: Mapping[str, Any] | None = None,
        contains_phi: bool = False,
        contains_eu_personal_data: bool = False,
    ) -> list[dict[str, Any]]:
        declared_phi, declared_eu = regulated_data(self.teardown)
        contains_phi = contains_phi or declared_phi
        contains_eu_personal_data = contains_eu_personal_data or declared_eu
        try:
            ticket: BoundaryTicket = open_ticket(
                self.teardown,
                self.endpoint_id,
                self.purpose,
                data_classes,
                contains_phi=contains_phi,
                contains_eu_personal_data=contains_eu_personal_data,
            )
            if self.client.endpoint != ticket.endpoint:
                raise BoundaryRefused("client endpoint differs from the approved endpoint")
        except BoundaryRefused as error:
            self.record_refusal(
                target_kind=target_kind,
                target_id=target_id,
                data_classes=data_classes,
                gate="boundary",
                reason=str(error),
            )
            raise
        questions = {question_id: item["question"] for question_id, item in catalog.items()}
        wire = {question_id: to_wire(question) for question_id, question in questions.items()}
        estimate = estimate_request_tokens(state, wire)
        key = stable_digest({
            "endpoint": ticket.endpoint, "endpoint_id": ticket.endpoint_id,
            "purpose": ticket.purpose, "model": self.client.model,
            "state": state, "questions": wire, "catalog_version": catalog_version,
            "target_kind": target_kind, "target_id": target_id,
            "data_classes": sorted(ticket.allowed_data_classes),
            "contains_phi": contains_phi, "contains_eu_personal_data": contains_eu_personal_data,
            "context": context,
        })
        response: Response
        source_seq = None
        try:
            cached = self.cache.get(key)
            response = self._from_cached(cached["response"], wire)
            self.cache_hits += 1
            if cached.get("annotations"):
                source_seq = cached["annotations"][0]["resolution"]["calllog_seq"]
            if self.mode == "replay":
                records = cached.get("annotations")
                if not isinstance(records, list) or len(records) != len(catalog):
                    raise CacheMiss("cache has no frozen annotations; re-record explicitly")
                for record in records:
                    qid = record.get("question_id")
                    if (
                        qid not in catalog or record.get("target_id") != target_id
                        or record.get("target_kind") != target_kind
                        or record.get("endpoint_id") != ticket.endpoint_id
                        or record.get("model_returned") != response.model
                        or record.get("question_hash") != question_hash(catalog[qid]["question"])
                    ):
                        raise ValueError("cached annotations do not match the request")
                self.annotations.extend(records)
                return records
        except CacheMiss:
            if self.mode == "replay":
                raise
            longest = max(estimate_request_tokens(state, {question_id: question}) for question_id, question in wire.items())
            self.limiter.acquire(estimate, longest)
            self.budget.reserve(reserve_request_tokens(state, wire))
            response = self.client.ask(state, questions)
            self.output_tokens += response.usage["output_tokens"]
            entry = self.calllog.record(
                run_id=self.run_id,
                endpoint_id=ticket.endpoint_id,
                purpose=ticket.purpose,
                model_requested=self.client.model,
                state=state,
                questions=wire,
                data_classes=data_classes,
                response=response,
                cache_key=key,
            )
            source_seq = entry["seq"]
            self.budget.record(response.usage["input_tokens"])

        created = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        records: list[dict[str, Any]] = []
        for question_id, item in catalog.items():
            # The former ThresholdSet lacks a pinned provider model, approval,
            # validation reference and canary. Retain it as routing-only input.
            policy = None if isinstance(thresholds, ThresholdSet) else (thresholds or {}).get(question_id)
            twin_id = policy.get("twin_question_id") if isinstance(policy, dict) else None
            twin = None
            if twin_id in catalog and twin_id != question_id and policy.get("twin_question_hash") == question_hash(catalog[twin_id]["question"]):
                twin = response.answers[twin_id]
            effect = evaluate(
                item, response.answers[question_id], mode=self.mode, model=response.model,
                catalog_version=catalog_version, policy=policy, twin=twin,
                canary_model=self.canary.model if self.canary and self.canary.passed else None,
                context=context,
            )
            record = {
                "schema_version": "0.10.0",
                "annotation_id": f"ann-{stable_digest([self.run_id, target_kind, target_id, question_id])[:24]}",
                "run_id": self.run_id,
                "target_kind": target_kind,
                "target_id": target_id,
                "endpoint_id": ticket.endpoint_id,
                "sent_data_classes": list(ticket.allowed_data_classes),
                "question_id": question_id,
                "question_hash": question_hash(item["question"]),
                "catalog_version": catalog_version,
                "model_returned": response.model,
                "answer": _answer_value(response.answers[question_id]),
                "calibrated_p": effect.calibrated_p,
                "threshold_set_id": effect.threshold_set_id,
                "effect": effect.effect,
                "resolution": {"status": "open", "resolved_by": None, "resolved_at": None, "calllog_seq": source_seq or 0},
                "created_at": created,
            }
            records.append(record)
        self.annotations.extend(records)
        # Bind replay to the recorded annotations, including their original effects.
        self.cache.put(key, response.raw, records)
        return records

    def record_refusal(
        self,
        *,
        target_kind: str,
        target_id: str,
        data_classes: tuple[str, ...],
        gate: str,
        reason: str,
    ) -> None:
        self.calllog.refused(
            run_id=self.run_id,
            endpoint_id=self.endpoint_id,
            purpose=self.purpose,
            target_kind=target_kind,
            target_id=target_id,
            data_classes=data_classes,
            gate=gate,
            reason=reason,
        )

    def _from_cached(self, body: dict[str, Any], wire: dict[str, Any]) -> Response:
        from .client import parse_answer

        answers = {
            question_id: parse_answer(wire[question_id], body["answers"][question_id])
            for question_id in wire
        }
        usage = body.get("usage") or {"input_tokens": 0, "output_tokens": 0}
        return Response(str(body["model"]), answers, {"input_tokens": int(usage.get("input_tokens", 0)), "output_tokens": int(usage.get("output_tokens", 0))}, None, 0, body)

    def write_annotations(self) -> Path | None:
        if not self.annotations or self.mode == "replay":
            return None
        target = self.artifact_root / "model-annotations.jsonl"
        with _exclusive(target.with_suffix(".lock")):
            self._append_annotations(target)
        return target

    def _append_annotations(self, target: Path) -> None:
        existing: dict[str, dict[str, Any]] = {}
        if target.is_file():
            for line in target.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    record = json.loads(line)
                    existing[str(record.get("annotation_id"))] = record
        for record in self.annotations:
            old = existing.get(record["annotation_id"])
            if old is not None and old != record:
                raise ValueError("annotation id conflicts with immutable recorded content")
        new_records = [record for record in self.annotations if record["annotation_id"] not in existing]
        if new_records:
            with target.open("a", encoding="utf-8") as handle:
                for record in new_records:
                    handle.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
                handle.flush()
                os.fsync(handle.fileno())

    def summary(self) -> RunSummary:
        head = self.calllog.head()[1] if self.calllog.head()[0] else None
        return RunSummary(
            self.run_id,
            self.mode,
            self.budget.calls,
            self.cache_hits,
            self.budget.input_tokens,
            self.output_tokens,
            len(self.annotations),
            head,
        )
