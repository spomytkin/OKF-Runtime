"""Graph construction and traversal."""

from __future__ import annotations

from collections import deque
from typing import Any


def neighborhood(
    start_id: str,
    forward_links: dict[str, list[dict[str, Any]]],
    reverse_links: dict[str, list[dict[str, Any]]],
    depth: int = 1,
    via: list[str] | None = None,
) -> dict[str, Any]:
    if depth < 0:
        raise ValueError("depth must be >= 0")

    visited = {start_id}
    queue: deque[tuple[str, int]] = deque([(start_id, 0)])
    edges: list[dict[str, str]] = []

    while queue:
        current, distance = queue.popleft()
        if distance >= depth:
            continue

        for link in forward_links.get(current, []):
            if via and link.get("via", "body") not in via:
                continue
            target = link.get("resolved_id")
            if not target:
                continue
            target_id = str(target)
            edges.append({"source": current, "target": target_id, "direction": "forward", "via": str(link.get("via", "body"))})
            if target_id not in visited:
                visited.add(target_id)
                queue.append((target_id, distance + 1))

        for link in reverse_links.get(current, []):
            if via and link.get("via", "body") not in via:
                continue
            source_id = str(link["source_id"])
            edges.append({"source": source_id, "target": current, "direction": "reverse", "via": str(link.get("via", "body"))})
            if source_id not in visited:
                visited.add(source_id)
                queue.append((source_id, distance + 1))

    return {"start": start_id, "depth": depth, "nodes": sorted(visited), "edges": edges}
