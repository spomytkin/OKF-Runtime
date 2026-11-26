# OKF v0.3 — Minimal Spec

Implementation reference for OKF v0.3. Scope: agentic coding — parsers, validators, generators, attestation runners. Contains every MUST/SHOULD/MAY rule and field. Excludes §1 narrative and §13 history (see `OKF-DELTA-0.2-to-0.3.md`; v0.1→v0.2 history in `OKF-DELTA-0.1-to-0.2.md`). Full spec: https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md or `SPEC.md` / `OKF-SPEC-Version-0.3.md` locally.

OKF: a directory tree of UTF-8 markdown files (YAML frontmatter + body) representing knowledge about data/systems. No registry, no central authority, no required tooling. Permissive consumption: a consumer MUST NOT reject a bundle over a soft violation (§11). Provenance, trust, lifecycle, and attestation are optional frontmatter families on top of a minimal core. Packaging/invocation of code behind a `resource` (script, container, Skill) is out of scope — OKF fixes the interface, not the packaging.

---

## §2 Terminology

| Term | Meaning |
|---|---|
| Knowledge Bundle | self-contained directory tree of knowledge docs; unit of distribution |
| Bundle root | top directory of a bundle; `/`-prefixed paths resolve from here (§6). A root `index.md` with frontmatter (§8.1) marks the root when the bundle is a subdirectory of a larger repo |
| Producer / Consumer | writes a bundle (person, agent, pipeline) / reads one (agent, UI, index, program) |
| Concept | one `.md` file = one unit of knowledge (§3.2) |
| Concept ID | concept's file path within the bundle, `.md` suffix removed |
| Asset | file whose name does not end in `.md` (image, attester code…); never a concept |
| Frontmatter / Body | YAML block between two `---` lines (§4) / everything after it |
| Link | markdown link from one concept to a different concept; asserts an untyped, **directed** relationship. Only the directory tree gives parent/child structure (§6.1) |
| Path field | frontmatter field whose value is a path or URI (§6.2) |
| Source | material a concept derives from (external or in-bundle), recorded in `sources` (§5.1) |
| Provenance | the set of sources a concept derives from |
| Credibility signal | objective per-source fact (`author`, `usage_count`, `last_modified`); OKF stores signals, not a verdict |
| Actor | identity string `<producer>/<version>` or `<scheme>:<id>` (§7) |
| Trust tier | derived from **current** `verified` events: unverified / machine-confirmed / human-reviewed (§5.3) |
| Attested Computation | concept (`type: Attested Computation`) carrying a sanctioned, checkable way to compute a value (§10) |
| Executor | run instructions/code that runs a computation and returns a receipt |
| Receipt | evidence a run returns, shaped by `executor.receipt`; runtime artifact, not stored in the bundle |
| Attester | deterministic, no-LLM code that inspects a receipt and returns a verdict |
| Extension key | frontmatter key this spec does not define (§4.1) |

---

## §3 Bundle

```
bundle/                  # bundle root
  index.md               # optional — directory listing + bundle metadata (§8)
  log.md                 # optional — change history (§9)
  <concept>.md
  <asset>                # optional, non-.md
  <subdir>/ index.md, <concept>.md, ...
```

Distribution: git repo (RECOMMENDED), tarball/zip, or subdirectory of a larger repo. Layout is domain-independent; concepts may nest to any depth.

### §3.1 Reserved filenames

| File | Purpose |
|---|---|
| `index.md` | directory listing + bundle metadata — §8 |
| `log.md` | change history — §9 |

Producers MUST NOT use them for concepts; consumers MUST NOT treat them as concepts, **whatever frontmatter they contain**. Tags are only a frontmatter field (§4.1); OKF defines no tag-index file — a consumer may synthesize a tag view from a frontmatter scan.

### §3.2 What is a concept / asset

1. `.md` file, not reserved, with frontmatter containing a non-empty `type` ⇒ **concept**.
2. `.md` file with no frontmatter, or no `type` ⇒ **not a concept**. Consumers skip it; validators SHOULD warn; conformance unaffected (permits `README.md`, `AGENTS.md`, `CONTRIBUTING.md`, `SKILL.md` in a bundle).
3. File not ending in `.md` ⇒ **asset**. MAY be a link/path-field target; body MAY embed image assets; never a concept.
4. Files/dirs whose names start with `.` are **not part of the bundle**.
5. Read only under the bundle root; do NOT follow symlinks leaving it.

