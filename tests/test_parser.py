from __future__ import annotations

import unittest
from pathlib import Path

from okf_runtime.parser import parse_frontmatter, split_frontmatter


class FrontmatterParserTests(unittest.TestCase):
    def test_v02_generated_block_parsing(self) -> None:
        metadata, errors = parse_frontmatter(
            """generated:
  by: reference_agent/gemini-2.5-pro
  at: 2026-06-30T14:00:00Z
"""
        )

        self.assertEqual(errors, [])
        self.assertEqual(
            metadata["generated"],
            {"by": "reference_agent/gemini-2.5-pro", "at": "2026-06-30T14:00:00Z"},
        )

    def test_v02_sources_list_of_dicts_parsing(self) -> None:
        sample = Path("tests/fixtures/samples/bundles/acme_retail/metrics/gross-margin-period.md")
        metadata, _, errors = split_frontmatter(sample.read_text(encoding="utf-8"))

        self.assertEqual(errors, [])
        self.assertEqual(
            metadata["sources"],
            [
                {
                    "id": "revenue",
                    "resource": "revenue.md",
                    "title": "Revenue metric",
                },
                {
                    "id": "margin-standard",
                    "resource": "../policies/margin-standard.md",
                    "title": "Gross margin standard",
                },
            ],
        )

    def test_v02_verified_list_of_dicts_parsing(self) -> None:
        metadata, errors = parse_frontmatter(
            """verified:
  - { by: human:jsmith@acme, at: 2026-07-01T09:00:00Z }
"""
        )

        self.assertEqual(errors, [])
        self.assertEqual(metadata["verified"], [{"by": "human:jsmith@acme", "at": "2026-07-01T09:00:00Z"}])

    def test_v01_frontmatter_is_unchanged(self) -> None:
        metadata, errors = parse_frontmatter(
            """type: Table
title: Orders
tags: [sales, revenue]
owners:
  - analytics
  - finance
enabled: true
"""
        )

        self.assertEqual(errors, [])
        self.assertEqual(
            metadata,
            {
                "type": "Table",
                "title": "Orders",
                "tags": ["sales", "revenue"],
                "owners": ["analytics", "finance"],
                "enabled": True,
            },
        )


if __name__ == "__main__":
    unittest.main()
