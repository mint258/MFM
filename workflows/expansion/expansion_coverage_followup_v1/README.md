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
-Future source216 supplies actual `source_manifest.json` and `augmentation_manifest.json` containing
  all2.5M original selected graph FP/scaffold/rings in frozen source order. They do not wait for UFF.

1. Pack after with the existing unchanged `workflows.expansion.exact_nn_cached_v1.pack_reference`
   `--plan PLAN --startup-proof PROOF`. Original plan schema `PUBCHEM_EXACT_REFERENCE_PACK_PLAN_V1`,
   reference_role=after, input_manifest=actual216 augmentation manifest, base_reference_manifest=actual196.
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
   is actual216 source. Usual Alpha profile/Guard and SQL fields sql_memory_bytes,parent_rss_cap_bytes,
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
