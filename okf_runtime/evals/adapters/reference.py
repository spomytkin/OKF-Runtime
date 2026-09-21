"""Built-in reference subject using the public OKF Runtime API."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from okf_runtime import api

from ..schema import PROTOCOL_VERSION, SubjectRequest, SubjectResponse


def _emit_tool(name: str, arguments: dict[str, Any], result: Any) -> dict[str, Any]:
    return {"type": "tool_call", "name": name, "arguments": arguments, "result": result}


def _execute_operation(root: Path, operation: dict[str, Any]) -> dict[str, Any]:
    op_type = operation.get("type") or operation.get("name")
    args = dict(operation.get("arguments") or operation.get("kwargs") or {})
    if op_type == "okf.discover":
        result = api.discover(root)
        return _emit_tool("okf.discover", {}, result)
    if op_type == "okf.catalog":
        result = api.catalog(root, include_links=bool(args.get("include_links")))
        return _emit_tool("okf.catalog", args, result)
    if op_type == "okf.query":
        filters = {key: str(value) for key, value in args.items() if key not in {"include_links"}}
        result = api.query(root, **filters)
        return _emit_tool("okf.query", filters, result)
    if op_type == "okf.show":
        concept_id = str(args["concept_id"])
        include_body = bool(args.get("include_body"))
        result = api.show(root, concept_id, include_body=include_body)
        return _emit_tool("okf.show", args, result)
    if op_type == "okf.links":
        concept_id = args.get("concept_id")
        result = api.links(root, concept_id) if concept_id else api.links(root)
        return _emit_tool("okf.links", args, result)
    if op_type == "okf.backlinks":
        concept_id = args.get("concept_id")
        result = api.backlinks(root, concept_id) if concept_id else api.backlinks(root)
        return _emit_tool("okf.backlinks", args, result)
    if op_type == "okf.graph":
        result = api.graph(root, str(args["concept_id"]), depth=int(args.get("depth", 1)))
        return _emit_tool("okf.graph", args, result)
    if op_type == "okf.compose":
        result = api.compose(
            root,
            str(args["topic"]),
            output_dir=args.get("output_dir"),
            depth=int(args.get("depth", 1)),
            min_trust=args.get("min_trust"),
        )
        return _emit_tool("okf.compose", args, result)
    if op_type == "okf.trust":
        concept_id = args.get("concept_id")
        result = api.trust(root, concept_id) if concept_id else api.trust(root)
        return _emit_tool("okf.trust", args, result)
    if op_type == "okf.lint_links":
        result = api.lint_links(root)
        return _emit_tool("okf.lint_links", args, result)
    if op_type == "skill.decision":
        return {
            "type": "skill_decision",
            "name": "skill.decision",
            "arguments": args,
            "result": {"invoke_okf": bool(args.get("invoke_okf"))},
        }
    raise ValueError(f"Unknown operation type: {op_type}")


def run_reference_subject(
    request: SubjectRequest,
    *,
    plan: dict[str, Any] | None = None,
) -> SubjectResponse:
    root = Path(str(request.context.get("bundle_root", ".")))
    plan = dict(plan or {})
    events: list[dict[str, Any]] = []
    structured: dict[str, Any] = {}
    status: str = "ok"
    error: str | None = None

    try:
        for operation in plan.get("operations") or []:
            event = _execute_operation(root, operation)
            events.append(event)
            if event.get("type") == "tool_call" and event.get("name") == "okf.catalog":
                structured["catalog_ids"] = [row["id"] for row in event.get("result") or []]
            if event.get("type") == "tool_call" and event.get("name") == "okf.query":
                structured["query_ids"] = [row["id"] for row in event.get("result") or []]
            if event.get("type") == "tool_call" and event.get("name") == "okf.show":
                structured["show"] = event.get("result")
            if event.get("type") == "tool_call" and event.get("name") == "okf.trust":
                structured["trust"] = event.get("result")
            if event.get("type") == "tool_call" and event.get("name") == "okf.compose":
                structured["compose"] = event.get("result")
            if event.get("type") == "tool_call" and event.get("name") == "okf.lint_links":
                structured["lint"] = event.get("result")
            if event.get("type") == "tool_call" and event.get("name") == "okf.graph":
                structured["graph"] = event.get("result")
            if event.get("type") == "tool_call" and event.get("name") == "okf.discover":
                structured["discover"] = event.get("result")
            if event.get("type") == "tool_call" and event.get("name") in {"okf.links", "okf.backlinks"}:
                structured[event["name"].split(".", 1)[1]] = event.get("result")

        skill_decision = plan.get("skill_decision")
        if skill_decision is not None:
            events.append(
                _execute_operation(
                    root,
                    {"type": "skill.decision", "arguments": {"invoke_okf": bool(skill_decision)}},
                )
            )
    except (KeyError, ValueError, TypeError) as exc:
        status = "error"
        error = str(exc)
        events.append({"type": "error", "name": "okf.error", "arguments": {}, "result": {"message": str(exc)}})

    return SubjectResponse(
        protocol_version=PROTOCOL_VERSION,
        case_id=request.case_id,
        status=status,  # type: ignore[arg-type]
        output={"answer": request.input.get("prompt", ""), "structured": structured},
        events=events,
        metadata={"framework": "reference", "model": "deterministic"},
        error=error,
    )
