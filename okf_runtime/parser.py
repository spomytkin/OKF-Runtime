"""Markdown and frontmatter parsing."""

from __future__ import annotations

import re
from dataclasses import replace
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from .models import ActorEvent, Document, Link, MarkdownFile, Source, TrustSignals
from .paths import resolve_path
from .spec import is_legacy
from .timestamps import parse_instant

FRONTMATTER_BOUNDARY = "---"
LINK_RE = re.compile(r"(?<!!)\[([^\]]+)\]\(([^)]+)\)")
REFERENCE_DEF_RE = re.compile(r"^\s*\[([^\]]+)\]:\s*(\S+).*$", re.MULTILINE)
REFERENCE_LINK_RE = re.compile(r"(?<!!)\[([^\]]+)\](?:\[([^\]]*)\])?")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$", re.MULTILINE)
SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*:")


def parse_document(file: MarkdownFile, root: str | Path, legacy: bool = True) -> Document:
    root_path = Path(root).resolve()
    text = file.path.read_text(encoding="utf-8")
    metadata, body, errors = split_frontmatter(text, allow_missing=file.is_reserved)
    warnings = [error.removeprefix("warning: ") for error in errors if error.startswith("warning: ")]
    errors = [error for error in errors if not error.startswith("warning: ")]
    links = extract_links(body, file.relative_path, root_path)
    anchors = extract_anchors(body)
    has_type = bool(str(metadata.get("type", "")).strip())
    # Legacy bundles keep the v0.2 error for a missing type, and the
    # document stays a concept (§12.1 gating, spec item 1c); v0.3+
    # bundles treat it as a non-concept instead.
    is_concept = not file.is_reserved and (legacy or has_type)
    if not has_type and not file.is_reserved and legacy:
        errors.append("Missing required non-empty frontmatter field: type")
    return Document(
        path=file.path,
        relative_path=file.relative_path,
        concept_id=file.concept_id,
        is_reserved=file.is_reserved,
        metadata=metadata,
        body=body,
        trust=extract_trust_signals(metadata, legacy, warnings),
        links=links,
        anchors=anchors,
        errors=errors,
        warnings=warnings,
        is_concept=is_concept,
        legacy=legacy,
    )


def parse_documents(files: list[MarkdownFile], root: str | Path) -> dict[str, Document]:
    root_index = next((item for item in files if item.relative_path == "index.md"), None)
    version = None
    if root_index is not None:
        version, _, _ = split_frontmatter(root_index.path.read_text(encoding="utf-8"), allow_missing=True)
        version = version.get("okf_version") if isinstance(version, dict) else None
    legacy = is_legacy(str(version) if version is not None else None)
    documents = {item.concept_id: parse_document(item, root, legacy) for item in files}
    for document in documents.values():
        document.trust = replace(document.trust, superseded_by_id=resolve_superseded_by_id(documents, document))
    return documents


def resolve_superseded_by_id(documents: dict[str, Document], document: Document) -> str | None:
    """Resolve a document's `superseded_by` path field to a concept id (§5.4)."""
    value = document.metadata.get("superseded_by")
    if not isinstance(value, str) or not value:
        return None
    resolved, external = resolve_path(document.relative_path, value)
    target_id = _concept_id_for_path(documents, resolved)
    if target_id is None and document.legacy and not value.startswith("/"):
        fallback, _ = resolve_path("index.md", value)
        target_id = _concept_id_for_path(documents, fallback)
    return target_id


def _concept_id_for_path(documents: dict[str, Document], resolved: str | None) -> str | None:
    if resolved is None:
        return None
    target_id = resolved.removesuffix(".md")
    target = documents.get(target_id)
    return target_id if target is not None and target.is_concept else None


