This independent package admits the real compiled full-pool result, calls original `typed_rank.run(plan)`
directly, then scans the closed original N remainder read-only. It changes no original rank/queue/NN/kernel
body, no tie rule and no active201 state. This source has not executed a full ranking or produced future hashes.

Root must first deploy a **new real rank capsule**. Copy the byte-identical original typed_rank.py into
CAPSULE/workflows/expansion/exact_nn_cached_v1/typed_rank.py and original external_sort.py into
CAPSULE/workflows/expansion/external_sort.py. Keep the existing exact_Common layer unchanged; no fake Main
path or symlink. The real imported create_queues source must equal the relative source path that original
typed_rank.py records at receipt time. The current exact_Common_b817ce7 layer lacks that relative file and
would fail only after the expensive sort, so the collector refuses such a deployment before DATA work.

Deployment metadata requires base_code_root, entry_reference, code_references,
original_rank_source_bindings keyed typed_rank.py/external_sort.py, each containing origin_reference and
execution_reference with identical bytes/SHA and real respective paths. Root's rank_namespace_manifest_reference
points to small JSON containing capsule_exact_nn_cached_v1_path, exact_nn_cached_v1_search_paths and
namespace_source_reference. The new exact_nn_cached_v1/__init__.py must explicitly assign the capsule path
FIRST followed by the original exact_Common module directory and any other actual borrowed package paths.
Include that namespace file in code/startup pins. Entry verifies the runtime __path__ exactly, original imported
rank/queue file pins and both source-copy byte identities. Root writes this deployer and reviews origin provenance.

After full CPP execution and its real Root C0 review exist, invoke metadata collector module
workflows.expansion.alpha_typed_rank_v1.collect with:

```
--compiled-wrapper ACTUAL_COMPILED_BACKEND_WRAPPER_JSON
--compiled-actual-review ACTUAL_ROOT_FULL_POOL_REVIEW_JSON
--rank-deployment ACTUAL_NEW_CAPSULE_DEPLOYMENT_JSON
--resource-template ACTUAL_ALPHA_SQL_RESOURCE_TEMPLATE
--storage-partition-review ACTUAL_ROOT_PRIVATE_PARTITIONS_REVIEW
--partition-key ACTUAL_RANK_PARTITION_KEY
--output-directory FRESH_METADATA_DIRECTORY
```

It opens small metadata/source files only and never submits. Missing future full-pool input is an error,
not a placeholder hash. The future review schema/status is ROOT_ALPHA_COMPILED_FULL_POOL_ACTUAL_ACCEPTANCE_V1 /
APPROVED_COMPLETE_COMPILED_COMMON_EXACT_FULL_POOL with reviewer root, compiled_execution_wrapper_reference,
original_scientific_receipt_reference, actual_parent/actual_accounting_reference, query_manifest_reference,
reference_manifest_reference and queries equal to the actual complete eligible census. Actual Alpha C0 and raw
accounting are mandatory. Source207 or worker64/kernel206 validation cannot substitute for full-pool completion.

CPP provenance gate retains the original scientific receipt separately from wrapper metadata. It checks exact
wrapper/plan/startup/namespace/query/ref/filtered bindings,206 adoption for actual196 full1196122 Common,
actual worker-entry integration, original run code-object and only-exact_batches injection claims, build/binary,
validated production sources and an unseeded fresh CPP namespace. It never opens the CPP query-cache database.
Plan.novelty_receipt points to the original expansion_exact_novelty_v1 receipt, not to its CPP wrapper.

The independent private budget review schema/status is
ROOT_ALPHA_PRIVATE_EXACT_BUDGET_PARTITION_ACTUAL_REVIEW_V1 / APPROVED_PRIVATE_EXACT_PARTITIONS, with Root,
Alpha endpoint/uid/quota_root, global_budget_reference, aggregate_scope_root, partitions,
partition_cap_total_bytes and all_other_goals_and_exact_partitions_reserved=true. It explicitly supplies
closed_legacy_allocated_bytes=B, closed_legacy_scopes[{path,allocated_bytes,owned_uid,all_writers_gone}],
closed_legacy_writers_gone/closed_legacy_own_disjoint=true, actual closed_legacy_scope_census_reference and
closed_legacy_actual_accounting_references. Legacy physical credit does not imply scientific acceptance.
Each partition supplies partition_key,output_scope_root,output_cap_bytes,allocated_bytes_credit,
remaining_reserved_bytes=cap-credit,other_future_reserved_bytes,minimum_free_bytes; positive credit needs an
actual physical_census_reference. Legacy and new roots must be disjoint private children of aggregate exact.
B+sum(new caps)<=actual global exact cap; no300GB constant or assumed B=0 exists. Nonexact remaining is the
global sum(cap-closedcredit), excluding exact; chosen other futures must include that plus every peer's remaining.
Source validates the actual Root metadata arithmetic/declarations and pins; it does not perform/replace Root's
physical census or invent quota/credits. Root supplies concrete cap/SQL/spill/tree/node allocations.

