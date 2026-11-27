"""Lexical path normalization for paths inside an OKF bundle."""

from __future__ import annotations

from pathlib import PurePosixPath
from urllib.parse import unquote, urlparse


def normalize_bundle_path(source_relative_path: str, target_path: str) -> str | None:
    """Return a normalized bundle-relative path, or None if it escapes the root.

    A leading slash is bundle-root-relative. No filesystem lookup or root
    resolution occurs, so callers may pass relative or unresolved bundle roots.
    """
    target = unquote(target_path).replace("\\", "/")
    parts = [] if target.startswith("/") else list(PurePosixPath(source_relative_path).parent.parts)
    for part in PurePosixPath(target).parts:
        if part in {"", ".", "/"}:
            continue
        if part == "..":
            if not parts:
                return None
            parts.pop()
        else:
            parts.append(part)
    return "/".join(parts)


def resolve_path(source_relative_path: str, value: str) -> tuple[str | None, bool]:
    """Resolve URI references lexically, returning (relative_path, external)."""
    parsed = urlparse(unquote(value))
    if parsed.scheme:
        return None, True
    return normalize_bundle_path(source_relative_path, parsed.path), False
