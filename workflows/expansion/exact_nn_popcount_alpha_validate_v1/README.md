# Guarded Alpha popcount validation benchmark (source-only harness)

This separate package leaves all original exact code and the prototype Core5
pinned sources unchanged. It creates neither production worker wiring nor an
adoption authority. Source-only delivery does not mean a compiler, tests or full
reference comparison have run. Root alone deploys, admits, builds and submits.
The standalone prototype build CLI is NOT a NodeLauncher target; this harness
calls its existing build.build(/usr/bin/gcc, own_stage/build) function directly.

## Metadata collector (no large-body hashing or computation)

Use the actual accepted Root200/196/183 review files, not placeholder receipts:

```text
ENTRY workflows.expansion.exact_nn_popcount_alpha_validate_v1.inputs --profile-review B/fullCommon_profile64_1885200_root_actual_v1.json --reference-review B/fullCommon_exact_reference_1885196_root_actual_v1.json --baseline-review B/corrected_baseline1m_1885183_root_actual_v1.json --output ABS_FRESH_INPUTS_JSON
```

The collector checks each real Alpha C0/accounting/raw-sacct source, all source
review schemas/statuses, receipt→historical plan/startup bindings, complete
reference metadata1196122 including repaired119, complete corrected1M baseline,
ordered historical64 FP bindings and16 full-reference workers. It extracts actual
refs for profile200's receipt/plan/startup/measurements, accepted196 manifest and
183 baseline, plus all original engine/cache/run/workers/math9/profile source
references found in the actual200 plan. Duplicate paths are permitted only for
identical bytes/SHA. No future build hash or fake terminal proof is constructed.

Collector output schema ALPHA_POPCOUNT_NATIVE_VALIDATION_INPUTS_V1 has status
METADATA_BOUND_NO_NEW_BUILD_OR_COMPUTE. Bind its actual triple in inputs_reference.
Its role fields are profile_review_reference/reference_review_reference/
baseline_review_reference/historical_receipt_reference/historical_plan_reference/
historical_startup_reference/historical_measurements_reference/
historical_native_math9_reference/
reference_manifest_reference/baseline_receipt_reference/original_source_references.
Re-collection inside the Guard must produce the same exact document.

## Root-bound actual validation plan and launch

```text
ENTRY workflows.expansion.exact_nn_popcount_alpha_validate_v1.test_metadata -v
ENTRY workflows.expansion.exact_nn_popcount_alpha_validate_v1.run --plan ABS_BOUND_PLAN --startup-proof ABS_STARTUP
```

Required new plan fields:

- schema ALPHA_EXACT_POPCOUNT_VALIDATION_PLAN_V1
- scope_key popcount_cpp_validation_v1; inputs_reference collector actual triple
- real Alpha runtime_profile_reference/quota_snapshot/quota_authority;
  endpoint218.192.171.238:22, uid1264 and actual launcher execution_argv
- workers16, worker_rss_cap_bytes2147483648, parent_rss_cap_bytes8589934592,
  software_rss_budget_bytes42949672960, minimum_node_available_bytes25769803776
- reviewed_storage_budget_reference actual Root budget (v3 currently retains
  ROOT_ALPHA_ALL_FUTURE_STORAGE_BUDGET_V2 schema); read its actual reports
  other-future reserve, not the obsolete numerical value from an older plan
- shared reports output_scope_root=/gfshome/alpha/pubchem_expansion_20261103/reports,
  output_cap_bytes5000000000, minimum_free_bytes200000000000;
  fresh private output_directory assigned by launcher
- code_references + actual startup source_references include every harness and
  prototype .py, kernel.c, actual guarded entry, and imported original six source
  modules. Source paths may relocate; actual body bytes/SHA must match historical
  source origins, which remain explicitly recorded. Never fall through Base497
  old engine. Keep Root prototype/exact_Common_b817ce7 namespace ordering.

profile.admit and allocation_guard check actual16CPU,40GiB software tree allowance
plus24GiB available-node reserve without inventing SBATCH memory reservation.
The unchanged Alpha Guard monitors actual tree RSS/quota/future floor. Original
parent RSS cap is checked separately around stages. No arbitrary timeout/retry
or job cancellation is introduced. The driver redirects TMPDIR to its own stage,
so compiler/test temporary output is counted; original small-suite files remain
small. Both temporary environment settings are restored on exit.

## Actual stages and precise scope

1. Guard begins before input/data verification. Strict startup proof checks Alpha
   UID/endpoint/job/boot, actual plan pin/scope/argv and every imported source pin.
2. Build prototype explicitly with actual gcc; keep build flags/ABI/CPU/library/
   binary provenance. Constructor/build imports remain lazy before this stage.
3. Run prototype8 tests then unchanged math9 as separate guarded-entry subprocesses.
   Actual suite count must match; failures, errors or skips fail the producer.
   Their independent receipts explicitly say SMALL_BOUNDARY_SUITE_ONLY.
4. Use original accepted-reference/baseline validators. Parent hashes full FP and
   key bodies; complete fixed1M projection/membership are verified by original
   baseline contract. Membership Parquet metadata must contain1M rows. Exact
   ordinals0..63/CID/fullkey match its selected64 rows, historical200 fingerprint
   SHAs and historical ordered identity digest. No query is substituted/dropped.
5. Spawn16 workers with two barriers. Every worker loads BOTH full1196122 private
   references through original/new same-FD loaders. Each receives2GiB actual cap;
   eight load original first, eight native first. No mmap or QueryCache hits.
6. One four-query paired task per worker; another barrier ensures every worker
   participates. Global query parity gives exactly32 original-first and32
   native-first query comparisons. All8 fields, debug group order and F64 bits
   must match; historical200's retained seven fields/F64 also match. Timings use
   per-query monotonic wall and process CPU, plus separate loads/order/baseline/
   combined RSS and native storage metadata. Combined RSS is not isolated memory
   footprint of a backend. Historical whole24s is not steady-state throughput.
7. Re-hash FP/keys, check full query file frame plus ctime and all code source pins again.
   The query stamp starts before its initial complete body binding and remains
   unchanged through the benchmark.
   Persist readiness, query bindings and measurements; final status is only
   BENCHMARK_PENDING_ROOT_ACTUAL_C0_REVIEW.

No1M NN completion, all-pool representativeness, ETA, production adoption, old
cache reuse, R/N generation or training release is claimed. Prefix64 is the exact
historical operational comparator, not a new statistical population sample.
Boundary tests alone can never create a full-reference success receipt. An error
keeps actual partial files/logs for Root; it produces no terminal approval.
Root must independently examine actual C0, source/native metrics and dataset
bindings before adoption. Current201 and its outputs are never read or modified.
