"""Pure evaluators: case + normalized response -> structured scores."""

from __future__ import annotations

import re
from typing import Any

from .schema import EvalCase, ScoreResult, SubjectResponse


def _score(
    name: str,
    value: float | int | bool,
    *,
    data_type: str,
    applicable: bool,
    passed: bool,
    evidence: dict[str, Any] | None = None,
    comment: str = "",
) -> ScoreResult:
    return ScoreResult(
        name=name,
        value=value,
        data_type=data_type,  # type: ignore[arg-type]
        applicable=applicable,
        passed=passed,
        evidence=evidence or {},
        comment=comment,
    )


def _match_value(actual: Any, spec: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    mode = spec.get("match", "exact")
    expected = spec.get("value")
    if mode == "exact":
        ok = actual == expected
        return ok, {"actual": actual, "expected": expected}
    if mode == "contains":
        ok = expected in actual if isinstance(actual, (list, str, dict)) else False
        return ok, {"actual": actual, "expected": expected}
    if mode == "subset":
        if not isinstance(actual, list) or not isinstance(expected, list):
            return False, {"actual": actual, "expected": expected}
        ok = set(expected).issubset(set(actual))
        return ok, {"actual": actual, "expected": expected}
    if mode == "set_equals":
        if not isinstance(actual, list) or not isinstance(expected, list):
            return False, {"actual": actual, "expected": expected}
        ok = set(actual) == set(expected)
        return ok, {"actual": sorted(actual), "expected": sorted(expected)}
    if mode == "regex":
        pattern = str(expected)
        ok = bool(re.search(pattern, str(actual)))
        return ok, {"actual": actual, "pattern": pattern}
    if mode == "predicate":
        predicate_id = str(spec.get("predicate_id", ""))
        ok = _run_predicate(predicate_id, actual, spec.get("context") or {})
        return ok, {"actual": actual, "predicate_id": predicate_id}
    return False, {"actual": actual, "expected": expected, "match": mode}


def _run_predicate(predicate_id: str, actual: Any, context: dict[str, Any]) -> bool:
    if predicate_id == "non_empty_list":
        return isinstance(actual, list) and len(actual) > 0
    if predicate_id == "no_body_field":
        return isinstance(actual, dict) and "body" not in actual
    if predicate_id == "has_boundary_json":
        return isinstance(actual, dict) and actual.get("boundary_path")
    if predicate_id == "discover_bundle_count":
        expected = int(context.get("expected", 0))
        return isinstance(actual, list) and len(actual) == expected
    return False


def _tool_events(response: SubjectResponse) -> list[dict[str, Any]]:
    return [event for event in response.events if event.get("type") == "tool_call"]


def score_case(
    case: EvalCase,
    response: SubjectResponse,
    *,
    source_unchanged: bool,
    replay_equivalent: bool | None = None,
) -> list[ScoreResult]:
    scores: list[ScoreResult] = []
    expect = case.expect

    structured_specs = expect.get("structured") or []
    correctness_parts: list[float] = []
    for spec in structured_specs:
        path = spec.get("path", "")
        actual = _resolve_path(response, path)
        ok, evidence = _match_value(actual, spec)
        correctness_parts.append(1.0 if ok else 0.0)
        scores.append(
            _score(
                f"structured:{path or 'root'}",
                1.0 if ok else 0.0,
                data_type="numeric",
                applicable=True,
                passed=ok,
                evidence=evidence,
                comment="Structured expectation",
            )
        )

    if structured_specs:
        avg = sum(correctness_parts) / len(correctness_parts)
        scores.append(
            _score(
                "result_correctness",
                avg,
                data_type="numeric",
                applicable=True,
                passed=avg >= float(expect.get("result_correctness_threshold", 1.0)),
                evidence={"checks": len(structured_specs)},
            )
        )
    else:
        scores.append(
            _score(
                "result_correctness",
                0.0,
                data_type="numeric",
                applicable=False,
                passed=True,
                comment="No structured expectations configured",
            )
        )

    skill_invoke = expect.get("skill_should_invoke")
    if skill_invoke is not None:
        invoked = any(event.get("name", "").startswith("okf.") for event in _tool_events(response))
        want = bool(skill_invoke)
        ok = invoked == want
        scores.append(
            _score(
                "tool_or_operation_selection",
                1.0 if ok else 0.0,
                data_type="numeric",
                applicable=True,
                passed=ok,
                evidence={"invoked": invoked, "expected": want},
            )
        )
    else:
        scores.append(
            _score(
                "tool_or_operation_selection",
                0.0,
                data_type="numeric",
                applicable=False,
                passed=True,
            )
        )

    grounded_required = bool(expect.get("requires_grounded_evidence"))
    if grounded_required:
        has_evidence = bool(_tool_events(response)) or bool(response.output.get("structured"))
        grounded = 1.0 if has_evidence else 0.0
        scores.append(
            _score(
                "groundedness",
                grounded,
                data_type="numeric",
                applicable=True,
                passed=grounded >= 1.0,
                evidence={"tool_events": len(_tool_events(response))},
            )
        )
    else:
        scores.append(
            _score(
                "groundedness",
                0.0,
                data_type="numeric",
                applicable=False,
                passed=True,
            )
        )

    scores.append(
        _score(
            "source_unchanged",
            source_unchanged,
            data_type="boolean",
            applicable=True,
            passed=source_unchanged,
        )
    )

    if expect.get("deterministic_replay"):
        replay_ok = bool(replay_equivalent)
        scores.append(
            _score(
                "deterministic_replay",
                replay_ok,
                data_type="boolean",
                applicable=True,
                passed=replay_ok,
            )
        )
    else:
        scores.append(
            _score(
                "deterministic_replay",
                False,
                data_type="boolean",
                applicable=False,
                passed=True,
            )
        )

    hard = expect.get("hard_invariants") or {}
    protocol_ok = response.protocol_version == "1" and response.case_id == case.id
    if hard.get("protocol_valid", True):
        scores.append(
            _score(
                "protocol_valid",
                protocol_ok,
                data_type="boolean",
                applicable=True,
                passed=protocol_ok,
            )
        )

    task_success = all(score.passed for score in scores if score.applicable and score.name in {
        "result_correctness",
        "tool_or_operation_selection",
        "groundedness",
        "source_unchanged",
        "deterministic_replay",
        "protocol_valid",
    })
    scores.append(
        _score(
            "task_success",
            task_success,
            data_type="boolean",
            applicable=True,
            passed=task_success,
        )
    )

    return scores


def _resolve_path(response: SubjectResponse, path: str) -> Any:
    if not path:
        return response.to_dict()
    current: Any = {
        "output": response.output,
        "events": response.events,
        "status": response.status,
        "error": response.error,
    }
    for part in path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def aggregate_scores(all_scores: list[list[ScoreResult]]) -> dict[str, Any]:
    buckets: dict[str, list[ScoreResult]] = {}
    for case_scores in all_scores:
        for score in case_scores:
            buckets.setdefault(score.name, []).append(score)
    aggregates: dict[str, Any] = {}
    for name, scores in buckets.items():
        applicable = [score for score in scores if score.applicable]
        if not applicable:
            aggregates[name] = {"applicable": False}
            continue
        numeric = [score for score in applicable if score.data_type == "numeric"]
        boolean = [score for score in applicable if score.data_type == "boolean"]
        entry: dict[str, Any] = {
            "applicable": True,
            "count": len(applicable),
            "passed_count": sum(1 for score in applicable if score.passed),
        }
        if numeric:
            entry["mean"] = sum(float(score.value) for score in numeric) / len(numeric)
        if boolean:
            entry["pass_rate"] = sum(1 for score in boolean if score.passed) / len(boolean)
        aggregates[name] = entry
    return aggregates
