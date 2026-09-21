"""In-process callable subject adapter."""

from __future__ import annotations

import importlib
from collections.abc import Callable

from ..schema import SubjectRequest, SubjectResponse


def load_callable(path: str) -> Callable[[SubjectRequest], SubjectResponse | dict]:
    module_name, _, attr = path.partition(":")
    if not attr:
        raise ValueError("Callable path must be module:callable")
    module = importlib.import_module(module_name)
    target = getattr(module, attr)
    if not callable(target):
        raise ValueError(f"Not callable: {path}")
    return target


def invoke_callable(path: str, request: SubjectRequest) -> SubjectResponse:
    target = load_callable(path)
    result = target(request)
    if isinstance(result, SubjectResponse):
        return result
    return SubjectResponse.from_dict(result)