---

## §4 Concept document

UTF-8 markdown: one YAML frontmatter block + one body.

**Frontmatter syntax:**
- File MUST start with a line that is exactly `---`; block ends at the next line that is exactly `---`.
- MUST parse as a **YAML 1.2 core-schema mapping**.
- Producers MUST NOT write duplicate keys; consumers MAY reject duplicate-key frontmatter.
- Producers SHOULD quote number/boolean-looking values (e.g. `okf_version: "0.3"`).
- Producers SHOULD NOT use custom YAML tags.
- A producer modifying an existing file SHOULD NOT re-serialize values it did not change.

### §4.1 Frontmatter

```yaml
---
type: <string>              # REQUIRED — non-empty, freeform (e.g. "BigQuery Table")
title: <string>             # optional — consumers MAY derive from filename
description: <sentence>     # optional — one-line summary (index generators, snippets)
resource: <URI>             # optional — canonical URI of underlying asset; omit if abstract
tags: [<string>, ...]       # optional
# provenance / trust / lifecycle fields — §5
# Attested Computation fields — §10
# extension keys — see below
---
```

- `type` is the only always-required key. A concept with just `type` is fully conformant (§11). Values unregistered/freeform; consumers MUST accept unknown types (treat as generic).
- **Extensions**: producers MAY add keys at **any level**, including inside spec-defined mappings (`sources` entry, `generated`, `verified` entry, `executor`, `attester`). Consumers MUST NOT reject unknown keys. A producer modifying an existing file MUST keep keys it doesn't know. Future OKF versions will never define keys starting with `x-`; producers SHOULD name theirs `x-<producer>-<name>`. No registry.

### §4.2 Body

CommonMark + GFM tables + footnotes in `[^label]` form. Producers SHOULD NOT depend on other extensions. No section required. Conventional headings:

| Heading | Purpose |
|---|---|
| `# Schema` | columns/fields of an asset |
| `# Examples` | concrete usage, often fenced code |
| `# Computation` | sanctioned computation of an Attested Computation — §10.3 |

Per-claim attribution uses a markdown footnote whose label is a `sources[].id` (§5.1) — not a body citation list.

---

## §5 Provenance, trust, lifecycle

All fields optional. Absence is meaningful (e.g. unverified) but never grounds for rejection (§11).

**Timestamps.** Keys: `generated.at`, `verified[].at`, `stale_after`, `sources[].last_modified`, `usage_window.from`, `usage_window.to`. Exactly two valid forms (RFC 3339):

| Form | Example | Meaning |
|---|---|---|
| `date-time` (offset REQUIRED) | `"2026-06-30T14:00:00Z"` | that instant |
| `full-date` | `"2026-06-30"` | start of that day, UTC |

- A date-time without an offset is invalid. No other form is valid.
- Consumers MUST accept quoted strings **and** YAML-native timestamps (native date = start of day UTC).
- Producers SHOULD use date-time for `generated.at` and `verified[].at` (they are compared, §5.3).

### §5.1 `sources` — provenance

```yaml
sources:
  - id: ga4-schema                # optional — stable key for footnote attribution; SHOULD be set if cited
    resource: <URL|path|scope>    # REQUIRED per entry
    title: <string>               # optional
    author: <actor>               # optional signal — §7
    usage_count: <int>            # optional signal — uses over usage_window
    last_modified: <timestamp>    # optional signal — when the source itself last changed
usage_window: { from: <timestamp>, to: <timestamp> }   # optional sibling; frames usage_count; an entry MAY carry its own
```

