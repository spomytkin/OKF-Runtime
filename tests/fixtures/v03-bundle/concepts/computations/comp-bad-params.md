---
type: Attested Computation
title: Bad parameters
runtime: python
computation: calc.py
parameters:
  - type: integer
  - name: nameless-type
  - name: ok
    type: string
attester:
  resource: attest.py
status: stable
---

# Bad parameters

Entries missing name or type are ignored with a warning.
