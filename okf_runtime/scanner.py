"""Filesystem scanning and bundle discovery."""

from __future__ import annotations

from pathlib import Path

from .models import MarkdownFile

EXCLUDED_DIRS = {"__pycache__"}


def normalize_root(root: str | Path) -> Path:
    return Path(root).expanduser().resolve()


def is_excluded(path: Path, root: Path) -> bool:
    try:
        parts = path.relative_to(root).parts
    except ValueError:
        return True
    return any(part in EXCLUDED_DIRS or part.startswith(".") for part in parts)


def scan_markdown(root: str | Path) -> list[MarkdownFile]:
    """Return all markdown files below root, excluding runtime artifacts."""

    base = normalize_root(root)
    if not base.exists():
        raise FileNotFoundError(f"Bundle root does not exist: {base}")
    if not base.is_dir():
        raise NotADirectoryError(f"Bundle root is not a directory: {base}")

    files: list[MarkdownFile] = []
    for path in sorted(base.rglob("*.md")):
        if is_excluded(path, base):
            continue
        try:
            path.resolve().relative_to(base.resolve())
        except ValueError:
            continue
        stat = path.stat()
        rel = path.relative_to(base).as_posix()
        files.append(MarkdownFile(path=path, relative_path=rel, mtime=stat.st_mtime, size=stat.st_size))
    return files


def max_markdown_mtime(root: str | Path) -> float:
    files = scan_markdown(root)
    return max((item.mtime for item in files), default=0.0)


def discover_bundles(root: str | Path) -> list[dict[str, object]]:
    """Discover OKF-like bundles below root.

    Phase 1 treats the provided root as a bundle when it contains markdown files.
    Immediate subdirectories with markdown files are also reported for broad scans.
    """

    base = normalize_root(root)
    bundles: list[dict[str, object]] = []

    root_files = scan_markdown(base)
    if root_files:
        bundles.append({"root": str(base), "markdown_files": len(root_files)})

    for child in sorted(item for item in base.iterdir() if item.is_dir() and item.name not in EXCLUDED_DIRS):
        files = scan_markdown(child)
        if files:
            bundles.append({"root": str(child), "markdown_files": len(files)})

    seen: set[str] = set()
    unique: list[dict[str, object]] = []
    for bundle in bundles:
        bundle_root = str(bundle["root"])
        if bundle_root not in seen:
            unique.append(bundle)
            seen.add(bundle_root)
    return unique
