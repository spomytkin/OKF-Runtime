---
type: Concept
title: Open Knowledge Format (OKF)
description: A lightweight, human- and agent-friendly specification for organizing structured knowledge using Markdown and YAML frontmatter.
tags: [okf, specification, metadata]
status: stable
stale_after: 2027-12-31
generated:
  by: human:spomytkin
  at: 2026-01-10T10:00:00Z
verified:
  - by: human:ahormati
    at: 2026-02-01T12:00:00Z
sources:
  - id: okf-spec-v02
    resource: https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md
    title: OKF v0.2 Authoritative Specification
    author: GoogleCloudPlatform
    last_modified: 2026-01-01
---

# Definition

The **Open Knowledge Format (OKF)** standardizes directory-based Markdown repositories using lightweight, self-describing conventions.

Key features include:
* **Permissive consumption**: missing optional fields or broken links do not necessarily prevent ingestion.
* **Provenance and trust**: documents can surface creation and verification events.
* **Agent portability**: OKF content can be consumed by AI agents and deterministic tooling.

Per the [OKF v0.2 Authoritative Specification](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md), Markdown files remain the source representation for the knowledge.
