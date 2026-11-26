# Contributing

Principles

- Deterministic algorithms over LLM reasoning
- Keep dependencies minimal
- Backward-compatible CLI
- Library API first
- No feature should require MCP
- No feature should require a database
- Prefer composable small modules over monolithic classes

Pull requests should include

- tests

- documentation

- performance considerations

- rationale

## Evaluation changes

Evaluation changes should keep the core runtime dependency-free and the subject
protocol framework-neutral. Expected outputs and operation plans remain
evaluator-side data and must not be exposed to external subjects. Contributions
should include offline tests, case-data rationale, artifact/privacy
considerations, and performance implications for adapters, timeouts, and
response-size limits.
