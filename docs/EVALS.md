# OKF Runtime Evaluations

Cross-framework evaluation harness for the OKF Runtime Agent Skill. Local JSON results are canonical; Langfuse is an optional observer.

## Quick start (offline)

```bash
python3 -B -m okf_runtime.evals.cli cases validate
python3 -B -m okf_runtime.evals.cli cases list --suite runtime
python -B -m okf_runtime.evals.cli run --adapter reference --output .evals/results.json
```

Exit code `0` means gates passed; `1` means a gate failed; `2` means invalid configuration or case data.

## Subject adapters

| Adapter | Flag | Purpose |
|---|---|---|
| `reference` | default | Built-in deterministic subject using `okf_runtime.api` |
| `callable` | `--target module:callable` | In-process Python integration |
| `subprocess` | `--command '...'` | JSONL stdin/stdout for any language |
| `http` | `--url https://...` | Remote agent service |

Subprocess example using the reference wrapper:

```bash
python3 -B -m okf_runtime.evals.cli run \
  --adapter subprocess \
  --command "python3 -B scripts/eval_reference_subject.py" \
  --output .evals/results.json
```

Third-party agents should accept the versioned `SubjectRequest` JSON documented in `prompts/evals/CONTEXT.md` and return `SubjectResponse` JSON with tool/evidence events.

Expected operation plans and ground-truth answers are never included in requests to external subjects; they remain evaluator-side data.

## Baselines

```bash
python3 -B -m okf_runtime.evals.cli compare .evals/results.json --baseline evals/data/baseline.reference.json
```

## Langfuse (optional)

Install optional dependencies:

```bash
python3 -m pip install -e ".[langfuse]"
```

Enable publication:

```bash
export OKF_EVAL_PUBLISH_LANGFUSE=1
export LANGFUSE_PUBLIC_KEY=...
export LANGFUSE_SECRET_KEY=...
export LANGFUSE_HOST=https://cloud.langfuse.com
python3 -B -m okf_runtime.evals.cli run --adapter reference --output .evals/results.json
```

Publication failures are recorded in `publication` on the result file and do not change local scores.

## CI

```bash
python -B -m unittest discover -s tests -p 'test_*.py'
python3 -B -m okf_runtime.evals.cli run --adapter reference --output .evals/results.json
```

See `prompts/evals/CONTEXT.md` and `prompts/evals/IMPLEMENT.md` for full requirements.
