"""Link index and link linting helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .models import Document


def build_forward_links(documents: dict[str, Document]) -> dict[str, list[dict[str, Any]]]:
    forward: dict[str, list[dict[str, Any]]] = {}
    for concept_id, document in sorted(documents.items()):
        if document.is_reserved:
            continue
        forward[concept_id] = [
            {
                "text": link.text,
                "target": link.target,
                "raw_target": link.raw_target,
                "anchor": link.anchor,
                "external": link.is_external,
                "resolved_path": link.resolved_path,
                "resolved_id": path_to_concept_id(link.resolved_path),
                "via": "body",
            }
            for link in document.links
        ]
    return forward


def build_reverse_links(forward_links: dict[str, list[dict[str, Any]]]) -> dict[str, list[dict[str, Any]]]:
    reverse: dict[str, list[dict[str, Any]]] = {}
    for source_id, links in forward_links.items():
        for link in links:
            target_id = link.get("resolved_id")
            if not target_id:
                continue
            reverse.setdefault(str(target_id), []).append(
                {
                    "source_id": source_id,
                    "source_text": link["text"],
                    "raw_target": link["raw_target"],
                    "anchor": link["anchor"],
                    "via": link.get("via", "body"),
                }
            )
    return {key: sorted(value, key=lambda item: item["source_id"]) for key, value in sorted(reverse.items())}


def path_to_concept_id(path: str | None) -> str | None:
    if path is None:
        return None
    normalized = path.replace("\\", "/")
    if normalized.endswith(".md"):
        return normalized[:-3]
    return normalized.rstrip("/")


def lint_links(
    documents: dict[str, Document],
    forward_links: dict[str, list[dict[str, Any]]],
    reverse_links: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    valid_paths = {document.relative_path for document in documents.values()}

    for concept_id, document in documents.items():
        for error in document.errors:
            issues.append({"level": "error", "type": "parse", "id": concept_id, "message": error})

    for source_id, items in forward_links.items():
        for link in items:
            if link["external"]:
                continue
            resolved_path = link["resolved_path"]
            if resolved_path is None or resolved_path not in valid_paths:
                issues.append(
                    {
                        "level": "warning",
                        "type": "broken_link",
                        "id": source_id,
                        "target": link["raw_target"],
                    }
                )
                continue
            anchor = link.get("anchor")
            if anchor:
                target_doc = documents[path_to_concept_id(resolved_path) or ""]
                if anchor not in target_doc.anchors:
                    issues.append(
                        {
                            "level": "warning",
                            "type": "broken_anchor",
                            "id": source_id,
                            "target": link["raw_target"],
                            "anchor": anchor,
                        }
                    )

    for concept_id, document in documents.items():
        if document.is_reserved:
            continue
        if not forward_links.get(concept_id) and not reverse_links.get(concept_id):
            issues.append({"level": "info", "type": "orphan", "id": concept_id})

    return sorted(issues, key=lambda item: (item["level"], item["type"], item["id"]))


def boundary_links(selected_ids: set[str], forward_links: dict[str, list[dict[str, Any]]], root: Path) -> list[dict[str, str]]:
    boundary: list[dict[str, str]] = []
    for source_id in sorted(selected_ids):
        for link in forward_links.get(source_id, []):
            target_id = link.get("resolved_id")
            resolved_path = link.get("resolved_path")
            if not target_id or not resolved_path or target_id in selected_ids or link.get("external"):
                continue
            boundary.append(
                {
                    "from": f"{source_id}.md",
                    "missing_target": str(link["raw_target"]),
                    "absolute_source": str(root / resolved_path),
                }
            )
    return boundary