- `resource` is either a **followable artifact** (absolute URL or in-bundle path, §6.2) or an **unfollowable scope/population descriptor** (e.g. `all queries in BigQuery project X`).
- `author` = authority signal; `usage_count` = adoption/liveness (for a scope descriptor: uses in scope touching the concept); `last_modified` = recency of the *source* (distinct from `generated.at`).
- Credibility is **inferred** from signals — OKF stores no score (subjective, non-portable, goes stale). `usage_count` is coarse: read as liveness/trend/order-of-magnitude, not precise cross-kind ranking.
- Lineage via links/path fields, no `derived_from`. If `resource` points at another in-bundle concept, the edge is already in the graph (§6.4); a consumer MAY recurse into that concept's `sources`. Deeper lineage out of scope.
- **Per-claim attribution**:
  ```markdown
  The `events_` table is sharded daily.[^ga4-schema]

  [^ga4-schema]: GA4 BigQuery Export schema
  ```
  Consumers join footnote → `sources` entry via `id`. MUST NOT join positionally (`sources[0]`) — order is unstable.

### §5.2 `generated` / `verified` — trust

```yaml
generated: { by: <actor>, at: <timestamp> }   # `by` REQUIRED
verified:                                      # list of events
  - { by: <actor>, at: <timestamp> }           # `by` and `at` BOTH REQUIRED
```

- `generated.at` = time of the last **meaningful** change to content; trivial edits (format, whitespace, link repair) do NOT change it. Different from `stale_after` (only that decides freshness, §5.5).
- `verified`: each event needs `by` and `at`; consumers **ignore** an event missing either. Multiple events = independent checks. Most recent = latest `at`.
- A bare `{ by, at }` mapping (no list dash) MUST be treated as a one-element list.
- `generated` ≠ `verified`: the writer is not necessarily the confirmer.

### §5.3 Trust tiers

An event is **current** when `verified[].at >= generated.at`, or when `generated` is absent. Consumers MUST compute the tier **only from current events**; older events are history (MAY be shown, e.g. "verified before the last change").

| Current `verified` events | Trust tier |
|---|---|
| none | unverified |
| non-`human:` actors only | machine-confirmed |
| at least one `human:<id>` actor | human-reviewed |

Lowest → highest. Advisory only, not access control; a concept with no trust frontmatter MUST NOT be rejected (§11). Rationale: if an agent rewrites a concept after a human review, the human hasn't read the new text.

> Spec text is silent on a `generated` mapping that lacks `at`; treat as an implementation choice (e.g. no baseline ⇒ all events current) and document it.

### §5.4 `status` / `superseded_by` — lifecycle

```yaml
status: stable            # draft | stable | deprecated; absent ⇒ stable
superseded_by: /metrics/gross-margin.md   # optional; one path (§6.2); meaningful only with status: deprecated
```

- `draft` = unreviewed/possibly incomplete. `stable` = default. `deprecated` = kept for links/history, not current.
- A value **not in the list is not `stable`**: consumers filtering to current knowledge exclude it; SHOULD show the raw value.
- Consumers filtering to current knowledge SHOULD follow `superseded_by` and return the replacement.
- Informative: retire = keep file + `status: deprecated` (+ `superseded_by`). Move/rename = leave a short deprecated stub at the old path with `superseded_by` → new path.

### §5.5 `stale_after` — lifecycle

`stale_after: <timestamp>` — optional, absolute instant. Stale when **`now >= stale_after`** (plain comparison; not a relative TTL).

- Stale = "a person/process must re-check", NOT "false".
- Omit when no review date is known; do not invent one.
- Empty/null ≡ absent.
- A value that cannot be parsed MUST NOT be treated as fresh; SHOULD be shown as malformed.

---

## §6 Links and paths

**Resolution** (links and path fields, same rules):
1. Value with a URI scheme (`https:` …) ⇒ absolute URL.
2. Starts with `/` ⇒ resolve from the **bundle root**.
3. Otherwise ⇒ resolve from the **directory of the file containing it**.

Both in-bundle forms (2, 3) are valid; consumers MUST resolve both; spec recommends neither. A value resolving **outside** the bundle root is external — MUST NOT be read from the local filesystem.

**Identifiers**: targets/path values are URI references (RFC 3986); spaces/reserved chars MUST be percent-encoded (`my%20concept.md`). Paths are **case-sensitive**; producers SHOULD NOT create paths differing only by case.

### §6.1 Links between concepts

