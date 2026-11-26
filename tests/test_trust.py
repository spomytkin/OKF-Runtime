from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from okf_runtime import api, cache


class TrustTests(unittest.TestCase):
    @property
    def fixture(self) -> Path:
        return Path(__file__).resolve().parent / "fixtures" / "v02-income-statement"

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name) / f"trust-{uuid.uuid4().hex}"
        shutil.copytree(self.fixture, self.root)

    def tearDown(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)
        self.temp_dir.cleanup()

    def test_v02_frontmatter_and_trust_derivation(self) -> None:
        index = cache.rebuild_cache(self.root)
        income = index.documents["income-statement"]

        self.assertEqual(index.okf_version, "0.2")
        self.assertEqual(income.trust_tier, "human-reviewed")
        self.assertFalse(income.is_stale)
        self.assertEqual(income.trust.generated.by, "reference_agent/gemini-2.5-pro")
        self.assertEqual(income.trust.sources[0].usage_count, 12)
        self.assertEqual(income.metadata["executor"]["receipt"], ["job_id"])
        self.assertEqual(income.metadata["attester"]["resource"], "attesters/check.py")
        self.assertEqual(index.trust_tier_index["machine-confirmed"], ["machine"])
        self.assertTrue(index.documents["draft"].is_stale)

    def test_query_compose_and_trust_summary(self) -> None:
        self.assertEqual([record["id"] for record in api.query(self.root, trust_tier="machine-confirmed")], ["machine"])
        self.assertEqual([record["id"] for record in api.query(self.root, status="draft", stale="true")], ["draft"])

        summary = api.trust(self.root)
        self.assertEqual(summary["okf_version"], "0.2")
        self.assertEqual(api.catalog(self.root)[0]["okf_version"], "0.2")
        self.assertEqual(summary["trust_tiers"]["human-reviewed"], 1)
        detail = api.trust(self.root, "income-statement")
        self.assertEqual(detail["verified"][0]["by"], "human:analyst")

        composed = api.compose(self.root, "income-statement", depth=1, min_trust="machine-confirmed")
        self.assertEqual(composed["files"], ["income-statement.md", "machine.md"])


if __name__ == "__main__":
    unittest.main()
