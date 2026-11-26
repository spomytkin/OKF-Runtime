"""Versioned JSON-serializable eval schemas."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

PROTOCOL_VERSION = "1"
CASE_SCHEMA_VERSION = "1"
RESULT_SCHEMA_VERSION = "1"

ScoreDataType = Literal["numeric", "boolean", "categorical"]
SubjectStatus = Literal["ok", "error", "timeout", "invalid"]


def _drop_none(data: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in data.items() if value is not None}


@dataclass
class EvalCase:
    case_schema_version: str
    case_version: str
    id: str
    suite: str
    description: str
    fixture: str
    input: dict[str, Any]
    tags: list[str] = field(default_factory=list)
    plan: dict[str, Any] = field(default_factory=dict)
    expect: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EvalCase:
        if data.get("case_schema_version") != CASE_SCHEMA_VERSION:
            raise ValueError(f"Unsupported case_schema_version: {data.get('case_schema_version')}")
        required = ("id", "suite", "description", "fixture", "input")
        for key in required:
            if key not in data:
                raise ValueError(f"Missing required case field: {key}")
        return cls(
            case_schema_version=data["case_schema_version"],
            case_version=str(data.get("case_version", "1")),
            id=str(data["id"]),
            suite=str(data["suite"]),
            description=str(data["description"]),
            fixture=str(data["fixture"]),
            input=dict(data["input"]),
            tags=list(data.get("tags") or []),
            plan=dict(data.get("plan") or {}),
            expect=dict(data.get("expect") or {}),
            metadata=dict(data.get("metadata") or {}),
        )


@dataclass
class SubjectRequest:
    protocol_version: str
    case_id: str
    input: dict[str, Any]
    context: dict[str, Any]
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SubjectRequest:
        if data.get("protocol_version") != PROTOCOL_VERSION:
            raise ValueError(f"Unsupported protocol_version: {data.get('protocol_version')}")
        return cls(
            protocol_version=data["protocol_version"],
            case_id=str(data["case_id"]),
            input=dict(data.get("input") or {}),
            context=dict(data.get("context") or {}),
            metadata=dict(data.get("metadata") or {}),
        )


@dataclass
class SubjectResponse:
    protocol_version: str
    case_id: str
    status: SubjectStatus
    output: dict[str, Any] = field(default_factory=dict)
    events: list[dict[str, Any]] = field(default_factory=list)
    usage: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return _drop_none(asdict(self))

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SubjectResponse:
        if data.get("protocol_version") != PROTOCOL_VERSION:
            raise ValueError(f"Unsupported protocol_version: {data.get('protocol_version')}")
        return cls(
            protocol_version=data["protocol_version"],
            case_id=str(data["case_id"]),
            status=data["status"],
            output=dict(data.get("output") or {}),
            events=list(data.get("events") or []),
            usage=dict(data.get("usage") or {}),
            metadata=dict(data.get("metadata") or {}),
            error=data.get("error"),
        )


@dataclass
class ScoreResult:
    name: str
    value: float | int | bool | str
    data_type: ScoreDataType
    applicable: bool
    passed: bool
    evidence: dict[str, Any] = field(default_factory=dict)
    comment: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CaseRunResult:
    case_id: str
    suite: str
    status: SubjectStatus
    scores: list[ScoreResult]
    latency_ms: float
    error_category: str | None = None
    gate_status: SubjectStatus | None = None
    subject_response: dict[str, Any] | None = None
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "suite": self.suite,
            "status": self.status,
            "gate_status": self.gate_status or self.status,
            "scores": [score.to_dict() for score in self.scores],
            "latency_ms": self.latency_ms,
            "error_category": self.error_category,
            "subject_response": self.subject_response,
            "evidence": self.evidence,
        }


@dataclass
class EvalRunResult:
    result_schema_version: str
    run_id: str
    run_name: str
    adapter: str
    started_at: str
    finished_at: str
    cases: list[CaseRunResult]
    aggregates: dict[str, Any]
    gates: dict[str, Any]
    publication: dict[str, Any]
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "result_schema_version": self.result_schema_version,
            "run_id": self.run_id,
            "run_name": self.run_name,
            "adapter": self.adapter,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "cases": [case.to_dict() for case in self.cases],
            "aggregates": self.aggregates,
            "gates": self.gates,
            "publication": self.publication,
            "metadata": self.metadata,
        }
