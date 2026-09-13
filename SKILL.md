---
name: okf-runtime
description: "Discover, catalog, query, traverse, lint, and compose Open Knowledge Format (OKF) markdown bundles. Use when: retrieving OKF concepts, filtering YAML frontmatter, tracing links, checking trust metadata, validating bundles, or creating context-limited sub-bundles."
version: 0.1.0
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

Use the derived v0.2 filters when trust or lifecycle is relevant: `trust_tier=unverified|machine-confirmed|human-reviewed`, `status=draft|stable|deprecated`, and `stale=true|false`.

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

### 7. `compose`
Generate a temporary sub-bundle composed of relevant files centered on a topic or start concept, using radial graph pruning to respect token/context limits.
```powershell
python -B -m okf_runtime.cli --root tests/fixtures/samples compose posts_questions --output-dir .cache\composed-output --depth 2
```
- **Flag**: `--min-trust unverified|machine-confirmed|human-reviewed` excludes concepts below the requested derived trust tier.
- Copies matched markdown files into the output directory.
- Generates `boundary.json` at the root of the composed folder to identify dangling/external links mapping to their original source bundle locations.

### 8. `trust`
Summarize v0.2 trust tiers, lifecycle status, stale concepts, and detected `okf_version`; pass a concept ID for its complete trust surface.
```powershell
python -B -m okf_runtime.cli --root tests/fixtures/samples --format yaml trust
python -B -m okf_runtime.cli --root tests/fixtures/samples --format yaml trust bundles/acme_retail/metrics/revenue
```

### 9. `lint-links`
Check for broken internal links, anchor issues, parser errors, or unreachable orphan documents.
```powershell
python -B -m okf_runtime.cli --root tests/fixtures/samples lint-links
```

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
- **Comma-Separated Lists:** YAML tags must be formatted as lists (e.g., `- posts` or `[posts]`). Comma-separated strings (e.g., `tags: legacy, posts`) are parsed as a single string and will not match list queries like `tags=posts`.
- **Cache Folder:** The tool automatically creates a `.cache/` folder under the root. This directory contains `manifest.json`, `metadata.json`, `links.json`, and `reverse_links.json`. It is safe to delete and will rebuild silently on the next command.

## References

Load only the material needed for the task:

- `references/USAGE.md` - CLI/API syntax and examples; use for operation questions.
- `references/OKF-Version-0.2-min.md` - default implementation reference for OKF v0.2.
- `references/OKFmin.SPEC.md` - legacy OKF v0.1 rules.
- `references/OKF-DELTA-0.1-to-0.2.md` - migration and compatibility work.
- `references/OKF-v0.2-SPEC-for-consumer-agent-context.md` - expanded consumer-agent implementation context.
- `references/OKF-SPEC-Version-0.2.md` - full specification; load only for details absent from distilled references.
- `references/SKILLminSPEC.md` - Agent Skills packaging and conformance work only.
