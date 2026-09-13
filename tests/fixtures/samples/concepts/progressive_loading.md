---
type: Concept
title: Progressive Loading
description: Loading only the information required for the current agent task instead of reading an entire knowledge repository.
tags: [agents, context, retrieval]
status: stable
generated:
  by: human:spomytkin
  at: 2026-03-10T00:00:00Z
verified:
  by: human:spomytkin
  at: 2026-03-11T00:00:00Z
sources:
  - id: okf-runtime
    resource: ../concepts/okf_runtime.md
    title: OKF Runtime Engine
---

# Progressive Loading

Progressive loading reduces irrelevant model context by discovering metadata first, then retrieving only documents and graph neighborhoods required for the task.

The [OKF Runtime Engine](okf_runtime.md) supports this pattern through catalog, query, graph, and compose operations.
