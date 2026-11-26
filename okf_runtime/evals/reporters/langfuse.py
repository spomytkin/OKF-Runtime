"""Optional Langfuse publication layer."""

from __future__ import annotations

from typing import Any, Protocol

from ..config import EvalConfig
from ..redaction import redact_run_result
from ..schema import EvalRunResult


class LangfuseObservation(Protocol):
    def update(self, **kwargs: Any) -> Any: ...


class LangfuseClientProtocol(Protocol):
    def start_as_current_observation(self, **kwargs: Any) -> Any: ...

    def create_score(self, **kwargs: Any) -> Any: ...

    def get_current_trace_id(self) -> str | None: ...

    def flush(self) -> None: ...


class LangfuseReporter:
    def __init__(self, client: LangfuseClientProtocol | None, config: EvalConfig) -> None:
        self.client = client
        self.config = config

    @classmethod
    def from_config(cls, config: EvalConfig) -> LangfuseReporter:
        if not config.publish_langfuse:
            return cls(None, config)
        if not config.langfuse_public_key or not config.langfuse_secret_key:
            raise ValueError("Langfuse publish requested but LANGFUSE_PUBLIC_KEY/SECRET_KEY are missing")
        try:
            from langfuse import Langfuse
        except ImportError as exc:
            raise ValueError("Langfuse publish requested but langfuse package is not installed") from exc
        client = Langfuse(
            public_key=config.langfuse_public_key,
            secret_key=config.langfuse_secret_key,
            base_url=config.langfuse_host,
        )
        return cls(client, config)

    def publish(self, result: EvalRunResult) -> dict[str, Any]:
        if self.client is None:
            return {"enabled": False, "status": "skipped"}

        sanitized = redact_run_result(result.to_dict())
        run_name = result.run_name
        try:
            with self.client.start_as_current_observation(
                as_type="span",
                name=f"okf-eval-run:{run_name}",
                input={"run_id": result.run_id},
                metadata={
                    "run_id": result.run_id,
                    "run_name": run_name,
                    "adapter": result.adapter,
                    "case_count": len(sanitized.get("cases", [])),
                },
            ) as run_observation:
                for case in sanitized.get("cases", []):
                    with self.client.start_as_current_observation(
                        as_type="span",
                        name=f"okf-eval:{case['case_id']}",
                        input={"case_id": case["case_id"]},
                        metadata={
                            "run_id": result.run_id,
                            "run_name": run_name,
                            "adapter": result.adapter,
                            "suite": case.get("suite"),
                        },
                    ) as observation:
                        observation.update(output=case.get("subject_response"))
                        trace_id = self.client.get_current_trace_id()
                        observation_id = getattr(observation, "id", None)
                        for score in case.get("scores", []):
                            if not score.get("applicable"):
                                continue
                            data_type = str(score.get("data_type", "")).upper()
                            value = score["value"]
                            if data_type == "BOOLEAN":
                                value = 1.0 if value else 0.0
                            elif data_type == "NUMERIC":
                                value = float(value)
                            score_kwargs = {
                                "trace_id": trace_id,
                                "name": str(score["name"]),
                                "value": value,
                                "data_type": data_type or None,
                                "comment": str(score.get("comment") or ""),
                                "metadata": {
                                    "run_id": result.run_id,
                                    "case_id": case["case_id"],
                                    "adapter": result.adapter,
                                },
                            }
                            if observation_id:
                                score_kwargs["observation_id"] = observation_id
                            self.client.create_score(**score_kwargs)
                run_observation.update(
                    output={
                        "gates": sanitized.get("gates"),
                        "aggregates": sanitized.get("aggregates"),
                    }
                )
            self.client.flush()
            return {"enabled": True, "status": "published", "run_name": run_name}
        except Exception as exc:  # noqa: BLE001 - publication must not crash runner
            return {"enabled": True, "status": "failed", "error": str(exc)}
