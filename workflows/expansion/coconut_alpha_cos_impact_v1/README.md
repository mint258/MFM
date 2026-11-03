# Exact full-pool hypothetical C/O/S impact

This allocated diagnostic reads only the existing `non_h_composition` VARCHAR
column of the complete unfiltered minCID Parquet (109871959 unique full keys).
It creates no candidate subset, index or queue and makes no source/scope adoption.
No RDKit, new chemistry, approximation, sampling or molecular descriptor work is
performed. `[]` remains a valid empty non-H vector, including H-only candidates.

The actual unadopted cached735/primary3 antichain supplies C>=1 OR O>=1 OR S>=1
and its original source IDs. The full Fe-containing out-of-X source vector is
retained as an observation, never shortened to C/N/O. The SQL casts the entire
composition to BIGINT[][], verifies exact compact JSON round-trip, positive
counts, non-H atomic numbers and unique sorted element pairs. Invalid rows are
accounted separately and cannot silently become non-hits. The result gives all
eight C/O/S combinations, union/nonunion counts, empty vectors, Fe and out-of-X
rows, and the exact executed SQL. A single tiny SQL fixture compares this actual
query with an independent Python JSON/list oracle, including H-only, Fe, Se/Si,
invalid counts, duplicate/unsorted pairs, malformed JSON and NULL.

Root creates a resource-reviewed plan using the existing Alpha runtime fields:
`runtime_profile_reference`, `quota_snapshot`, `quota_authority`, `workers` (16),
`software_rss_budget_bytes`, `minimum_node_available_bytes`, `output_scope_root`,
`output_directory`, `output_cap_bytes`, `other_future_reserved_bytes`,
`minimum_free_bytes`, `duckdb_memory_bytes`, `endpoint`, `uid`, and
`code_references`. Budget values come from Root's actual concurrent reservations;
the module supplies no invented defaults. The node launcher replaces the quota
publisher, output directory and execution argv with the actual job namespace.

Additional exact plan keys:

```text
schema = COCONUT_ALPHA_COS_IMPACT_PLAN_V1
scope_key = coconut_alpha_cos_impact_v1
candidate_pool_receipt_reference = machine pin of /gfshome/alpha/pubchem_expansion_20261103/bulk/original502/unfiltered_pool/receipt.json
candidate_actual_parent_reference = machine pin of A/control/pubchem_expansion_runtime_20261103/mincid_full502_actual_parent.json
primary3_receipt_reference = machine pin of A/artifacts/pubchem_native735_fields_20261103/primary3_node_v1_job_1885152/receipt.json
primary3_actual_parent_reference = machine pin of A/control/pubchem_expansion_runtime_20261103/primary3_root_actual_parent.json
closed_candidate_frames_reference = machine pin of A/control/pubchem_expansion_runtime_20261103/bulk_closed_other_future_credit_v1.json
```

`A` means `/gfshome/alpha/codex_data_v1_20261026`. References are actual
`{path,bytes,sha256}` triples, never handwritten SHA strings. The required code
references include every Python file in this new package, the actual imported
`coconut_alpha_cached735_v1/support.py`, and the actual current runtime sources.
The primary3 receipt supplies the antichain reference and its cached1885150
receipt/accounting pins; do not substitute an unbound manually entered C/O/S list.

The candidate SHA is established by the actual1885149 C0 producer receipt and
Root accounting. This job explicitly does **not** repeat a 34 GB body hash. It
holds an O_NOFOLLOW read-only descriptor, checks UID/link count/size, compares
the retained historical inode/mtime/ctime record when supplied, and checks
the unchanged current physical frame, including device, after the column-pruned
scan. Gluster `st_dev` is a client-local device ID, so historical and current
device values are explicitly recorded without requiring cross-node equality.
The historical ledger has no hostname or volume identity fields: the result
does not invent those. The exact historical file reference and Alpha endpoint/UID
are checked. Current input volume identity is verified through the existing fresh
same-node native quota validator (backend, volume UUID, mount source, quota and
volume roots), source path boundary, and current file device equality to the
current quota-root device. The validated native snapshot is retained as evidence.
A historical inode/timestamp
frame mismatch is reported with both actual witnesses; there is no silent fallback
to a newly asserted historical frame. If no historical reference is supplied,
the result honestly records only its current immutable frame plus existing SHA
authority. The actual available ledger above should be supplied for this run.

Root submits the existing node launcher with a fresh plan template and source
layer, using the approved CPU allocation and clean base cwd:

```text
PY -I -B NEW_ENTRY workflows.expansion.alpha_runtime_v1.node_launcher --template ACTUAL_TEMPLATE --base-root ACTUAL_CLEAN_BASE --entry NEW_ENTRY --module workflows.expansion.coconut_alpha_cos_impact_v1.run --tag cos_impact_v1 --control-root A/control/pubchem_expansion_runtime_20261103/node_epochs --gluster-rpc-program ACTUAL_READONLY_RPC
```

The module accepts `--plan PATH --startup-proof PATH` generated by that launcher,
uses `profile.admit(..., minimum_workers=16)` and the shared `Guard`, then runs
the one fixture before the complete scan. The fixture can also be run by the
standard unittest module entry:

```text
PY -I -B NEW_ENTRY workflows.expansion.coconut_alpha_cos_impact_v1.test_source -v
```

Outputs are private `source_tests.json`, `impact_diagnostic.json` and a producer
`receipt.json`. Actual parent C0 remains pending Root's normal accounting
readback. The counts describe hypothetical conservative impact only; no all735,
all11, filter, scientific exception or source-scope decision is inferred.
