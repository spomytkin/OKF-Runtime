"""HTTP JSON subject adapter."""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from ..schema import SubjectRequest, SubjectResponse


class HttpAdapterError(RuntimeError):
    pass


def invoke_http(url: str, request: SubjectRequest, *, timeout_seconds: float) -> SubjectResponse:
    body = json.dumps(request.to_dict()).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise HttpAdapterError(f"HTTP subject error {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise HttpAdapterError(f"HTTP subject unreachable: {exc}") from exc
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise HttpAdapterError(f"Invalid HTTP subject JSON: {exc}") from exc
    try:
        return SubjectResponse.from_dict(payload)
    except ValueError as exc:
        raise HttpAdapterError(f"Invalid HTTP subject JSON: {exc}") from exc
