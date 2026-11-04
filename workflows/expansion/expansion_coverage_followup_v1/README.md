# Fixed1M coverage and distribution continuation

The original taskbook at project top level, section2.1, requires full Common statistics and the same-rule
screened/internal-InChIKey-deduplicated random1M PubChem comparison, including exact ECFP4 nearest
coverage. Section2.9 requires separate R/N distributions against Common and PubChem, and coverage
after addition. Existing scientific coverage contracts make this comparison explicit: the identical frozen
PRE-decontamination1M query membership/order is reused; before is complete Common; after is that
Common as an exact byte/ordinal prefix followed by all2.5M actual first-batch graph rows. No UFF-success
filter is applied to the graph coverage. Identity-self and fingerprint-score-one cases remain in the sample
and are reported separately by the original coverage producer. No downstream features rank/select anything.

Actual reusable inputs (take exact pins from existing machine receipts, no future hashes):

-183 baseline: `/gfshome/alpha/pubchem_expansion_20261103/bulk/corrected_population_baseline1m_v2_job_1885183/receipt.json`.
-190 statistics: `/gfshome/alpha/pubchem_expansion_20261103/reports/corrected_baseline_Common_statistics_v1_job_1885190/counted_statistics.sqlite`
  (555991040B), with actual retained two-population manifests, all five logical tables each and original
  ten statistical/functional-group sources. Its existing source authority is
  `B/current_baseline_Common_statistics_1885190_root_actual_v1.json`; B is the actual Alpha runtime control.
-196 complete Common: `/gfshome/alpha/pubchem_expansion_20261103/exact/fullCommon_exact_v3_reference_before_job_1885196/manifest.json`.
-201 is running independently. Its actual plan is `PUBCHEM_EXACT_SCIENTIFIC_COVERAGE_PLAN_V1`,
  baseline183 is `EXPANSION_PUBCHEM_PREDECON_BASELINE_V1/COMPLETE`, sample_ordinal_ASC. The
  original producer exports `EXPANSION_EXACT_SCIENTIFIC_COVERAGE_V1/COMPLETE` only after complete
  fixed1M membership, cache-pending-zero and physical projection EOF; this is scientific coverage, not
  full candidate-pool release. No active201 SQL is read and its receipts/code are never modified here.
-Queued source217 supplies actual `source_manifest.json` and `augmentation_manifest.json` containing
  all2.5M original selected graph FP/scaffold/rings in frozen source order. They do not wait for UFF.

1. Pack after with the existing unchanged `workflows.expansion.exact_nn_cached_v1.pack_reference`
   `--plan PLAN --startup-proof PROOF`. Original plan schema `PUBCHEM_EXACT_REFERENCE_PACK_PLAN_V1`,
   reference_role=after, input_manifest=actual217 augmentation manifest, base_reference_manifest=actual196.
   It copies the exact original prefix and appends all2.5M rows, producing3696122 complete ordinals.
2. Run `workflows.expansion.expansion_coverage_followup_v1.coverage --plan PLAN --startup-proof PROOF`.
   Retain the original `PUBCHEM_EXACT_SCIENTIFIC_COVERAGE_PLAN_V1` fields, actual baseline183 and its
   existing historical authority, actual after reference, reference_role=after, actual native206 adoption
   as backend_adoption_reference, source/runtime/CPU/quota and explicit worker/parent memory budgets.
   The original coverage.run code object, sampleOrdinal ingestion/export and cache proof are unchanged;
   only its worker binding uses the new manifest-aware module. The worker calls the original compiled
   backend.load_reference and original production fixed_result. N is taken from the full before/after
   artifact; integer math, binary64 division, reference order and earliest ordinal ties are untouched.
   No new kernel, benchmark or per-job Root approval is introduced. Original attempt receipt remains;
   compiled_coverage_manifest.json records the actual wrapper/underlying receipt/source binding.
3. Prepare full R/N graph statistics using `...expansion_coverage_followup_v1.rn_populations --plan PLAN
   --startup-proof PROOF`. Schema PUBCHEM_RN_DISTRIBUTION_SOURCE_PLAN_V1, ordered_source_manifest_reference
   is actual217 source. Usual Alpha profile/Guard and SQL fields sql_memory_bytes,parent_rss_cap_bytes,
   spill_cap_bytes apply; keep spill<=4GB and source outputs in the actual private report budget.
   It follows actual ranking.batch1 and filtered candidate parts, joins all original fields by CID/fullkey,
   writes small typed FP-bucket feature parts and R/N population manifests (1.25M each). These are all
   selected graphs, not successful conformers. Original distribution enrichment computes only the same
   additive functional-group recipe; original graph descriptor values and screening decisions stay fixed.
