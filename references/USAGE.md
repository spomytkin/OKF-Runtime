# OKF Runtime Usage Guide

This guide describes the implemented functionality in `okf_runtime`, including OKF v0.3 consumer support. v0.2 and unversioned bundles keep working through the §12.1 fallbacks: bare path fields retry from the bundle root, the v0.1 `timestamp` → `generated` fallback applies, and a `.md` file without a non-empty `type` keeps the v0.2 error and stays a concept. On v0.3 bundles such a file is a non-concept instead.

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
- `--cache-dir <path>`: place the disposable cache outside the bundle. Defaults to `<root>/.cache`.

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

The `metadata` field is the parsed frontmatter. `trust_tier`, `status`, `is_stale`, `is_current` (`status == "stable"`), and `warnings` are derived fields. The `errors` field records parse or conformance issues without rejecting the whole bundle. Unknown keys are kept at every nesting level; a scalar `tags` value is one tag, never split on commas.

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
Nested list-of-mapping fields can select an item by a sibling key in the filter key itself, for example `query 'relations[kind=depends_on].target=payments.md'`.

Derived trust/lifecycle filters are also available:

```powershell
python -B -m okf_runtime.cli --root tests/fixtures/samples query trust_tier=human-reviewed
python -B -m okf_runtime.cli --root tests/fixtures/samples query status=deprecated stale=true
```

Trust tiers are computed only from current verification events (`verified[].at >= generated.at`); older events are kept as history (`verified_history`). An event missing `by` or `at` is ignored, with a warning on the document.

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

Use repeatable `--via` to keep graph traversal to edges produced by a source key path. Markdown body links use `via=body`; frontmatter resource edges retain the key path that produced them:

```powershell
python -B -m okf_runtime.cli --root tests/fixtures/feature-bundle graph source --resolve-resources --via 'relations[kind=depends_on].target'
```

Resource matching is opt-in: `--resolve-resources` matches exact strings across all frontmatter values, including `sources[].resource`, against another concept's `resource` value. A duplicate resource value produces a warning listing its concepts and creates no edges for that value.

Path-field edges (`resource`, `sources[].resource`, `computation`, `executor.resource`, `attester.resource`, `superseded_by` resolving to in-bundle concepts) are included by default on v0.3 bundles and excluded by default on v0.2/unversioned bundles; override with `--path-edges` / `--no-path-edges`.

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
Add `--resolve-resources` to include opt-in resource-value edges while choosing the composed neighborhood. Add `--path-edges` / `--no-path-edges` (same defaults as `graph`). Deprecated concepts follow their `superseded_by` chain (cycle-safe, max 10 hops) so the replacement is included.

### `verify-sources`

Check each `sources[].resource` path relative to its document. Existing in-bundle resources carrying `x-sha256` are hashed and compared. The JSON result reports `checked`, `missing`, `mismatched`, and a `problems` list.

```powershell
python -B -m okf_runtime.cli --root tests/fixtures/feature-bundle verify-sources
```

On v0.3 bundles, a `sources[].resource` that resolves to no file may be a scope descriptor and is not flagged missing unless it starts with `/`, `./`, or `../` or ends in a file extension. On v0.2/unversioned bundles the previous counts are kept, including the bundle-root retry for bare paths. A value resolving outside the bundle root is reported as `out_of_root` and never read from disk.

### `trust`

Summarize trust tiers, lifecycle status, stale concepts, and the root `index.md` `okf_version` declaration:

```powershell
python -B -m okf_runtime.cli --root tests/fixtures/samples --format yaml trust
```

Pass a concept ID to inspect its generated and verified events, sources, credibility signals, status, and staleness:

```powershell
python -B -m okf_runtime.cli --root tests/fixtures/samples --format yaml trust bundles/acme_retail/metrics/revenue
```

The per-concept trust surface includes `verified_current` and `verified_history`, `stale_after_malformed` (an unparseable `stale_after` is never fresh), and `superseded_by_id` (the resolved concept id of the `superseded_by` path field, or `null`).

### `lint-links`

Report parser issues, broken internal links, broken anchors, and orphan documents.

