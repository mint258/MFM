# Source-role and byte-bounded inventory draft v2

This supersedes the recommended execution paths in full_sources_execution_v1.md.
All v1 sources remain unchanged as review history. These v2 sources are drafts
pending Root static review; no Python/tests/science, SSH, Git or Slurm was run
by the author. Root will freeze actual pins only after reviewing the drafts.

## Exact roles: original physical members, not training-molecule roles

547 proves current file bytes, footer rows/columns and source metadata. It did
not read the formal member_train/member_full/member_routine value pages and
therefore did not measure those boolean counts.

New projection_v3 preserves each formal row's three original booleans inside
source_metadata_json.original_physical_member_flags, and names its exclusive
role SOURCE_TRAIN, SOURCE_FULL or SOURCE_ROUTINE. ROUTINE rows preserve both
SOURCE_FULL and SOURCE_ROUTINE memberships. Embargo rows use SOURCE_EMBARGO.
Every v1 row and the receipt explicitly state effective_training_roles_applied=false.
No molecule_roles mapping or final-common filtering is applied.

The old11322/115760 ROUTINE/non-ROUTINE FULL counts are historical physical-record
expectations only. The full export will actually aggregate and report them as
original_physical_membership_counts and observed_original_bool_counts. It never
calls the old coverage helper returning effective_roles. The new frozen training
VAL72525/FULL54557 semantics are not claimed here. The decontamination union
still contains all11,231,854 formal+4900 embargo original records, including any
future common exclusions, with complete unique source IDs.

## Raw inventory: hard serialized bounds and checked allocation reserve

Source TSV is the exact original decompressed bytes: no ordinal/CID/SMILES text
column is added, no text assembly copy or SQLite database is created, and no
compression ratio is assumed. Global ordinals are stored only in bounded shard
metadata. Atomic partial→final renames retain the same inode and do not double
the body. There is no deletion or reuse by overwriting.

Let B be the actual producer's uncompressed byte count, R=250000 and S=64MiB.
A valid nonfinal record needs at least CIDdigit+TAB+LF (3B), while the last may
omit LF (2B); empty SMILES is not silently excluded. Thus:

```text
N_max = floor((B+1)/3)
P_max = floor(N_max/R) + floor(B/S) + 1
payload_bound = B + 2*P_max*4096
whole_bound = payload_bound + 256MiB
```

Each completed shard contributes one≤4KiB compact receipt and one≤4KiB JSONL
index entry. CID endpoints have bounded decimal-prefix/digit-count/SHA summaries;
complete CID bytes always remain in the TSV. Large integer conversion is not
used or capped: positive decimal ordering uses canonical digit length and bytes.
The part list is never loaded or dumped as one giant JSON array. Final receipt
is≤1MiB and references the streamed index by path/bytes/SHA. Verification streams
individual≤4KiB index lines with at most32 pending hash tasks.

For actual B=8,880,849,781B, N_max=2,960,283,260, P_max=11974;
payload_bound=8,978,940,789B and whole_bound=9,247,376,245B,
below10GiB=10,737,418,240B. These are conservative framing bounds, not a guess
of PubChem's actual row count. Inventory still measures real N and EOF/CRC.

256MiB is explicitly reserved for allocation/directory overhead and final or
failure metadata. Runtime samples st_blocks for owned files and the directory,
and stops if actual allocation overhead exhausts the reserve or the whole cap;
it does not claim an unmeasured filesystem overhead as fact. Source/index/receipt
payload writes also check their exact logical counter before writing. All partials,
including index partials, remain owned and budgeted; old attempts outside the new
output already consume the fresh account quota before the200GB reserve check.
The final accepted result requires independent source/part/index SHA and all
byte/row/ordinal conservation checks. Nonmonotonic CIDs remain explicit pending
global uniqueness rather than dropping records.

## New scopes, entries and metadata CLI

Use the existing strict queued16CPU/64GiB/4h/exclusive=user contract with no memory
exception, fresh startup proof once, current-RSS/MemAvailable cooperative stop,
and the same guide/Root-goal/fullX414/547/compat597 anchors. Old queue_v1 files
and prefix guards are unchanged. New names prevent accidental old-plan reuse:

| Stage | Scope | Entry | Pilot | Whole output cap |
|---|---|---|---|---:|
| identity profile | sb5_identity_profile_source_roles_v4 | identity_v3.export_v2 | true |2GiB|
| identity full | sb5_identity_full_source_roles_v4 | identity_v3.export_v2 | false |16GiB|
| raw inventory | sb5_pubchem_raw_inventory_v2 | pubchem_full_v1.inventory_v2 | false |10GiB|

After source review/integration, Root personally invokes on sonmi with repo:deps:

```text
PY -B -m workflows.expansion.materialize_full_sources_v2 --stage identity-profile --tag v1 --goal-authority ABS_ROOT_CURRENT_AUTHORITY_JSON --accounting ABS_CURRENT_OWNED_ACCOUNTING_JSON
PY -B -m workflows.expansion.materialize_full_sources_v2 --stage raw-inventory --tag v1 --goal-authority ABS_ROOT_CURRENT_AUTHORITY_JSON --accounting ABS_CURRENT_OWNED_ACCOUNTING_JSON
```

The helper reads only small metadata, automatically computes all pin triples,
and creates exclusive plans,547 actual closure and stage specs under
control/queue_specs/SCOPE_TAG*.json. No request/script/probe/download/submission
is performed. Root's nonpilot queue creator copies scope_key/scope_parameters,
supports pilot=false, and replaces __ROOT_STARTUP_PROOF__. Raw references remain
data locators; identity has3 metadata source refs and73 disjoint body refs.

Full identity preparation requires an actual accepted profile and refreshed
accounting containing its successful parent:

```text
PY -B -m workflows.expansion.materialize_full_sources_v2 --stage identity-full --tag v1 --goal-authority ABS_ROOT_CURRENT_AUTHORITY_JSON --accounting ABS_ACCOUNTING_WITH_PROFILE_PARENT --profile-receipt ABS_SOURCE_ROLE_PROFILE_RECEIPT
```

The helper rejects old role semantics, stale/different code, missing profile,
forecast storage over the fixed cap or worker estimate beyond one4h allocation.
Profile runs65536 formal rows across16 endpoint-inclusive row groups, all4900
embargo and whole local small cohorts. Actual counts/bytes/time/RSS remain to
be measured; v3/v4 names do not imply execution.

New test_full_sources_v2 keeps four synthetic methods, extending byte-budget
pre-write refusal, streamed≤4KiB index/UTF8/no-final-LF conservation and explicit
SOURCE_ROUTINE/bool retention. It does no RDKit or real body access. The same
strict source authority, complete-fold/global-ID proofs and external PENDING
boundaries remain. Local identity completion is not TDC/MoleculeNet17/MARCEL/
COCONUT all-source closure and never releases a pool, UFF/QM or training.

No full-source chemical screening is implemented or authorized by this inventory
entry. Later raw-uniform cost profiling is distinct from guide2.1's filtered,
deduplicated1M reference-molecule sample.
