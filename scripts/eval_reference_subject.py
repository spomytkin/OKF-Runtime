#!/usr/bin/env python3
"""JSONL subprocess subject wrapper for the built-in reference adapter."""

from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from okf_runtime.evals.adapters.reference import run_reference_subject
from okf_runtime.evals.cases import default_cases_path, load_cases
from okf_runtime.evals.schema import SubjectRequest


def main() -> int:
    payload = sys.stdin.read()
    request = SubjectRequest.from_dict(json.loads(payload))
    cases = {case.id: case for case in load_cases(default_cases_path(_ROOT))}
    try:
        plan = cases[request.case_id].plan
    except KeyError as exc:
        raise SystemExit(f"Unknown eval case: {request.case_id}") from exc
    response = run_reference_subject(request, plan=plan)
    sys.stdout.write(json.dumps(response.to_dict(), ensure_ascii=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
