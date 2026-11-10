# AEGIS AI evaluation

This directory contains versioned, reviewable regression scenarios. The runtime evaluator in
`aegis_ai.evaluation` checks deterministic output properties: evidence references, required
content, forbidden claims, uncertainty language and advisory-only language. It makes no claim
that keyword checks establish factual correctness or replace analyst review.

## Running

From `services/ai`:

```bash
python -m pytest -q
python -m ruff check src tests
```

## Dataset contract

`dataset.json` records specialist, evidence IDs, required/forbidden phrases and safety
expectations. Dataset changes require review alongside prompt/model changes. Future model-backed
evaluations should add expert-labelled expected findings, false-positive/false-negative scoring,
provider/model metadata, and reproducible fixtures. Do not send customer telemetry to a shared
evaluation service or use it for model training without explicit authorization and privacy review.

## Release gate

Critical safety failures (unsupported compromise claims, missing required provenance, or claims
of executed production actions) are release blockers. A passing deterministic suite is a minimum
regression gate, not a declaration of 95% real-world AI accuracy.
