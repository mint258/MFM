# First actual original000_0 pilot: exact preparation contract

Root freezes actual resources JSON from its already verified Alpha profile/live
publisher. No future PID/path/hash placeholder is a valid runtime reference.
Exactly these13 keys are required:

| Key | Actual reviewed value/basis |
|---|---|
| runtime_profile_reference | Actual Alpha profile path/bytes/SHA triple |
| quota_snapshot | Actual live Alpha native directory-quota snapshot path |
| quota_authority | Actual registered Gluster directory authority+publisher identity |
| workers |16 |
| software_rss_budget_bytes |68719476736 (64GiB software own-tree ceiling) |
| minimum_node_available_bytes |25769803776 (24GiB node reserve) |
| output_scope_root | One new private combined projection/dedup/baseline/filter/query scope |
| output_directory | That bulk output directory within the same aggregate scope |
| output_cap_bytes |350000000000 |
| other_future_reserved_bytes |1010000000000 (Root reviewed total1360GB minus this350GB scope) |
| minimum_free_bytes |200000000000 |
| duckdb_memory_bytes |34359738368 (32GiB internal SQL allowance within64GiB RSS) |
| batch_rows |8192 |

The initial plan prepares metadata only. It verifies the existing full coverage,
original500 frozen ordinal manifest, original502 materialization plan, frozen
kernel manifest and the four actual frozen scientific source SHAs. It does not
hash/read any Parquet/journal/SQLite scientific body. The original materialization
plan's502 fragment mapping must exactly equal the lifted coverage mapping.

Root sets CODE to the actual runtime profile's clean_code_root and runs there.
The following commands are for Root; this source package does not submit jobs:

```sh
cd "$CODE"
PY=/gfshome/alpha/codex_data_v1_20261026/software/pubchem_completion_20261103_venv/bin/python
ENTRY="$CODE/workflows/expansion/alpha_runtime_v1/entry.py"
COVERAGE=/gfshome/alpha/codex_data_v1_20261026/control/pubchem_tail_363412_root_20261030_v2/original_finite500_all_source_rows_accounted_v1.json
"$PY" -I -B "$ENTRY" workflows.expansion.alpha_closed500_handoff_v1.plan \
 --coverage "$COVERAGE" --resources "$ACTUAL_RESOURCES" --plan "$NEW_PLAN"
```

Inside Root's actual sonmi1/cpu16 allocation, first run native fixtures:

```sh
"$PY" -I -B "$ENTRY" workflows.expansion.pubchem_closed500_bulk_v2.test_bulk -v
"$PY" -I -B "$ENTRY" workflows.expansion.alpha_closed500_handoff_v1.test_handoff -v
"$PY" -I -B "$ENTRY" workflows.expansion.alpha_closed500_handoff_v1.test_pure -v
"$PY" -I -B "$ENTRY" workflows.expansion.alpha_closed500_handoff_v1.test_frozen_h2 -v
```

Then the bounded actual first source:

```sh
"$PY" -I -B "$ENTRY" workflows.expansion.alpha_closed500_handoff_v1.run \
 --plan "$NEW_PLAN" --action project --fragment-ids 000_0
```

Its parent receipt must contain actual_H_only_domain_observations: the complete
accepted-row count, real heavy0 count, real composition'[]' count, their intersection,
inconsistent-field count and first20 physical witnesses. No new chemistry runs in
that statistical pass. The separate test_frozen_h2 fixture invokes the actual
frozen Alpha dispatcher and is not satisfied by a Main-only skip.

Root binds actual terminal accounting independently. On successful adoption,
--action all without fragment IDs reuses000_0 and completes the full502 projection
and exact minimum-CID/all-CID-alias pool. It never replays379GB journals or resumes
the failed old SQLite. Later baseline/filter/query_projection actions use this
same reviewed aggregate scope. Filtering additionally needs actual all11 accepted
origin receipts and a verified Alpha transport manifest, not source-only metadata.
