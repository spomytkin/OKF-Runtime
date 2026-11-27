"""Stable library-first API for OKF Runtime."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from . import cache, metadata as metadata_module, scanner
from .compose import compose_bundle
from .graph import neighborhood
from .links import lint_links as lint_link_index
from .links import build_reverse_links
from .paths import normalize_bundle_path
from .spec import is_legacy


def discover(root: str | Path = ".") -> list[dict[str, object]]:
    return scanner.discover_bundles(root)


def catalog(root: str | Path = ".", include_links: bool = False, cache_dir: str | Path | None = None) -> list[dict[str, Any]]:
    index = cache.load_or_rebuild(root, cache_dir)
    records = [
        {**_compat_record(record, index.okf_version), **({"okf_version": index.okf_version} if index.okf_version is not None else {})}
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
    return [_compat_record(record, index.okf_version) for record in metadata_module.query_metadata(index.metadata_index, filters)]


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


def graph(
    root: str | Path,
    concept_id: str,
    depth: int = 1,
    resolve_resources: bool = False,
    cache_dir: str | Path | None = None,
    via: list[str] | None = None,
    path_edges: bool | None = None,
) -> dict[str, Any]:
    index = cache.load_or_rebuild(root, cache_dir)
    normalized = concept_id.removesuffix(".md")
    if normalized not in index.metadata_index:
        raise KeyError(f"Unknown concept: {concept_id}")
    warnings: list[dict[str, Any]] = []
    if resolve_resources:
        forward, reverse, warnings = resource_edges(index)
    else:
        forward, reverse = index.forward_links, index.reverse_links
    if path_edges is None:
        path_edges = not is_legacy(index.okf_version)
    if path_edges:
        forward, reverse = add_path_edges(index, forward)
    result = neighborhood(normalized, forward, reverse, depth=depth, via=via)
    if warnings:
        result["warnings"] = warnings
    return result


def compose(
    root: str | Path,
    topic: str,
    output_dir: str | Path | None = None,
    depth: int = 1,
    min_trust: str | None = None,
    resolve_resources: bool = False,
    cache_dir: str | Path | None = None,
    path_edges: bool | None = None,
) -> dict[str, Any]:
    index = cache.load_or_rebuild(root, cache_dir)
    forward, reverse = index.forward_links, index.reverse_links
    warnings: list[dict[str, Any]] = []
    if resolve_resources:
        forward, reverse, warnings = resource_edges(index)
    if path_edges is None:
        path_edges = not is_legacy(index.okf_version)
    if path_edges:
        forward, reverse = add_path_edges(index, forward)
    return compose_bundle(
        index, topic, output_dir=output_dir, depth=depth, min_trust=min_trust,
        forward_links=forward, reverse_links=reverse, warnings=warnings,
    )


def trust(root: str | Path = ".", concept_id: str | None = None, cache_dir: str | Path | None = None) -> dict[str, Any]:
    index = cache.load_or_rebuild(root, cache_dir)
    if concept_id is not None:
        normalized = concept_id.removesuffix(".md")
        document = index.documents.get(normalized)
        if document is None or document.is_reserved:
            raise KeyError(f"Unknown concept: {concept_id}")
        return {"id": normalized, **_compat_trust(document.trust.to_dict(), index.okf_version)}
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


def _compat_record(record: dict[str, Any], version: str | None) -> dict[str, Any]:
    result = dict(record)
    if is_legacy(version):
        result.pop("warnings", None)
        result.pop("is_current", None)
    return result


def _compat_trust(value: dict[str, Any], version: str | None) -> dict[str, Any]:
    if not is_legacy(version):
        return value
    result = dict(value)
    result.pop("verified_current", None)
    result.pop("verified_history", None)
    result.pop("stale_after_malformed", None)
    return result


def lint_links(root: str | Path = ".", cache_dir: str | Path | None = None) -> list[dict[str, Any]]:
    index = cache.load_or_rebuild(root, cache_dir)
    return lint_link_index(index.documents, index.forward_links, index.reverse_links)


def bundle_info(root: str | Path = ".", cache_dir: str | Path | None = None) -> dict[str, Any]:
    index = cache.load_or_rebuild(root, cache_dir)
    document = index.documents.get("index")
    metadata = dict(document.metadata) if document else {}
    result = {"okf_version": index.okf_version, **metadata}
    license_value = metadata.get("license")
    if isinstance(license_value, str) and ("/" in license_value or license_value.startswith(".")):
        resolved = normalize_bundle_path("index.md", license_value)
        result["license_path"] = resolved
    return result


def conformance(root: str | Path = ".", cache_dir: str | Path | None = None) -> dict[str, Any]:
    index = cache.load_or_rebuild(root, cache_dir)
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    legacy = is_legacy(index.okf_version)
    for concept_id, document in index.documents.items():
        for error in document.errors:
            if legacy or error != "Missing required non-empty frontmatter field: type":
                errors.append({"id": concept_id, "message": error})
        if document.is_reserved and document.metadata and document.relative_path != "index.md":
            warnings.append({"id": concept_id, "message": "reserved file has frontmatter"})
        for warning in document.warnings:
            warnings.append({"id": concept_id, "message": warning})
    return {"conformant": not errors, "errors": errors, "warnings": warnings}


def computations(root: str | Path = ".", cache_dir: str | Path | None = None) -> list[dict[str, Any]]:
    index = cache.load_or_rebuild(root, cache_dir)
    results: list[dict[str, Any]] = []
    for concept_id, document in sorted(index.documents.items()):
        if not document.is_concept or document.metadata.get("type") != "Attested Computation":
            continue
        warnings = list(document.warnings)
        params = document.metadata.get("parameters", [])
        if isinstance(params, dict):
            params = [params]
        valid_params = []
        for item in params if isinstance(params, list) else []:
            if not isinstance(item, dict) or not item.get("name") or not item.get("type"):
                warnings.append("invalid parameter")
                continue
            valid_params.append({**item, "required": bool(item.get("required", False))})
        source = _computation_source(index, document)
        attestable = bool(document.metadata.get("runtime")) and source["kind"] != "missing"
        results.append({
            "id": concept_id,
            "runtime": document.metadata.get("runtime"),
            "parameters": valid_params,
            "computation_source": source,
            "attestable": attestable,
            "attestation_display": "not attested" if attestable and document.metadata.get("attester") else "not attestable",
            "warnings": warnings,
        })
    return results


def _computation_source(index: Any, document: Any) -> dict[str, Any]:
    computation = document.metadata.get("computation")
    if isinstance(computation, str):
        path = normalize_bundle_path(document.relative_path, computation)
        target = index.root.joinpath(*(path or "").split("/"))
        if path and target.is_file():
            return {"kind": "file", "path": path}
        return {"kind": "missing"}
    heading = re.compile(r"^(#{1,6})\s+Computation\s*$", re.MULTILINE | re.IGNORECASE)
    match = heading.search(document.body)
    if not match:
        return {"kind": "missing"}
    level = len(match.group(1))
    section = document.body[match.end():]
    stop = re.search(rf"^#{{1,{level}}}\s+", section, re.MULTILINE)
    if stop:
        section = section[:stop.start()]
    fence = re.search(r"^(```|~~~)([^\n]*)\n(.*?)^\1\s*$", section, re.MULTILINE | re.DOTALL)
    if not fence:
        return {"kind": "missing"}
    return {"kind": "inline", "language": fence.group(2).strip(), "code": fence.group(3)}


def resource_edges(index: Any) -> tuple[dict[str, list[dict[str, Any]]], dict[str, list[dict[str, Any]]], list[dict[str, Any]]]:
    """Build local opt-in graph edges for exact frontmatter resource matches."""
    forward = {key: list(value) for key, value in index.forward_links.items()}
    resource_owners: dict[str, list[str]] = {}
    for concept_id, document in index.documents.items():
        resource = document.metadata.get("resource")
        if not document.is_reserved and isinstance(resource, str):
            resource_owners.setdefault(resource, []).append(concept_id)

    warnings = [
        {"type": "duplicate_resource", "resource": value, "concepts": sorted(concepts)}
        for value, concepts in sorted(resource_owners.items())
        if len(concepts) > 1
    ]
    unique_resources = {value: concepts[0] for value, concepts in resource_owners.items() if len(concepts) == 1}

    def strings(value: Any, key_path: str = ""):
        if isinstance(value, str):
            yield value, key_path
        elif isinstance(value, dict):
            for key, child in value.items():
                child_path = f"{key_path}.{key}" if key_path else str(key)
                yield from strings(child, child_path)
        elif isinstance(value, list):
            for child in value:
                if isinstance(child, dict):
                    selector_key = next(
                        (candidate for candidate in ("kind", "id", "type", "name")
                         if candidate in child and isinstance(child[candidate], (str, int, float, bool))),
                        None,
                    )
                    selector = f"[{selector_key}={child[selector_key]}]" if selector_key else "[]"
                    yield from strings(child, f"{key_path}{selector}")
                else:
                    yield from strings(child, key_path)

    for source_id, document in index.documents.items():
        if document.is_reserved:
            continue
        for value, key_path in strings(document.metadata):
            target_id = unique_resources.get(value)
            if target_id and target_id != source_id:
                forward.setdefault(source_id, []).append({"text": value, "target": value, "raw_target": value,
                    "anchor": None, "external": False, "resolved_path": index.documents[target_id].relative_path,
                    "resolved_id": target_id, "resource": True, "via": key_path})
    return forward, build_reverse_links(forward), warnings


def add_path_edges(index: Any, original: dict[str, list[dict[str, Any]]]) -> tuple[dict[str, list[dict[str, Any]]], dict[str, list[dict[str, Any]]]]:
    forward = {key: list(value) for key, value in original.items()}
    for source_id, document in index.documents.items():
        if not document.is_concept:
            continue
        for value, field_path in _path_field_values(document.metadata):
            if not isinstance(value, str) or urlparse(value).scheme:
                continue
            resolved = normalize_bundle_path(document.relative_path, value)
            if resolved is None:
                continue
            target_id = resolved.removesuffix(".md")
            if target_id not in index.documents and is_legacy(index.okf_version) and not value.startswith("/"):
                fallback = normalize_bundle_path("index.md", value)
                target_id = (fallback or "").removesuffix(".md")
                resolved = fallback
            target = index.documents.get(target_id)
            if target and target.is_concept:
                forward.setdefault(source_id, []).append({
                    "text": value, "target": value, "raw_target": value, "anchor": None,
                    "external": False, "resolved_path": resolved, "resolved_id": target_id,
                    "via": field_path,
                })
    return forward, build_reverse_links(forward)


def _path_field_values(metadata: dict[str, Any]) -> list[tuple[Any, str]]:
    values: list[tuple[Any, str]] = []
    for key in ("resource", "computation", "superseded_by"):
        if key in metadata:
            values.append((metadata[key], key))
    for key in ("sources",):
        entries = metadata.get(key, [])
        if isinstance(entries, dict):
            entries = [entries]
        if isinstance(entries, list):
            for entry in entries:
                if isinstance(entry, dict) and "resource" in entry:
                    values.append((entry["resource"], f"{key}[].resource"))
    for key in ("executor", "attester"):
        entry = metadata.get(key)
        if isinstance(entry, dict) and "resource" in entry:
            values.append((entry["resource"], f"{key}.resource"))
    return values


def verify_sources(root: str | Path = ".", cache_dir: str | Path | None = None) -> dict[str, Any]:
    index = cache.load_or_rebuild(root, cache_dir)
    checked = missing = mismatched = 0
    problems: list[dict[str, str]] = []
    digests: dict[Path, str] = {}
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
            if urlparse(resource).scheme:
                continue
            checked += 1
            relative = normalize_bundle_path(document.relative_path, resource)
            if relative is None:
                problems.append({"id": source_id, "resource": resource, "type": "out_of_root"})
                continue
            target = index.root.joinpath(*relative.split("/"))
            exists = target.is_file()
            version = is_legacy(index.okf_version)
            if not exists and not resource.startswith("/") and version:
                root_relative = normalize_bundle_path("index.md", resource)
                if root_relative is not None:
                    root_target = index.root.joinpath(*root_relative.split("/"))
                    if root_target.is_file():
                        target = root_target
                        exists = True
            if not exists:
                missing += 1
                problems.append({"id": source_id, "resource": resource, "type": "missing"})
                continue
            expected = entry.get("x-sha256")
            if expected is not None:
                target = target.resolve()
                if target not in digests:
                    digests[target] = _sha256_file(target)
                actual = digests[target]
                if str(expected).lower() != actual:
                    mismatched += 1
                    problems.append({"id": source_id, "resource": resource, "type": "mismatched", "expected": str(expected), "actual": actual})
    return {"checked": checked, "missing": missing, "mismatched": mismatched, "problems": problems}


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