```markdown
See the [neighboring concept](./other.md).
See the [customers table](/tables/customers.md).
```

- A link **refers to a concept** when its target, minus `#fragment`, resolves to a concept file (§3.2). Links to assets, directories, or non-concepts are valid but not concept links.
- A link asserts an untyped, directed relationship; its kind lives in surrounding prose. Only `[text](target)` and reference-style links are links; `[[wikilinks]]` are not.
- Consumers MUST accept broken links (target may be not-yet-written).

### §6.2 Path fields

`resource`, `sources[].resource`, `computation`, `executor.resource`, `attester.resource` (§10), `superseded_by` (§5.4). Values resolve per §6. `sources[].resource` MAY instead be a non-path scope descriptor (§5.1).

**v0.2 compatibility**: if a value without a leading `/` doesn't resolve from its file's directory, and the bundle declares `okf_version` ≤ 0.2 or no version, a consumer MAY try the bundle root.

### §6.3 `references/` convention

Conventional location for copies of external material, run instructions, and code (`/references/attesters/sql-equality.py`). Naming convention only; other concepts may live there too.

### §6.4 Bundle graph

Directed edges:
- a link (§6.1) from a concept to an in-bundle concept;
- a path field (§6.2) resolving to an in-bundle concept (edge: containing concept → target).

---

## §7 Actor convention

Identity fields (`generated.by`, `verified[].by`, `sources[].author`) use one of:

| Form | For | Example |
|---|---|---|
| `<producer>/<version>` | agents/tools | `reference_agent/gemini-2.5-pro` |
| `human:<id>` | a person | `human:ahormati` |
| `team:<id>` | a group of people | `team:finance-fpa` |
| `process:<id>` | automated process | `process:finance-nightly` |
| `<other-scheme>:<id>` | anything else (MAY be used) | — |

