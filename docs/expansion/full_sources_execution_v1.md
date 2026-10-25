# New source scopes: identity_v3 and pubchem_full_v1

These sources have not been executed or tested by their author. Root alone
reviews, integrates, runs the static checker, materializes stage specs, creates
queue requests and submits. Existing queue_v1, prefix gates, scientific code,
STOP artifacts and original pools are unchanged.

## Entry and queue contracts

Both entries use DATA_V1_QUEUED_REQUEST_V1 through the actual queue_contract
validate_request and validate_fresh_startup_proof APIs. Startup freshness120s
is checked once in main before body I/O, not after expensive SHA or in workers.
The actual Slurm job/node/UID/partition,16CPU,64GiB,exclusive=user,CPU-only thread
environment, exact plan/self/runtime pins, scope parameters and execution argv
must match. The new Root creator must copy scope_key and scope_parameters from
the stage spec and support pilot=false; the old pilot-only materializer is not
changed or called. Four-hour wall and the200GB post-output reserve remain.

The cooperative runtime samples current owned process-tree RSS and current
MemAvailable1s. At75% of the64GiB own request, node availability below15%, sample
failure, output cap or the120-second drain margin, it stops new dispatch/records
through the owned event and naturally drains. It sends no signals, performs no
SSH/scheduler calls and does not use inherited ru_maxrss. Output size sampling
is rate-limited to avoid shared-FS stat operations on every source line; closed
units and source counts provide separate exact final conservation checks.

Each plan explicitly binds the guide, Root's continuous-execution authority,
full-X4520414 receipt/actual closure, current547 pins and actual597 compatibility
receipt/compact closure. The chemistry proof covers all15,879,477 original IDs
without common. The original1926 explained portable differences and the
COMMON_PENDING/final-training-not-released meaning remain intact. These new
scopes permit source work; they never reinterpret an old prefix gate as full
authorization or release common/training.

## Root metadata preparation

After integrating these sources and the four frozen identity_v2 dependencies
from6b2947f (`__init__`,readers_v2,projection_v2,coverage_v2), Root may run:

```text
PY -B -m workflows.expansion.materialize_full_sources_v1 --stage identity-profile --tag v1 --goal-authority ABS_CURRENT_ROOT_AUTHORITY_JSON --accounting ABS_CURRENT_OWNED_ACCOUNTING_JSON
PY -B -m workflows.expansion.materialize_full_sources_v1 --stage raw-inventory --tag v1 --goal-authority ABS_CURRENT_ROOT_AUTHORITY_JSON --accounting ABS_CURRENT_OWNED_ACCOUNTING_JSON
```

PYTHONPATH must contain the reviewed repository and the established deps overlay.
These commands are metadata-only on sonmi/UID1278. They do not read/stat/hash
data bodies, create queue requests or submit. They automatically compute source
pins from actual files, including accounting/raw sacct and the547 completed
parent. There are no copied SHA literals for new closure pins.

Outputs are exclusive new files under control/queue_specs:
`SCOPE_TAG_547_actual_closure.json`, `SCOPE_TAG_plan.json`, `SCOPE_TAG.json`.
The stage spec contains small exact source triples, large known body locators,
16CPU/64GiB/4h resources, whole output cap and direct execution argv. Root's new
queue creator handles `__ROOT_STARTUP_PROOF__` and final fresh startup proof.

Scopes are sb5_identity_profile_all_roles_v3, sb5_identity_full_all_roles_v3,
and sb5_pubchem_raw_inventory_v1. Profile is pilot=true; full export and whole
raw inventory are pilot=false. Raw inventory is not chemical full screening.

## Identity implementation

Actual547 has76 current pins,16 I/O workers and no missing/blocked locators.
Three metadata_json inputs are small source refs; the remaining73 bodies are
data refs, with no path present in both. The authority verifies the exact CPU
producer schema, original catalog, completed parent and all76 source versions.
Only st_dev may differ across nodes; inode/mtime/size/UID stay exact, with full
current SHA and same-node before/after frames in the allocation.

The profile reads4096 records from16 evenly spaced physical row groups including
both endpoints of the86-group formal source (65536 total), all4900 embargo rows
and the whole local cohorts. Full export reads every formal row group. VAL is
the existing ROUTINE authority, exported once with FULL membership retained.
No final-common filter is read or applied.

