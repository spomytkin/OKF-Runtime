# OKF Runtime Canonical Sample Corpus

This directory is the combined canonical sample corpus for OKF Runtime.

It is intentionally small but semantically dense. It exercises:
- deterministic discovery and cataloging
- metadata queries
- forward links and backlinks
- graph traversal beyond one hop
- bundle composition and boundaries
- trust, verification, lifecycle, and staleness
- cross-bundle references
- broken, external, and orphan links
- ambiguous versions of the same business concept

The `concepts/` directory is the explanatory OKF Runtime sample bundle.
The `bundles/` directories provide realistic multi-bundle retrieval data.
The `edge-cases/` directory contains deliberate negative/boundary cases.
