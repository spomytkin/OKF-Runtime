from __future__ import annotations

import contextlib
import hashlib
import io
import json
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from okf_runtime import api, cache
from okf_runtime.cli import main


class FeatureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "bundle"
        fixture = Path(__file__).resolve().parent / "fixtures" / "feature-bundle"
        shutil.copytree(fixture, self.root)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_case_sensitive_lexical_links_and_outside_cache(self) -> None:
        issues = api.lint_links(self.root, cache_dir=Path(self.tmp.name) / "cache")
        self.assertTrue(any(i["type"] == "broken_link" and i["target"] == "Target.md" for i in issues))
        self.assertTrue((Path(self.tmp.name) / "cache" / "metadata.json").exists())

    def test_verify_sources_missing_and_hash(self) -> None:
        result = api.verify_sources(self.root)
        self.assertEqual((result["checked"], result["missing"], result["mismatched"]), (5, 1, 0))
        self.assertTrue(any(problem["resource"] == "missing.txt" for problem in result["problems"]))
        self.assertTrue(any(problem["type"] == "out_of_root" for problem in result["problems"]))
        self.assertFalse(any(problem["resource"].startswith("http") for problem in result["problems"]))
        source = self.root / "source.md"
        source.write_text(source.read_text(encoding="utf-8").replace("5891b5b5", "0891b5b5"), encoding="utf-8")
        result = api.verify_sources(self.root, cache_dir=Path(self.tmp.name) / "changed-cache")
        self.assertEqual(result["mismatched"], 1)

    def test_nested_mapping_filters_and_opt_in_resource_edges(self) -> None:
        matches = api.query(self.root, **{"relations[kind=depends_on].target": "target.md"})
        self.assertEqual([item["id"] for item in matches], ["source"])
        literal = api.query(self.root, **{"literal.key": "exact"})
        self.assertEqual([item["id"] for item in literal], ["source"])
        with self.assertRaises(ValueError):
            api.query(self.root, **{"relations[kind=depends_on].target[broken": "target.md"})
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            code = main(["--root", str(self.root), "query", "relations[kind=depends_on].target[broken=target.md"])
        self.assertEqual(code, 2)
        self.assertIn("Invalid metadata path", stderr.getvalue())

        resolved = api.graph(
            self.root, "source", resolve_resources=True,
            via=["relations[kind=depends_on].target"],
        )
        self.assertIn("target", resolved["nodes"])
        self.assertTrue(all(edge["via"] == "relations[kind=depends_on].target" for edge in resolved["edges"]))
        self.assertFalse(any(link.get("resource") for link in api.links(self.root, "source")))

        with contextlib.redirect_stdout(io.StringIO()) as stdout:
            parsed = main([
                "--root", str(self.root), "graph", "source", "--resolve-resources",
                "--via", "relations[kind=depends_on].target",
            ])
        self.assertEqual(parsed, 0)
        self.assertIn('"target"', stdout.getvalue())

    def test_compose_reverse_resource_edges_and_duplicate_warning(self) -> None:
        composed = api.compose(
            self.root, "target", output_dir=Path(self.tmp.name) / "composed", resolve_resources=True,
        )
        self.assertIn("source.md", composed["files"])
        self.assertTrue(any(
            warning["type"] == "duplicate_resource"
            and warning["concepts"] == ["duplicate-one", "duplicate-two"]
            for warning in api.graph(self.root, "duplicate-ref", resolve_resources=True).get("warnings", [])
        ))
        duplicate_graph = api.graph(self.root, "duplicate-ref", resolve_resources=True)
        self.assertNotIn("duplicate-one", duplicate_graph["nodes"])
        self.assertNotIn("duplicate-two", duplicate_graph["nodes"])

    def test_old_cache_schema_is_rebuilt(self) -> None:
        cache_dir = Path(self.tmp.name) / "versioned-cache"
        cache.load_or_rebuild(self.root, cache_dir)
        manifest_path = cache_dir / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["schema_version"] = cache.CACHE_SCHEMA_VERSION - 1
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        index = cache.load_or_rebuild(self.root, cache_dir)
        self.assertTrue(index.stale_rebuilt)
        self.assertEqual(json.loads(manifest_path.read_text(encoding="utf-8"))["schema_version"], cache.CACHE_SCHEMA_VERSION)

    def test_verify_sources_hashes_each_resolved_file_once(self) -> None:
        fixture = Path(__file__).resolve().parent / "fixtures" / "source-digest-cache"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "bundle"
            shutil.copytree(fixture, root)
            shared_bytes = b"shared source bytes\r\nsecond line\n"
            shared_path = root / "references" / "shared.txt"
            shared_path.parent.mkdir(parents=True)
            shared_path.write_bytes(shared_bytes)

            correct_hash = hashlib.sha256(shared_bytes).hexdigest()
            for concept_file in (root / "concepts" / "a.md", root / "concepts" / "b.md"):
                content = concept_file.read_text(encoding="utf-8")
                content = content.replace("HASH_PLACEHOLDER", correct_hash)
                content = content.replace("WRONG_HASH_PLACEHOLDER", "0" * 64)
                concept_file.write_text(content, encoding="utf-8")

            with patch("okf_runtime.api._sha256_file", wraps=api._sha256_file) as hash_file:
                result = api.verify_sources(root)

        self.assertEqual(result["checked"], 3)
        self.assertEqual(result["mismatched"], 1)
        self.assertEqual(result["missing"], 0)
        hash_file.assert_called_once()

    def test_verify_sources_cli(self) -> None:
        with contextlib.redirect_stdout(io.StringIO()):
            parsed = main(["--root", str(self.root), "verify-sources"])
        self.assertEqual(parsed, 0)


if __name__ == "__main__":
    unittest.main()
