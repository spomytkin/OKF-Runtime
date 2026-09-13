---
type: Concept
title: Trust and Provenance
description: Using verification, lifecycle, freshness, and source metadata to select an appropriate knowledge artifact.
tags: [trust, provenance, lifecycle]
status: stable
stale_after: 2028-01-01
generated:
  by: human:spomytkin
  at: 2026-03-14T00:00:00Z
verified:
  by: human:ahormati
    at: 2026-03-15T00:00:00Z
sources:
  - id: okf-spec
    resource: okf_spec.md
    title: Open Knowledge Format
---

# Trust and Provenance

Trust is not equivalent to a filename. A retrieval system should inspect explicit lifecycle, verification, and freshness metadata when choosing among competing artifacts.

The [Open Knowledge Format](okf_spec.md) supports provenance and verification metadata that can be used for this purpose.
