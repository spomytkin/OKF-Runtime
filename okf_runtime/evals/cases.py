"""Load and validate versioned eval cases."""

from __future__ import annotations

import json
from pathlib import Path

from .schema import CASE_SCHEMA_VERSION, EvalCase


def default_cases_path(repo_root: Path | None = None) -> Path:
    root = repo_root or Path.cwd()
    return root / "evals" / "data" / "cases.jsonl"


def load_cases(path: Path) -> list[EvalCase]:
    cases: list[EvalCase] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        try:
            payload = json.loads(stripped)
            cases.append(EvalCase.from_dict(payload))
        except (json.JSONDecodeError, ValueError) as exc:
            raise ValueError(f"Invalid case at {path}:{line_number}: {exc}") from exc
    return cases


def validate_cases(cases: list[EvalCase]) -> list[str]:
    errors: list[str] = []
    seen: set[str] = set()
    for case in cases:
        if case.case_schema_version != CASE_SCHEMA_VERSION:
            errors.append(f"{case.id}: unsupported case_schema_version")
        if case.id in seen:
            errors.append(f"{case.id}: duplicate case id")
        seen.add(case.id)
        if not case.fixture:
            errors.append(f"{case.id}: missing fixture")
        if "prompt" not in case.input:
            errors.append(f"{case.id}: input.prompt is required")
    return errors


def filter_cases(cases: list[EvalCase], suite: str | None = None, tags: set[str] | None = None) -> list[EvalCase]:
    filtered = cases
    if suite:
        filtered = [case for case in filtered if case.suite == suite]
    if tags:
        filtered = [case for case in filtered if tags.intersection(case.tags)]
    return filtered
