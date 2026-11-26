# Context: OKF Runtime Skill Evaluations

This file is implementation context for an agent adding evaluations to
`spdev2025/OKF-Runtime`. It records repository facts, required boundaries, and
acceptance decisions so the implementer does not have to infer product intent.

## 1. What is being evaluated

OKF Runtime is a Python 3.10+ deterministic consumer for Open Knowledge Format
(OKF) Markdown bundles. The repository is also packaged as an Agent Skill via
the root `SKILL.md`.

The skill promises that an agent can discover, catalog, query, show, traverse,
lint, inspect trust, and compose OKF bundles while conserving model context.
Evaluation therefore has two distinct targets:

| Target | Question | Preferred evaluator |
|---|---|---|
| Runtime contract | Did the operation return the correct structured result? | Deterministic code |
| Skill/agent behavior | Did the agent invoke and use the skill appropriately and ground the answer in its output? | Deterministic evidence first; rubric only where necessary |

Do not conflate these layers. Existing unit tests protect individual Python
behaviors; evals exercise end-to-end tasks, adapter portability, behavioral
policy, regression gates, and observability.

## 2. Repository facts

- Base package: `okf_runtime`; base project currently has no runtime
  dependencies.
- Stable public API: `okf_runtime/api.py`.
- Thin CLI: `python -B -m okf_runtime.cli --root <path> <command>`.
- Current commands: `discover`, `catalog`, `query`, `show`, `links`,
  `backlinks`, `graph`, `compose`, `trust`, and `lint-links`.
- Existing fixtures: `tests/fixtures/samples` and
  `tests/fixtures/v02-income-statement`.
- Existing tests: parser, runtime/API, and v0.2 trust behavior.
- Generated `.cache/`, `.test-tmp/`, bytecode, and credentials must not be
  committed.
- Architectural rules: library first, deterministic before AI, filesystem as
  source of truth, minimal dependencies, no required database/daemon/cloud
  service, and no business logic that exists only in a CLI or integration.

Important API behavior to preserve:

- concept IDs are normalized paths without `.md`;
- `catalog` and graph-related results are deterministically ordered;
- `query` performs exact metadata filtering and list containment;
- `show(..., include_body=False)` avoids loading body content into output;
- `compose` writes a temporary sub-bundle and `boundary.json`, never mutating
  source files;
- trust tier derives only from `verified`: no entries = `unverified`, non-human
  entries = `machine-confirmed`, any `human:` entry = `human-reviewed`;
- absent status defaults to `stable`;
- staleness begins exactly when `today >= stale_after`;
- unknown types/keys, missing optional fields, broken links, and missing indexes
  are tolerated and surfaced where relevant rather than causing bundle
  rejection.

## 3. Meaning of “cross-framework”

Cross-framework does not mean adding one class per popular agent library. It
means the dataset, execution contract, scoring, and result format are independent
of any agent framework.

The portable boundary is a normalized request/response protocol:

```json
{
  "protocol_version": "1",
  "case_id": "query.tags.revenue",
  "input": {"prompt": "Find revenue-tagged concepts."},
  "context": {"bundle_root": "/absolute/isolated/fixture"},
  "metadata": {"suite": "runtime", "timeout_seconds": 30}
}
```

```json
{
  "protocol_version": "1",
  "case_id": "query.tags.revenue",
  "status": "ok",
  "output": {"answer": "...", "structured": {}},
  "events": [
    {
      "type": "tool_call",
      "name": "okf.query",
      "arguments": {"tags": "revenue"},
      "result": []
    }
  ],
  "usage": {},
  "metadata": {"framework": "example", "model": "example"}
}
```

The final schema may refine this example, but it must remain versioned,
JSON-serializable, forward-compatible with unknown metadata fields, and capable
of representing timeouts and partial failures. Define limits for response size,
event count, and execution time.

The expected operation plan is evaluator-side data. Never place case plans,
expected answers, or other ground-truth expectations in a request sent to an
external subject adapter. The built-in reference subject may receive the plan
through an internal runner-only call because it is a deterministic fixture
executor, not an agent-under-test.

Required adapters:

