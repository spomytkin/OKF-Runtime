# OKF v0.2 → v0.3 Delta

v0.3 is a minor version bump (§12) with **two deliberate breaking changes** (both alter how a consumer *reads* an existing v0.2 value), a large set of clarifications/errata that make v0.2 text precise, and three small additive capabilities. Pre-1.0, minor versions MAY break; from 1.0 on, minors are additive only (§12). A v0.2 bundle stays consumable by a v0.3 consumer via the fallbacks below — nothing needs to be rewritten to upgrade a bundle. Companion file for the full v0.3 rule set: `OKF-Version-0.3-min.md`.

## Breaking changes

| v0.2 | v0.3 | Consumer fallback |
|------|------|-------------------|
| Path field values without a leading `/` were written bundle-root-relative in v0.2 examples (e.g. `resource: references/skills/run-on-bq.md`) | A value without a leading `/` resolves from the **directory of the file that contains it** (§6, §6.2). One rule for links *and* path fields | If the bundle declares `okf_version` ≤ 0.2 **or declares no version**, and the value doesn't resolve from the file's directory, a consumer MAY retry from the bundle root (§6.2, §12.1) |
| Trust tier derived from the presence/actors of *any* `verified` event | Tier derived **only from current events**: an event is current when `verified[].at >= generated.at`, or when `generated` is absent (§5.3). Older events are history | None needed — tier can only move *down* (human-reviewed → lower), the safe direction |

## Additive

### Lifecycle: `superseded_by` (§5.4)
```yaml
status: deprecated
superseded_by: /metrics/gross-margin.md   # one path (§6.2); meaningful only with status: deprecated
```
* Consumers filtering to current knowledge SHOULD follow it and return the replacement.
* Informative: retire = keep file + `status: deprecated` (+ `superseded_by`). Move/rename = leave a short deprecated stub at the old path pointing to the new one.

### Bundle metadata in bundle-root `index.md` (§8.1)
```yaml
---
okf_version: "0.3"
title: Acme retail analytics        # optional
description: <scope + when to use>  # optional; lets an agent pick among many bundles
license: CC-BY-4.0                  # optional; SPDX expression or path (§6.2) to a license file
---
```
* v0.2 allowed only `okf_version`. Extension keys (§4.1) are also permitted here and apply to the bundle, not its concepts.
* A producer that regenerates `index.md` MUST preserve the existing root frontmatter. Producers SHOULD ship a root `index.md` with `okf_version`.
* Subdirectory `index.md` files still have **no** frontmatter.

### Extension-key rules (§4.1)
* Extension keys allowed at **any level**, including inside spec-defined mappings (`sources` entry, `generated`, `verified` entry, `executor`, `attester`).
* A producer modifying an existing file MUST keep keys it doesn't know (v0.2: SHOULD preserve).
* Future OKF versions will never define keys starting with `x-`. Producers SHOULD name theirs `x-<producer>-<name>` (e.g. `x-acme-owner`). No registry.

