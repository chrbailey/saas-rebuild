"""Typed System One questions and canonical hashes."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Mapping, Sequence


JsonValue = str | int | float | bool | None | list[Any] | dict[str, Any]


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


@dataclass(frozen=True)
class Noul:
    instructions: JsonValue
    criteria: Mapping[str, JsonValue] | None = None
    type: str = "noul"

    def to_wire(self) -> dict[str, Any]:
        if self.instructions in (None, "", [], {}):
            raise ValueError("noul instructions must not be empty")
        value: dict[str, Any] = {"type": self.type, "instructions": self.instructions}
        if self.criteria is not None:
            if set(self.criteria) != {"true", "false"}:
                raise ValueError("noul criteria must define exactly true and false")
            value["criteria"] = dict(self.criteria)
        return value


@dataclass(frozen=True)
class Choice:
    instructions: JsonValue
    criteria: Mapping[str, JsonValue]
    type: str = "choice"

    def to_wire(self) -> dict[str, Any]:
        if self.instructions in (None, "", [], {}):
            raise ValueError("choice instructions must not be empty")
        if not 2 <= len(self.criteria) <= 255:
            raise ValueError("choice criteria must contain 2 to 255 options")
        if any(not isinstance(key, str) or not key for key in self.criteria):
            raise ValueError("choice option names must be non-empty strings")
        return {"type": self.type, "instructions": self.instructions, "criteria": dict(self.criteria)}


@dataclass(frozen=True)
class Score:
    instructions: JsonValue
    criteria: Sequence[JsonValue]
    type: str = "score"

    def to_wire(self) -> dict[str, Any]:
        if self.instructions in (None, "", [], {}):
            raise ValueError("score instructions must not be empty")
        if not 2 <= len(self.criteria) <= 10:
            raise ValueError("score criteria must contain 2 to 10 ordered levels")
        return {"type": self.type, "instructions": self.instructions, "criteria": list(self.criteria)}


Question = Noul | Choice | Score


def to_wire(question: Question | Mapping[str, Any]) -> dict[str, Any]:
    if hasattr(question, "to_wire"):
        return question.to_wire()  # type: ignore[union-attr]
    if not isinstance(question, Mapping):
        raise TypeError("question must be a typed question or mapping")
    kind = question.get("type")
    if kind == "noul":
        return Noul(question.get("instructions"), question.get("criteria")).to_wire()
    if kind == "choice":
        return Choice(question.get("instructions"), question.get("criteria") or {}).to_wire()
    if kind == "score":
        return Score(question.get("instructions"), question.get("criteria") or []).to_wire()
    raise ValueError(f"unknown question type: {kind!r}")


def question_hash(question: Question | Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical(to_wire(question))).hexdigest()


def questions_hash(questions: Mapping[str, Question | Mapping[str, Any]]) -> str:
    wire = {question_id: to_wire(question) for question_id, question in sorted(questions.items())}
    return hashlib.sha256(_canonical(wire)).hexdigest()