```powershell
python -B -m okf_runtime.cli --root tests/fixtures/samples lint-links
```

This command uses the same cached parsed documents and link indexes as the retrieval commands. On v0.3 bundles it also warns on `.md` files without frontmatter/`type` (`non_concept`), on subdirectory `index.md` / `log.md` files carrying frontmatter (`reserved_frontmatter`), and on document warnings such as malformed timestamps (`parse_warning`). Links to assets, directories, or non-concepts are valid and not broken; reference-style links (`[text][label]`, collapsed and shortcut forms) are links, `[[wikilinks]]` are not.

### `bundle-info`

Report the bundle-root `index.md` metadata: `okf_version`, `title`, `description`, `license`, and any other root keys. When `license` is a path rather than an SPDX expression, `license_path` gives the bundle-relative path.

```powershell
python -B -m okf_runtime.cli --root tests/fixtures/samples bundle-info
```

### `conformance`

Check the bundle against the §11.1 conformance rules and report `{conformant, errors, warnings}`. On v0.3 only the two §11.1 rules apply (frontmatter blocks parse as mappings; reserved files follow §8/§9); on v0.2/unversioned bundles the v0.2 "type required" error is added. A `.md` file with no frontmatter or no `type` does not break conformance.

```powershell
python -B -m okf_runtime.cli --root tests/fixtures/samples conformance
```

### `computations`

List Attested Computation concepts with their `runtime`, validated `parameters` (`name`/`type` required, `required` defaults to `false`), `computation_source` (`file` / `inline` / `missing` per the §10.3 locator), `attestable`, and `attestation_display` (`not attestable` or `not attested` — never `attested`; no runs happen here).

```powershell
python -B -m okf_runtime.cli --root tests/fixtures/samples computations
```

## Python API

The CLI maps directly to the public API:

```python
from okf_runtime import (
    bundle_info,
    catalog,
    computations,
    conformance,
    query,
    show,
    links,
    backlinks,
    graph,
    compose,
    trust,
    lint_links,
)

records = query("tests/fixtures/samples", type="BigQuery Table", tags="posts")
one = show("tests/fixtures/samples", "bundles/stackoverflow/tables/posts_questions")
```

Available API functions:

- `discover(root=".")`
- `catalog(root=".", include_links=False, cache_dir=None)`
- `query(root=".", cache_dir=None, **filters)`
- `show(root, concept_id, include_body=False, cache_dir=None)`
- `links(root=".", concept_id=None, cache_dir=None)`
- `backlinks(root=".", concept_id=None, cache_dir=None)`
- `graph(root, concept_id, depth=1, resolve_resources=False, cache_dir=None, via=None, path_edges=None)`
- `compose(root, topic, output_dir=None, depth=1, min_trust=None, resolve_resources=False, cache_dir=None, path_edges=None)`
- `trust(root=".", concept_id=None, cache_dir=None)`
- `lint_links(root=".", cache_dir=None)`
- `verify_sources(root=".", cache_dir=None)`
- `bundle_info(root=".", cache_dir=None)`
- `conformance(root=".", cache_dir=None)`
- `computations(root=".", cache_dir=None)`

## Cache Behavior

The runtime writes derived files under `.cache/` inside the root, or under the directory passed with `--cache-dir`:

- `manifest.json`
- `metadata.json`
- `links.json`
- `reverse_links.json`
- `compositions/`

The cache is disposable. Deleting `.cache/` does not delete source knowledge. The next retrieval command rebuilds it automatically.

Cache schema version 3 stores document `is_concept`/`warnings`, the bundle metadata, and version-dependent derived data, so a v0.2 cache never feeds a v0.3 run and vice versa. The cache also rebuilds when the root `index.md` `okf_version` changes, even if file modification times are unchanged.

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
- v0.3 provenance, trust tier, lifecycle, and `okf_version` support (v0.2/unversioned bundles via fallbacks)
- Trust-aware query filters and composition

Not implemented in Phase 1:

- Full YAML 1.2 parsing
- Content-hash cache invalidation
- Parallel scanning
- File watching
- MCP server
- Semantic search or embeddings
