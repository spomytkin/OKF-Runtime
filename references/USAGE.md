# OKF Runtime Usage Guide

This guide describes the implemented Phase 1 and Phase 1.5 functionality in `okf_runtime`.

OKF Runtime is library-first. The CLI is a thin wrapper around `okf_runtime.api`, so CLI commands and Python API calls use the same scanner, parser, cache, metadata index, link index, graph builder, and compose logic.

## Running The CLI

From the repository root:

```powershell
python -B -m okf_runtime.cli --root <bundle-or-scan-root> <command>
```

Use `-B` when you want to avoid Python bytecode writes in restricted environments.

After installing from the skill root with `python -m pip install -e .`, the thin wrapper `python scripts/okf.py <command>` delegates to the same CLI. Prefer the module form above when installation is unnecessary.

Global options:

- `--root <path>`: bundle root or scan root. Defaults to the current directory.
- `--format json|yaml`: output format. Defaults to `json`.

All retrieval commands automatically rebuild the disposable `.cache/` index when markdown files are newer than the cache.

## Output Shape

Most metadata commands return catalog records:

```yaml
- id: bundles/stackoverflow/tables/posts_questions
  path: bundles/stackoverflow/tables/posts_questions.md
  reserved: false
  metadata:
    type: BigQuery Table
    title: Stack Overflow Questions
    tags:
      - Stack Overflow
      - questions
      - posts
  errors: []
  trust_tier: human-reviewed
  status: stable
  is_stale: false
```

The `metadata` field is the parsed frontmatter. `trust_tier`, `status`, and `is_stale` are derived v0.2 fields. The `errors` field records parse or conformance issues without rejecting the whole bundle.

## Example Query

Command:

```powershell
python -B -m okf_runtime.cli --root tests/fixtures/samples --format yaml query type="BigQuery Table" tags=posts
```

Expected result:

Frontmatter catalog records for every concept under `tests/fixtures/samples` whose parsed frontmatter has:

- `type: BigQuery Table`
- `tags` containing `posts`

For the included sample bundles, this returns records such as:

- `bundles/stackoverflow/tables/post_links`
- `bundles/stackoverflow/tables/posts_answers`
- `bundles/stackoverflow/tables/posts_questions`
- `bundles/stackoverflow/tables/votes`

The command does not load or print markdown bodies. It queries the metadata cache and returns matching concept records.

## Commands

### `discover`

Find OKF-like bundles below the root.

```powershell
python -B -m okf_runtime.cli --root tests/fixtures/samples discover
```

Returns bundle roots and markdown file counts.

### `catalog`

Return parsed frontmatter catalog records for all non-reserved concept documents.

```powershell
python -B -m okf_runtime.cli --root tests/fixtures/samples --format yaml catalog
```

Short output:

```powershell
python -B -m okf_runtime.cli --root tests/fixtures/samples --format yaml catalog --short
```

Verbose output includes forward links and backlinks:

```powershell
python -B -m okf_runtime.cli --root tests/fixtures/samples --format yaml catalog --verbose
```

### `query`

Filter metadata without loading markdown bodies.

```powershell
python -B -m okf_runtime.cli --root tests/fixtures/samples query type="BigQuery Dataset"
python -B -m okf_runtime.cli --root tests/fixtures/samples query tags=posts
python -B -m okf_runtime.cli --root tests/fixtures/samples query type="BigQuery Table" tags=posts
```

Filters are exact `key=value` matches. For list fields such as `tags`, a record matches when the list contains the requested value.

Derived v0.2 filters are also available:

```powershell
python -B -m okf_runtime.cli --root tests/fixtures/samples query trust_tier=human-reviewed
python -B -m okf_runtime.cli --root tests/fixtures/samples query status=deprecated stale=true
```

### `show`

Return one concept record by concept ID.

```powershell
python -B -m okf_runtime.cli --root tests/fixtures/samples show bundles/stackoverflow/tables/posts_questions
```

Include the markdown body:

```powershell
python -B -m okf_runtime.cli --root tests/fixtures/samples show bundles/stackoverflow/tables/posts_questions --body
```

### `links`

Return forward markdown links.

