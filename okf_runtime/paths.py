"""Lexical path normalization for paths inside an OKF bundle."""

from __future__ import annotations

from pathlib import PurePosixPath


def normalize_bundle_path(source_relative_path: str, target_path: str) -> str | None:
    """Return a normalized bundle-relative path, or None if it escapes the root.

    A leading slash is bundle-root-relative. No filesystem lookup or root
    resolution occurs, so callers may pass relative or unresolved bundle roots.
    """
    target = target_path.replace("\\", "/")
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
