# First-batch report composer

This is a bounded metadata-only composer for task2.9. It never opens the2.5M
molecule directories, large Parquet catalogs, active SQLite or scientific DATA;
it neither recalculates chemistry/statistics nor introduces a Root approval job.
Missing/incomplete actual evidence is an error, never a placeholder completion.

Run in the actual server environment after all required producers are terminal:

```sh
python -m workflows.expansion.batch1_report_v1.compose \
  --config ACTUAL_CLOSED_REPORT_CONFIG.json \
  --output-directory FRESH_REPORT_DIRECTORY
```

Publish the resulting `batch1_report.md`, `batch1_report.json` and copied
`batch1_figures/` together under `docs/expansion/` using the coordinator's normal
publication workflow. The composer never writes a repository by implication.
Large table/catalogs remain pinned external references, without a new body read.
Every input/copy is at most16MiB, SHA checked with one stable regular-file FD and
before/after path frame. An explicit `replicas` list can map an original
`source_reference` to an actual `replica_reference` only with identical bytes/SHA;
origin paths/proofs remain unchanged. No implicit path or basename rewriting.

The config schema is `PUBCHEM_BATCH1_REPORT_CONFIG_V1`. `inputs` must contain
actual path/bytes/sha256 references for exactly these existing producer objects:

| Key | Actual existing producer object |
|---|---|
| registry | Canonical decontamination source registry (`decontamination_sources.json`); provenance only, no specific schema/relabeling |
| acquisition | `PUBCHEM_ACQUIRED_SOURCE_SNAPSHOT_V1` official complete acquisition/EOF snapshot |
| funnel | `PUBCHEM_CLOSED_SCREENING_FUNNEL_V1` from complete502 closed fragment metadata |
| pool | Sealed `PUBCHEM_EXACT_MINCID_OVERLAY_POOL_V1` corrected population authority |
| regression | Actual195-style `ALPHA_COMMON_SELECTION_REGRESSION_BIND_PRODUCER_V1` with passed comparisons |
| filtered | Current complete `PUBCHEM_EXACT_KEY_FILTERED_SHARDS_V1`, never the old composition policy |
| novelty | Complete `PUBCHEM_SHARDED_FULL_POOL_NOVELTY_V1` aggregate, not SHARD_COMPLETE |
| rank | `expansion_nested_queues_v1`, original full10M ordering |
| source | Actual complete `PUBCHEM_UFF3_ORDERED_SOURCE_MANIFEST_V1` |
| graph | `PUBCHEM_DISTRIBUTION_FOLLOWUP_REPORT_V1`, full batch_graph scope, not baseline-only |
| closure | Full `PUBCHEM_UFF3_CANDIDATE_STORAGE_CLOSURE_V1` including finalizer report_metrics |
| quality | Full original `PUBCHEM_UFF3_VALIDITY_REVIEW_V1` |
| pilot | Actual completed original10k pilot allocation receipt bound to the same source/recipe |

Optional `reference_bindings` entries `{input,pointer,equals_input}` assert
additional original field-to-reference provenance without changing producer
schemas. The ordered-source→rank→filter→pool/novelty, graph R/N→ordered-source,
before/after identical1M, finalizer→source/QA, exact-only policy, source mass,
UNKNOWN and original mask bindings are checked directly. The original graph
report already establishes the complete comparison recipe and scientific tables;
this composer reuses those results rather than executing another comparison.

`accounting_inventory_reference` pins an ordinary machine inventory (not an
approval): `{inventory_complete_for_declared_goal_scope:true,coverage_statement,
parents:[{endpoint,uid,job_id,stage,disposition,accounting_reference}]}`.
Disposition is adopted/failed/superseded/cancelled/diagnostic. Include all relevant
original, resumed, failed and superseded goal parents, including Main/Alpha work;
do not restrict costs to successful current layers. Each accounting document has
the actual endpoint/UID and either `raw_sacct` text or a `raw_sacct_reference`.
The native pipe-delimited header must include JobIDRaw,State,ExitCode,UID,
ElapsedRaw,AllocCPUS,TotalCPU. Acquire missing fields from native sacct; never infer
them from wall time, configured workers, TotalCPU or kernel clocks. All parents
must be terminal; adopted parents require COMPLETED0:0. Steps are excluded from
allocation sums, and duplicate inventory parents are refused. Pending cancellations
can have actual zero allocation. Missing TotalCPU remains unavailable, not zero.
Accounting completeness is explicit for this declared goal inventory, not a
claim to independently discover every unrelated scheduler job.

`producer_accounting_bindings` connects each actual adopted producer reference
to its terminal inventory row: `{producer_reference,endpoint,uid,job_pointer}`.
For old receipts without a job ID (NN partitions), instead supply
`startup_proof_reference` and `plan_pointer`; the proof's exact producer-plan pin
must match the receipt before its actual job ID is used. The required set covers
regression/filter/rank/source/graph/finalizer/QA/pilot, both actual NN partition
manifests, all generation receipts and before/after scientific coverage receipts.
One physical parent may legitimately produce multiple required artifacts; its
native allocation is still counted once. No new Root acceptance schema is used.

Output includes chemical first-failure and overlapping counts separately,
technical UNKNOWN before/after accepted-only recovery, minCID aliases, exact
decontamination/source dispositions, complete population and exact coverage
results, delivery0/1/2/3/UNKNOWN, source states/QA masks and error catalog pointers,
actual measured native/worker clocks, allocation costs and measured storage.
Only the original finalizer's variable UFF/D dataset10M extrapolation is reused;
fixed/shared NN/calibration/QA/finalizer costs are not multiplied4×. No rate is
invented for unmeasured legacy calls and no training release is asserted.
The selected actual10k pilot allocation is divided by all10,000 source molecules,
including failure/sparsity, and multiplied250 for an explicitly rough2.5M cost
forecast. Comparable balanced R/N size/throughput is assumed; startup/I/O overhead
amortization may differ. Actual full allocation costs remain authoritative. A
matching finalizer producer-job group is reused for optional pilot delivery bins,
known retained conformers and measured native wall-time averages. Partial groups
or timing coverage are labelled; UNKNOWN or unmeasured quantities are unavailable,
not zero. No extra reads or completion gates are added for these optional metrics.
Native TotalCPU00:00 is an accounting observation, not proof of zero actual CPU.

One Main20 standard-library fixture exercises the real metadata validator and
native cost parser, rejects baseline-only graphs and erased UNKNOWN, counts
failed allocations, distinguishes TotalCPU and allocated time, avoids step double
counting and rejects changed bytes. It does not certify large DATA or actual jobs:

```sh
python -m unittest workflows.expansion.batch1_report_v1.test_compose -v
```