def extract_trust_signals(metadata: dict[str, Any], legacy: bool = True, warnings: list[str] | None = None) -> TrustSignals:
    """Normalize optional v0.2 trust frontmatter into a stable value object."""

    def event(value: Any) -> ActorEvent | None:
        if not isinstance(value, dict) or not value.get("by"):
            return None
        at = value.get("at")
        return ActorEvent(by=str(value["by"]), at=str(at) if at is not None else None)

    warnings = warnings if warnings is not None else []
    generated_raw = metadata.get("generated")
    generated = event(generated_raw)
    if generated is None and generated_raw is not None:
        # A present generated entry without a usable `by` is ignored (§11.2
        # rule 3: entries missing a REQUIRED key are ignored, with a warning).
        warnings.append("generated entry missing by")
    if generated is None and legacy and metadata.get("timestamp") is not None:
        generated = ActorEvent(by="process:legacy", at=str(metadata["timestamp"]))
    verified_raw = metadata.get("verified", [])
    if isinstance(verified_raw, dict):
        verified_raw = [verified_raw]
    verified: list[ActorEvent] = []
    if isinstance(verified_raw, list):
        for value in verified_raw:
            item = event(value)
            if item is None:
                warnings.append("verified entry missing by")
                continue
            verified.append(item)
    verified_current: list[ActorEvent] = []
    verified_history: list[ActorEvent] = []
    generated_at = None
    if generated and generated.at:
        try:
            generated_at = parse_instant(generated.at)
        except ValueError:
            warnings.append("malformed generated.at")
    for item in verified:
        if not item.at:
            warnings.append("verified entry missing at")
            continue
        try:
            event_at = parse_instant(item.at)
        except ValueError:
            warnings.append("malformed verified.at")
            continue
        if generated_at is None or event_at >= generated_at:
            verified_current.append(item)
        else:
            verified_history.append(item)
    stale_after = _optional_string(metadata.get("stale_after"))
    stale_malformed = False
    if stale_after:
        try:
            parse_instant(stale_after)
        except ValueError:
            stale_malformed = True
            warnings.append("malformed stale_after")

    window = metadata.get("usage_window")
    usage_window = {str(key): str(value) for key, value in window.items()} if isinstance(window, dict) else None
    sources: list[Source] = []
    sources_raw = metadata.get("sources", [])
    if isinstance(sources_raw, dict):
        sources_raw = [sources_raw]
    if isinstance(sources_raw, list):
        for value in sources_raw:
            if not isinstance(value, dict) or not value.get("resource"):
                warnings.append("sources entry missing resource")
                continue
            source_window = value.get("usage_window")
            sources.append(
                Source(
                    resource=str(value["resource"]),
                    id=_optional_string(value.get("id")),
                    title=_optional_string(value.get("title")),
                    author=_optional_string(value.get("author")),
                    usage_count=value.get("usage_count") if isinstance(value.get("usage_count"), int) else None,
                    last_modified=_optional_string(value.get("last_modified")),
                    usage_window={str(key): str(item) for key, item in source_window.items()}
                    if isinstance(source_window, dict)
                    else None,
                )
            )
    status_raw = metadata.get("status")
    status = str(status_raw) if status_raw not in (None, "", []) else "stable"
    return TrustSignals(
        generated=generated,
        verified=verified,
        status=status,
        stale_after=stale_after,
        sources=sources,
        usage_window=usage_window,
        verified_current=verified_current,
        verified_history=verified_history,
        stale_after_malformed=stale_malformed,
    )


def _optional_string(value: Any) -> str | None:
    # §11.2: null, empty string and empty list are all "absent".
    if value is None or value == "" or value == []:
        return None
    return str(value)


def split_frontmatter(text: str, allow_missing: bool = False) -> tuple[dict[str, Any], str, list[str]]:
    errors: list[str] = []
    lines = text.splitlines()
    if not lines or lines[0] != FRONTMATTER_BOUNDARY:
        if allow_missing:
            return {}, text, errors
        return {}, text, ["Missing YAML frontmatter block"]

    end_index: int | None = None
    for index, line in enumerate(lines[1:], start=1):
        if line == FRONTMATTER_BOUNDARY:
            end_index = index
            break

    if end_index is None:
        return {}, text, ["Unclosed YAML frontmatter block"]

    frontmatter = "\n".join(lines[1:end_index])
    body = "\n".join(lines[end_index + 1 :])
    metadata, parse_errors = parse_frontmatter(frontmatter)
    errors.extend(parse_errors)
    return metadata, body, errors


