# OKF Runtime

OKF Runtime is a lightweight, deterministic consumption engine for Open Knowledge Format (OKF) bundles. It is designed to help agents and tools discover, index, and traverse OKF repositories without requiring a database, daemon, or heavy external dependencies.

![OKF Runtime](docs/OKF-Runtime.png)

## Quickstart
Requires Python 3.10+ and nothing else — zero dependencies.
```bash
git clone https://github.com/spomytkin/OKF-Runtime.git
cd OKF-Runtime
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .
```
Verify it works:
```bash
python -m unittest discover -s tests
okf --help
```
Try it on the included sample bundle — no database, daemon, or cloud service:
```bash
okf --root tests/fixtures/samples discover
okf --root tests/fixtures/samples --format yaml query type="BigQuery Table" tags=posts
okf --root tests/fixtures/samples show bundles/stackoverflow/tables/posts_questions
okf --root tests/fixtures/samples --format yaml trust
```
Or use it as a library — the CLI is a thin wrapper around the same API:
```python
from okf_runtime import query, show
records = query("tests/fixtures/samples", type="BigQuery Table", tags="posts")
one = show("tests/fixtures/samples", "bundles/stackoverflow/tables/posts_questions")
```
See `references/USAGE.md` for every command (`catalog`, `links`, `backlinks`, `graph`, `compose`, `lint-links`, `bundle-info`, `conformance`, `computations`) and the full Python API.

OKF v0.3 is supported; v0.2 and unversioned bundles keep working through the §12.1 fallbacks (bare path fields retry from the bundle root, the v0.1 `timestamp` → `generated` fallback, and the v0.2 "type required" error).

## What it is

- A filesystem-first runtime for OKF markdown bundles
- A deterministic metadata and link graph builder
- A cache-friendly engine for bundle discovery, link analysis, and composition
- A thin, JSON-friendly runtime API for downstream tools and agent integrations
- Provenance, lifecycle, and derived trust signals for OKF v0.3 bundles (v0.2 and unversioned bundles via fallbacks)

## Why this exists

Most existing OKF tooling focuses on authoring, validation, or enrichment. OKF Runtime focuses on efficient consumption:

- discover bundles and markdown concepts
- parse YAML frontmatter and markdown bodies
- index metadata, tags, and types
- build forward and reverse link graphs
- compose temporary topic bundles without mutating source files
- validate links, anchors, and graph structure
- derive trust tiers and staleness from frontmatter (OKF v0.3 rules; v0.2 bundles keep their behaviour through gated fallbacks)

## Core design principles

- Deterministic before AI: solve retrieval tasks without consuming LLM context
- Library first: runtime logic belongs in reusable modules, not only CLI wrappers
- Filesystem is source of truth: markdown files remain authoritative
- Zero infrastructure: no database server, no background daemon, no cloud service
- Progressive enhancement: features should layer cleanly from filesystem to CLI to optional agent integrations

## Current focus

The implemented Phase 1 and 1.5 surface includes:

- filesystem scanner and bundle discovery
- markdown/YAML parser and metadata extraction
- cache-based metadata and link indexes
- graph construction for forward and reverse links
- v0.3 nested frontmatter, provenance, trust, lifecycle, and `okf_version` support, plus `bundle-info`, `conformance`, and `computations` commands
- lightweight CLI commands for discovery, catalog, query, graph, compose, and linting

## Repository structure

- `okf_runtime/` - runtime library and CLI
- `scripts/` - thin agent-facing entry point
- `references/` - agent-facing usage and specification material
- `docs/` - architecture, decisions, contribution guidance, and plans
- `tests/` - runtime tests and fixtures

## Documentation

- `docs/ARCHITECTURE.md` – runtime architecture and goals
- `docs/CONTRIBUTING_GUIDE.md` – contribution principles
- `docs/IMPLEMENTATION_PLAN.md` - phased roadmap and acceptance criteria
- `docs/EVALS.md` - cross-framework evaluation harness and Langfuse integration
- `references/OKF-Version-0.3-min.md` – distilled OKF v0.3 specification (default reference)
- `references/OKF-DELTA-0.2-to-0.3.md` – migration checklist and compatibility notes
- `references/OKF-Version-0.2-min.md` – legacy OKF v0.2 rules
- `references/USAGE.md` - implemented functionality and command examples

## Agent Skills packaging

This directory is a conformant Agent Skill package: its `okf-runtime` directory matches the frontmatter `name`. The Python implementation lives in `okf_runtime/`, agent-facing material in `references/`, and maintainer documentation in `docs/`.

## Contributing

Contributions should include:

- tests
- documentation
- performance considerations
- rationale for changes

See `docs/CONTRIBUTING_GUIDE.md` for more details.

## License

This repository is intended to be a community-driven open source project. Please refer to the repository license file for licensing details.
