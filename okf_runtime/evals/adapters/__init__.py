"""Subject transport adapters."""

from .callable import invoke_callable
from .http import invoke_http
from .reference import run_reference_subject
from .subprocess import invoke_subprocess

__all__ = [
    "invoke_callable",
    "invoke_http",
    "invoke_subprocess",
    "run_reference_subject",
]
