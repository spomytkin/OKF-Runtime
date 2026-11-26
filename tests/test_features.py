from __future__ import annotations

import contextlib
import io
import shutil
import tempfile
import unittest
from pathlib import Path

from okf_runtime import api
from okf_runtime.cli import main


class FeatureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(dir=Path.cwd() / ".test-tmp")
        self.root = Path(self.tmp.name) / "bundle"
        shutil.copytree(Path("tests/fixtures/feature-bundle"), self.root)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_case_sensitive_lexical_links_and_outside_cache(self) -> None:
        issues = api.lint_links(self.root, cache_dir=Path(self.tmp.name) / "cache")
        self.assertTrue(any(i["type"] == "broken_link" and i["target"] == "Target.md" for i in issues))
        self.assertTrue((Path(self.tmp.name) / "cache" / "metadata.json").exists())

    def test_verify_sources_missing_and_hash(self) -> None:
        result = api.verify_sources(self.root)
        self.assertEqual((result["checked"], result["missing"], result["mismatched"]), (2, 1, 0))
        self.assertEqual(result["problems"][0]["resource"], "missing.txt")
        source = self.root / "source.md"
        source.write_text(source.read_text(encoding="utf-8").replace("5891b5b5", "0891b5b5"), encoding="utf-8")
        result = api.verify_sources(self.root, cache_dir=Path(self.tmp.name) / "changed-cache")
        self.assertEqual(result["mismatched"], 1)

    def test_nested_mapping_via_and_opt_in_resource_edges(self) -> None:
        matches = api.query(self.root, **{"relations[kind=depends_on].target": "target.md"})
        self.assertEqual([item["id"] for item in matches], ["source"])
        ordinary = api.graph(self.root, "source")
        resolved = api.graph(self.root, "source", resolve_resources=True)
        self.assertNotIn("target", ordinary["nodes"])
        self.assertIn("target", resolved["nodes"])
        with contextlib.redirect_stdout(io.StringIO()):
            parsed = main(["--root", str(self.root), "verify-sources"])
        self.assertEqual(parsed, 0)


if __name__ == "__main__":
    unittest.main()
