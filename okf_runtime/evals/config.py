"""Eval configuration from environment."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class EvalConfig:
    publish_langfuse: bool
    langfuse_public_key: str | None
    langfuse_secret_key: str | None
    langfuse_host: str | None
    max_events: int = 200
    max_response_bytes: int = 2_000_000


def load_config() -> EvalConfig:
    publish = os.environ.get("OKF_EVAL_PUBLISH_LANGFUSE", "").lower() in {"1", "true", "yes"}
    return EvalConfig(
        publish_langfuse=publish,
        langfuse_public_key=os.environ.get("LANGFUSE_PUBLIC_KEY"),
        langfuse_secret_key=os.environ.get("LANGFUSE_SECRET_KEY"),
        langfuse_host=os.environ.get("LANGFUSE_HOST") or os.environ.get("LANGFUSE_BASE_URL"),
        max_events=int(os.environ.get("OKF_EVAL_MAX_EVENTS", "200")),
        max_response_bytes=int(os.environ.get("OKF_EVAL_MAX_RESPONSE_BYTES", "2000000")),
    )
