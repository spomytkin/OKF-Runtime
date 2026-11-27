---
name: okf-runtime
description: "Discover, catalog, query, traverse, lint, and compose Open Knowledge Format (OKF) markdown bundles. Use when: retrieving OKF concepts, filtering YAML frontmatter, tracing links, checking trust metadata, validating bundles, or creating context-limited sub-bundles."
version: 0.3.0
authors:
  - spomytkin, OKF-Runtime contributors
tags:
  - okf
  - knowledge-catalog
  - metadata-extraction
  - link-linting
  - agent-context
license: MIT
compatibility: Requires Python 3.10+
---

# OKF Runtime Repository Agent Guide

This skill provides a deterministic runtime and retrieval toolkit for Open Knowledge Format (OKF) repositories. It enables AI agents to query, traverse, and compose OKF document bundles without reading entire markdown files, preserving LLM context and reducing token usage.

This directory is a conformant Agent Skill package: its `okf-runtime` directory matches the frontmatter `name`. The Python implementation lives in `okf_runtime/`, agent-facing material in `references/`, and maintainer documentation in `docs/`.

## Available Command Interface

The OKF Runtime is written in Python and can be executed via the command line from the repository root:

```powershell
python -B -m okf_runtime.cli --root <bundle-or-scan-root> <command> [options]
```

*Note: Always use `-B` to avoid writing Python bytecode (`.pyc` files) to disk in restricted/containerized agent environments.*

The module invocation is the primary no-install path. After installing the package from the skill root (`python -m pip install -e .`), `python scripts/okf.py ...` is an equivalent convenience wrapper.

### Global Flags
- `--root <path>`: Directory containing OKF bundles. Defaults to `.`.
- `--format <json|yaml>`: Standardize output for programmatic parsing or token-efficient agent reading. Defaults to `json`.
- `--cache-dir <path>`: Store the disposable runtime cache outside the bundle. Defaults to `<root>/.cache`.

---

## Command Reference

### 1. `discover`
Discover all OKF bundles containing markdown files under the root.
```powershell
python -B -m okf_runtime.cli --root tests/fixtures/samples discover
```
- **Output**: List of bundle paths and their markdown file count.

### 2. `catalog`
Extract and return parsed frontmatter records for all non-reserved documents.
```powershell
python -B -m okf_runtime.cli --root tests/fixtures/samples --format yaml catalog
```
- **Flags**:
  - `--short`: Minimize tokens by listing only `id`, `path`, `type`, and `title`.
  - `--verbose`: Includes forward links and backlinks in each record.

### 3. `query`
Filter concepts without loading markdown bodies. Matches are exact `key=value`. For lists (e.g., `tags`), matches succeed if the value is contained within the list.
```powershell
python -B -m okf_runtime.cli --root tests/fixtures/samples --format yaml query type="BigQuery Table" tags=posts
```

Use the derived trust/lifecycle filters when trust or lifecycle is relevant: `trust_tier=unverified|machine-confirmed|human-reviewed`, `status=draft|stable|deprecated`, and `stale=true|false`. Trust tiers are computed only from current verification events (`verified[].at >= generated.at`); older events are kept as history. Catalog records also carry `is_current` (`status == "stable"`) and `warnings`.

### 4. `show`
Retrieve metadata catalog record for a specific concept by its ID.
```powershell
python -B -m okf_runtime.cli --root tests/fixtures/samples show bundles/stackoverflow/tables/posts_questions
```
- **Flags**:
  - `--body`: Includes the full markdown content of the file.

### 5. `links` and `backlinks`
Trace references in the knowledge graph.
```powershell
python -B -m okf_runtime.cli --root tests/fixtures/samples links bundles/stackoverflow/tables/posts_questions
python -B -m okf_runtime.cli --root tests/fixtures/samples backlinks bundles/stackoverflow/tables/posts_questions
```

### 6. `graph`
Build a deterministic neighborhood around a concept node.
```powershell
python -B -m okf_runtime.cli --root tests/fixtures/samples graph bundles/stackoverflow/tables/posts_questions --depth 2
```
- Add `--resolve-resources` to opt in to edges when a frontmatter string exactly matches another concept's `resource` value.
- Add `--path-edges` / `--no-path-edges` to include or exclude path-field edges (`resource`, `sources[].resource`, `computation`, `executor.resource`, `attester.resource`, `superseded_by` resolving to in-bundle concepts). Path edges default ON for v0.3 bundles and OFF for v0.2/unversioned bundles.

### 7. `compose`
Generate a temporary sub-bundle composed of relevant files centered on a topic or start concept, using radial graph pruning to respect token/context limits.
```powershell
python -B -m okf_runtime.cli --root tests/fixtures/samples compose posts_questions --output-dir .cache\composed-output --depth 2
```
- Add `--resolve-resources` to use exact resource-value matches as graph edges during composition.
- Add `--path-edges` / `--no-path-edges` (same defaults as `graph`). When composing, deprecated concepts follow their `superseded_by` chain (cycle-safe, max 10 hops) so the replacement is included.
- **Flag**: `--min-trust unverified|machine-confirmed|human-reviewed` excludes concepts below the requested derived trust tier.
- Copies matched markdown files into the output directory.
- Generates `boundary.json` at the root of the composed folder to identify dangling/external links mapping to their original source bundle locations.

### 8. `trust`
Summarize trust tiers, lifecycle status, stale concepts, and detected `okf_version`; pass a concept ID for its complete trust surface.
```powershell
python -B -m okf_runtime.cli --root tests/fixtures/samples --format yaml trust
python -B -m okf_runtime.cli --root tests/fixtures/samples --format yaml trust bundles/acme_retail/metrics/revenue
```

