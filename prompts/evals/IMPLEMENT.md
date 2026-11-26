# Implementation Prompt: Cross-Framework Evaluations for OKF Runtime

You are implementing a production-quality evaluation subsystem in the
`spdev2025/OKF-Runtime` repository.

Read these files before changing code, in this order:

1. `prompts/evals/CONTEXT.md` — repository-specific requirements and decisions.
2. `SKILL.md` — the agent-facing contract being evaluated.
3. `README.md`, `docs/ARCHITECTURE.md`, and `docs/CONTRIBUTING_GUIDE.md`.
4. `okf_runtime/api.py`, `okf_runtime/cli.py`, and the existing tests/fixtures.
5. Only the OKF specification references needed for a disputed behavior; prefer
   `references/OKF-Version-0.2-min.md` before the full specification.

## Objective

Build a deterministic, locally runnable evaluation harness for the OKF Runtime
skill. It must evaluate both:

- runtime correctness: whether the library/CLI returns the right structured
  result for discovery, retrieval, graph, trust, composition, and lint tasks;
- agent behavior: whether an arbitrary agent or application correctly decides
  to use the skill, selects an appropriate operation, avoids prohibited source
  mutation, and returns grounded results.

The harness must be framework-neutral. Langfuse is an optional integration for
trace, dataset, experiment, and score publication; it must not be the execution
engine or the source of truth for pass/fail.

## Non-negotiable architecture

Implement these boundaries rather than coupling cases to a vendor SDK:

1. A versioned, JSON-serializable `EvalCase` schema.
2. A versioned, JSON-serializable `SubjectRequest`/`SubjectResponse` protocol.
3. Subject adapters for:
   - an in-process Python callable referenced by dotted path;
   - a subprocess using newline-delimited JSON over stdin/stdout;
   - an HTTP endpoint using JSON request/response bodies.
4. Pure evaluator functions that consume a case and normalized response and
   return structured scores/evidence without network access.
5. Reporter/observer plugins. JSON output is always available; Langfuse is
   optional and receives already-computed results.
6. A runner that does not import LangChain, LlamaIndex, OpenAI Agents SDK,
   Anthropic SDK, or any other agent framework.

Ground-truth case plans and expected results are evaluator-only data. Do not
send them to callable, subprocess, or HTTP subjects. Only the deterministic
built-in reference adapter may receive a case plan through an internal call.

Framework-specific examples or adapters may be documented separately, but no
framework package may be required to run the core suite.

## Required evaluation coverage

Create a small, high-signal golden dataset from existing repository fixtures.
Cover at least:

- skill applicability: positive, negative, and ambiguous requests;
- `discover`, `catalog`, `query`, `show`, `links`, `backlinks`, and `graph`;
- `compose`, including depth, boundary output, and `min_trust` behavior;
- v0.2 trust tier, lifecycle status, staleness, and `okf_version` behavior;
- broken links/anchors, orphans, malformed frontmatter, missing `type`, unknown
  types, unknown keys, and reserved `index.md`/`log.md` handling;
- permissive consumption requirements (soft violations are surfaced, not used
  to reject the bundle);
- determinism: stable ordering and equivalent repeated-run results after
  volatile fields are normalized;
- source safety: source fixture files are never modified by evaluation runs.

Include regression-oriented deterministic checks and agent-oriented rubric
checks. Do not use an LLM judge for facts that can be checked in code. If an
optional judge evaluator is included, it must be disabled by default, record
the judge/model/prompt version, and never replace deterministic gate metrics.

## Metrics and gating

At minimum, emit per-case and aggregate values for:

- `task_success` (binary);
- `result_correctness` (0..1);
- `tool_or_operation_selection` (0..1 when applicable);
- `groundedness` (0..1 when applicable);
- `source_unchanged` (binary);
- `deterministic_replay` (binary for replay cases);
- latency in milliseconds and error category.

Define metric direction, applicability, and aggregation explicitly. Exclude
not-applicable values from denominators. CI must fail on case errors, violated
hard invariants, or configured threshold regression—not merely because
Langfuse is unavailable.

## Langfuse integration

Use the current supported Langfuse Python SDK and verify API names against the
official documentation linked from `prompts/evals/CONTEXT.md` at implementation
time. Keep `langfuse` in an optional dependency group.

Support two modes:

- local/offline: execute all cases, write versioned JSON results, and require no
  credentials or network;
- publishing: send experiment/tracing data and deterministic scores to Langfuse
  when explicitly enabled and configured through environment variables.

Never log secrets. Redact configured sensitive fields before export. Flush the
Langfuse client before process exit. A publication failure must be visible but
must not discard local results or change their score values.

Attach useful metadata, including repository revision, eval schema version,
dataset/case version, subject adapter, framework/model identifiers supplied by
the subject, Python version, and run name. Use stable case IDs so local results
and Langfuse dataset items can be correlated.

## Repository deliverables

Choose names consistent with the repository, but the completed change must
include:

- an `okf_runtime.evals` package with schemas, adapters, evaluators, runner,
  reporters, and configuration;
- versioned eval cases stored as reviewable JSON or JSONL (not hidden in code);
- a CLI entry point that can list/validate cases, run a selected suite, and
  compare a result to a checked-in or explicitly supplied baseline;
- optional dependency metadata for eval and Langfuse features, leaving the base
  runtime dependency-light;
- unit tests for schemas, scoring, adapters, redaction, and failure isolation;
- integration tests using a fake subject and existing OKF fixtures;
- documentation for local runs, third-party framework adapters, CI gating,
  Langfuse setup, environment variables, and data/privacy behavior;
- one CI workflow or documented CI command that runs fully offline.

Prefer standard-library code in the core. Adding a small validation/testing
dependency is acceptable only with a clear rationale. Do not move runtime
business logic into eval code and do not mutate source bundles.

## Verification

Before finishing:

1. Run the existing test suite unchanged.
2. Run all new unit and integration tests offline with no Langfuse variables.
3. Run case validation and one full local eval against the built-in reference
   subject.
4. Confirm repeated runs produce equivalent normalized results.
5. Confirm an intentionally failing subject yields a non-zero gate result and a
   complete diagnostic artifact.
6. Test the Langfuse reporter with a fake client; perform a live smoke test only
   when credentials are already available, never as a CI requirement.
7. Inspect the diff for accidental fixture/cache/credential artifacts.

## Completion report

Return:

- a concise architecture summary;
- files added/changed;
- commands run and results;
- the implemented metric gates;
- any intentionally deferred work and why;
- exact local and Langfuse-enabled commands for the next maintainer.

Do not claim success unless the offline suite and existing tests pass.
