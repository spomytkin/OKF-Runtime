"""Local JSON result reporter."""

from __future__ import annotations

import json
from pathlib import Path

from ..redaction import redact_run_result
from ..schema import EvalRunResult


def write_json_result(result: EvalRunResult, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = redact_run_result(result.to_dict())
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
