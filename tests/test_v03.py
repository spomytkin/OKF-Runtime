"""OKF v0.3 consumer checklist tests (spec items 1-9).

Each checklist item gets at least one named test_v03_<item> test, run
against tests/fixtures/v03-bundle (okf_version "0.3") and the legacy
twins v03-legacy-bundle ("0.2") and v03-unversioned-bundle (no version).
Clock-dependent tests patch okf_runtime.timestamps.now().
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from okf_runtime import api
from okf_runtime import cache as cache_module
from okf_runtime import parser
from okf_runtime import spec as spec_module
from okf_runtime import timestamps
from okf_runtime.cli import build_parser, run_command

FIXTURES = Path(__file__).resolve().parent / "fixtures"
V03 = FIXTURES / "v03-bundle"
LEGACY = FIXTURES / "v03-legacy-bundle"
UNVERSIONED = FIXTURES / "v03-unversioned-bundle"
FIXED_NOW = datetime(2026, 6, 1, tzinfo=timezone.utc)


class V03Tests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.cache_dir = Path(self._tmp.name) / "cache"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _catalog(self, root: Path = V03) -> list[dict]:
        return api.catalog(root, cache_dir=self.cache_dir)

    def _record(self, concept_id: str, root: Path = V03) -> dict:
        return next(item for item in self._catalog(root) if item["id"] == concept_id)

    def _trust(self, concept_id: str, root: Path = V03) -> dict:
        return api.trust(root, concept_id, cache_dir=self.cache_dir)

    def _run(self, *argv: str) -> object:
        return run_command(build_parser().parse_args(["--root", str(V03), "--cache-dir", str(self.cache_dir), *argv]))

    # -- item 1: version gating -------------------------------------

    def test_v03_version_gating(self) -> None:
        self.assertEqual(spec_module.parse_okf_version("0.3"), (0, 3, 0))
        self.assertEqual(spec_module.parse_okf_version("0.2"), (0, 2, 0))
        self.assertEqual(spec_module.parse_okf_version("0.2.0"), (0, 2, 0))
        self.assertEqual(spec_module.parse_okf_version("1.0"), (1, 0, 0))
        self.assertIsNone(spec_module.parse_okf_version(None))
        self.assertIsNone(spec_module.parse_okf_version("garbage"))
        self.assertTrue(spec_module.is_legacy(None))
        self.assertTrue(spec_module.is_legacy("0.2"))
        self.assertTrue(spec_module.is_legacy("0.1"))
        self.assertFalse(spec_module.is_legacy("0.3"))
        self.assertFalse(spec_module.is_legacy("garbage"))
        self.assertEqual(api.bundle_info(V03, cache_dir=self.cache_dir)["okf_version"], "0.3")
        self.assertEqual(api.bundle_info(LEGACY, cache_dir=self.cache_dir)["okf_version"], "0.2")
        self.assertIsNone(api.bundle_info(UNVERSIONED, cache_dir=self.cache_dir)["okf_version"])

    def test_v03_bare_path_no_root_fallback(self) -> None:
        """On v0.3 a bare path resolves from the containing file only (§6.2)."""
        result = api.verify_sources(V03, cache_dir=self.cache_dir)
        self.assertIn(
            {"id": "concepts/paths", "resource": "shared.md", "type": "missing"},
            result["problems"],
        )
        # The /-rooted /shared.md is the only edge to the root concept.
        edges = api.graph(V03, "concepts/paths", depth=1, cache_dir=self.cache_dir)["edges"]
        shared_edges = [edge for edge in edges if edge["target"] == "shared"]
        self.assertEqual(len(shared_edges), 1)
        self.assertEqual(shared_edges[0]["via"], "sources[].resource")

    def test_v03_legacy_bare_path_root_fallback(self) -> None:
        """On okf_version 0.2 a bare path retries from the bundle root (§12.1)."""
        result = api.verify_sources(LEGACY, cache_dir=self.cache_dir)
        self.assertEqual(result["missing"], 0)
        self.assertEqual(result["problems"], [])
        edges = api.graph(
            LEGACY, "concepts/paths", depth=1, path_edges=True, cache_dir=self.cache_dir
        )["edges"]
        self.assertIn("shared", {edge["target"] for edge in edges})
        # Legacy keeps the v0.2 type error AND keeps the document a concept.
        readme = self._record("README", root=LEGACY)
        self.assertIn("Missing required non-empty frontmatter field: type", readme["errors"])

    def test_v03_unversioned_bare_path_root_fallback(self) -> None:
        """With no okf_version the bare path also resolves via the root."""
        result = api.verify_sources(UNVERSIONED, cache_dir=self.cache_dir)
        self.assertEqual(result["missing"], 0)
        self.assertEqual(result["problems"], [])

    def test_v03_timestamp_fallback_legacy_only(self) -> None:
        """The v0.1 timestamp -> generated fallback applies on legacy only (1b)."""
        self.assertIsNone(self._trust("concepts/ts-timestamp")["generated"])
        legacy_generated = api.trust(LEGACY, "concepts/legacy-ts", cache_dir=self.cache_dir)["generated"]
        self.assertEqual(legacy_generated, {"by": "process:legacy", "at": "2026-01-01T10:00:00Z"})

    def test_v03_non_concept(self) -> None:
        """A .md without frontmatter or type is a non-concept on v0.3 (§3.2, 1c)."""
        ids = {record["id"] for record in self._catalog()}
        self.assertNotIn("README", ids)
        self.assertNotIn("LICENSE", ids)
        self.assertNotIn("log", ids)
        self.assertNotIn("sub/index", ids)
        self.assertNotIn(".hidden/secret", ids)
        self.assertEqual(api.trust(V03, cache_dir=self.cache_dir)["concept_count"], len(ids))
        with self.assertRaises(KeyError):
            api.graph(V03, "README", cache_dir=self.cache_dir)
        lint = api.lint_links(V03, cache_dir=self.cache_dir)
        self.assertIn({"level": "warning", "type": "non_concept", "id": "README"}, lint)
        self.assertIn({"level": "warning", "type": "non_concept", "id": "LICENSE"}, lint)

    def test_v03_path_edges_default(self) -> None:
        """Path-field edges default ON for v0.3, OFF for legacy (1d)."""
        edges = api.graph(V03, "concepts/paths", depth=1, cache_dir=self.cache_dir)["edges"]
        self.assertTrue(any(edge["via"] == "resource" for edge in edges))
        off = api.graph(V03, "concepts/paths", depth=1, path_edges=False, cache_dir=self.cache_dir)
        self.assertEqual(off["edges"], [])
        legacy_default = api.graph(LEGACY, "concepts/paths", depth=1, cache_dir=self.cache_dir)
        self.assertEqual(legacy_default["nodes"], ["concepts/paths"])
        # CLI flags: --path-edges / --no-path-edges.
        flagged = self._run("graph", "concepts/paths", "--path-edges")
        self.assertTrue(any(edge["via"] == "resource" for edge in flagged["edges"]))
        unflagged = self._run("graph", "concepts/paths", "--no-path-edges")
        self.assertEqual(unflagged["edges"], [])

    # -- item 2: parsing and normalisation ---------------------------

    def test_v03_frontmatter(self) -> None:
        """Exact --- boundaries, duplicate keys, custom tags, non-mapping (§4)."""
        metadata, errors = parser.parse_frontmatter("type: Concept\ntitle: First\ntitle: Second\n")
        self.assertEqual(metadata["title"], "Second")
        self.assertIn("duplicate_key: title", errors)
        _, _, errors = parser.split_frontmatter(" ---\ntype: Concept\n---\nbody\n")
        self.assertIn("Missing YAML frontmatter block", errors)
        _, _, errors = parser.split_frontmatter("---\ntype: Concept\n--- \nbody\n")
        self.assertIn("Unclosed YAML frontmatter block", errors)
        _, errors = parser.parse_frontmatter("- a\n- b\n")
        self.assertIn("Frontmatter must be a mapping", errors)
        record = self._record("concepts/frontmatter-edges")
        self.assertEqual(record["metadata"]["custom"], "!weird value")
        self.assertIn("custom YAML tag preserved as raw text", record["warnings"])

    def test_v03_normalization(self) -> None:
        """Null/empty absent; single items as lists; scalar tags; missing keys (§11.2)."""
        tags = self._record("concepts/tags-scalar")
        self.assertEqual(tags["metadata"]["tags"], "a, b")
        tagged = {item["id"] for item in api.query(V03, cache_dir=self.cache_dir, tags="a, b")}
        self.assertIn("concepts/tags-scalar", tagged)
        untagged = {item["id"] for item in api.query(V03, cache_dir=self.cache_dir, tags="a")}
        self.assertNotIn("concepts/tags-scalar", untagged)
        # Unknown keys are kept at every nesting level (§4.1).
        xkeys = self._record("concepts/xkeys")["metadata"]
        self.assertEqual(xkeys["x-acme-owner"], "acme")
        self.assertEqual(xkeys["x-acme-review"], {"level": "deep"})
        self.assertEqual(xkeys["generated"]["x-acme-note"], "generated note")
        self.assertEqual(xkeys["verified"][0]["x-acme-note"], "verified note")
        self.assertEqual(xkeys["sources"][0]["x-acme-note"], "source note")
        self.assertEqual(xkeys["executor"]["x-acme-note"], "executor note")
        self.assertEqual(xkeys["attester"]["x-acme-note"], "attester note")
        single = self._trust("concepts/single-mapping")
        self.assertEqual(len(single["sources"]), 1)
        self.assertEqual(single["sources"][0]["resource"], "target.md")
        self.assertEqual(len(single["verified"]), 1)
        missing = self._record("concepts/missing-keys")
        for message in (
            "generated entry missing by",
            "verified entry missing by",
            "verified entry missing at",
            "sources entry missing resource",
        ):
            self.assertIn(message, missing["warnings"])
        self.assertIsNone(self._trust("concepts/missing-keys")["generated"])
        # The by-only event stays in the raw verified list, but it cannot
        # be current without an at, so it never counts toward the tier.
        self.assertEqual(
            self._trust("concepts/missing-keys")["verified"],
            [{"by": "human:alice", "at": None}],
        )
        self.assertEqual(self._trust("concepts/missing-keys")["verified_current"], [])
        self.assertEqual(len(self._trust("concepts/missing-keys")["sources"]), 1)
        stale_empty = self._trust("concepts/stale-empty")
        self.assertIsNone(stale_empty["stale_after"])
        self.assertFalse(stale_empty["is_stale"])

    def test_v03_timestamps(self) -> None:
        """RFC 3339 with offset, full-date, quoted/unquoted; offset-less malformed (§5)."""
        self.assertEqual(
            timestamps.parse_instant("2026-01-01T10:00:00Z"),
            datetime(2026, 1, 1, 10, tzinfo=timezone.utc),
        )
        self.assertEqual(
            timestamps.parse_instant("2026-01-01T10:00:00+02:00"),
            datetime(2026, 1, 1, 8, tzinfo=timezone.utc),
        )
        self.assertEqual(
            timestamps.parse_instant("2026-01-01"),
            datetime(2026, 1, 1, 0, tzinfo=timezone.utc),
        )
        self.assertEqual(
            timestamps.parse_instant("'2026-01-01T10:00:00Z'"),
            datetime(2026, 1, 1, 10, tzinfo=timezone.utc),
        )
        with self.assertRaises(ValueError):
            timestamps.parse_instant("2026-01-01T10:00:00")
        self.assertEqual(self._trust("concepts/ts-z")["trust_tier"], "human-reviewed")
        self.assertEqual(self._trust("concepts/ts-offset")["trust_tier"], "human-reviewed")
        self.assertEqual(self._trust("concepts/ts-date")["trust_tier"], "human-reviewed")
        self.assertEqual(self._trust("concepts/ts-unquoted")["trust_tier"], "human-reviewed")
        offset_less = self._trust("concepts/ts-offset-less")
        self.assertIn("malformed generated.at", self._record("concepts/ts-offset-less")["warnings"])
        self.assertEqual(offset_less["trust_tier"], "human-reviewed")

    def test_v03_actors(self) -> None:
        """Only human: counts as human (§7)."""
        for concept_id in (
            "concepts/actor-team",
            "concepts/actor-process",
            "concepts/actor-producer",
            "concepts/actor-unknown",
        ):
            self.assertEqual(self._trust(concept_id)["trust_tier"], "machine-confirmed", concept_id)
        self.assertEqual(self._trust("concepts/trust-after")["trust_tier"], "human-reviewed")

    # -- item 3: trust and lifecycle ---------------------------------

    def test_v03_trust_current_events(self) -> None:
        """Tier only from current events; history kept (§5.3)."""
        before = self._trust("concepts/trust-before")
        self.assertEqual(before["verified_current"], [])
        self.assertEqual(len(before["verified_history"]), 1)
        self.assertEqual(before["trust_tier"], "unverified")
        after = self._trust("concepts/trust-after")
        self.assertEqual(len(after["verified_current"]), 1)
        self.assertEqual(after["verified_history"], [])
        self.assertEqual(after["trust_tier"], "human-reviewed")
        self.assertEqual(len(self._trust("concepts/trust-no-generated")["verified_current"]), 1)
        # Documented choice: generated without at => all events are current.
        self.assertEqual(len(self._trust("concepts/trust-generated-no-at")["verified_current"]), 1)

    def test_v03_staleness(self) -> None:
        """is_stale compares instants; unparseable is never fresh (§5.5)."""
        with patch.object(timestamps, "now", return_value=FIXED_NOW):
            self.assertTrue(self._trust("concepts/stale-expired")["is_stale"])
            self.assertFalse(self._trust("concepts/stale-fresh")["is_stale"])
            malformed = self._trust("concepts/stale-malformed")
            self.assertTrue(malformed["is_stale"])
            self.assertTrue(malformed["stale_after_malformed"])
            self.assertIn("malformed stale_after", self._record("concepts/stale-malformed")["warnings"])
            self.assertFalse(self._trust("concepts/stale-empty")["is_stale"])

    def test_v03_status_and_superseded(self) -> None:
        """Unknown status is not current; deprecated follows superseded_by (§5.4)."""
        unknown = self._trust("concepts/status-unknown")
        self.assertEqual(unknown["status"], "archived")
        self.assertFalse(self._record("concepts/status-unknown")["is_current"])
        summary = api.trust(V03, cache_dir=self.cache_dir)
        self.assertEqual(summary["status"].get("archived"), 1)
        deprecated = self._trust("concepts/deprecated")
        self.assertEqual(deprecated["superseded_by_id"], "concepts/replacement")
        composed = api.compose(
            V03, "deprecated",
            output_dir=Path(self._tmp.name) / "composed",
            cache_dir=self.cache_dir,
        )
        self.assertIn("concepts/deprecated.md", composed["files"])
        self.assertIn("concepts/replacement.md", composed["files"])

    def test_v03_superseded_chain_cycles(self) -> None:
        """Superseded_by chains are cycle-safe and capped at 10 hops."""
        root = Path(self._tmp.name) / "cycle-bundle"
        (root / "concepts").mkdir(parents=True)
        (root / "index.md").write_text('---\nokf_version: "0.3"\n---\n', encoding="utf-8")
        for name, target in (("a", "b"), ("b", "a")):
            (root / "concepts" / f"{name}.md").write_text(
                f"---\ntype: Concept\ntitle: {name}\nstatus: deprecated\nsuperseded_by: /concepts/{target}.md\n---\n",
                encoding="utf-8",
            )
        composed = api.compose(
            root, "a",
            output_dir=Path(self._tmp.name) / "cycle-composed",
            cache_dir=self.cache_dir,
        )
        self.assertEqual(set(composed["files"]), {"concepts/a.md", "concepts/b.md"})

    # -- item 4: paths, links, graph ---------------------------------

    def test_v03_paths(self) -> None:
        """Relative, /-rooted, %20, case-mismatch, out-of-root, scope descriptor (§6)."""
        result = api.verify_sources(V03, cache_dir=self.cache_dir)
        self.assertEqual(result["checked"], 9)
        self.assertEqual(result["missing"], 2)
        self.assertIn(
            {"id": "concepts/paths", "resource": "TARGET.md", "type": "missing"},
            result["problems"],
        )
        self.assertIn(
            {"id": "concepts/paths", "resource": "../../outside.md", "type": "out_of_root"},
            result["problems"],
        )
        # A scope descriptor is not flagged missing on v0.3.
        self.assertNotIn("concepts/scope", {problem["id"] for problem in result["problems"]})
        edges = api.graph(V03, "concepts/paths", depth=1, cache_dir=self.cache_dir)["edges"]
        by_via: dict[str, set[str]] = {}
        for edge in edges:
            by_via.setdefault(edge["via"], set()).add(edge["target"])
        self.assertEqual(by_via["resource"], {"concepts/target"})
        self.assertEqual(by_via["sources[].resource"], {"shared", "concepts/my file"})
        self.assertEqual(by_via["executor.resource"], {"concepts/target"})

    def test_v03_links(self) -> None:
        """Reference-style links; wikilinks ignored; asset links valid (§6.1)."""
        links = api.links(V03, "concepts/links", cache_dir=self.cache_dir)
        targets = [(link["text"], link.get("resolved_id")) for link in links]
        self.assertEqual(targets.count(("Target", "concepts/target")), 3)
        self.assertIn(("logo", None), targets)
        self.assertFalse(any(link["text"].startswith("[") for link in links))
        backlinks = api.backlinks(V03, "concepts/target", cache_dir=self.cache_dir)
        self.assertIn("concepts/links", {item["source_id"] for item in backlinks})
        lint = api.lint_links(V03, cache_dir=self.cache_dir)
        self.assertFalse(
            [issue for issue in lint if issue["type"] == "broken_link" and issue["id"] == "concepts/links"]
        )

    # -- item 5: discovery and files ---------------------------------

    def test_v03_discovery(self) -> None:
        """Dot-paths ignored; index/log never concepts; assets never concepts (§3)."""
        ids = {record["id"] for record in self._catalog()}
        self.assertNotIn(".hidden/secret", ids)
        self.assertNotIn("data/table.csv", ids)
        self.assertNotIn("asset.png", ids)
        bundles = api.discover(V03)
        self.assertFalse(any(str(bundle["root"]).endswith(".hidden") for bundle in bundles))

    def test_v03_bundle_info(self) -> None:
        """Root index.md metadata via bundle-info (§8.1)."""
        info = api.bundle_info(V03, cache_dir=self.cache_dir)
        self.assertEqual(info["okf_version"], "0.3")
        self.assertEqual(info["title"], "OKF v0.3 consumer test bundle")
        self.assertEqual(info["description"], "Minimal cases for the v0.3 migration checklist.")
        self.assertEqual(info["license"], "LICENSE.md")
        self.assertEqual(info["license_path"], "LICENSE.md")
        self.assertEqual(info["x-acme-owner"], "acme")
        legacy_info = api.bundle_info(LEGACY, cache_dir=self.cache_dir)
        self.assertEqual(legacy_info["license"], "CC-BY-4.0")
        self.assertNotIn("license_path", legacy_info)
        cli_info = self._run("bundle-info")
        self.assertEqual(cli_info["okf_version"], "0.3")

    def test_v03_conformance(self) -> None:
        """v0.3: the two §11.1 rules only; legacy adds the type-required error."""
        result = api.conformance(V03, cache_dir=self.cache_dir)
        self.assertTrue(result["conformant"])
        self.assertEqual(result["errors"], [])
        warnings = {(item["id"], item["message"]) for item in result["warnings"]}
        self.assertIn(("log", "reserved file has frontmatter"), warnings)
        self.assertIn(("sub/index", "reserved file has frontmatter"), warnings)
        legacy_result = api.conformance(LEGACY, cache_dir=self.cache_dir)
        self.assertFalse(legacy_result["conformant"])
        self.assertIn(
            {"id": "README", "message": "Missing required non-empty frontmatter field: type"},
            legacy_result["errors"],
        )
        # A frontmatter block that does not parse as a mapping breaks conformance.
        root = Path(self._tmp.name) / "bad-bundle"
        root.mkdir(parents=True)
        (root / "index.md").write_text('---\nokf_version: "0.3"\n---\n', encoding="utf-8")
        (root / "bad.md").write_text("---\ntype: Concept\ntitle: x\n", encoding="utf-8")
        bad = api.conformance(root, cache_dir=self.cache_dir)
        self.assertFalse(bad["conformant"])
        self.assertIn(
            {"id": "bad", "message": "Unclosed YAML frontmatter block"}, bad["errors"]
        )

    # -- item 6: Attested Computation --------------------------------

    def test_v03_computations(self) -> None:
        """Locator, parameters, attestable and display rules (§10)."""
        results = {item["id"]: item for item in api.computations(V03, cache_dir=self.cache_dir)}
        self.assertEqual(
            results["concepts/computations/comp-file"]["computation_source"],
            {"kind": "file", "path": "concepts/computations/calc.py"},
        )
        self.assertTrue(results["concepts/computations/comp-file"]["attestable"])
        self.assertEqual(results["concepts/computations/comp-file"]["attestation_display"], "not attested")
        self.assertEqual(
            results["concepts/computations/comp-file"]["parameters"],
            [{"name": "year", "type": "integer", "required": True}],
        )
        inline = results["concepts/computations/comp-inline"]
        self.assertEqual(inline["computation_source"]["kind"], "inline")
        self.assertEqual(inline["computation_source"]["language"], "python")
        self.assertEqual(inline["computation_source"]["code"], 'print("inline value")\n')
        self.assertTrue(inline["attestable"])
        # A single-mapping parameters value is one parameter, required False.
        self.assertEqual(inline["parameters"], [{"name": "year", "type": "integer", "required": False}])
        indented = results["concepts/computations/comp-indented"]
        self.assertEqual(indented["computation_source"], {"kind": "missing"})
        self.assertFalse(indented["attestable"])
        self.assertEqual(indented["attestation_display"], "not attestable")
        no_attester = results["concepts/computations/comp-no-attester"]
        self.assertTrue(no_attester["attestable"])
        self.assertEqual(no_attester["attestation_display"], "not attestable")
        no_runtime = results["concepts/computations/comp-no-runtime"]
        self.assertFalse(no_runtime["attestable"])
        self.assertEqual(no_runtime["attestation_display"], "not attestable")
        bad_params = results["concepts/computations/comp-bad-params"]
        self.assertEqual(bad_params["parameters"], [{"name": "ok", "type": "string", "required": False}])
        self.assertEqual(bad_params["warnings"].count("invalid parameter"), 2)
        self.assertNotIn("attested", {item["attestation_display"] for item in results.values()})
        cli_results = self._run("computations")
        self.assertEqual({item["id"] for item in cli_results}, set(results))

    # -- item 7: cache -------------------------------------------------

    def test_v03_cache(self) -> None:
        """Schema 3; is_concept/warnings cached; rebuild on version change."""
        self.assertEqual(cache_module.CACHE_SCHEMA_VERSION, 3)
        first = self._catalog()
        second = api.catalog(V03, cache_dir=self.cache_dir)
        self.assertEqual(first, second)
        manifest = json.loads((self.cache_dir / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["schema_version"], 3)
        self.assertEqual(manifest["okf_version"], "0.3")
        payload = json.loads((self.cache_dir / "metadata.json").read_text(encoding="utf-8"))
        by_id = {item["concept_id"]: item for item in payload["documents"]}
        self.assertFalse(by_id["README"]["is_concept"])
        self.assertIn("custom YAML tag preserved as raw text", by_id["concepts/frontmatter-edges"]["warnings"])
        # Changing okf_version rebuilds even when mtimes are unchanged.
        root = Path(self._tmp.name) / "versioned"
        shutil.copytree(V03, root)
        cache_dir = Path(self._tmp.name) / "versioned-cache"
        self.assertEqual(api.bundle_info(root, cache_dir=cache_dir)["okf_version"], "0.3")
        index = root / "index.md"
        stat = index.stat()
        text = index.read_text(encoding="utf-8").replace('"0.3"', '"0.2"')
        index.write_text(text, encoding="utf-8")
        os.utime(index, (stat.st_atime, stat.st_mtime))
        self.assertEqual(api.bundle_info(root, cache_dir=cache_dir)["okf_version"], "0.2")
        manifest = json.loads((cache_dir / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["okf_version"], "0.2")

    # -- item 9: version -----------------------------------------------

    def test_v03_version_bump(self) -> None:
        """Release version is 0.3.0 in packaging and skill frontmatter."""
        pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn('version = "0.3.0"', pyproject)
        skill = (REPO_ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("version: 0.3.0", skill.split("---", 2)[1])


if __name__ == "__main__":
    unittest.main()
