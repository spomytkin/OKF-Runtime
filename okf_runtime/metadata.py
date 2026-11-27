"""Metadata catalogs and indexes."""

from __future__ import annotations

import re
from typing import Any

from .models import Document


def build_metadata_index(documents: dict[str, Document]) -> dict[str, dict[str, Any]]:
    return {
        concept_id: document.to_catalog_record()
        for concept_id, document in sorted(documents.items())
        if document.is_concept
    }


def build_tag_index(metadata_index: dict[str, dict[str, Any]]) -> dict[str, list[str]]:
    index: dict[str, list[str]] = {}
    for concept_id, record in metadata_index.items():
        tags = record["metadata"].get("tags", [])
        if isinstance(tags, str):
            tags = [tags]
        if not isinstance(tags, list):
            continue
        for tag in tags:
            index.setdefault(str(tag), []).append(concept_id)
    return {key: sorted(value) for key, value in sorted(index.items())}


def build_type_index(metadata_index: dict[str, dict[str, Any]]) -> dict[str, list[str]]:
    index: dict[str, list[str]] = {}
    for concept_id, record in metadata_index.items():
        doc_type = record["metadata"].get("type")
        if doc_type is None:
            continue
        index.setdefault(str(doc_type), []).append(concept_id)
    return {key: sorted(value) for key, value in sorted(index.items())}


def build_trust_index(documents: dict[str, Document]) -> tuple[dict[str, dict[str, Any]], dict[str, list[str]]]:
    trust_index = {
        concept_id: document.trust.to_dict()
        for concept_id, document in sorted(documents.items())
        if document.is_concept
    }
    tier_index: dict[str, list[str]] = {}
    for concept_id, trust in trust_index.items():
        tier_index.setdefault(str(trust["trust_tier"]), []).append(concept_id)
    return trust_index, {tier: sorted(ids) for tier, ids in sorted(tier_index.items())}


def query_metadata(metadata_index: dict[str, dict[str, Any]], filters: dict[str, str]) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    for record in metadata_index.values():
        if all(_matches(record, key, value) for key, value in filters.items()):
            matches.append(record)
    return sorted(matches, key=lambda item: str(item["id"]))


def _matches(record: dict[str, Any], key: str, expected: str) -> bool:
    if key in {"trust_tier", "status"}:
        return str(record.get(key)) == expected
    if key == "stale":
        if expected.lower() not in {"true", "false"}:
            return False
        return bool(record.get("is_stale")) == (expected.lower() == "true")
    metadata = record["metadata"]
    values = _path_values(metadata, key)
    return any(_scalar_or_list_matches(value, expected) for value in values)


def _scalar_or_list_matches(value: Any, expected: str) -> bool:
    if isinstance(value, list):
        return expected in {str(item) for item in value}
    return str(value) == expected


def _path_values(root: Any, path: str) -> list[Any]:
    """Read dotted metadata paths, optionally filtering mapping lists by siblings."""
    if isinstance(root, dict) and path in root:
        return [root[path]]
    pattern = r"[^.[\]]+(?:\[[^=\]]+=[^\]]*\])?(?:\.[^.[\]]+(?:\[[^=\]]+=[^\]]*\])?)*"
    if not re.fullmatch(pattern, path):
        raise ValueError(f"Invalid metadata path: {path}")
    tokens = []
    for token in path.split("."):
        match = re.fullmatch(r"([^\[]+)(?:\[([^=\]]+)=([^\]]*)\])?", token)
        if not match:
            return []
        tokens.append(match.groups())
    values = [root]
    for name, filter_key, filter_value in tokens:
        next_values: list[Any] = []
        for value in values:
            child = value.get(name) if isinstance(value, dict) else None
            children = child if isinstance(child, list) else [child]
            for item in children:
                if filter_key and (not isinstance(item, dict) or str(item.get(filter_key)) != filter_value):
                    continue
                if item is not None:
                    next_values.append(item)
        values = next_values
    return values
