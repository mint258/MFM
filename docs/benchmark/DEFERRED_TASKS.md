# Deferred benchmark endpoints — scope note

- Decision date: **2026-11-19** (owner request, before B1 model-based task selection).
- **5 distinct benchmark endpoints** are deferred from the current B1 task-screening stage and all subsequent B2–B4 evaluations.
- Exact endpoint identities are intentionally **not recorded in this repository**. A separate owner-controlled private mapping is retained for a possible later independent study.
- The active inventory must apply `configs/benchmark_data/B1.deferred_tasks.json` using `workflows/benchmark_data/task_selection.py` before fitting any baseline or calculating endpoint averages.
- Treat source groups independently: **retain all other endpoints from the same sources**. Do not remove entire source groups.
- Previously acquired B0 source archives, domain counts, source files, original row identifiers, data lineage, official splits and QA evidence remain immutable. Historical B0 totals are *not* counts of active B1 tasks.
- Validate the full candidate inventory with `verify_full_inventory=True`. A mismatch blocks benchmark task selection; do not silently ignore or reinterpret an unmatched digest.
- Do not use these deferred endpoints for task selection, downstream scoring, final tables, or model comparisons in the current study. Do not claim that they failed a model-based scientific screening.
- Reactivation requires a separately approved study and revalidation of exact source identities. Do not amend historical source manifests to simulate their removal.
- The scientific scope change must be disclosed accurately when writing the paper; an internal opaque registry is not a substitute for appropriate public methodology disclosure.