| Adapter | Purpose | Portability |
|---|---|---|
| Python callable | Fast reference subject and Python integrations | Any Python framework via a thin wrapper |
| JSONL subprocess | Coding agents, CLIs, and other languages | Language/framework neutral |
| HTTP JSON | Remote services and deployed agents | Language/framework neutral |

Adapters normalize transport only. They must not contain scoring logic.

## 4. Case model and corpus

Each versioned case should include at least:

- stable ID, suite, description, and tags;
- input prompt/request and fixture reference;
- expected operation(s) and allowed alternatives;
- structured expectations (exact, subset, contains, set equality, regex, or
  predicate identifier—avoid executable code embedded in case data);
- hard invariants and optional rubric criteria;
- timeout and applicability metadata;
- case schema version and case content version.

Copy each fixture to an isolated temporary directory before a case runs. Hash
the source tree before and after execution, ignoring documented runtime outputs
such as `.cache/` and the designated compose directory. This distinguishes
allowed disposable artifacts from forbidden source mutation.

Start with a compact corpus (roughly 20–35 cases) selected for branch coverage,
not a large collection of paraphrases. Include:

1. positive skill-trigger requests involving OKF discovery/query/graph/trust;
2. negative requests unrelated to OKF, where invoking the skill is incorrect;
3. ambiguous Markdown-repository requests where the agent should inspect before
   assuming OKF;
4. exact structured outcomes for every public API/CLI operation;
5. v0.2 trust, status, staleness, bare-mapping `verified`, and legacy timestamp;
6. malformed and permissive-consumption cases;
7. graph/link/anchor/boundary cases;
8. compose safety and trust filtering;
9. stable ordering and repeated execution;
10. error paths: unknown concept, invalid filter, timeout, malformed subject
    response, and one case failure not aborting the run.

If existing fixtures cannot express a requirement, add the smallest focused
fixture rather than overloading an unrelated one.

## 5. Scoring contract

Evaluators are pure functions of case plus normalized response wherever
possible. They return a common structure such as:

```json
{
  "name": "result_correctness",
  "value": 1.0,
  "data_type": "numeric",
  "applicable": true,
  "passed": true,
  "evidence": {"matched": ["bundles/acme_retail/metrics/revenue"]},
  "comment": "Exact expected concept ID found."
}
```

Rules:

- metric names and meaning are stable and documented;
- numeric quality scores use 0..1 with higher-is-better;
- latency is informational unless a threshold is explicitly configured;
- not-applicable is distinct from zero and excluded from aggregates;
- unexpected exceptions become categorized results, not runner crashes;
- task success is not inferred solely from fluent answer text;
- an agent answer cannot receive groundedness credit without inspectable tool or
  evidence events;
- deterministic facts use exact/structural checks, not an LLM judge;
- optional judge results are supplemental and non-gating by default.

Recommended hard gates for the initial baseline:

- 100% source safety;
- 100% deterministic replay cases;
- 100% protocol/schema validity;
- 100% core runtime golden cases;
- no case execution errors/timeouts in the reference subject;
- configurable aggregate threshold for agent behavior (do not hard-code a
  vendor/model-specific number in library code).

Baseline comparisons should fail only on configured regressions. Store enough
raw evidence to explain every failed gate.

## 6. Langfuse boundary

Langfuse is an optional reporter/observer. The local result artifact is
canonical; identical evaluator inputs must produce identical scores whether
Langfuse is enabled or disabled.

As of September 2026, current Langfuse guidance is:

- Python SDK v4 is the general-availability line and is OpenTelemetry-based;
- the SDK experiment runner accepts local or Langfuse-hosted datasets and
  supports item-level and run-level evaluators;
- datasets provide reusable inputs and expected outputs;
- experiments are intended for side-by-side comparisons and CI/CD regression
  checks;
- quality scores can be submitted through supported SDK/API mechanisms.

Official references (verify again while implementing):

- https://langfuse.com/docs/compatibility
- https://langfuse.com/docs/evaluation/overview
- https://langfuse.com/docs/evaluation/experiments/experiments-via-sdk
- https://langfuse.com/docs/evaluation/experiments/datasets
- https://langfuse.com/docs/observability/overview

