"""JSONL subprocess subject adapter."""

from __future__ import annotations

import json
import subprocess
from typing import Sequence

from ..schema import SubjectRequest, SubjectResponse


class SubprocessAdapterError(RuntimeError):
    pass


def invoke_subprocess(command: Sequence[str], request: SubjectRequest, *, timeout_seconds: float) -> SubjectResponse:
    payload = json.dumps(request.to_dict(), ensure_ascii=True)
    try:
        completed = subprocess.run(
            list(command),
            input=payload,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise SubprocessAdapterError("Subject subprocess timed out") from exc
    if completed.returncode != 0:
        raise SubprocessAdapterError(
            f"Subject subprocess failed ({completed.returncode}): {completed.stderr.strip()}"
        )
    line = completed.stdout.strip().splitlines()[-1] if completed.stdout.strip() else ""
    if not line:
        raise SubprocessAdapterError("Subject subprocess returned empty stdout")
    try:
        data = json.loads(line)
        return SubjectResponse.from_dict(data)
    except (json.JSONDecodeError, ValueError) as exc:
        raise SubprocessAdapterError(f"Invalid subject JSON response: {exc}") from exc
