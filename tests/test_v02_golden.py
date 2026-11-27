"""Frozen v0.2 consumer outputs used as a compatibility safety net."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from okf_runtime import api

FIXTURES = {
    "v02-income-statement": "v02-income-statement",
    "feature-bundle": "feature-bundle",
    "source-digest-cache": "source-digest-cache",
    "samples": "samples",
    "samples-acme-retail": "samples/bundles/acme_retail",
    "samples-stackoverflow": "samples/bundles/stackoverflow",
}
GOLDEN_ROOT = Path(__file__).resolve().parent / "fixtures" / "golden-v02"


def normalize(value: object, root: Path) -> object:
    if isinstance(value, Path):
        value = str(value)
    if isinstance(value, dict):
        return {key: normalize(item, root) for key, item in sorted(value.items())}
    if isinstance(value, list):
        items = [normalize(item, root) for item in value]
        return sorted(items, key=lambda item: json.dumps(item, sort_keys=True, separators=(",", ":")))
    if isinstance(value, str):
        root_text = str(root.resolve()).replace("\\", "/")
        return value.replace("\\", "/").replace(root_text, ".")
    return value


def snapshot(root: Path) -> dict[str, object]:
    catalog = api.catalog(root)
    concept_ids = [str(record["id"]) for record in catalog]
    queries = {
        "trust_tier_machine_confirmed": api.query(root, trust_tier="machine-confirmed"),
        "trust_tier_human_reviewed": api.query(root, trust_tier="human-reviewed"),
        "status_draft": api.query(root, status="draft"),
        "status_deprecated": api.query(root, status="deprecated"),
        "stale_true": api.query(root, stale="true"),
        "stale_false": api.query(root, stale="false"),
    }
    return normalize(
        {
            "catalog": catalog,
            "query": queries,
            "trust": {"summary": api.trust(root), "concepts": {concept_id: api.trust(root, concept_id) for concept_id in concept_ids}},
            "links": api.links(root),
            "backlinks": api.backlinks(root),
            "lint_links": api.lint_links(root),
            "verify_sources": api.verify_sources(root),
            "graph": {
                concept_id: {
                    "default": api.graph(root, concept_id, depth=1),
                    "resolve_resources": api.graph(root, concept_id, depth=1, resolve_resources=True),
                }
                for concept_id in concept_ids
            },
        },
        root,
    )


class V02GoldenTests(unittest.TestCase):
    def test_v02_golden_outputs(self) -> None:
        fixture_root = Path(__file__).resolve().parent / "fixtures"
        for name, relative in FIXTURES.items():
            actual = snapshot(fixture_root / relative)
            expected = json.loads((GOLDEN_ROOT / f"{name}.json").read_text(encoding="utf-8"))
            self.assertEqual(actual, expected, name)


if __name__ == "__main__":
    unittest.main()
