"""Fixture isolation and source-tree integrity checks."""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

IGNORED_SEGMENTS = frozenset({".cache", "__pycache__", ".evals-run"})


def copy_fixture(source: Path, destination: Path) -> None:
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination, ignore=shutil.ignore_patterns(*IGNORED_SEGMENTS))


def tree_hash(root: Path, *, extra_ignore: set[str] | None = None) -> str:
    ignore = IGNORED_SEGMENTS | set(extra_ignore or ())
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if any(part in ignore for part in rel.parts):
            continue
        digest.update(str(rel).encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()