The per-concept trust surface includes `verified_current` and `verified_history` (events split by whether `verified[].at >= generated.at`), `stale_after_malformed` (an unparseable `stale_after` is never fresh), and `superseded_by_id` (the resolved concept id of the `superseded_by` path field, or `null`). An event missing `by` or `at` is ignored, with a warning. A `generated` entry without `at` means all events are current (documented choice).

### 9. `lint-links`
Check for broken internal links, anchor issues, parser errors, or unreachable orphan documents.
```powershell
python -B -m okf_runtime.cli --root tests/fixtures/samples lint-links
```

Internal paths are normalized lexically and compared case-sensitively, without checking the filesystem during resolution. On v0.3 bundles, lint also warns on `.md` files without frontmatter/`type` (`non_concept`), on subdirectory `index.md` / `log.md` files carrying frontmatter (`reserved_frontmatter`), and on document warnings such as malformed timestamps (`parse_warning`). Links to assets, directories, or non-concepts are valid and not broken; reference-style links (`[text][label]`, collapsed and shortcut forms) are links, `[[wikilinks]]` are not.

### 10. `verify-sources`
Check each in-bundle `sources[].resource` path and compare `x-sha256` when present. Output includes checked, missing, and mismatched counts plus problem details.
```powershell
python -B -m okf_runtime.cli --root tests/fixtures/feature-bundle verify-sources
```

On v0.3 bundles, a `sources[].resource` that resolves to no file may be a scope descriptor and is not flagged missing unless it starts with `/`, `./`, or `../` or ends in a file extension. On v0.2/unversioned bundles the previous counts are kept, including the bundle-root retry for bare paths.

### 11. `bundle-info`
Report the bundle-root `index.md` metadata: `okf_version`, `title`, `description`, `license`, and any other root keys. When `license` is a path (rather than an SPDX expression), `license_path` gives the bundle-relative path.
```powershell
python -B -m okf_runtime.cli --root tests/fixtures/samples bundle-info
```

### 12. `conformance`
Check the bundle against the §11.1 conformance rules and report `{conformant, errors, warnings}`. On v0.3 only the two §11.1 rules apply (frontmatter blocks parse as mappings; reserved files follow §8/§9); on v0.2/unversioned bundles the v0.2 "type required" error is added. A `.md` file with no frontmatter or no `type` does not break conformance.
```powershell
python -B -m okf_runtime.cli --root tests/fixtures/samples conformance
```

### 13. `computations`
List Attested Computation concepts with their `runtime`, validated `parameters` (`name`/`type` required, `required` defaults to `false`), `computation_source` (`file` / `inline` / `missing` per the §10.3 locator), `attestable`, and `attestation_display` (`not attestable` or `not attested` — never `attested`; no runs happen here).
```powershell
python -B -m okf_runtime.cli --root tests/fixtures/samples computations
```

### Nested metadata filters
Filter a list of mappings by a sibling key directly in the filter path, such as:
```powershell
python -B -m okf_runtime.cli --root tests/fixtures/feature-bundle query "relations[kind=depends_on].target=target.md"
```

`graph --via` is repeatable and filters traversal edges by source key path. Body links use `via=body`; frontmatter resource edges use the path of the exact string that matched, such as `relations[kind=depends_on].target`.

With `--resolve-resources`, graph and compose compare exact strings across all frontmatter values, including `sources[].resource`, with other concepts' `resource` values. Duplicate resource values are reported as warnings and produce no edges.

---

## Actionable Workflows for Agents

### Workflow A: Preserving Context via Compose
When a user asks a complex question about a topic (e.g., "how is StackOverflow posts schema structured"):
1. Query relevant concept IDs: `query tags=posts`.
2. Generate a sub-bundle: `compose posts_questions --output-dir .cache\posts-info`.
3. Check the `boundary.json` file in the generated folder to see what external files/links were skipped.
4. Read the copied files and referenced boundary documents only as needed to answer.

### Workflow B: Validating Bundle Quality
Before completing work on OKF markdown files:
1. Run `lint-links` on the repository root.
2. Review the list of failures under `errors` or broken links. Correct these by updating paths in markdown files.
3. Re-run `lint-links` to ensure errors are cleared.

---

## Gotchas & Limitations

- **Frontmatter subset:** The dependency-free parser supports scalars, inline collections, indented mappings, list-of-dicts, and folded scalar continuations. It is not a complete YAML 1.2 implementation.
- **Comma-Separated Lists:** A scalar `tags` value is ONE tag, never split on commas (e.g., `tags: legacy, posts` is the single tag `legacy, posts`) and will not match list queries like `tags=posts`. Use a YAML list for multiple tags.
- **Cache Folder:** The tool automatically creates `.cache/` under the root, unless `--cache-dir` selects another directory. The cache contains `manifest.json`, `metadata.json`, `links.json`, and `reverse_links.json`; it is safe to delete.

## References

Load only the material needed for the task:

- `references/USAGE.md` - CLI/API syntax and examples; use for operation questions.
- `references/OKF-Version-0.3-min.md` - default implementation reference for OKF v0.3.
- `references/OKF-DELTA-0.2-to-0.3.md` - migration checklist and compatibility work.
- `references/OKF-Version-0.2-min.md` - legacy OKF v0.2 rules.
- `references/OKF-DELTA-0.1-to-0.2.md` - legacy migration and compatibility work.
- `references/OKF-v0.2-SPEC-for-consumer-agent-context.md` - expanded consumer-agent implementation context.
- `references/OKF-SPEC-Version-0.2.md` - full v0.2 specification; load only for details absent from distilled references.
- `references/SKILLminSPEC.md` - Agent Skills packaging and conformance work only.