### Other additions
* **`team:<id>` actor scheme** (§7) — group of people. Treated as non-human for trust (a team name doesn't identify who checked). Generalizes the actor form to `<scheme>:<id>`; unknown schemes MUST be accepted as non-human.
* **`license`, `title`, `description`** in root `index.md` (above).
* **Bundle graph definition** (§6.4): edges = in-bundle concept links **plus** path fields resolving to an in-bundle concept (edge from containing concept to target).
* **Versioning policy** (§12) and **bundles-from-earlier-versions** fallbacks (§12.1).

## Clarifications and errata (v0.2 text made precise)

### Definitions & structure
* **§2** — New defined terms: bundle root, producer, consumer, asset, path field, extension key.
* **§2, §6.1** — Wording fix: only the **directory tree** gives parent/child structure. A link is an untyped, *directed relationship* (v0.2's "parent/child" for links was misread; okf#34).
* **§3.2** — Rules for what is a concept (new):
  1. `.md`, not reserved, frontmatter with non-empty `type` ⇒ **concept**.
  2. `.md` with no frontmatter or no `type` ⇒ **not a concept**; consumers skip it, validators SHOULD warn, bundle stays conformant (allows `README.md`, `AGENTS.md`, `CONTRIBUTING.md`, `SKILL.md` in a bundle).
  3. Non-`.md` file ⇒ **asset** (valid link/path-field target; embeddable image; never a concept).
  4. Names starting with `.` are not part of the bundle.
  5. Read only under the bundle root; do not follow symlinks that escape it.
* **§3.1** — Reserved files: consumers MUST NOT treat `index.md`/`log.md` as concepts *whatever frontmatter they contain*.

### Syntax
* **§4** — Frontmatter syntax: first line exactly `---`; ends at next line exactly `---`; MUST parse as a **YAML 1.2 core-schema mapping**; producers MUST NOT write duplicate keys (consumers MAY reject); SHOULD quote number/boolean-looking values (`okf_version: "0.3"`); SHOULD NOT use custom YAML tags; a producer editing a file SHOULD NOT re-serialize values it didn't change.
* **§4.2** — Body dialect = **CommonMark + GFM tables + `[^label]` footnotes**. Don't depend on other extensions. (v0.2: "SHOULD favor structure" — dropped.)

### Timestamps (§5)
* Timestamp keys: `generated.at`, `verified[].at`, `stale_after`, `sources[].last_modified`, `usage_window.from`, `usage_window.to`.
* Exactly two valid forms (RFC 3339 profile of ISO 8601):

| Form | Example | Meaning |
|------|---------|---------|
| `date-time` (offset REQUIRED) | `"2026-06-30T14:00:00Z"` | that instant |
| `full-date` | `"2026-06-30"` | start of that day, UTC (`…T00:00:00Z`) |

* A date-time **without an offset stays invalid**. Consumers MUST accept quoted strings *and* YAML-native timestamps (native date = start of day UTC). Producers SHOULD use date-time for `generated.at` and `verified[].at` (they are compared, §5.3).
* History: v0.2 text didn't define a zone for date-only values; post-release it was changed to require an offset (okf#24). v0.3 re-admits date-only with a fixed meaning so v0.2 bundles stay valid.
* All v0.3 examples quote timestamps.

### Provenance & trust
* **§5.1** — `sources[].resource` is either a followable artifact (URL or bundle path) or an unfollowable scope descriptor. `author` is an actor (§7).
* **§5.2** — `generated.at` has one meaning: last *meaningful* change (trivial format/whitespace/link-repair edits don't bump it). `verified` events REQUIRE both `by` and `at`; consumers **ignore** an event missing either. Latest `at` = most recent check.
* **§5.3** — Current-event rule (see Breaking). Earlier events MAY be shown as history ("verified before the last change"). Rationale: an agent rewriting a concept after a human review means the human didn't read the new text.
* **§7** — `team:` scheme; general `<scheme>:<id>` form; only `human:` yields human-reviewed; `sources[].author` uses the actor convention.

### Lifecycle
* **§5.4** — An **unknown `status` value is not `stable`**: consumers filtering to current knowledge exclude it; SHOULD show the raw value. (v0.2 silent.)
* **§5.5** — `stale_after` is an absolute **instant**; stale when `now >= stale_after`. Stale = "re-check", not "false". Empty/null ≡ absent. A value that can't be parsed MUST NOT be treated as fresh (SHOULD be shown as malformed). Don't invent a date when none is known.

### Links & paths
* **§6** — Single resolution rule for links and path fields: (1) URI scheme ⇒ absolute URL; (2) leading `/` ⇒ bundle root; (3) else ⇒ directory of containing file. **Both in-bundle forms valid; spec no longer recommends one** (v0.2 recommended `/` for links). Consumers MUST resolve both. Values resolving **outside** the bundle root are external; MUST NOT be read from the local filesystem.
* **§6** — Targets are URI references (RFC 3986): reserved characters/spaces MUST be percent-encoded (`my%20concept.md`). Paths are **case-sensitive**; producers SHOULD NOT create paths differing only by case.
* **§6.1** — A link refers to a concept iff its target **minus `#fragment`** resolves to a concept file (§3.2). Links to assets/directories/non-concepts are valid but not concept links. Only `[text](target)` and reference-style links are links; `[[wikilinks]]` are not.
* **§6.2** — Path-field list now includes `superseded_by`.
* **§6.3** — `references/` no longer described as external-material-only; other concepts may live there.

### Files
* **§8** — Subdirectory `index.md`: no frontmatter. Root: optional frontmatter (above). Entries SHOULD reuse the linked concept's `description`.
* **§9** — `log.md` has **no frontmatter**.

### Attested Computation
* **§10.2** — `parameters` entries REQUIRE `name` and `type`; `required` optional, default `false`. Common types: `string`, `integer`, `number`, `boolean`, `date`, `timestamp` (others runtime-specific).
* **§10.2** — Consumers MUST NOT show a value as attested when the concept has no `runtime` **or** no `attester`.
* **§10.3** — Locator rule for the computation:
  1. `computation` present ⇒ the file it points to.
  2. Else ⇒ the **first fenced code block** in the section headed `Computation` (any ATX heading level; section ends at next heading of same or higher level).
  3. No fence / file missing ⇒ computation **missing** ⇒ consumer MUST treat the concept as **not attestable**.
  Producers SHOULD put exactly one fence in the section. (v0.2's examples used indented blocks; v0.3 examples use real fences.)
* **§10.5** — Discovery by scanning frontmatter for `type: Attested Computation` (or following a link). Attester verdict = mapping with at least `ok` (bool) and optional `reason` (string). Attester re-reads the authoritative source by job/run ID, not from agent text. Gate: warn or withhold when `now >= stale_after`; on success surface the verdict.

### Conformance & versioning
* **§11.1** — Conformance reduced to **two** rules: (1) every frontmatter block in a `.md` under the bundle root parses as a YAML mapping; (2) present `index.md`/`log.md` follow §8/§9. v0.2's "every non-reserved `.md` has frontmatter with non-empty `type`" is gone — such files are simply non-concepts (§3.2).
* **§11.2** — Consumer value-normalization rules (new):
  1. null / empty string / empty list ≡ absent key.
  2. List-typed fields (`tags`, `sources`, `verified`, `parameters`): a single item MUST be accepted as a one-item list. A scalar `tags` is one tag — MUST NOT split on commas.
  3. Ignore an entry missing its REQUIRED key; SHOULD warn.
  4. Out-of-vocabulary value for a spec-defined key ⇒ keep it, MAY warn (unknown `status` per §5.4).
  Bundle stays conformant in all cases.
* **§11.2** — New/strengthened consumer MUSTs: no unknown-key rejection at any level; unparseable `stale_after` ≠ fresh; no "attested" without `runtime` + `attester`; trust tiers from current events only. SHOULDs: staleness only from `stale_after`; surface failed attestations.
* **§12** — Versioning policy: pre-1.0 minors MAY break (each break MUST be listed in the Changes section with a consumer fallback if any); from 1.0 minors are additive only. A *breaking change* = removing/renaming a field, conflicting redefinition, or changing how an existing value is read. Released text is frozen — normative changes need a new version. Unknown declared version ⇒ best-effort consumption, SHOULD NOT refuse.

### Editorial
Removed a duplicate sentence in §1; added *freshness* to the first-class families list; examples now quote timestamps, use relative links, and use a leading `/` in path fields; Appendix A uses current-verification timestamps and a URL for the dashboard source.

## Unchanged (carried forward)

* Bundle = directory tree of UTF-8 `.md` (YAML frontmatter + body); reserved filenames `index.md`, `log.md`; Concept ID = path minus `.md`
* `type` is the only always-required concept key; unregistered, freeform; unknown types tolerated
* Recommended: `title`, `description`, `resource`, `tags`
* Provenance/trust/lifecycle families and shapes: `sources` (+ `id`, `title`, `author`, `usage_count`, `last_modified`), `usage_window` (per-entry override allowed), `generated`, `verified` (bare mapping ≡ one-element list), `status`, `stale_after`
* Footnote attribution joined via `sources[].id` — never positionally
* Credibility is inferred from signals; OKF stores no score; `usage_count` is coarse (liveness/trend)
* Lineage via links / path fields — no `derived_from`
* Trust tier ladder: unverified < machine-confirmed < human-reviewed; advisory only
* Attested Computation contract (`runtime` REQUIRED; `parameters`, `computation`, `executor{resource,receipt}`, `attester{resource}`); agent supplies parameter *values* only; runtime artifacts (receipt, verdict) never stored in the bundle; `verified` ≠ attestation
* Broken links tolerated; missing `index.md` tolerated; unknown `type`/keys tolerated
* Version declared only via `okf_version` in bundle-root `index.md` (quoted string)
* Ethos: permissive consumption; no registry, no central authority, no required tooling

## Deferred (out of v0.3)

Carried over from v0.2: runtime receipt/verdict wire formats and attestation lifecycle; attester ABI/portability/sandboxing; attestation caches; semantic-layer (Looker/dbt) model-and-binding comparison.

Newly listed as considered-and-deferred in v0.3 (§12.2): **typed relationships** between concepts (use links, path fields, extension keys meanwhile); **validity windows, source-drift signals, and a `refuted` verification event** (use extension keys meanwhile). Deeper lineage (explicit external `derived_from`, data lineage) is also out of scope.

## Migration checklist for an existing v0.2 tool

* [ ] **Path resolver**: implement the 3-step rule (URI scheme → `/` bundle root → containing file's directory) for links **and** path fields; reject filesystem reads for anything resolving outside the bundle root; percent-decode targets; treat paths as case-sensitive.
* [ ] **Path resolver (compat)**: if `okf_version` ≤ 0.2 or absent, and a bare path doesn't resolve from the file's directory, retry from the bundle root. Detect version from root `index.md` first.
* [ ] **Timestamp parser**: accept RFC 3339 `date-time` (offset required) and `full-date` (= 00:00:00Z), quoted *or* YAML-native; flag offset-less date-times as malformed; compare as instants, not dates.
* [ ] **Trust derivation**: compute tier from **current** events only (`verified[].at >= generated.at`, or `generated` absent); drop events missing `by` or `at`; keep stale events available as history. Re-check any tier index/cache that previously keyed on mere presence of `verified`.
* [ ] **Staleness**: `now >= stale_after` as an instant (was date comparison); empty/null ≡ absent; unparseable ⇒ never fresh, surface as malformed.
* [ ] **Lifecycle**: unknown `status` ⇒ not `stable` (excluded from "current" filters, raw value shown); parse `superseded_by` as a path field and follow it for deprecated concepts.
* [ ] **Concept discovery**: concept ⇔ non-reserved `.md` + frontmatter + non-empty `type`; skip (and optionally warn on) other `.md`; classify non-`.md` as assets; ignore dot-paths; don't follow out-of-root symlinks.
* [ ] **Frontmatter reader**: YAML 1.2 core schema; tolerate duplicate-key rejection; no custom tags; keep unknown keys at every nesting level.
* [ ] **Value normalization**: null/empty ≡ absent; single item ⇒ one-item list for `tags`, `sources`, `verified`, `parameters`; never comma-split a scalar `tags`; ignore + warn on entries missing REQUIRED keys (`sources[].resource`, `generated.by`, `verified[].by/at`, `parameters[].name/type`).
* [ ] **Actors**: parse general `<scheme>:<id>`; only `human:` ⇒ human; `team:`, `process:`, unknown schemes ⇒ non-human.
* [ ] **Root `index.md`**: read `okf_version`, `title`, `description`, `license`; keep unknown keys; never overwrite this frontmatter when regenerating. Subdirectory `index.md` and `log.md`: no frontmatter.
* [ ] **Graph builder**: add path fields (`resource`, `sources[].resource`, `computation`, `executor.resource`, `attester.resource`, `superseded_by`) that resolve to in-bundle concepts as edges, alongside body links; strip `#fragment` before concept matching; ignore wikilinks; accept reference-style links.
* [ ] **Validator / attestation**: enforce `parameters[].name/type`; apply the §10.3 locator (file → first fence under `Computation` heading → missing ⇒ not attestable); refuse "attested" display without `runtime` + `attester`; verdict shape `{ ok, reason? }`.
* [ ] **Conformance check**: reduce to the two v0.3 rules; downgrade "`.md` without `type`" from error to skipped-non-concept (optional warning).
* [ ] **Generator**: emit `okf_version: "0.3"` in root `index.md`; quote timestamps; prefer date-time for `generated.at`/`verified[].at`; use a leading `/` for bundle-root paths; name own keys `x-<producer>-<name>`; preserve unknown keys and unchanged values when editing; emit real fenced code blocks under `# Computation`.
* [ ] Everything else — reserved-filename handling, `type` routing, footnote→`sources[].id` joins, `verified` bare-mapping normalization, Attested Computation contract fields — is unchanged.
