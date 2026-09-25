"""Boundary-gated, cached System One execution and annotation writing."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import uuid
from typing import Any, Mapping, Sequence

from .boundary import BoundaryRefused, BoundaryTicket, open_ticket, regulated_data
from .calibrate import IsotonicModel
from .cache import CacheMiss, ResponseCache, cache_key
from .calllog import CallLog
from .client import Answer, Response, SystemOne, estimate_request_tokens
from .digest import stable_digest
from .limiter import BudgetGuard, RateLimiter
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


HIGH_AUTHORITY = frozenset({"veto", "flag", "reject"})
# Uncalibrated signals only ever route work; this cutoff never gates a veto,
# flag, or reject, which require a fitted threshold on eligible gold.
ROUTING_CUTOFF = 0.5


@dataclass(frozen=True)
class CalibratedThreshold:
    """A fitted threshold, bound to the exact question text it was fitted on."""

    question_hash: str
    model: IsotonicModel
    threshold: float


@dataclass(frozen=True)
class ThresholdSet:
    threshold_set_id: str
    entries: Mapping[str, CalibratedThreshold]


def _signal(
    catalog_item: dict[str, Any],
    answer: Answer,
    context: Mapping[str, Any] | None = None,
) -> float | None:
    """Probability that the answer is the one the question's authority acts on.

    A noul answer is already that probability. A choice answer counts only the
    options its catalog entry names: a fixed ``trigger``, or under ``compare``
    the options that contradict the target's declared value. Without either,
    or when that declared value is absent or unmapped, there is no signal, so
    the question cannot act on anything.
    """

    if answer.type == "noul":
        return float(answer.value)
    if answer.type != "choice" or answer.probabilities is None:
        return None
    options = catalog_item.get("trigger")
    compare = catalog_item.get("compare")
    if compare is not None:
        declared = (context or {}).get(compare["against"])
        options = compare["contradicts"].get(declared) if isinstance(declared, str) else None
        if options is not None and not options:
            return 0.0
    if not options:
        return None
    return min(1.0, sum(answer.probabilities.get(option, 0.0) for option in options))


def offered_slots(candidates: Sequence[str]) -> frozenset[str]:
    return frozenset(f"candidate-{position}" for position in range(1, len(candidates) + 1))


def _effect(
    catalog_item: dict[str, Any],
    answer: Answer,
    mode: str,
    calibration: CalibratedThreshold | None,
    context: Mapping[str, Any] | None = None,
    candidates: Sequence[str] = (),
) -> tuple[str, float | None]:
    """Return the annotation effect and the calibrated probability behind it.

    Shadow and replay never carry authority: shadow is a no-effect spike, and a
    replay must not mint effects its original run was never approved to have.
    A candidate-slot question suggests only a slot that was actually offered;
    ``none`` or an empty slot suggests nothing.
    """

    if mode in {"shadow", "replay"}:
        return "none", None
    if catalog_item.get("candidate_slots"):
        return ("suggest" if answer.value in offered_slots(candidates) else "none"), None
    declared = catalog_item.get("authority", "prioritize")
    if declared == "suggest" and answer.type == "choice" and not (catalog_item.get("trigger") or catalog_item.get("compare")):
        return "suggest", None
    signal = _signal(catalog_item, answer, context)
    if signal is None:
        return "none", None
    if declared in HIGH_AUTHORITY:
        if calibration is None:
            return ("prioritize" if signal >= ROUTING_CUTOFF else "none"), None
        calibrated = calibration.model.predict(signal)
        return (declared if calibrated >= calibration.threshold else "none"), calibrated
    if declared in {"prioritize", "suggest"}:
        return (declared if signal >= ROUTING_CUTOFF else "none"), None
    return "none", None


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
        thresholds: ThresholdSet | None = None,
        context: Mapping[str, Any] | None = None,
        candidates: Sequence[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Ask the catalog about one target.

        ``context`` carries the target's declared fields (for example a
        citation's ``evidence_class``) that ``compare`` questions check the
        answer against. It is never sent to the model. ``candidates`` are the
        ids behind a candidate-slot question's options, in slot order; the
        caller sends their descriptions in ``state`` in the same order.
        """
        slotted = [question_id for question_id, item in catalog.items() if item.get("candidate_slots")]
        if slotted and not candidates:
            raise ValueError(f"candidate-slot questions need candidates: {slotted}")
        for question_id in slotted:
            options = set((catalog[question_id]["question"].get("criteria") or {}))
            if not offered_slots(candidates or ()) <= options:
                raise ValueError(f"{question_id} has fewer slots than the {len(candidates or ())} candidates offered")
        contains_phi, contains_eu_personal_data = regulated_data(self.teardown)
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
        key = cache_key(ticket.endpoint, self.client.model, state, wire)
        response: Response
        try:
            cached = self.cache.get(key)
            response = self._from_cached(cached["response"], wire)
            self.cache_hits += 1
        except CacheMiss:
            if self.mode == "replay":
                raise
            self.budget.reserve(estimate)
            longest = max(estimate_request_tokens("", {question_id: question}) for question_id, question in wire.items())
            self.limiter.acquire(estimate, estimate + longest)
            response = self.client.ask(state, questions)
            self.budget.record(response.usage["input_tokens"])
            self.output_tokens += response.usage["output_tokens"]
            self.cache.put(key, response.raw)
            self.calllog.record(
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

        created = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        records: list[dict[str, Any]] = []
        for question_id, item in catalog.items():
            calibration = thresholds.entries.get(question_id) if thresholds else None
            if calibration is not None and calibration.question_hash != question_hash(item["question"]):
                # A threshold fitted on different question text does not apply.
                calibration = None
            effect, calibrated_p = _effect(
                item, response.answers[question_id], self.mode, calibration, context, candidates or ()
            )
            record = {
                "schema_version": "0.12.0",
                "annotation_id": f"ann-{stable_digest([self.run_id, target_kind, target_id, question_id])[:24]}",
                "run_id": self.run_id,
                "target_kind": target_kind,
                "target_id": target_id,
                **({"candidates": list(candidates or ())} if item.get("candidate_slots") else {}),
                "endpoint_id": ticket.endpoint_id,
                "sent_data_classes": list(data_classes),
                "question_id": question_id,
                "question_hash": question_hash(item["question"]),
                "catalog_version": catalog_version,
                "model_returned": response.model,
                "answer": _answer_value(response.answers[question_id]),
                "calibrated_p": calibrated_p,
                "threshold_set_id": thresholds.threshold_set_id if calibrated_p is not None else None,
                "effect": effect,
                "resolution": {"status": "open", "resolved_by": None, "resolved_at": None, "calllog_seq": self.calllog.head()[0]},
                "created_at": created,
            }
            records.append(record)
        self.annotations.extend(records)
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
        # Replay reproduces cached answers for audit; it never appends records.
        if not self.annotations or self.mode == "replay":
            return None
        target = self.artifact_root / "model-annotations.jsonl"
        existing: set[str] = set()
        if target.is_file():
            for line in target.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    existing.add(str(json.loads(line).get("annotation_id")))
        new_records = [record for record in self.annotations if record["annotation_id"] not in existing]
        if new_records:
            with target.open("a", encoding="utf-8") as handle:
                for record in new_records:
                    handle.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
        return target

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
