"""Deterministic bundle composition."""

from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path
from typing import Any

from .graph import neighborhood
from .links import boundary_links
from .models import RuntimeIndex


TRUST_TIER_ORDER = {"unverified": 0, "machine-confirmed": 1, "human-reviewed": 2}


def compose_bundle(
    index: RuntimeIndex,
    topic: str,
    output_dir: str | Path | None = None,
    depth: int = 1,
    min_trust: str | None = None,
    forward_links: dict[str, list[dict[str, Any]]] | None = None,
    reverse_links: dict[str, list[dict[str, Any]]] | None = None,
    warnings: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    start_id = resolve_topic(index, topic)
    forward = forward_links if forward_links is not None else index.forward_links
    reverse = reverse_links if reverse_links is not None else index.reverse_links
    graph = neighborhood(start_id, forward, reverse, depth=depth)
    selected_ids = set(graph["nodes"])
    if min_trust is not None:
        if min_trust not in TRUST_TIER_ORDER:
            raise ValueError(f"Invalid minimum trust tier: {min_trust}")
        threshold = TRUST_TIER_ORDER[min_trust]
        selected_ids = {
            concept_id
            for concept_id in selected_ids
            if concept_id in index.documents and TRUST_TIER_ORDER[index.documents[concept_id].trust_tier] >= threshold
        }

    if output_dir:
        destination = Path(output_dir).expanduser().resolve()
    else:
        compose_cache = index.root / ".cache" / "compositions"
        destination = compose_cache / f"okf-compose-{uuid.uuid4().hex}"
    destination.mkdir(parents=True, exist_ok=True)

    copied: list[str] = []
    for concept_id in sorted(selected_ids):
        document = index.documents.get(concept_id)
        if not document or document.is_reserved:
            continue
        target = destination / document.relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(document.path, target)
        copied.append(document.relative_path)

    boundary = boundary_links(selected_ids, forward, index.root)
    boundary_payload = {
        "composed_topic": topic,
        "start_id": start_id,
        "source_bundle_root": str(index.root),
        "depth": depth,
        "min_trust": min_trust,
        "files": copied,
        "boundary_links": boundary,
    }
    if warnings:
        boundary_payload["warnings"] = warnings
    (destination / "boundary.json").write_text(json.dumps(boundary_payload, indent=2, sort_keys=True), encoding="utf-8")

    return {"output_dir": str(destination), **boundary_payload}


def resolve_topic(index: RuntimeIndex, topic: str) -> str:
    normalized = topic.strip().removesuffix(".md")
    if normalized in index.metadata_index:
        return normalized

    lowered = normalized.lower()
    matches: list[str] = []
    for concept_id, record in index.metadata_index.items():
        metadata = record["metadata"]
        title = str(metadata.get("title", "")).lower()
        tags = metadata.get("tags", [])
        if isinstance(tags, str):
            tags = [tags]
        tag_match = any(str(tag).lower() == lowered for tag in tags if tags)
        if lowered in concept_id.lower() or lowered == title or tag_match:
            matches.append(concept_id)

    if not matches:
        raise KeyError(f"No concept matches topic: {topic}")
    if len(matches) > 1:
        exact = [item for item in matches if item.lower().endswith(lowered)]
        if len(exact) == 1:
            return exact[0]
        raise ValueError(f"Topic is ambiguous: {topic}. Matches: {', '.join(sorted(matches))}")
    return matches[0]