Do not copy an obsolete Langfuse snippet from memory. Encapsulate SDK calls in a
small reporter module and test it behind a fake client so an SDK change has a
limited blast radius.

Configuration should use standard Langfuse environment variables supported by
the current SDK (commonly public key, secret key, and base URL/host) plus an
explicit OKF eval publish flag. Do not invent a second credential store. Missing
credentials mean offline mode or a clear configuration error only when the user
explicitly requested publication.

Publication mapping:

- one eval run -> one experiment/run identity;
- one stable case -> one dataset item/correlatable trace;
- subject execution -> trace/span with sanitized input/output and metadata;
- each local score -> corresponding Langfuse score with the same name/value;
- aggregate metrics -> run-level evaluation or run metadata as supported by the
  current SDK.

Always preserve local JSON if export fails. Mark publication status and error in
the run summary, flush on shutdown, and never put credentials into results,
traces, test snapshots, or exception strings.

## 7. Suggested module shape

This is a boundary recommendation, not a mandate on exact filenames:

```text
okf_runtime/evals/
  schema.py          # versioned dataclasses and validation
  cases.py           # load/validate/filter case data
  runner.py          # isolation, timeout, orchestration, aggregation
  scoring.py         # pure deterministic evaluators
  baseline.py        # comparison and gates
  redaction.py       # export sanitization
  adapters/
    callable.py
    subprocess.py
    http.py
    reference.py     # built-in subject using public OKF APIs
  reporters/
    json.py
    langfuse.py
```

Keep the built-in reference subject thin: it demonstrates the protocol and
exercises the existing public API; it must not duplicate runtime logic.

## 8. CLI and artifacts

A reasonable CLI shape is:

```bash
python -B -m okf_runtime.evals.cli cases validate
python -B -m okf_runtime.evals.cli cases list --suite runtime
python -B -m okf_runtime.evals.cli run --adapter reference --output .evals/results.json
python -B -m okf_runtime.evals.cli run --adapter subprocess --command '<wrapper command>'
python -B -m okf_runtime.evals.cli compare .evals/results.json --baseline <path>
```

Exact flags may differ, but automation must not require an interactive UI.
Result JSON must include schema version, run metadata, case results, scores,
aggregates, gates, errors, timing, publication status, and enough evidence for
diagnosis. Volatile fields must be separable so normalized replay comparisons
remain stable.

Ignore local result directories in Git. A reviewed baseline may be checked in
under a clearly named eval data directory if it omits secrets, absolute paths,
and volatile timestamps.

## 9. Test strategy

Unit tests:

- schema validation and compatibility;
- matching/evaluator semantics, including not-applicable aggregation;
- adapter success, malformed data, non-zero exit, HTTP error, timeout, and size
  limits;
- redaction and secret non-disclosure;
- baseline gate direction and threshold behavior;
- Langfuse mapping through a fake client with no network.

Integration tests:

- full local suite against the built-in reference subject;
- source tree unchanged except ignored outputs;
- one bad case/subject response does not abort remaining cases;
- deterministic normalized replay;
- subprocess wrapper round trip;
- CLI exit codes: success, regression, invalid configuration, and execution
  failure are distinguishable and documented.

Avoid flaky wall-clock assertions. Inject a clock for staleness-sensitive evals
or use fixture dates that remain unambiguous, while still separately testing the
exact boundary rule.

## 10. Out of scope for the first implementation

- requiring a specific commercial model or agent framework;
- provisioning or administering Langfuse;
- making network-backed or LLM-judge evals mandatory in CI;
- changing OKF format semantics;
- benchmarking model intelligence unrelated to correct use of the skill;
- moving existing runtime behavior into the eval package;
- a generalized distributed eval scheduler or web dashboard.

## 11. Definition of done

The implementation is complete when a contributor can clone the repository and,
without credentials or network access:

1. validate and list the versioned cases;
2. run the full reference suite;
3. obtain readable machine-parseable results and a correct process exit code;
4. reproduce normalized results;
5. test an arbitrary framework through a documented adapter contract;
6. compare against a baseline and see actionable regression evidence;
7. optionally publish the same run and score values to Langfuse by enabling the
   reporter and providing supported credentials.
