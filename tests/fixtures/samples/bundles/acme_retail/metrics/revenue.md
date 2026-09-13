---
type: Metric
title: Revenue
description: Acme Retail recognized revenue metric.
tags: [revenue, metric]
status: stable
stale_after: 2027-12-31
generated:
  by: reference_agent/gemini-2.5-pro
  at: 2026-06-30T14:00:00Z
verified:
  by: human:analyst
  at: 2026-07-01T09:00:00Z
sources:
  - id: revenue-policy
    resource: ../policies/revenue-recognition.md
    title: Revenue recognition policy
    author: human:controller
    usage_count: 12
    last_modified: 2026-06-15
usage_window:
  from: 2026-01-01
  to: 2026-06-30
executor:
  resource: skills/run.md
  receipt: [job_id]
attester:
  resource: ../../../tests/test_trust.py
---

# Revenue

The metric is based on the current [Revenue Recognition Policy](../policies/revenue-recognition.md).