```powershell
python -B -m okf_runtime.cli --root tests/fixtures/samples links
python -B -m okf_runtime.cli --root tests/fixtures/samples links bundles/stackoverflow/tables/posts_questions
```

Each link includes link text, raw target, resolved path, resolved concept ID when available, anchor, and whether the link is external.

### `backlinks`

Return reverse links.

```powershell
python -B -m okf_runtime.cli --root tests/fixtures/samples backlinks
python -B -m okf_runtime.cli --root tests/fixtures/samples backlinks bundles/stackoverflow/tables/posts_questions
```

### `graph`

Return a deterministic neighborhood around a concept.

```powershell
python -B -m okf_runtime.cli --root tests/fixtures/samples graph bundles/stackoverflow/tables/posts_questions
python -B -m okf_runtime.cli --root tests/fixtures/samples graph bundles/stackoverflow/tables/posts_questions --depth 2
```

The result contains:

- `start`
- `depth`
- `nodes`
- `edges`

### `compose`

Create a temporary composed bundle around a topic or concept.

```powershell
python -B -m okf_runtime.cli --root tests/fixtures/samples compose posts_questions
```

With an explicit output directory:

```powershell
python -B -m okf_runtime.cli --root tests/fixtures/samples compose posts_questions --output-dir .cache\demo-compose
```

Compose copies selected source markdown files unchanged and writes `boundary.json` describing selected files and links that point outside the composed set.

Require a minimum derived trust tier when composing:

```powershell
python -B -m okf_runtime.cli --root tests/fixtures/samples compose posts_questions --min-trust machine-confirmed
```

The ordering is `unverified`, `machine-confirmed`, then `human-reviewed`.

### `trust`

Summarize trust tiers, lifecycle status, stale concepts, and the root `index.md` `okf_version` declaration:

```powershell
python -B -m okf_runtime.cli --root tests/fixtures/samples --format yaml trust
```

Pass a concept ID to inspect its generated and verified events, sources, credibility signals, status, and staleness:

```powershell
python -B -m okf_runtime.cli --root tests/fixtures/samples --format yaml trust bundles/acme_retail/metrics/revenue
```

### `lint-links`

Report parser issues, broken internal links, broken anchors, and orphan documents.

```powershell
python -B -m okf_runtime.cli --root tests/fixtures/samples lint-links
```

This command uses the same cached parsed documents and link indexes as the retrieval commands.

## Python API

The CLI maps directly to the public API:

```python
from okf_runtime import catalog, query, show, links, backlinks, graph, compose, trust, lint_links

records = query("tests/fixtures/samples", type="BigQuery Table", tags="posts")
one = show("tests/fixtures/samples", "bundles/stackoverflow/tables/posts_questions")
```

Available API functions:

- `discover(root=".")`
- `catalog(root=".", include_links=False)`
- `query(root=".", **filters)`
- `show(root, concept_id, include_body=False)`
- `links(root=".", concept_id=None)`
- `backlinks(root=".", concept_id=None)`
- `graph(root, concept_id, depth=1)`
- `compose(root, topic, output_dir=None, depth=1, min_trust=None)`
- `trust(root=".", concept_id=None)`
- `lint_links(root=".")`

## Cache Behavior

The runtime writes derived files under `.cache/` inside the root:

- `manifest.json`
- `metadata.json`
- `links.json`
- `reverse_links.json`
- `compositions/`

The cache is disposable. Deleting `.cache/` does not delete source knowledge. The next retrieval command rebuilds it automatically.

Phase 1 freshness uses markdown modification times. Content hashing and incremental rebuilds are future Phase 2 improvements.

## Phase 1 Boundaries

Implemented:

- Filesystem scanning
- Markdown document discovery
- Dependency-free frontmatter extraction for scalars, inline collections, nested mappings, list-of-dicts, and folded scalar continuations
- Metadata catalog and exact-match query
- Forward links and backlinks
- Graph neighborhoods
- Basic composition with boundary reporting
- Link, anchor, parser, and orphan linting
- JSON and YAML-like CLI output
- v0.2 provenance, trust tier, lifecycle, and `okf_version` support
- Trust-aware query filters and composition

Not implemented in Phase 1:

- Full YAML 1.2 parsing
- Content-hash cache invalidation
- Parallel scanning
- File watching
- MCP server
- Semantic search or embeddings