4. Run `...expansion_coverage_followup_v1.report --plan PLAN --startup-proof PROOF` with schema
   PUBCHEM_DISTRIBUTION_FOLLOWUP_REPORT_PLAN_V1, report_scope=baseline or batch_graph, actual
   statistics_actual_review_reference=existing190 authority, before_coverage_reference=actual201 completed
   receipt. For batch_graph also supply actual after_coverage_reference and rn_population_sources_reference
   from step3. Include a fresh analysis_version, normal actual Alpha profile/quota and SQLite budgets,
   exact original190 statistical source namespace/pins, and this package in startup source refs.

The report clones both closed190 populations with the existing held-FD/read-lock/source-frame/hash and
five-table digest proof; it never uses the old clone that deletes1M. It bypasses baseline_population.prepare
and its legacy schema assumptions. It consumes actual complete scientific NN receipts directly and checks
their fixed183 sample, recipe/reference and real launcher lineage; there is no new NN Root-review field.
The original population/nearest/report functions generate v1_distribution.md or the complete graph report,
CSV/JSON/Parquet tables and PNG/PDF figures. Old Common/1M descriptors are not recomputed; both five-table
partitions must remain equal after NN and R/N ingestion. R/N graph statistics and coverage do not claim
UFF/D quality, actual generation success/cost or the final task2.9 batch report is finished; those existing
generation/quality artifacts must still be included in the final batch report. The user's max3/no-fill UFF
instruction and new exact-key-only decontamination policy remain unchanged.

## Direct two-phase allocated continuation

Source216 was replaced while PENDING because compute-local sacct could not reach localhost6819. The actual
replacement is217, tag `direct_completion_b2b2407_ordered_source`. The source references above now
mean the real217 outputs selected through its native epoch plan; no old output path or future SHA is reused.

`workflows.expansion.expansion_coverage_followup_v1.prepare_pipeline` prepares only `pack-after` and
`coverage-after`, then execs the existing `node_launcher_rpc_v3_resume.py`. Invoke inside an actual
sonmi1/cpu16 allocation with actual isolated Alpha Python and the immutable layer entry:

```
...prepare_pipeline --phase pack-after --config CONFIG --entry ENTRY --tag AFTER_PACK_TAG
...prepare_pipeline --phase coverage-after --config CONFIG --upstream-job ACTUAL_PACK_JOB --upstream-tag AFTER_PACK_TAG --entry ENTRY --tag AFTER_COVERAGE_TAG
```

Config fields are pinned `resources_reference` (current resource template), `deployment_reference`
(current immutable deployment containing these helpers), `coverage_template_reference` (the actual201
plan, only its JSON is read), `before_reference_manifest` (actual196), `backend_adoption_reference`
(existing206), and `source_job_id="1885217"`, `source_tag="direct_completion_b2b2407_ordered_source"`.
Optional `runtime_profile_reference` and `reviewed_storage_budget_reference` replace old template pins
with the current actual profile/budget. `background_scope_exclusions` may declare other live exact
scopes;201's output directory is always added without walking its files. For coverage, an actual pack
job/tag may alternatively be supplied as config `pack_job_id`/`pack_tag`. No future job ID or artifact
hash is generated. Optional launcher/control/python/base/RPC CLI paths follow the existing UFF helper.

Both phases reuse existing UFF `upstream`/`terminal_account` and require native completed0:0 parents,
using exactly `['ssh','-n','-o','BatchMode=yes','-o','ConnectTimeout=5','218.192.171.238','sacct']`.
There is no compute-local sacct fallback, Root acceptance file, Slurm submission or background watcher.
The source phase reads217's actual `node_epochs/TAG_job_1885217/plan.json` and startup, follows its actual
output_directory and pins the closed source/augmentation manifests. Coverage follows the actual pack
epoch, checks the complete3696122-row reference and exact196 prefix, then pins that closed manifest.
Its original201 sample/ingestion/query settings remain unchanged while role/reference, current immutable
source pins and206 compiled worker adoption change to the actual after reference.

