# Full original-source rule replay, common scope pending

The new `regression_x_full_v3.py` reuses the frozen v2 evaluator and historical
source proofs. It streams every one of the 15,879,477 original records, including
unassigned and excluded records. It does not sample, rerun geometry, screen the
PubChem raw source, change chemistry/unknown/isotope policies, or release final
training/expansion gates. The original 335 IDs are regression checks on the
frozen pilot subset; they do not restrict where the historical coalesce formula
applies in the full population.

The new plan binds the actual completed v2 pilot (4520376), its Root sacct
closure, its immutable plan/code pins, and its 175606-byte decision Parquet.
All historical v1 and diagnostic proofs remain bound. On completion, the full
result must contain exactly the unique original source ID set. Its 8741 pilot
IDs must match every boolean decision from v2 and the original v1 decisions,
including the exact 335 explained cohort.

Every full record stores ID, molecule ID, source family, 14 boolean decision
bits, five rule layers, and cause bits. Each X01–X05 layer is encoded in uint16
using two bits per rule: 0=false, 1=true, 2=unknown; 3 is reserved and rejected.
The layers are raw nullable, stored enriched, native raw, native enriched, and
portable graph. Parquet schema metadata and the receipt include the codebooks.
All mismatch details, including source pointer/SMILES and the separate raw and
cache comparisons, are saved in `all_mismatches.parquet` using ZSTD. No mismatch
count limit or detail sampling is applied.

Sixteen spawn workers execute the same immutable v2 semantics on 512-record
batches, with at most 32 tasks in flight. Each worker reports its actual PID
and processed-record count; all 16 must contribute. Per-worker exact-SMILES
LRU4096 is inherited unchanged. Source/native/geometry annotations are still
evaluated per record; molecule IDs are not used as blind chemistry cache keys.
Rows are stored by their unique record IDs in complete join-stream order,
without a new external full-population sort. Aggregation/check SQL uses 16
threads before/after the graph workers; the graph phase coordinator uses one.

The hard allocation is compute20, 16 CPUs, 32 GiB, four hours (at most 64 core
hours). The internal processing deadline is 3h50m. Total new disk is capped at
16 GiB: DuckDB spill <=8 GiB, artifact soft cap7 GiB, and 1 GiB reserved for
buffer flushes/footers/failure receipts. Memory is bounded by DuckDB8 GB, the
16 workers' fixed LRU caches, 32 bounded task batches, 65536-row Parquet buffers,
and mismatch buffers flushed at2048 rows or8 MiB uncompressed. The soft cap or
time limit stops the attempt and preserves partial artifacts with no full
coverage claim. Successful output verifies that every generated mismatch row
was stored. Fresh published quota <=300s old is required at start.

The four-hour request is a ceiling, not the wall-clock prediction. Actual
4520376 measured 61.6929s total: source SHA/join6.5824s, full-population
stratification/sort54.2934s, and graph-worker/output/check segment0.8170s. Full
execution does not repeat sampling/sorting; multiplying the complete61.6929s
by1816.67 would incorrectly repeat that fixed whole-pool scan and imply31.1h.
The measured graph segment linearly projects to1484s (24.7min). Independent
failed pilot4520357 measured2.0688s for its worker segment, projecting to62.6min.
Neither receipt reports pure RDKit-only timing. The 8741 pilot rows contain6034
molecule IDs (the frozen v1/v2 identity comparison proves the same IDs); the
original inventory reports1,778,229 molecule IDs. The stratified pilot's parser
failure, size distribution and cache locality do not represent the full pool.

A planning estimate is40–120min, with uncertainty from full compact encoding,
Parquet I/O, full-ID/molecule aggregation, cache and node/filesystem contention.
This is an inference, not a measured confidence bound. Actual cold source-pin
parallel hashing took246.95s while the hot pilot source stage took6.58s. Progress
is persisted every65536 rows with worker contributions, observed bytes, elapsed
time and mismatch count so Root can assess real throughput. No additional
global molecule-cache phase is needed to make the observed per-record pipeline
projections fit the four-hour cap.

Root prepares a fresh READY plan from
`configs/data_v1/expansion/x_full_regression_plan_template_v3.json`, fills
`code_sources`, and reviews the new request. Runtime code pins include the new
full runner, immutable v2/v1, common, data_authority, screen, source,
download_raw_v1, package init, and the new wrapper. All code/plan/history/closed
pilot proofs and the small source-pin receipt go in `request.source_references`.
The three GB source files go only in `request.data_references`; they are fully
SHA-verified on compute20 with same-node stable stat checks. Existing raw,
regression, STOP, and v1/v2 source bytes remain untouched.

CLI:

```bash
/share/home/zixiao/.conda/envs/chemprop/bin/python -B -m workflows.expansion.regression_x_full_v3 --plan NEW_READY_PLAN --root-submit-intent ACTUAL_NEW_INTENT
```

Wrapper exports: `EXPANSION_REPO`, `X_FULL_V3_PLAN`, `X_FULL_V3_ROOT_INTENT`.
Root alone submits Slurm. Only three incremental synthetic tests are needed:
`python -B -m unittest workflows.expansion.test_regression_x_full_v3 -v`.
The existing v2 suite is already accepted and need not be repeated.

The success state is only `FULL_X_RULE_PASS_COMMON_SCOPE_PENDING`. It requires
zero native/raw/enriched/metadata or unexplained mismatches and >=99.9% chemical,
fixed-geometry record and fixed-geometry molecule selection agreement. Common
population is explicitly unbound; `full_v1_selection_regression_passed` and
`final_training_or_full_expansion_gate_released` remain false. Root may review
the completed evidence before arranging the separate bounded raw prefix pilot.
