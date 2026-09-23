"""Minimize and scrub state before it can reach a model boundary."""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
import re
from typing import Any, Iterable, Mapping


class StateRefused(RuntimeError):
    """State cannot safely or honestly cross the approved boundary."""


SECRET_PATTERNS = (
    re.compile(r"(?i)\b(?:api[_-]?key|access[_-]?token|secret|password)\s*[:=]\s*[^\s,;]+"),
    re.compile(r"(?i)\b(?:bearer|basic)\s+[A-Za-z0-9._~+/=-]{8,}"),
    re.compile(r"(?i)\b(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?)://[^\s]+"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b"),
)
EMAIL = re.compile(r"(?<![\w.+-])[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}(?![\w.-])")
HOST = re.compile(
    r"(?i)\b(?:(?:https?://)?(?:localhost|(?:[a-z0-9-]+\.)+[a-z]{2,63})"
    r"(?::\d{1,5})?(?:/[^\s]*)?|(?:\d{1,3}\.){3}\d{1,3}(?::\d{1,5})?)"
)
ISO_DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}(?:[T ][0-9:.+-Z]+)?\b")
DIGIT_RUN = re.compile(r"\d+(?:[.,]\d+)*")
LABEL_LEAK = re.compile(
    r"(?i)(?:\b(?:KEEP|SIMPLIFY|DROP|DEFER)\b|out[ -]of[ -]scope|"
    r"requested\s+by\s+.{0,40}\bteam\b|counts?\s+since\s+tenant\s+creation)"
)


@dataclass(frozen=True)
class StateEnvelope:
    value: Any
    data_classes: tuple[str, ...]
    estimated_tokens: int
    redactions: tuple[str, ...]


def scrub_text(value: str, *, strip_numbers: bool = True) -> tuple[str, set[str]]:
    redactions: set[str] = set()
    text = value.replace("<", "(").replace(">", ")")
    for pattern in SECRET_PATTERNS:
        text, count = pattern.subn("[REDACTED_SECRET]", text)
        if count:
            redactions.add("secret")
    text, count = EMAIL.subn("[REDACTED_EMAIL]", text)
    if count:
        redactions.add("email")
    text, count = HOST.subn("[REDACTED_HOST]", text)
    if count:
        redactions.add("host")
    if strip_numbers:
        text, count = ISO_DATE.subn("[DATE]", text)
        if count:
            redactions.add("date")
        text, count = DIGIT_RUN.subn("[NUMBER]", text)
        if count:
            redactions.add("number")
    return text, redactions


def _get(value: Mapping[str, Any], dotted: str) -> Any:
    current: Any = value
    for part in dotted.split("."):
        if not isinstance(current, Mapping) or part not in current:
            raise KeyError(dotted)
        current = current[part]
    return current


def _scrub(value: Any, *, strip_numbers: bool, redactions: set[str]) -> Any:
    if isinstance(value, str):
        cleaned, found = scrub_text(value, strip_numbers=strip_numbers)
        redactions.update(found)
        return cleaned
    if isinstance(value, list):
        return [_scrub(item, strip_numbers=strip_numbers, redactions=redactions) for item in value]
    if isinstance(value, dict):
        return {
            str(key): _scrub(item, strip_numbers=strip_numbers, redactions=redactions)
            for key, item in value.items()
        }
    if isinstance(value, (int, float)) and not isinstance(value, bool) and strip_numbers:
        redactions.add("number")
        return "[NUMBER]"
    return value


def build_state(
    source: Mapping[str, Any],
    field_classes: Mapping[str, str],
    *,
    allowed_fields: Iterable[str],
    allowed_data_classes: Iterable[str],
    strip_numbers: bool = True,
    max_tokens: int = 32_000,
) -> StateEnvelope:
    """Allow-list fields, enforce classes, scrub, lint, and cap the payload."""

    allowed_classes = set(allowed_data_classes)
    selected: dict[str, Any] = {}
    classes: set[str] = set()
    for dotted in allowed_fields:
        try:
            value = _get(source, dotted)
        except KeyError:
            continue
        data_class = field_classes.get(dotted, "restricted")
        if data_class not in allowed_classes:
            raise StateRefused(f"field {dotted!r} is classed {data_class!r}, which is not allowed")
        selected[dotted] = value
        classes.add(data_class)
    if not selected:
        raise StateRefused("no approved fields remain after minimization")

    redactions: set[str] = set()
    cleaned = _scrub(selected, strip_numbers=strip_numbers, redactions=redactions)
    rendered = json.dumps(cleaned, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    if LABEL_LEAK.search(rendered):
        raise StateRefused("state contains a verdict or scope label that would leak the answer")
    estimate = math.ceil(len(rendered.encode("utf-8")) / 4)
    if estimate > max_tokens:
        raise StateRefused(f"state estimate {estimate} tokens exceeds the {max_tokens} token budget")
    return StateEnvelope(cleaned, tuple(sorted(classes)), estimate, tuple(sorted(redactions)))
