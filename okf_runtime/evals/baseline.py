"""Baseline comparison and gate evaluation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DEFAULT_GATES = {
    "source_unchanged_pass_rate": 1.0,
    "protocol_valid_pass_rate": 1.0,
    "result_correctness_mean": 1.0,
    "case_error_count_max": 0,
}


def normalize_for_compare(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = json.loads(json.dumps(payload))
    for volatile in ("run_id", "started_at", "finished_at"):
        normalized.pop(volatile, None)
        normalized.get("metadata", {}).pop(volatile, None)
    for case in normalized.get("cases", []):
        case.pop("latency_ms", None)
        subject = case.get("subject_response") or {}
        subject.get("metadata", {}).pop("timestamp", None)
    return normalized


def evaluate_gates(aggregates: dict[str, Any], case_results: list[dict[str, Any]], gates: dict[str, float]) -> dict[str, Any]:
    errors = sum(1 for case in case_results if case.get("gate_status", case.get("status")) != "ok")
    checks: dict[str, Any] = {}

    def pass_rate(metric: str) -> float:
        entry = aggregates.get(metric) or {}
        if not entry.get("applicable"):
            return 1.0
        return float(entry.get("pass_rate", entry.get("mean", 0.0)))

    checks["source_unchanged_pass_rate"] = {
        "value": pass_rate("source_unchanged"),
        "threshold": gates["source_unchanged_pass_rate"],
        "passed": pass_rate("source_unchanged") >= gates["source_unchanged_pass_rate"],
    }
    checks["protocol_valid_pass_rate"] = {
        "value": pass_rate("protocol_valid"),
        "threshold": gates["protocol_valid_pass_rate"],
        "passed": pass_rate("protocol_valid") >= gates["protocol_valid_pass_rate"],
    }
    rc = aggregates.get("result_correctness") or {}
    rc_mean = float(rc.get("mean", 0.0)) if rc.get("applicable") else 1.0
    checks["result_correctness_mean"] = {
        "value": rc_mean,
        "threshold": gates["result_correctness_mean"],
        "passed": rc_mean >= gates["result_correctness_mean"],
    }
    checks["case_error_count_max"] = {
        "value": errors,
        "threshold": gates["case_error_count_max"],
        "passed": errors <= gates["case_error_count_max"],
    }
    passed = all(item["passed"] for item in checks.values())
    return {"passed": passed, "checks": checks}


def compare_results(current: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    current_norm = normalize_for_compare(current)
    baseline_norm = normalize_for_compare(baseline)
    regressions: list[str] = []
    for gate_name, gate in current_norm.get("gates", {}).get("checks", {}).items():
        base_gate = baseline_norm.get("gates", {}).get("checks", {}).get(gate_name, {})
        if base_gate.get("passed") and not gate.get("passed"):
            regressions.append(gate_name)
    return {"passed": not regressions, "regressions": regressions}


def load_baseline(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))
