---
type: Attested Computation
title: Validate OKF Bundle Conformance
description: Deterministically checks frontmatter parseability and link consistency across a target bundle.
tags: [computation, validation, lint]
status: stable
runtime: python
parameters:
  - name: bundle_path
    type: string
    required: true
executor:
  resource: scripts/okf.py
  receipt: [status, scanned_files, error_count]
attester:
  resource: ../../../tests/test_trust.py
generated:
  by: process:ci-builder
  at: 2026-03-05T12:00:00Z
sources:
  - id: okf-min-spec
    resource: https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md
    title: OKF Conformance Checklist
---

# Computation

This computation describes the deterministic validation operation used by the runtime.

The `executor.resource` points to the runtime's executable boundary; the sample does not assume that this fixture itself is the repository root.
