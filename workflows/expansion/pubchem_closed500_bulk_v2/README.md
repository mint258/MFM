# Restartable closed500 bulk materialization v2

This package consumes the existing formally closed 500 logical PubChem units
(502 immutable physical Parquet fragments, 124,857,440 rows). It does not invoke
RDKit, recalculate any molecular feature, or replay all old journals again.
Every original Arrow field and binary64 value is preserved. Only `cid` (parsed
from its exact source decimal text) and a source fragment locator are added.

The old `1885120` SQLite database, old source, intent, and failed parent evidence
remain untouched. That database cannot be safely resumed by fragment because
its interleaved committed rows have no durable per-fragment completion ledger.

Each physical fragment is streamed in bounded Arrow batches. A same-FD forward
SHA frontier covers every source byte once despite Arrow's seek reads. Exact
original schema, contiguous source ordinals, row counts, and all three category
counts must match the formal coverage. First/overlapping chemical rule and
technical-reason counts are also retained. A new attempt's accepted Parquet is
closed and hashed before an atomic `complete.json` is published. Resuming
validates and reuses completed units, retaining interrupted attempts separately.
No temporary output is promoted merely because it exists.

DuckDB performs the original full-InChIKey/minimum-CID selection in external
bulk SQL. All 110,046,364 accepted CID aliases survive in a separate Parquet.
Actual exported counts, candidate key/CID uniqueness, and the minimum CID
against all aliases are checked. Original JSON payload text is never decoded
or rewritten; no floating arithmetic is applied to original columns. Failed
merge attempts are retained separately; complete per-fragment work is reused.

The output status is `MATERIALIZED_UNFILTERED_NO_RELEASE`. This is not an
all-source exclusion, novelty ranking, final candidate release, or training
release. The 46,201 technical UNKNOWN rows remain distinct from chemical
exclusions, with original source locators retained.

Dependencies: Python 3.10+, PyArrow 17, DuckDB. Root provides actual cluster
allocation, storage and memory reservations. There is no arbitrary application
wall-clock/repair-count limit. Actual resource limits of a Slurm allocation
still apply; restarts use the durable units. The CLI refuses data work outside
a compute host/allocation and workers above actual affinity/CPU resources.

Commands from the repository root:

```sh
python -m workflows.expansion.pubchem_closed500_bulk_v2 prepare \
  --coverage EXACT_COVERAGE_JSON --plan FRESH_PLAN_JSON --output FRESH_OUTPUT_ROOT \
  --workers ACTUAL_CPUS --output-cap-bytes ROOT_REVIEWED_OUTPUT_BYTES \
  --minimum-free-bytes ACCOUNT_FLOOR_BYTES \
  --other-future-reserved-bytes ALL_OTHER_FUTURES \
  --duckdb-memory-bytes REVIEWED_WORKING_MEMORY
python -m workflows.expansion.pubchem_closed500_bulk_v2 run --plan FRESH_PLAN_JSON
```

`prepare` reads only small metadata and original coverage references. `project`
and `merge` can also be run separately. Root submits and records actual parents;
this package does not manufacture accounting or auto-submit replacement jobs.

Verification tests use synthetic data to exercise duplicate full keys with a
smaller CID arriving later, chemical rejects, technical UNKNOWN, exact original
JSON and float64 bytes (including signed zero), valid resume, corrupt source
SHA, changed checkpoint body and ordinal discontinuity. Run them on the server:

```sh
python -m unittest workflows.expansion.pubchem_closed500_bulk_v2.test_bulk
```

These fixture tests do not establish production completion. Production receipts
and actual parent terminal state are required for the real unfiltered pool.
