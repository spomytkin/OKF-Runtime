"""OKF version helpers."""

from __future__ import annotations


def parse_okf_version(value: str | None) -> tuple[int, int, int] | None:
    if value is None:
        return None
    try:
        parts = tuple(int(part) for part in str(value).split("."))
    except ValueError:
        return None
    if not 1 <= len(parts) <= 3:
        return None
    return (parts + (0, 0, 0))[:3]


def is_legacy(version: str | None) -> bool:
    parsed = parse_okf_version(version)
    return version is None or (parsed is not None and parsed <= (0, 2, 0))
