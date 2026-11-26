"""Stable library-first API for OKF Runtime."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from . import cache, metadata as metadata_module, scanner
from .compose import compose_bundle
from .graph import neighborhood
from .links import lint_links as lint_link_index


def discover(root: str | Path = ".") -> list[dict[str, object]]:
    return scanner.discover_bundles(root)


def catalog(root: str | Path = ".", include_links: bool = False, cache_dir: str | Path | None = None) -> list[dict[str, Any]]:
    index = cache.load_or_rebuild(root, cache_dir)
    records = [
        {**record, **({"okf_version": index.okf_version} if index.okf_version is not None else {})}
        for record in index.metadata_index.values()
    ]
    if include_links:
        for record in records:
            concept_id = str(record["id"])
            record["links"] = index.forward_links.get(concept_id, [])
            record["backlinks"] = index.reverse_links.get(concept_id, [])
    return sorted(records, key=lambda item: str(item["id"]))


def query(root: str | Path = ".", cache_dir: str | Path | None = None, **filters: str) -> list[dict[str, Any]]:
    index = cache.load_or_rebuild(root, cache_dir)
    return metadata_module.query_metadata(index.metadata_index, filters)


def show(root: str | Path, concept_id: str, include_body: bool = False, cache_dir: str | Path | None = None) -> dict[str, Any]:
    index = cache.load_or_rebuild(root, cache_dir)
    normalized = concept_id.removesuffix(".md")
    record = index.metadata_index.get(normalized)
    if record is None:
        raise KeyError(f"Unknown concept: {concept_id}")
    result = dict(record)
    if include_body:
        result["body"] = index.documents[normalized].body
    return result


def links(root: str | Path = ".", concept_id: str | None = None, cache_dir: str | Path | None = None) -> dict[str, list[dict[str, Any]]] | list[dict[str, Any]]:
    index = cache.load_or_rebuild(root, cache_dir)
    if concept_id is None:
        return index.forward_links
    return index.forward_links.get(concept_id.removesuffix(".md"), [])


def backlinks(root: str | Path = ".", concept_id: str | None = None, cache_dir: str | Path | None = None) -> dict[str, list[dict[str, Any]]] | list[dict[str, Any]]:
    index = cache.load_or_rebuild(root, cache_dir)
    if concept_id is None:
        return index.reverse_links
    return index.reverse_links.get(concept_id.removesuffix(".md"), [])


def graph(root: str | Path, concept_id: str, depth: int = 1, resolve_resources: bool = False, cache_dir: str | Path | None = None) -> dict[str, Any]:
    index = cache.load_or_rebuild(root, cache_dir)
    normalized = concept_id.removesuffix(".md")
    if normalized not in index.metadata_index:
        raise KeyError(f"Unknown concept: {concept_id}")
    forward, reverse = resource_edges(index) if resolve_resources else (index.forward_links, index.reverse_links)
    return neighborhood(normalized, forward, reverse, depth=depth)


def compose(
    root: str | Path,
    topic: str,
    output_dir: str | Path | None = None,
    depth: int = 1,
    min_trust: str | None = None,
    resolve_resources: bool = False,
    cache_dir: str | Path | None = None,
) -> dict[str, Any]:
    index = cache.load_or_rebuild(root, cache_dir)
    if resolve_resources:
        index.forward_links, index.reverse_links = resource_edges(index)
    return compose_bundle(index, topic, output_dir=output_dir, depth=depth, min_trust=min_trust)


def trust(root: str | Path = ".", concept_id: str | None = None, cache_dir: str | Path | None = None) -> dict[str, Any]:
    index = cache.load_or_rebuild(root, cache_dir)
    if concept_id is not None:
        normalized = concept_id.removesuffix(".md")
        document = index.documents.get(normalized)
        if document is None or document.is_reserved:
            raise KeyError(f"Unknown concept: {concept_id}")
        return {"id": normalized, **document.trust.to_dict()}
    statuses: dict[str, int] = {}
    stale_count = 0
    for trust_data in index.trust_index.values():
        statuses[str(trust_data["status"])] = statuses.get(str(trust_data["status"]), 0) + 1
        stale_count += bool(trust_data["is_stale"])
    return {
        "okf_version": index.okf_version,
        "concept_count": len(index.trust_index),
        "trust_tiers": {tier: len(ids) for tier, ids in index.trust_tier_index.items()},
        "status": dict(sorted(statuses.items())),
        "stale_count": stale_count,
    }


def lint_links(root: str | Path = ".", cache_dir: str | Path | None = None) -> list[dict[str, Any]]:
    index = cache.load_or_rebuild(root, cache_dir)
    return lint_link_index(index.documents, index.forward_links, index.reverse_links)


def resource_edges(index: Any) -> tuple[dict[str, list[dict[str, Any]]], dict[str, list[dict[str, Any]]]]:
    """Add opt-in edges where a frontmatter string equals a concept resource."""
    from .links import build_reverse_links

    forward = {key: list(value) for key, value in index.forward_links.items()}
    resources = {str(doc.metadata["resource"]): key for key, doc in index.documents.items()
                 if not doc.is_reserved and isinstance(doc.metadata.get("resource"), str)}

    def strings(value: Any):
        if isinstance(value, str):
            yield value
        elif isinstance(value, dict):
            for child in value.values():
                yield from strings(child)
        elif isinstance(value, list):
            for child in value:
                yield from strings(child)

    for source_id, document in index.documents.items():
        if document.is_reserved:
            continue
        for value in strings(document.metadata):
            target_id = resources.get(value)
            if target_id and target_id != source_id:
                forward.setdefault(source_id, []).append({"text": value, "target": value, "raw_target": value,
                    "anchor": None, "external": False, "resolved_path": index.documents[target_id].relative_path,
                    "resolved_id": target_id, "resource": True})
    return forward, build_reverse_links(forward)


def verify_sources(root: str | Path = ".", cache_dir: str | Path | None = None) -> dict[str, Any]:
    import hashlib
    from pathlib import PurePosixPath

    index = cache.load_or_rebuild(root, cache_dir)
    checked = missing = mismatched = 0
    problems: list[dict[str, str]] = []
    for source_id, document in sorted(index.documents.items()):
        sources = document.metadata.get("sources", [])
        if isinstance(sources, dict):
            sources = [sources]
        if not isinstance(sources, list):
            continue
        for entry in sources:
            if not isinstance(entry, dict) or not isinstance(entry.get("resource"), str):
                continue
            resource = entry["resource"]
            from urllib.parse import urlparse
            if urlparse(resource).scheme or resource.startswith("/"):
                continue
            checked += 1
            parts: list[str] = []
            for part in PurePosixPath((Path(document.relative_path).parent / resource).as_posix()).parts:
                if part in {"", "."}: continue
                if part == "..":
                    if not parts: break
                    parts.pop()
                else: parts.append(part)
            else:
                target = index.root.joinpath(*parts)
                if target.is_file():
                    expected = entry.get("x-sha256")
                    if expected is not None:
                        actual = hashlib.sha256(target.read_bytes()).hexdigest()
                        if str(expected).lower() != actual:
                            mismatched += 1
                            problems.append({"id": source_id, "resource": resource, "type": "mismatched", "expected": str(expected), "actual": actual})
                    continue
            missing += 1
            problems.append({"id": source_id, "resource": resource, "type": "missing"})
    return {"checked": checked, "missing": missing, "mismatched": mismatched, "problems": problems}