Run module workflows.expansion.alpha_typed_rank_v1.entry through the existing isolated Alpha node launcher,
with --plan/--startup-proof. Plan retains original PUBCHEM_TYPED_EXACT_RANK_PLAN_V1, adds scope_key
alpha_typed_rank_closed_N_v1, compiled_execution_wrapper_reference, compiled_full_pool_actual_review_reference,
rank_deployment_reference, storage_partition_actual_review_reference and storage_partition_key. It keeps actual
runtime/quota/source refs, workers>=16 and independent private output_scope_root/cap/other-future fields. No
original typed_rank/create_queues global is replaced. Original complete all11/X/typed membership/reference,
H-only validation and fixed R5M/N5M/first1.25M each gates execute unchanged.

On original return its CHECKPOINT and close have completed. Locate attempt/ranking.duckdb through the actual
queues path; check no WAL, actual owner/inode/size/times and hold a source FD during a new read_only=True
connection. Register original stable_hash('N-tie',20261025,key) locally as n_hash. Independent temp/spill files
go under the new private audit directory, never the source DB. Scan **all** n_candidates, whose expected size
is complete eligible minus5M R; GROUP BY exactly heavy_stratum,element_combination,zero-count flags,nearest
score,scaffold/ring counts,n_hash(full_key). Do NOT add full_key/CID to that key, which would conceal ties.
Mass, unique IDs, all duplicate tuple groups/rows and max multiplicity are reported without sampling or LIMIT.

The original rank receipt does not pin the DuckDB body. This audit honestly records a new actual closed
frame/read-only/full-scan witness and whole_database_SHA_recomputed=false; it does not fabricate historical
or fresh whole-DB SHA. The extra full scan/hash/grouping IO is real and budgeted. Duplicate tuples produce
REJECT_STRICT_SAME_N_CLAIM_DUPLICATE_TUPLES, preserve the original completed rank/audit, and fail the new
wrapper. No additional identity tie key is introduced. A successful wrapper remains pending its own actual C0
and Root review; Root must require its audit before accepting strict N ordering or downstream UFF source.
It proves order independence from unchanged full row values and unique original sort keys, not a nonexistent
paired replay or byte-identical Parquet files.

Tests: test_metadata is standard-library-only and uses explicitly synthetic dictionaries (not actual C0).
It covers legacy/partition/future arithmetic and real full-pool vs64/1M/cost/schema boundaries. Root runs
test_native_sql on Alpha DuckDB: deliberately colliding hashes must be detected despite unique identities;
and a real closed readonly connection must register the original hash without mutating the DB frame.

Root may use the independent `deploy_capsule.py` helper (Alpha deployment has not been executed by the preparing agent).
Run it with the actual private Alpha Python `-I -B`, from the exact clean BASE code cwd, and pass
`--archive ACTUAL_SOURCE_ZIP --source-manifest ACTUAL_SOURCE_JSON --capsule A/code/alpha_typed_rank_TAG
--output-metadata D/alpha_typed_rank_TAG_actual_deployment.json`. D is the existing completion environment
control directory. Default prior deployment is the actual93797B popcount_production_8cfcee1 record, pinned by
its accepted SHA. Source JSON has source_commit,archive_sha256,files[{path,bytes,sha256}], with exactly the
reviewed nine alpha_typed_rank files (optionally deploy_capsule.py too). The helper bounds all reads to small
source/metadata (including a 2 MiB archive maximum), validates the zip body set, refuses symlink/traversal/duplicate/foreign members and existing
destinations, and leaves any failed new capsule intact. No old layer is patched or removed.

It reuses actual prior source pins and literal namespace lists, byte-copies actual old typed_rank and BASE
external_sort into a new real capsule, records origin/execution pins, explicitly prepends the new exactNN
directory and retains original exact_Common modules, generates a metadata namespace manifest and guarded
entry, then runs an isolated import-only preflight for actual imported paths and authority.deployed. The final
deployment record distinguishes archived source bodies, copied originals and helper-generated metadata sources.
Preflight failures preserve stdout/stderr. It never compiles, scans DATA, opens a query cache, invents a future
plan or submits. Root reviews and executes this helper; deployment itself is not a native ranking acceptance.

An optional generated fixture_bundle module accepts an actual Alpha NodeLauncher --plan/--startup-proof:
plan schema ALPHA_TYPED_RANK_SOURCE_FIXTURE_PLAN_V1, scope_key alpha_typed_rank_source_fixtures_v1.
It uses actual profile/Guard/source pins and runs metadata4 plus DuckDB2, writing a small source-only receipt.
It needs no nonexistent fullpool receipt and claims no fullpool/queue/rank completion. This adds no production gate.
Root may explicitly add `additional_fixture_suites=[{module,expected_tests,source_reference},...]` to that
actual fixture plan, allowing only uff3_candidate_v1.test_credit (5), test_credit_threads (2), and
test_ledger_epoch (Root must explicitly state its actual expected count, currently7; no future count assumed).
Full module names use workflows.expansion. The optional modules must resolve through Root's actual merged
namespace, with exact imported source refs in both plan and startup proof before tests run. Root may deploy
the UFF layer separately and use a new combined outer entry/namespace rather than modifying this pinned
rank capsule. The receipt records actual loaded/executed counts and per-suite source/expected details;
rank6 plus the current ledger14 is20 only if all real loaded counts and execution agree. No additional suite
claims fullDATA or production completion.
