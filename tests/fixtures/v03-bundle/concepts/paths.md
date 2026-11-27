---
type: Concept
title: Path fields
description: Relative, /-rooted, %20, case-mismatch, out-of-root and bare-root-only path fields.
resource: target.md
sources:
  - id: root-target
    resource: /shared.md
  - id: bare-root-only
    resource: shared.md
  - id: pct
    resource: my%20file.md
  - id: case
    resource: TARGET.md
  - id: outside
    resource: ../../outside.md
executor:
  resource: target.md
status: stable
---

# Path fields
