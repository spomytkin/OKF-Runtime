"""Lexical path normalization for paths inside an OKF bundle."""

from __future__ import annotations

from pathlib import Path, PurePosixPath
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


def case_sensitive_is_file(root: Path, relative_path: str) -> bool:
    """Return True only if ``relative_path`` exists under ``root`` with exactly
    this casing (spec §6: path matching is case-sensitive).

    ``Path.is_file()`` alone is case-insensitive on Windows, so ``TARGET.md``
    would resolve to ``target.md`` there. Walk each component against the real
    directory listing and require an exact match.
    """
    current = root
    for part in PurePosixPath(relative_path).parts:
        if part in {"", "."}:
            continue
        try:
            names = {entry.name for entry in current.iterdir()}
        except OSError:
            return False
        if part not in names:
            return False
        current = current / part
    return current.is_file()
