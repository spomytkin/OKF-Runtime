from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from okf_runtime import api


class RuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace_tmp = Path(self.temp_dir.name)
        self.root = self.workspace_tmp / f"{self._testMethodName}-{uuid.uuid4().hex}"
        if self.root.exists():
            shutil.rmtree(self.root, ignore_errors=True)
        self.root.mkdir(parents=True)
        (self.root / "tables").mkdir()
        (self.root / "tables" / "orders.md").write_text(
            """---
type: Table
title: Orders
tags: [sales, revenue]
---

# Schema

Joined with [Customers](/tables/customers.md#schema).
Missing [Payment](payments.md).
""",
            encoding="utf-8",
        )
        (self.root / "tables" / "customers.md").write_text(
            """---
type: Table
title: Customers
tags:
  - sales
---

# Schema

Customer rows.
""",
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_catalog_query_and_cache(self) -> None:
        catalog = api.catalog(self.root)
        self.assertEqual([record["id"] for record in catalog], ["tables/customers", "tables/orders"])
        self.assertTrue((self.root / ".cache" / "metadata.json").exists())

        results = api.query(self.root, type="Table")
        self.assertEqual(len(results), 2)
        tagged = api.query(self.root, tags="revenue")
        self.assertEqual(tagged[0]["id"], "tables/orders")

    def test_links_backlinks_graph_and_lint(self) -> None:
        links = api.links(self.root, "tables/orders")
        self.assertEqual(links[0]["resolved_id"], "tables/customers")

        backlinks = api.backlinks(self.root, "tables/customers")
        self.assertEqual(backlinks[0]["source_id"], "tables/orders")

        graph = api.graph(self.root, "tables/orders")
        self.assertIn("tables/customers", graph["nodes"])

        issues = api.lint_links(self.root)
        self.assertTrue(any(issue["type"] == "broken_link" for issue in issues))

    def test_show_body_and_compose(self) -> None:
        shown = api.show(self.root, "tables/orders", include_body=True)
        self.assertIn("# Schema", shown["body"])

        output = api.compose(self.root, "orders", output_dir=self.workspace_tmp / f"composed-{uuid.uuid4().hex}")
        output_dir = Path(output["output_dir"])
        self.assertTrue((output_dir / "tables" / "orders.md").exists())
        boundary = json.loads((output_dir / "boundary.json").read_text(encoding="utf-8"))
        self.assertEqual(boundary["start_id"], "tables/orders")


if __name__ == "__main__":
    unittest.main()