`id` is an opaque string. Consumers MUST accept unknown schemes and treat them as **non-human**. Only `human:` yields human-reviewed (§5.3); producers MUST use it for content a person wrote or confirmed. A `team:` actor in `verified` ⇒ machine-confirmed (a team name doesn't identify who checked).

---

## §8 `index.md`

MAY appear in any directory, including the bundle root. Lists directory contents for progressive disclosure. **Subdirectory `index.md`: no frontmatter.** Bundle-root `index.md`: MAY carry frontmatter (§8.1). Body = headed sections of link bullets; entries SHOULD reuse the target's `description`:

```markdown
# Section
* [Title](relative-url) - short description
* [Subdirectory](subdir/) - short description
```

Producer-generated or consumer-synthesized on the fly.

### §8.1 Bundle metadata (root `index.md` frontmatter)

```yaml
---
okf_version: "0.3"          # quoted string — §12
title: Acme retail analytics
description: <scope + when to use>   # lets an agent choose among many bundles
license: CC-BY-4.0          # SPDX expression, or path (§6.2) to a license file in the bundle
---
```

All keys optional. Extension keys permitted; they apply to the bundle, not its concepts. A producer that regenerates `index.md` MUST keep existing root frontmatter. Producers SHOULD ship a root `index.md` with `okf_version`.

---

## §9 `log.md`

MAY appear at any level; **no frontmatter**. Flat, date-grouped, newest first. Date headings MUST be ISO 8601 `YYYY-MM-DD`. Leading bold action word (`**Update**`, `**Creation**`, `**Deprecation**`) is convention, not required. Entries are prose.

```markdown
# Update Log
## 2026-05-22
* **Update**: Added [Customer Metrics](tables/customer-metrics.md).
```

---

## §10 Attested Computation

A concept (`type: Attested Computation`) carrying a sanctioned, checkable way to compute a value. Provenance asks "where did this claim come from?"; attestation asks "was this number made the way we said it must be?". OKF specifies the contract and the check, not execution.

### §10.1 Why standalone

- `runtime` defines what `parameters` mean (SQL bind var, dbt var, Python arg).
- One computation, many consumers: concepts link to it with ordinary links.
- Each computation has its own `verified` / `stale_after` / `attester`. Group with a directory (+ `index.md`), not frontmatter.

A concept needing the value (Metric, table…) links to the computation. A narrative concept can link several.

### §10.2 Contract fields

```yaml
type: Attested Computation
runtime: bigquery                          # REQUIRED — e.g. bigquery, postgres, dbt, python, Looker
parameters:                                # optional — typed, named holes the agent may fill
  - { name: year, type: integer, required: true }
computation: <path>                        # optional — file; see §10.3
executor:                                  # optional
  resource: <path>                         # run instructions/code a runner follows
  receipt: [job_id, executed_sql, result]  # fields a run MUST return
attester:                                  # optional
  resource: <path>                         # deterministic, no-LLM code; receipt → verdict; consumer-side
```

- Also carries the §5 families (`generated`, `verified`, `status`, `stale_after`, `sources`…).
- `runtime` is the only REQUIRED field. It fixes how `parameters`, `executor`, `attester` are interpreted.
- `parameters[]`: `name` and `type` REQUIRED; `required` optional, default `false`. Common types: `string`, `integer`, `number`, `boolean`, `date`, `timestamp`; others are runtime-specific. Binding follows `runtime`.
- **Consumers MUST NOT show a value as attested when the concept lacks `runtime` or `attester`.**
- Code behind a `resource` may be a Skill, script, or container — packaging is out of scope.

### §10.3 The computation itself

Delivery is one of:
- **inline** — fenced code block in the body under the `Computation` heading (best for short, reviewed-with-contract computations), or
- **file** — `computation: <path>` (§6.2), no body fence (best for long/generated/shared files).

**Locator (how a consumer finds it):**
1. `computation` present ⇒ the file it names.
2. Else ⇒ the **first fenced code block** in the section headed `Computation` (any ATX heading level); the section ends at the next heading of the same or higher level.
3. No fence, or file missing ⇒ computation **missing** ⇒ consumer MUST treat the concept as **not attestable**.

Producers SHOULD put exactly one fence in the `Computation` section.

The agent MAY supply only *values* for the declared `parameters`; it MUST NOT author or edit the computation. The consumer binds the computation with those values to make the executable artifact. The attester independently re-derives the same binding and compares it to the expanded/compiled artifact in the receipt (`executed_sql`, `compiled_sql` — not the source query). A rewritten query, swapped computation file, or changed dependency fails the check.

### §10.4 Concepts that use a computation

A concept about one figure links to one computation; an overview (e.g. income statement) stays one readable concept and links one computation per figure. Each computation carries its own trust/freshness state (revenue can be fresh while profit is past `stale_after`).

### §10.5 Consumption flow — informative, not normative

Runtime artifacts (receipts, verdicts) are NOT stored in the bundle.

1. **Discover** — scan frontmatter for `type: Attested Computation`, or follow a link.
2. **Load** — contract from frontmatter; computation per §10.3.
3. **Parameterize** — agent supplies values for declared parameters.
4. **Execute** — executor runs the bound computation, returns a receipt shaped by `executor.receipt`.
5. **Attest** — consumer runs the attester on the receipt; verdict is a mapping with at least `ok` (bool) and optional `reason` (string). Checks **provenance** (what ran = `computation` bound with the claimed parameters, not agent-written code) and **fidelity** (displayed value agrees with the receipt's authoritative source, re-read by job/run ID — not from agent text).
6. **Gate** — do not show a value whose attestation failed; warn or withhold when `now >= stale_after`; on success show the verdict (e.g. link to the job log).

### §10.6 Verified vs. attested

| Dimension | `verified` (§5.2) | Attestation (§10) |
|---|---|---|
| Confirms | the *definition* still matches policy | one *run* made the value the sanctioned way |
| Granularity | doc-level | per-call |
| Speed | slow | runtime |
| Stored in bundle | yes | no |

Both needed: a stale definition can still attest cleanly; a freshly verified definition still needs attestation per run.

---

## §11 Conformance

### §11.1 Bundle

A bundle is conformant with v0.3 when:
1. Every frontmatter block in a `.md` file under the bundle root parses as a YAML mapping (§4).
2. Every present reserved file (`index.md`, `log.md`) follows §8 / §9.

A `.md` file with no frontmatter or no `type` is not a concept (§3.2) and does not break conformance.

### §11.2 Consumer rules

Consumers:
- MUST resolve both in-bundle forms of links and path fields (§6).
- MUST NOT read a value that resolves outside the bundle root from the local filesystem (§6).
- MUST NOT treat `index.md` / `log.md` as concepts (§3.1).
- MUST NOT reject unknown keys at any level (§4.1).
- MUST NOT treat an unparseable `stale_after` as fresh (§5.5).
- MUST NOT show a value as attested without `runtime` and `attester` (§10.2).
- MUST NOT reject a concept for a missing optional family (§5.3).
- MUST compute trust tiers only from current verification events (§5.3).
- MUST treat a bare `verified` mapping as a one-element list (§5.2).
- SHOULD compute staleness only from `stale_after` (§5.5).
- SHOULD surface a failed attestation, not silently drop it (§10.5).

**Value normalization** (absent / empty / odd shapes):
1. null, empty string, empty list ≡ absent key.
2. List-typed fields (`tags`, `sources`, `verified`, `parameters`): a single item MUST be accepted as a one-item list. A scalar `tags` is ONE tag — MUST NOT split on commas.
3. Ignore an entry of a family lacking its REQUIRED key; SHOULD warn.
4. A spec-defined key with an out-of-vocabulary value: keep the value, MAY warn (unknown `status` ⇒ §5.4).

Bundle stays conformant in all of these.

Consumers MUST NOT reject a bundle for: missing optional fields; unknown `type` values; unknown extension keys; broken links; missing `index.md`.

---

## §12 Versioning

Current version: **0.3**. Format `<major>.<minor>`.

- **Before 1.0**, a minor MAY contain breaking changes; each MUST be listed in the changes section with a consumer fallback where one exists.
- **From 1.0**, minors are backward-compatible additions only (new optional fields, new conventional headings); only a major may break.
- **Breaking change** = removing a field, renaming a field, redefining a field in conflict with its earlier definition, or changing how a consumer reads an existing value.
- After release, a change to normative text requires a new version.

Declared via `okf_version: "0.3"` in the bundle-root `index.md` frontmatter (§8.1). A consumer that doesn't know the declared version SHOULD best-effort-consume, SHOULD NOT refuse.

### §12.1 Bundles from earlier versions

For bundles declaring `okf_version` ≤ 0.2 or no version, a consumer MAY apply:
- bare path-field values that don't resolve from the file's directory MAY resolve from the bundle root (§6.2);
- v0.1 fallbacks (below).

---

## Deferred

Out of scope for v0.3. Do not build these against this spec version:
- Runtime receipt/verdict wire protocol and the attestation lifecycle around a run.
- Attester ABI, portability, and sandboxing.
- Attestation caching.
- Semantic-layer (Looker/dbt) model-and-binding comparison beyond SQL-text equality.
- Typed relationships between concepts (use links, path fields, extension keys).
- Validity windows, source-drift signals, a `refuted` verification event (use extension keys).
- Explicit external `derived_from` / data lineage.

---

## Migration Notes

**v0.2 → v0.3** (breaking; full checklist in `OKF-DELTA-0.2-to-0.3.md`):

| v0.2 | v0.3 | Fallback |
|---|---|---|
| bare path (no leading `/`) written bundle-root-relative | resolves from the **containing file's directory** (§6.2) | `okf_version` ≤ 0.2 or none ⇒ MAY retry from bundle root |
| trust tier from any `verified` event | from **current** events only (`at >= generated.at`) (§5.3) | none needed — tier can only drop |

**v0.1 → v0.2 → v0.3 legacy fallbacks** (consumers MAY apply for old bundles):

| v0.1 | Replacement | Fallback |
|---|---|---|
| `timestamp` | `generated: { by, at }` (§5.2) | MAY read legacy `timestamp` when `generated` is absent |
| body `# Citations` list | `sources` (§5.1) + footnotes | MAY parse a legacy `# Citations` list when `sources` is absent |

---

## Worked example

```
bundles/finance/
├── index.md                       # okf_version, title, description, license
├── metrics/
│   └── income-statement.md        # type: Metric — narrates, links both computations
├── computations/
│   ├── revenue.md                 # type: Attested Computation (bigquery)
│   └── profit.md                  # type: Attested Computation (dbt)
└── references/
    ├── skills/run-on-bq.md, run-dbt.md
    └── attesters/sql-equality.py, dbt-binding.py     # assets (§3.2)
```

`index.md`:

```markdown
---
okf_version: "0.3"
title: Acme finance
description: Income-statement metrics and their sanctioned computations. Use it for revenue and profit questions.
license: CC-BY-4.0
---

# Metrics
* [Income statement (fiscal year)](metrics/income-statement.md) - Headline income-statement figures for a fiscal year.

# Computations
* [Revenue for fiscal year](computations/revenue.md) - Recognized revenue for a fiscal year, per Finance's definition.
* [Gross profit for fiscal year](computations/profit.md) - Gross profit by segment for a fiscal year.
```

`metrics/income-statement.md`:

```markdown
---
type: Metric
title: Income statement (fiscal year)
description: Headline income-statement figures for a fiscal year.
tags: [finance, income-statement]
status: stable
generated: { by: reference_agent/gemini-2.5-pro, at: "2026-06-20T22:53:05Z" }
verified: { by: "human:ahormati", at: "2026-06-25T09:00:00Z" }
stale_after: "2026-12-31T00:00:00Z"
sources:
  - id: fpa-handbook
    resource: https://wiki.acme/finance/fpa-handbook
    title: FP&A reporting handbook
---

# Definition
The income statement reports [revenue](../computations/revenue.md) and
[gross profit](../computations/profit.md) for a fiscal year, per the FP&A
reporting handbook.[^fpa-handbook]

[^fpa-handbook]: FP&A reporting handbook
```

`computations/revenue.md` (note `/`-prefixed path fields, quoted timestamps, real fence):

````markdown
---
type: Attested Computation
title: Revenue for fiscal year
description: Recognized revenue for a fiscal year, per Finance's definition.
tags: [finance, revenue]
status: stable
runtime: bigquery
parameters:
  - { name: year, type: integer, required: true }
executor:
  resource: /references/skills/run-on-bq.md
  receipt: [job_id, executed_sql, result]
attester:
  resource: /references/attesters/sql-equality.py
generated: { by: reference_agent/gemini-2.5-pro, at: "2026-06-20T14:00:00Z" }
verified: { by: "human:ahormati", at: "2026-06-25T09:00:00Z" }
stale_after: "2026-12-31T00:00:00Z"
sources:
  - id: rev-policy
    resource: https://wiki.acme/finance/revenue-recognition
    title: Revenue recognition policy
    author: "team:finance-fpa"
    last_modified: "2026-04-02T00:00:00Z"
  - id: exec-rev-dash
    resource: https://bi.acme.example/dashboards/exec-revenue
    title: Executive revenue dashboard
    author: "team:finance-fpa"
    usage_count: 5000
    last_modified: "2026-06-18T00:00:00Z"
usage_window: { from: "2026-06-01T00:00:00Z", to: "2026-06-30T00:00:00Z" }
---

# Computation

```sql
SELECT SUM(amount) AS revenue
FROM finance.recognized_revenue
WHERE fiscal_year = @year
```

Recognized revenue per the recognition policy,[^rev-policy] corroborated by
the executive revenue dashboard.[^exec-rev-dash]

[^rev-policy]: Revenue recognition policy
[^exec-rev-dash]: Executive revenue dashboard
````

`computations/profit.md` (summary): `runtime: dbt`, params `year` + `segment`, `generated.at 2026-06-10T14:00:00Z`, `verified: { by: "process:finance-nightly", at: "2026-06-12T08:00:00Z" }`, `stale_after: "2026-06-15T00:00:00Z"`.

Result for a consumer reading on/after 2026-06-15 and before 2026-12-31:

| Concept | Trust tier | Fresh | Attestable |
|---|---|---|---|
| `metrics/income-statement` | human-reviewed | yes | no (not a computation) |
| `computations/revenue` | human-reviewed | yes | yes |
| `computations/profit` | machine-confirmed | no | yes, with a staleness warning |