def parse_frontmatter(text: str) -> tuple[dict[str, Any], list[str]]:
    """Parse the small YAML subset used by OKF frontmatter.

    Supports scalars, inline collections, indented mappings, and block lists.
    This deliberately remains a small, dependency-free YAML subset rather
    than a general YAML implementation.
    """

    errors: list[str] = []
    for line in text.splitlines():
        if re.search(r":\s*!\w+", line):
            errors.append("warning: custom YAML tag preserved as raw text")
    lines = [
        (number, len(raw_line) - len(raw_line.lstrip(" ")), raw_line.strip())
        for number, raw_line in enumerate(text.splitlines(), start=1)
        if raw_line.strip() and not raw_line.lstrip().startswith("#")
    ]
    if not lines:
        return {}, errors
    if lines[0][1] != 0:
        errors.append(f"Invalid frontmatter line {lines[0][0]}: unexpected indentation")
        return {}, errors

    value, next_index = _parse_frontmatter_block(lines, 0, 0, errors)
    while next_index < len(lines):
        line_number, _, _ = lines[next_index]
        errors.append(f"Invalid frontmatter line {line_number}: unexpected indentation")
        next_index += 1
    return value if isinstance(value, dict) else {}, errors


def _parse_frontmatter_block(
    lines: list[tuple[int, int, str]], index: int, indent: int, errors: list[str]
) -> tuple[Any, int]:
    """Parse one same-indentation mapping or list block."""

    is_list = lines[index][2].startswith("- ") or lines[index][2] == "-"
    result: list[Any] | dict[str, Any] = [] if is_list else {}

    while index < len(lines):
        line_number, line_indent, content = lines[index]
        if line_indent < indent:
            break
        if line_indent > indent:
            break

        if is_list:
            if not (content.startswith("- ") or content == "-"):
                break
            item = content[1:].strip()
            index += 1
            if not item:
                if index < len(lines) and lines[index][1] > indent:
                    child_indent = lines[index][1]
                    value, index = _parse_frontmatter_block(lines, index, child_indent, errors)
                else:
                    value = None
                result.append(value)
                continue

            # A flow mapping is a complete list item, not the ``key: value``
            # shorthand used by block list mappings.
            if item.startswith("{") and item.endswith("}"):
                result.append(_parse_value(item))
                continue

            key_value = _split_mapping_item(item)
            if key_value is None:
                result.append(_parse_value(item))
                continue

            key, raw_value = key_value
            mapping: dict[str, Any] = {}
            if raw_value:
                mapping[key] = _parse_value(raw_value)
            elif index < len(lines) and lines[index][1] > indent:
                child_indent = lines[index][1]
                mapping[key], index = _parse_frontmatter_block(lines, index, child_indent, errors)
            else:
                mapping[key] = []
            if index < len(lines) and lines[index][1] > indent:
                child_indent = lines[index][1]
                sibling_values, index = _parse_frontmatter_block(lines, index, child_indent, errors)
                if isinstance(sibling_values, dict):
                    mapping.update(sibling_values)
                else:
                    errors.append(f"Invalid frontmatter line {line_number}: list mapping has list-valued siblings")
            result.append(mapping)
            continue

        if content.startswith("- ") or content == "-":
            break
        key_value = _split_mapping_item(content)
        if key_value is None:
            errors.append(f"Invalid frontmatter line {line_number}: expected key: value")
            index += 1
            continue
        key, raw_value = key_value
        if not key:
            errors.append(f"Invalid frontmatter line {line_number}: empty key")
            index += 1
            continue
        if key in result:
            errors.append(f"duplicate_key: {key}")
        index += 1
        if raw_value:
            value = _parse_value(raw_value)
            # YAML permits plain scalars to continue on subsequent indented
            # lines.  Fold them so generated v0.2 bundle descriptions remain
            # usable without implementing YAML's full block-scalar grammar.
            if index < len(lines) and lines[index][1] > indent and not isinstance(value, (dict, list)):
                continuation: list[str] = []
                while index < len(lines) and lines[index][1] > indent:
                    continuation.append(lines[index][2])
                    index += 1
                result[key] = " ".join([str(value), *continuation])
            else:
                result[key] = value
        elif index < len(lines) and (
            lines[index][1] > indent or lines[index][2].startswith("- ") or lines[index][2] == "-"
        ):
            # YAML also allows an "indentless" block sequence directly
            # beneath a mapping key (``sources:\n- id: ...``).
            child_indent = lines[index][1]
            result[key], index = _parse_frontmatter_block(lines, index, child_indent, errors)
        else:
            result[key] = []

    return result, index


