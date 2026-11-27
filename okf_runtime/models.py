"""Shared data models for the OKF runtime."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


RESERVED_FILENAMES = {"index.md", "log.md"}


@dataclass(frozen=True)
class MarkdownFile:
    """A markdown file discovered in a bundle."""

    path: Path
    relative_path: str
    mtime: float
    size: int

    @property
    def is_reserved(self) -> bool:
        return Path(self.relative_path).name in RESERVED_FILENAMES

    @property
    def concept_id(self) -> str:
        rel = self.relative_path.replace("\\", "/")
        return rel[:-3] if rel.endswith(".md") else rel


@dataclass(frozen=True)
class Link:
    """A markdown link found in a document."""

    text: str
    target: str
    raw_target: str
    anchor: str | None = None
    is_external: bool = False
    resolved_path: str | None = None


@dataclass(frozen=True)
class ActorEvent:
    """A generation or verification event recorded in frontmatter."""

    by: str
    at: str | None = None


@dataclass(frozen=True)
class Source:
    """An attributed source and its optional credibility signals."""

    resource: str
    id: str | None = None
    title: str | None = None
    author: str | None = None
    usage_count: int | None = None
    last_modified: str | None = None
    usage_window: dict[str, str] | None = None


@dataclass(frozen=True)
class TrustSignals:
    """Derived v0.2 provenance, trust, and lifecycle metadata."""

    generated: ActorEvent | None = None
    verified: list[ActorEvent] = field(default_factory=list)
    status: str = "stable"
    stale_after: str | None = None
    sources: list[Source] = field(default_factory=list)
    usage_window: dict[str, str] | None = None
    verified_current: list[ActorEvent] = field(default_factory=list)
    verified_history: list[ActorEvent] = field(default_factory=list)
    stale_after_malformed: bool = False
    # Resolved concept id of the `superseded_by` path field, or None when
    # absent, external, out of the bundle, or not a concept (§5.4).
    superseded_by_id: str | None = None

    @property
    def trust_tier(self) -> str:
        if not self.verified_current:
            return "unverified"
        if any(event.by.startswith("human:") for event in self.verified_current):
            return "human-reviewed"
        return "machine-confirmed"

    @property
    def is_stale(self) -> bool:
        if self.stale_after_malformed:
            return True
        if not self.stale_after:
            return False
        from .timestamps import now, parse_instant
        try:
            return now() >= parse_instant(self.stale_after)
        except ValueError:
            # Unparseable stale_after is never fresh (§5.5).
            return True

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "trust_tier": self.trust_tier, "is_stale": self.is_stale}


@dataclass
class Document:
    """A parsed markdown document."""

    path: Path
    relative_path: str
    concept_id: str
    is_reserved: bool
    metadata: dict[str, Any]
    body: str
    trust: TrustSignals = field(default_factory=TrustSignals)
    links: list[Link] = field(default_factory=list)
    anchors: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    is_concept: bool = True
    legacy: bool = True

    @property
    def title(self) -> str | None:
        value = self.metadata.get("title")
        return str(value) if value is not None else None

    @property
    def type(self) -> str | None:
        value = self.metadata.get("type")
        return str(value) if value is not None else None

    @property
    def trust_tier(self) -> str:
        return self.trust.trust_tier

    @property
    def is_stale(self) -> bool:
        return self.trust.is_stale

    @property
    def status(self) -> str:
        return self.trust.status

    @property
    def is_current(self) -> bool:
        return self.status == "stable"

    def to_catalog_record(self) -> dict[str, Any]:
        return {
            "id": self.concept_id,
            "path": self.relative_path,
            "reserved": self.is_reserved,
            "metadata": self.metadata,
            "trust_tier": self.trust_tier,
            "status": self.status,
            "is_stale": self.is_stale,
            "is_current": self.is_current,
            "errors": self.errors,
            "warnings": self.warnings,
        }


@dataclass
class RuntimeIndex:
    """Derived runtime state for a bundle."""

    root: Path
    documents: dict[str, Document]
    forward_links: dict[str, list[dict[str, Any]]]
    reverse_links: dict[str, list[dict[str, Any]]]
    metadata_index: dict[str, dict[str, Any]]
    tag_index: dict[str, list[str]]
    type_index: dict[str, list[str]]
    trust_index: dict[str, dict[str, Any]] = field(default_factory=dict)
    trust_tier_index: dict[str, list[str]] = field(default_factory=dict)
    okf_version: str | None = None
    stale_rebuilt: bool = False

    def concept_ids(self) -> list[str]:
        return sorted(self.metadata_index)
