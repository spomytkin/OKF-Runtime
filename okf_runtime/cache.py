"""Disposable JSON cache for derived runtime indexes."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

from . import metadata as metadata_module
from . import parser, scanner
from .links import build_forward_links, build_reverse_links
from .models import Document, Link, RuntimeIndex

CACHE_DIR_NAME = ".cache"
MANIFEST_FILE = "manifest.json"
METADATA_FILE = "metadata.json"
LINKS_FILE = "links.json"
REVERSE_LINKS_FILE = "reverse_links.json"
CACHE_SCHEMA_VERSION = 3


def load_or_rebuild(root: str | Path, cache_dir: str | Path | None = None) -> RuntimeIndex:
    root_path = scanner.normalize_root(root)
    selected_cache = Path(cache_dir).expanduser().resolve() if cache_dir else root_path / CACHE_DIR_NAME
    if is_cache_fresh(root_path, selected_cache):
        return load_cache(root_path, stale_rebuilt=False, cache_dir=selected_cache)
    return rebuild_cache(root_path, selected_cache)


def is_cache_fresh(root: Path, cache_dir: Path | None = None) -> bool:
    cache_dir = cache_dir or root / CACHE_DIR_NAME
    manifest_path = cache_dir / MANIFEST_FILE
    metadata_path = cache_dir / METADATA_FILE
    if not manifest_path.exists() or not metadata_path.exists():
        return False
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    if manifest.get("schema_version") != CACHE_SCHEMA_VERSION:
        return False
    if "okf_version" in manifest:
        # A version change in the root index.md invalidates the cache even
        # when file mtimes are unchanged (e.g. a checkout that preserves
        # mtimes), because derived data is version-dependent.
        if manifest.get("okf_version") != _read_root_okf_version(root):
            return False
    return float(manifest.get("source_mtime", -1)) >= scanner.max_markdown_mtime(root)


def _read_root_okf_version(root: Path) -> str | None:
    """Read okf_version from the bundle-root index.md frontmatter only."""
    index_path = root / "index.md"
    if not index_path.is_file():
        return None
    try:
        metadata, _, _ = parser.split_frontmatter(index_path.read_text(encoding="utf-8"), allow_missing=True)
    except (OSError, UnicodeDecodeError):
        return None
    value = metadata.get("okf_version") if isinstance(metadata, dict) else None
    return str(value) if value is not None else None


def rebuild_cache(root: Path, cache_dir: Path | None = None) -> RuntimeIndex:
    target_cache_dir = cache_dir or root / CACHE_DIR_NAME
    target_cache_dir.mkdir(parents=True, exist_ok=True)

    files = scanner.scan_markdown(root)
    documents = parser.parse_documents(files, root)
    metadata_index = metadata_module.build_metadata_index(documents)
    tag_index = metadata_module.build_tag_index(metadata_index)
    type_index = metadata_module.build_type_index(metadata_index)
    trust_index, trust_tier_index = metadata_module.build_trust_index(documents)
    forward = build_forward_links(documents)
    reverse = build_reverse_links(forward)
    source_mtime = max((item.mtime for item in files), default=0.0)

    (target_cache_dir / METADATA_FILE).write_text(
        json.dumps(
            {
                "documents": [document_to_json(document) for document in documents.values()],
                "metadata_index": metadata_index,
                "tag_index": tag_index,
                "type_index": type_index,
                "trust_index": trust_index,
                "trust_tier_index": trust_tier_index,
                "okf_version": detect_okf_version(documents),
                "bundle_metadata": documents.get("index").metadata if documents.get("index") else {},
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    (target_cache_dir / LINKS_FILE).write_text(json.dumps(forward, indent=2, sort_keys=True), encoding="utf-8")
    (target_cache_dir / REVERSE_LINKS_FILE).write_text(json.dumps(reverse, indent=2, sort_keys=True), encoding="utf-8")
    (target_cache_dir / MANIFEST_FILE).write_text(
        json.dumps(
            {
                "schema_version": CACHE_SCHEMA_VERSION,
                "source_mtime": source_mtime,
                "document_count": len(documents),
                "okf_version": detect_okf_version(documents),
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    return RuntimeIndex(
        root=root,
        documents=documents,
        forward_links=forward,
        reverse_links=reverse,
        metadata_index=metadata_index,
        tag_index=tag_index,
        type_index=type_index,
        trust_index=trust_index,
        trust_tier_index=trust_tier_index,
        okf_version=detect_okf_version(documents),
        stale_rebuilt=True,
    )


def load_cache(root: Path, stale_rebuilt: bool, cache_dir: Path | None = None) -> RuntimeIndex:
    cache_dir = cache_dir or root / CACHE_DIR_NAME
    metadata_payload = json.loads((cache_dir / METADATA_FILE).read_text(encoding="utf-8"))
    forward = json.loads((cache_dir / LINKS_FILE).read_text(encoding="utf-8"))
    reverse = json.loads((cache_dir / REVERSE_LINKS_FILE).read_text(encoding="utf-8"))
    documents = {
        item["concept_id"]: document_from_json(root, item)
        for item in metadata_payload.get("documents", [])
    }
    # The cached trust payloads are recomputed from metadata on load, so
    # re-apply the superseded_by resolution here (as parse_documents does)
    # and rebuild the trust indexes from the documents: a cache load must
    # agree with a fresh parse.
    for document in documents.values():
        document.trust = replace(document.trust, superseded_by_id=parser.resolve_superseded_by_id(documents, document))
    trust_index, trust_tier_index = metadata_module.build_trust_index(documents)
    return RuntimeIndex(
        root=root,
        documents=documents,
        forward_links=forward,
        reverse_links=reverse,
        metadata_index=metadata_payload.get("metadata_index", {}),
        tag_index=metadata_payload.get("tag_index", {}),
        type_index=metadata_payload.get("type_index", {}),
        trust_index=trust_index,
        trust_tier_index=trust_tier_index,
        okf_version=metadata_payload.get("okf_version", detect_okf_version(documents)),
        stale_rebuilt=stale_rebuilt,
    )


def document_to_json(document: Document) -> dict[str, Any]:
    return {
        "relative_path": document.relative_path,
        "concept_id": document.concept_id,
        "reserved": document.is_reserved,
        "is_concept": document.is_concept,
        "legacy": document.legacy,
        "metadata": document.metadata,
        "body": document.body,
        "trust": document.trust.to_dict(),
        "links": [
            {
                "text": link.text,
                "target": link.target,
                "raw_target": link.raw_target,
                "anchor": link.anchor,
                "external": link.is_external,
                "resolved_path": link.resolved_path,
            }
            for link in document.links
        ],
        "anchors": document.anchors,
        "errors": document.errors,
        "warnings": document.warnings,
    }


def document_from_json(root: Path, payload: dict[str, Any]) -> Document:
    links = [
        Link(
            text=item["text"],
            target=item["target"],
            raw_target=item["raw_target"],
            anchor=item.get("anchor"),
            is_external=bool(item.get("external")),
            resolved_path=item.get("resolved_path"),
        )
        for item in payload.get("links", [])
    ]
    relative_path = payload["relative_path"]
    # Recompute trust from metadata, but do not reuse the cached warnings
    # list as the sink: extract_trust_signals appends to it, which would
    # duplicate every cached warning on each load. The cached warnings are
    # already the parse-time result, so they are restored as-is below.
    # Pass the cached legacy flag so the v0.1 timestamp fallback is not
    # re-applied to v0.3 bundles loaded from cache.
    return Document(
        path=root / relative_path,
        relative_path=relative_path,
        concept_id=payload["concept_id"],
        is_reserved=bool(payload.get("reserved")),
        metadata=payload.get("metadata", {}),
        body=payload.get("body", ""),
        trust=parser.extract_trust_signals(
            payload.get("metadata", {}), legacy=bool(payload.get("legacy", True)), warnings=[]
        ),
        links=links,
        anchors=payload.get("anchors", []),
        errors=payload.get("errors", []),
        warnings=payload.get("warnings", []),
        is_concept=bool(payload.get("is_concept", not bool(payload.get("reserved")))),
        legacy=bool(payload.get("legacy", True)),
    )


def detect_okf_version(documents: dict[str, Document]) -> str | None:
    """Return the optional version declaration from the bundle-root index."""

    root_index = documents.get("index")
    if root_index is None:
        return None
    value = root_index.metadata.get("okf_version")
    return str(value) if value is not None else None