def _split_mapping_item(value: str) -> tuple[str, str] | None:
    """Split a YAML ``key: value`` pair, ignoring colons inside quotes."""

    quote: str | None = None
    for index, char in enumerate(value):
        if char in {"'", '"'}:
            quote = None if quote == char else char if quote is None else quote
        elif char == ":" and quote is None:
            return value[:index].strip(), value[index + 1 :].strip()
    return None


def _parse_value(value: str) -> Any:
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [_parse_value(part.strip()) for part in _split_inline_list(inner)]
    if value.startswith("{") and value.endswith("}"):
        inner = value[1:-1].strip()
        if not inner:
            return {}
        mapping: dict[str, Any] = {}
        for part in _split_inline_list(inner):
            key_value = _split_mapping_item(part.strip())
            if key_value is None:
                return _parse_scalar(value)
            key, item_value = key_value
            mapping[key] = _parse_value(item_value)
        return mapping
    return _parse_scalar(value)


def _parse_scalar(value: str) -> str | bool | int | float | None:
    if value in {"null", "Null", "NULL", "~"}:
        return None
    if value in {"true", "True", "TRUE"}:
        return True
    if value in {"false", "False", "FALSE"}:
        return False
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        return value


def _split_inline_list(value: str) -> list[str]:
    parts: list[str] = []
    current: list[str] = []
    quote: str | None = None
    for char in value:
        if char in {"'", '"'}:
            quote = None if quote == char else char if quote is None else quote
        if char == "," and quote is None:
            parts.append("".join(current))
            current = []
        else:
            current.append(char)
    parts.append("".join(current))
    return parts


def extract_links(body: str, source_relative_path: str, root: Path) -> list[Link]:
    links: list[Link] = []
    definitions = {label.casefold(): target for label, target in REFERENCE_DEF_RE.findall(body)}

    def append_link(text: str, raw_target: str) -> None:
        target_without_title = raw_target.split(maxsplit=1)[0]
        target, anchor = split_anchor(target_without_title)
        is_external = is_external_link(target)
        resolved = None if is_external else resolve_internal_link(target, source_relative_path, root)
        links.append(
            Link(
                text=text,
                target=target,
                raw_target=raw_target,
                anchor=anchor,
                is_external=is_external,
                resolved_path=resolved,
            )
        )

    for match in LINK_RE.finditer(body):
        append_link(match.group(1), match.group(2).strip())
    for match in REFERENCE_LINK_RE.finditer(body):
        # With the label optional, the pattern also matches inline links
        # ([text](target)) and link definitions ([label]: target); skip
        # those, and the label half of an image reference (![alt][label]).
        following = body[match.end():match.end() + 1]
        if following in ("(", ":"):
            continue
        if match.group(2) is None and re.search(r"!\[[^\]]*\]$", body[:match.start()]):
            continue
        label = (match.group(2) or match.group(1)).casefold()
        if label in definitions:
            append_link(match.group(1), definitions[label])
    return links


def split_anchor(target: str) -> tuple[str, str | None]:
    if "#" not in target:
        return target, None
    path, anchor = target.split("#", 1)
    return path, anchor or None


def is_external_link(target: str) -> bool:
    if target.startswith("#"):
        return False
    return bool(SCHEME_RE.match(target)) or target.startswith("mailto:")


def resolve_internal_link(target: str, source_relative_path: str, root: Path) -> str | None:
    """Resolve a body-link target through the shared path resolver (§6)."""
    if not target or target.startswith("#"):
        return source_relative_path
    if not urlparse(unquote(target)).path:
        return source_relative_path
    resolved, _external = resolve_path(source_relative_path, target)
    return resolved


def extract_anchors(body: str) -> list[str]:
    anchors: list[str] = []
    for match in HEADING_RE.finditer(body):
        anchors.append(slugify_heading(match.group(2)))
    return anchors


def slugify_heading(text: str) -> str:
    value = re.sub(r"`([^`]*)`", r"\1", text).strip().lower()
    value = re.sub(r"[^\w\s-]", "", value)
    value = re.sub(r"\s+", "-", value)
    return value.strip("-")
