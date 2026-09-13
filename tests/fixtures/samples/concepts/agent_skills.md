---
type: Concept
title: Agent Skills Specification
description: Standardized directory layout and format for providing AI agents with reusable capabilities.
tags: [agent, skills, standard]
status: stable
generated:
  by: process:skills-generator
  at: 2026-02-15T08:30:00Z
verified:
  by: human:spomytkin
  at: 2026-02-20T14:00:00Z
sources:
  - id: skills-io
    resource: https://agentskills.io/specification
    title: Agent Skills Open Specification
---

# Overview

The **Agent Skills Specification** standardizes how AI agents discover and invoke reusable capabilities.

## Integration with OKF

An agent tool repository can be packaged both as an Agent Skill and an OKF knowledge bundle:

1. **`SKILL.md` root wrapper**: informs the agent how to invoke executable tooling.
2. **Library-first runtime**: underlying tools such as [OKF Runtime](okf_runtime.md) execute deterministic operations outside the model's context window.

This separation keeps business logic decoupled from agent instructions.
