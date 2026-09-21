"""Sanitize eval artifacts before export."""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any

SECRET_PATTERNS = (
    re.compile(r"(?i)(secret|token|password|api[_-]?key)\s*[:=]\s*\S+"),
    re.compile(r"sk-[A-Za-z0-9]{10,}"),
)


def redact_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: redact_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [redact_value(item) for item in value]
    if isinstance(value, str):
        redacted = value
        for pattern in SECRET_PATTERNS:
            redacted = pattern.sub("[REDACTED]", redacted)
        return redacted
    return value


def redact_run_result(payload: dict[str, Any]) -> dict[str, Any]:
    return redact_value(deepcopy(payload))
