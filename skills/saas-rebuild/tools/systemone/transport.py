"""Stdlib-only HTTP transport with bounded retry and response headers."""

from __future__ import annotations

import json
import os
import ssl
import urllib.error
import urllib.request
from typing import Any, Callable


class TransportError(RuntimeError):
    """Authentication, transport, or protocol failure; never a judgment."""


def _ssl_ctx() -> ssl.SSLContext:
    ca = (
        os.environ.get("XSCREEN_CA_BUNDLE")
        or os.environ.get("REQUESTS_CA_BUNDLE")
        or os.environ.get("SSL_CERT_FILE")
    )
    if ca and os.path.exists(ca):
        return ssl.create_default_context(cafile=ca)
    return ssl.create_default_context()


RETRYABLE_STATUS = frozenset({408, 409, 425, 429, 500, 502, 503, 504, 529})
MAX_TRANSPORT_ATTEMPTS = 4
BACKOFF_BASE_S = 1.0
BACKOFF_CAP_S = 30.0


def _sleep_for(attempt: int, retry_after: str | None) -> float:
    """Backoff delay. Honours Retry-After when the server sends one."""

    if retry_after:
        try:
            return min(BACKOFF_CAP_S, max(0.0, float(retry_after)))
        except ValueError:
            pass
    return min(BACKOFF_CAP_S, BACKOFF_BASE_S * (2 ** attempt))


def _redacted_error(error: urllib.error.HTTPError) -> str:
    return f"HTTPError: {error.code} {error.reason}"


def post_json(
    url: str,
    headers: dict[str, str],
    payload: dict[str, Any],
    timeout: int = 60,
    *,
    sleep: Callable[[float], None] | None = None,
) -> tuple[dict[str, Any], dict[str, str]]:
    """POST JSON, returning parsed body and lower-cased response headers."""

    import time

    sleeper = sleep or time.sleep
    body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    last = ""
    for attempt in range(MAX_TRANSPORT_ATTEMPTS):
        request = urllib.request.Request(url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=timeout, context=_ssl_ctx()) as response:
                parsed = json.loads(response.read().decode("utf-8"))
                if not isinstance(parsed, dict):
                    raise TransportError("System One returned a non-object JSON response")
                return parsed, {key.lower(): value for key, value in response.headers.items()}
        except urllib.error.HTTPError as error:
            last = f"HTTP {error.code}"
            if error.code not in RETRYABLE_STATUS or attempt == MAX_TRANSPORT_ATTEMPTS - 1:
                raise TransportError(_redacted_error(error)) from error
            retry_after = error.headers.get("Retry-After") if error.headers else None
            sleeper(_sleep_for(attempt, retry_after))
        except (TimeoutError, urllib.error.URLError, ConnectionError) as error:
            last = f"{type(error).__name__}: {error}"
            if attempt == MAX_TRANSPORT_ATTEMPTS - 1:
                raise TransportError(f"{last} (after {MAX_TRANSPORT_ATTEMPTS} attempts)") from error
            sleeper(_sleep_for(attempt, None))
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            raise TransportError("System One returned invalid JSON") from error
        except TransportError:
            raise
        except Exception as error:  # noqa: BLE001 - non-transient, fail closed
            raise TransportError(f"{type(error).__name__}: {error}") from error
    raise TransportError(f"exhausted {MAX_TRANSPORT_ATTEMPTS} attempts: {last}")
