# Changelog

## 0.3.0 — 2026-11-27

OKF v0.3 consumer support per `references/OKF-Version-0.3-min.md`; acceptance
criteria are the migration checklist in `references/OKF-DELTA-0.2-to-0.3.md`
(minus the Generator item). Stdlib-only, no new dependencies.

### Added

- `okf bundle-info` / `api.bundle_info()`: root `index.md` metadata
  (`okf_version`, `title`, `description`, `license`, other root keys);
  `license_path` when the license value is a path.
- `okf conformance` / `api.conformance()`: the two §11.1 rules on v0.3,
  plus the v0.2 "type required" error on legacy bundles. Rule 2 covers
  the §8/§9 reserved-file checks: a subdirectory `index.md` or any
  `log.md` must have no frontmatter, and `log.md` date headings must be
  ISO 8601 `YYYY-MM-DD`.
  Output `{conformant, errors, warnings}`.
- `okf computations` / `api.computations()`: Attested Computation discovery
  with the §10.3 locator (file → first fenced block under a `Computation`
  heading → missing), validated parameters, `attestable`, and
  `attestation_display`: `attested` only when `runtime`, `attester` and a
  resolvable computation source are all present, `not attested` when
  attestable but no attester, `not attestable` when the runtime is missing
  or the source is missing (no runs happen here).
- `--path-edges` / `--no-path-edges` for `graph` and `compose`
  (`argparse.BooleanOptionalAction`): path-field edges
  (`resource`, `sources[].resource`, `computation`, `executor.resource`,
  `attester.resource`, `superseded_by`) with `via="<field path>"`.
- Trust surface: `verified_current` and `verified_history` (tier computed
  only from current events), `stale_after_malformed`, `superseded_by_id`,
  and catalog `is_current` (`status == "stable"`).
- `Document.warnings` (malformed timestamps, entries missing a REQUIRED key,
  custom YAML tags), surfaced in catalog records, `lint-links`
  (`parse_warning`) and `conformance` on v0.3 bundles.
- Reference-style links (`[text][label]`, collapsed `[text][]`, shortcut
  `[text]`); `[[wikilinks]]` stay ignored; links to assets/dirs/non-concepts
  are valid, not broken. Angle-bracketed link destinations (`<...>`) are
  stripped before the scheme check, so `[x](<https://a/b>)` is external
  (CommonMark); a `.md` without frontmatter is a non-concept, not an
  error, on v0.3 bundles (conformance and lint).
- `okf_runtime/spec.py` (`parse_okf_version`, `is_legacy`),
  `okf_runtime/timestamps.py` (`parse_instant`, `now`), and
  `okf_runtime/paths.py::resolve_path` — one resolver for links and path
  fields (URI scheme → bundle root → containing file's directory,
  percent-decoded, case-sensitive, `#fragment` stripped).
- Cache schema version 3: caches `is_concept`/`warnings`, bundle metadata,
  and version-dependent derived data; rebuilds when the root `index.md`
  `okf_version` changes.
- `tests/fixtures/v03-bundle/` (one minimal case per checklist item),
  legacy twins `v03-legacy-bundle` / `v03-unversioned-bundle`, and
  `tests/test_v03.py` (23 named `test_v03_<item>` tests).

### Changed (gated — legacy bundles keep v0.2 behaviour)

- Bare path fields resolve from the containing file's directory; on legacy
  bundles they retry from the bundle root (§6.2, §12.1). Body links never
  retry from the root.
- The v0.1 `timestamp` → `generated` fallback applies on legacy only.
- A `.md` without frontmatter or a non-empty `type` is a non-concept on
  v0.3 (excluded from catalog/query/trust/graph; `lint-links` reports
  `{"type": "non_concept"}` as a warning); on legacy it keeps the v0.2
  "type required" error and stays a concept.
- Path-field graph edges default ON for v0.3, OFF for legacy.
- `lint-links` warnings (`parse_warning`, `reserved_frontmatter`) and the
  subdirectory `index.md` / `log.md` frontmatter warning are v0.3-facing;
  legacy lint output is unchanged.

### Changed (not gated — clarification/erratum or consumer MUST)

- Trust tier is computed only from current verification events
  (`verified[].at >= generated.at`, or `generated` absent); events missing
  `by` or `at` are ignored, with a warning. A `generated` entry without
  `at` means all events are current (documented choice).
- Staleness compares instants (`now >= stale_after`); an unparseable
  `stale_after` is never fresh (`is_stale=True`, `stale_after_malformed=True`).
- `verify-sources` on v0.3 does not flag a `sources[].resource` as missing
  when it looks like a scope descriptor (not `/`-, `./`- or `../`-prefixed
  and no file extension).
- `compose` follows the `superseded_by` chain from deprecated concepts
  (cycle-safe, max 10 hops) and includes the replacement.

### v0.2 result changes

- `tests/fixtures/samples`: `concepts/deterministic_retrieval` and
  `concepts/trust_and_provenance` change trust tier `human-reviewed` →
  `unverified`. Their `verified` entries lack `at` (the over-indented
  `at:` line folds into the `by` value), so under the §5.3 current-event
  rule the events are dropped. Trust summary: `human-reviewed` 18 → 16,
  `unverified` 7 → 9; the two concepts leave the
  `trust_tier=human-reviewed` query. No other golden file changes.