New coordinator tasks write typed compact Parquet in fresh partial/final units.
The frozen identity projections preserve both v1 full-key authorities, original
SMILES and conservative composition reasons. CYP2003 and AZraw120/fold109+extra11
need their exact complete10-fold unions and source ledgers. QM7 uses only MAT Z;
QM9 uses all133885 original archive members, two source SMILES and member-byte
comparison to all original ledger records, including previous failed variants.
CSV/JSON projection is explicit; targets/features never enter output or order.
Six local MoleculeNet files are exported as partial family evidence only.

Actual16 spawned nonempty worker coverage, all per-source counts, full global
(dataset,source_id) uniqueness and original v1 roles/4100+800 embargo classes
are checked. Missing or unresolved identities are retained in a separate Parquet
and never become a successful all-source decontamination claim. The full local
record count is11,398,552 including11017 records from the six local MoleculeNet
files; profile count is232234. Full v1 itself remains11,236,754 records.

The profile cap is2GiB; full proposed cap16GiB includes output and spill.
At most32 tasks are queued, each unit has its own bounded cap, Arrow batches
are4096 rows, DuckDB memory32GB and spill has a fixed budget. Existing inputs,
prior pools and prior attempt data are read-only. Failures keep partials and
closed-unit receipts. Source bodies are rehashed with16 actual I/O threads.

After the actual profile closes, Root can prepare full with refreshed accounting:

```text
PY -B -m workflows.expansion.materialize_full_sources_v1 --stage identity-full --tag v1 --goal-authority ABS_CURRENT_ROOT_AUTHORITY_JSON --accounting ABS_ACCOUNTING_WITH_PROFILE_PARENT --profile-receipt ABS_PROFILE_RECEIPT
```

The materializer refuses full without the actual COMPLETED profile parent and
matching current code. It derives a conservative storage forecast and rough
worker cost from measured formal bytes/seconds; it refuses a forecast above the
fixed16GiB cap or single4h allocation. Global-sort full-scale uncertainty remains
explicit. No elapsed-time prediction is fabricated from an allocation ceiling.
Work over500 core-hours retains explicit Root profile review.

TDC22 endpoints with both roles, all17 proposed MoleculeNet datasets, MARCEL
Drugs75K+Kraken and COCONUT active/inactive identities remain separately PENDING.
Local completion does not close those families or authorize global pool release.
Their data are used only for identity exclusion, never novelty scoring.

## Raw inventory implementation

The exact raw producer proves1,488,715,010 compressed bytes and8,880,849,781
uncompressed bytes. The new main completely rehashes that raw and streams it
through gzip EOF/CRC. One-MiB segments permit arbitrarily long source lines
without retaining a whole giant SMILES. CID/tab/UTF8 framing is checked against
the original source format; all bytes and source rows are conserved.

Task-owned TSV shards preserve original bytes, line endings and CID–SMILES
payload. They close only at record boundaries, at250000 rows or64MiB target.
Each has exact global ordinal range, rows, bytes, first/last CID and SHA.
Final hashes use up to16 independent I/O threads with actual IDs reported.
The10GiB whole cap derives from the measured8.880GB source body plus metadata.
Atomic rename does not assemble or duplicate a second source body.

Observed strictly increasing positive CIDs prove global uniqueness. If order is
not monotonic, no source rows are dropped: the receipt explicitly marks global
CID uniqueness PENDING external verification. Final candidate selection must not
interpret that as a dedup pass. The receipt records real N and maximum line
length, never guesses PubChem size. It performs no chemistry, decontamination,
novelty ranking, UFF/QM or training.

The next separately reviewed cost profile must sample across this complete raw
inventory, use the exact597-compatible feature dispatch and measure physical
production Parquet/CPU costs. This raw-uniform cost sample is different from
guide2.1's1M filtered-and-deduplicated reference molecules.

## New boundaries, not run by the author

Four synthetic source tests cover a UTF8/multisegment huge line plus no-final-LF,
bad framing/nonmonotonic CID conservation, original VAL/unknown embargo policy,
and refusal of a noncompleted547 parent before data stat. They use no RDKit or
real source body. Profile and inventory plans run these tests in their actual
reviewed allocation before body I/O; full reuses actual profile evidence.

No Python/test/scientific command, SSH, Git or Slurm was executed by the author.
Root must run source checker, review exact code/spec pins, and inspect actual
profile/complete receipts and Slurm parents before accepting any next stage.
