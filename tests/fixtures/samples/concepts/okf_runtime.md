---
type: Architecture
title: OKF Runtime Engine
description: A lightweight Python engine for deterministic discovery, graph traversal, trust evaluation, and composition of OKF repositories.
tags: [runtime, deterministic, python]
status: stable
stale_after: 2027-01-01
generated:
  by: human:spomytkin
  at: 2026-03-01T00:00:00Z
verified:
  - by: human:spomytkin
    at: 2026-03-02T10:00:00Z
sources:
  - id: okf-runtime-repo
    resource: https://github.com/spomytkin/OKF-Runtime
    title: OKF-Runtime Source Repository
---

# Architecture

**OKF Runtime** offloads deterministic retrieval work from LLMs into standard local code.

Instead of spending model context reading directory trees or extracting YAML, the runtime performs deterministic operations:

* **Bundle scanning and parsing**: discovers and parses OKF documents.
* **Graph construction**: generates forward links, backlinks, and neighborhoods.
* **Trust and lifecycle derivation**: evaluates status, verification, and staleness metadata.
* **Bundle composition**: constructs temporary sub-bundles for topic-focused agent contexts without mutating original sources.

The runtime is designed to fulfill retrieval requirements of the [Open Knowledge Format](okf_spec.md) and interface cleanly with [Agent Skills](agent_skills.md).
