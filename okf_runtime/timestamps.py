"""RFC 3339 timestamp handling for OKF lifecycle fields."""

from __future__ import annotations

from datetime import date, datetime, timezone


def parse_instant(value: object) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, date):
        parsed = datetime.combine(value, datetime.min.time(), tzinfo=timezone.utc)
    else:
        text = str(value).strip().strip("'\"")
        if len(text) == 10:
            parsed = datetime.combine(date.fromisoformat(text), datetime.min.time(), tzinfo=timezone.utc)
        else:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include an offset")
    return parsed.astimezone(timezone.utc)


def now() -> datetime:
    return datetime.now(timezone.utc)