Each phase owns a separate private child of the actual exact aggregate, cap4_000_000_000 bytes.
The existing `source_reservations` measures actual closed outer blocks, explicitly excludes201, and
keeps the whole current exact/future budget. Both plans use16 workers,2GiB/worker,8GiB parent,48GiB
process-tree software budget,24GiB available-memory reserve and256MiB SQLite cache. Pack and coverage
are dependency ordered; together their declared active-file allowance is at most8GB, and neither
modifies201's Guard or SQLite. The one scheduling fixture checks preserved baseline/reference selection,
the real module dispatch, resource partition and mandatory RPC command without running a launcher,
accounting query or scientific computation.

## Three allocated report continuations

The new `workflows.expansion.expansion_coverage_followup_v1.report_pipeline` supports only
`baseline-report`, `rn-populations`, and `batch-graph-report`. It builds an actual input plan inside
the16CPU allocation and execs the existing NodeLauncher; it never calls sbatch or creates a Root review.
The existing report.run, rn_populations.run and all original statistics sources remain unchanged.

```
...report_pipeline --phase baseline-report --config CONFIG --entry ENTRY --tag BASELINE_TAG
...report_pipeline --phase rn-populations --config CONFIG --entry ENTRY --tag RN_TAG
...report_pipeline --phase batch-graph-report --config CONFIG --upstream-job ACTUAL_RN_JOB --upstream-tag RN_TAG --entry ENTRY --tag BATCH_TAG
```

`--upstream-job/tag` optionally replaces the phase's primary dependency: before201 for baseline,
source217 for RN, actual RN preparation for batch graph. Baseline requires actual201 C0 and exactly
one original `attempt*.receipt.json` matching its real plan/startup and complete scientific fixed1M
EOF/reference/membership. RN requires actual217 source C0 and does not wait for201; it reads only201's
plan/startup to exclude its files from budget credit. Batch graph requires actual201, after223 and RN
C0, selects `compiled_coverage_manifest.json` and actual RN `manifest.json`, and feeds those real pins
to the unchanged reporter. No phase opens201 SQLite. All accounting uses the existing explicit SSH
RPC to Alpha login sacct; the compute-local command is never used.

Config requires `resources_reference` (actual190/current runtime template), `deployment_reference`
(alias `source_deployment_reference`), `baseline_budget_reference` (current original global budgetV3),
`before_job_id`/`before_tag`, and optional current `runtime_profile_reference`. RN additionally needs
`source_job_id`/`source_tag`; batch needs `after_job_id`/`after_tag` and `rn_job_id`/`rn_tag` unless the
RN dependency is passed on CLI. Real jobs/tags are supplied after submission; no future hashes exist here.
`statistics_actual_review_reference` defaults to the actual190 authority in B. Its original ten-source
references must be present in the immutable deployment and resolve to the same statistics_cache capsule.
`closed_allocation_sources=[{job_id,tag,scope},...]` declares actual closed filter/NN/source/report
allocations such as209; optional existing `closed_allocations` bindings are reused. The helper also adds
the phase's closed source217, after223 and RN dependencies to their exact/reports scopes. Actual201 is
always excluded, even after terminal state; its C0 remains a data dependency, not a block-credit claim.

Existing budget.census/inline stat native closed blocks with actual C0 bindings, without whole-DATA
SHA reads. The unchanged total reports cap is5GB. `private_caps_bytes` may override each phase's cap;
defaults are1_500_000_000 for baseline and RN. Batch cap is min(configured upper cap, actual remaining
reports reservation). Other-future reserve is all other scope remaining plus reports remaining minus
this private cap. New output_scope_root is a fresh private reports/TAG child. Insufficient actual budget
or output capacity fails normally and preserves partials; populations are never sampled, trimmed or
truncated to fit. Future practical cap adjustments belong in the real resource config/global budget.

Plans use16 workers,48GiB tree RSS,1GiB SQLite cache,32GiB SQL memory,40GiB parent allowance,
24GiB available reserve and spill<=min(2GB, private cap). No node is hardcoded: Root's actual profile
and Slurm request select baseline compute-0-1/cpu or the other phases sonmi1/cpu. Baseline and batch
get separate analysis_version values; optional `analysis_versions` must keep those phases distinct.
The one scheduling/reference fixture checks scientific receipt selection, no SQLite dependency,
budget remaining arithmetic and all three original module dispatches; it runs no native accounting,
census, launcher or scientific computation.
