# Family export: one CPU Parent, real final-policy gates

SOURCE ONLY. No Python, AST, fixtures, scientific DATA, SSH, Slurm or Model runtime
was executed by the author. All old sources, DATA, failed parents and UNKNOWN
outputs stay unchanged. This package is not a D1/D2/D3/D4/D6 release.

The exact entry is `workflows.data_v1_final.export.family_export_day_v1.run`:
16 allocated CPUs, 16 spawn workers, at most 32 pending source tasks, one 86400 s
CPU-only/no-mem generic `cpu_auto_memory_queue_v2` allocation. It uses the frozen
D5 resource Budget/Authority, original actual observed_at/Slurm-to-monotonic
clock, current-node25h quota Client, whole-output cap, 16 GiB drain reserve and
200 GB account/disk margin. The explicit output cap is 32 GiB..1 TiB; this is a
software ceiling, not a size/time forecast. Root must approve actual other
future writers, current cap and a real provider identity with enough lifetime.
The provider is neither started nor renewed by this code. No signals, GPU,
new QM/UFF, training, per-shard Slurm or fake internal C0 are produced.

Root's shortest metadata sequence, after installing this package and SB1's
`labels/final_release_v1` exactly:

```
PY -B -m workflows.data_v1_final.export.family_export_day_v1.metadata proposal --output ROOT/control/family_export_proposal_v1
PY -B -m workflows.data_v1_final.export.family_export_day_v1.metadata draft --request ACTUAL_ROOT_REQUEST --output FRESH_CONTROL
PY -B -m workflows.data_v1_final.export.family_export_day_v1.metadata finalize --draft FRESH_CONTROL/draft.json --root-review ACTUAL_SEPARATE_REVIEW
```

Here PY/ROOT stand for the existing Main environment and run root, not new
literal aliases. The produced stage_spec uses the existing central helper.
Root selects the actually free reviewed node14/18 and signs its exact scope.
There is no added queue or SCOPES expansion. Runtime argv is exactly:

```
PY -B -m workflows.data_v1_final.export.family_export_day_v1.run --plan ACTUAL_PLAN --startup-proof ACTUAL_GENERIC_PROOF
```

`ROOT_REQUESTED_FAMILY_EXPORT_DAY_V1`, REQUESTED_FOR_REVIEW/requested_by=root,
requires all `contract.REQUIRED` references, purpose pilot55k/full, node,
fresh absolute output_directory, actual output_cap_bytes and
final_release_mode=SAME_PARENT_REVIEWED_CANDIDATE. The generated proposal has
null missing refs and is NONEXECUTABLE. No future hashes/ACKs/parents are made.
Metadata opens only declared small Source/operational review documents; numeric
JSON, source specifications, field maps, Parquet, SQL and LMDB stay DATA.

The joint directive is SB1's actual `ROOT_FINAL_LABEL_RELEASE_DIRECTIVE_V1`;
validate_directive requires real prior D4 C0+Root acceptance, final Root/Model
physical policy/actual ACK and accepted D5. Draft3 or a numeric component audit
is insufficient. Its parent_output_directory is this fresh Parent output.
The exact field-claim builder sources/review are required in the real request.
A separate ROOT_FAMILY_EXPORT_DAY_RESOURCE_REVIEW_V1 must APPROVE the same
node16/wall86400/cap/output/provider identity/carveout and finite lease. This is
not a resource approval supplied by the source author.

`ROOT_FROZEN_FAMILY_EXPORT_SOURCE_RELEASE_V1` is a new, explicit Root source
projection review, not an existing accepted fact. APPROVED_EXACT_FULL_SOURCE_PROJECTION
requires D5_components_reference, joint_policy_reference,
field_geometry_policy_reference, field_map_reference, source_references,
data_references, source_specification_reference (JSONL DATA),
native_pointer_reference (original payload-pointer Parquet DATA),
canonical_index_reference, latest_owner_manifest_reference,
reason_codebook_reference, accepted_additional_identity_namespaces,
additional_actual_geometry_tables and export_configuration. The configuration
contains molecules_per_shard (1..5000), map_bytes_per_store (original LMDB
bounds), group_exposure_mask and family_exposure_mask. Store partitions are
computed from actual equal geometry/view/family/target memberships; different
field geometries never acquire each other's values or masks. The Source
review asserts all_physical_geometry_and_child_sources_bound, no Pprime PM7
copy and zero reviewed source_identity_or_mask_gaps; actual CPU claims and
coverage still check them. Source selectors are explicit old source.py syntax,
plus claim_columns/native_anchor_columns/precision_column as applicable.
There is no graph repair, value normalization, unit conversion or source-owner
choice in this exporter.

The CPU route is complete:

1. Exact generic startup/full argv/source checks. Before DATA and before the
   Budget sampler, run original wire8+its16-spawn CLI, original sparse-pair4,
   new3 and the Source inverse. Count15 is fixed; failures never reduce count.
2. Whole-SHA/current-stable-FD validation of declared DATA. Build a compact f64
   actual geometry index from Root-accepted D5 tables. Reconstruct original
   PM7 per-call input hashes through the frozen renderer/protocol/seed objects.
   Root/Model field policy separately binds actual output frame/unit/basis.
   Same-task fields are bound independently to their actual geometry; input
   hashes alone do not prove native output axes. No unknown is a base fallback.
3. Whole Common PM7146field claims feed SB1's hook. It partitions original
   compact field/reason/leaf masks, preserves every original bit/reason and
   computes the original final-series/size-family candidate. That current
   Parent candidate does not claim C0 or publication. P/Pprime normalizers
   remain independent and no unimplemented policy receives a default formula.
4. Original D5 pilot_train/pilot_val tables select exactly50000 Common TRAIN
   and5000 Common VAL MIDs; whole ROUTINE role assignment is not permission to
   include Common-excluded VAL. Full uses original train_all/val_all only after
   actual pilot C0+Root acceptance+actual Model loader ACK. Original diagnostic
   anti-join and all actual base/child conformers are checked. N1 extras enter
   only through independently accepted actual geometry tables, never N inflation.
5. One persistent pool projects bounded complete source RGs into binary f64
   pieces, with original extract/compact restore/sparse-pair math. A strict PK
   rejects duplicate owners. Actual per-cell field unions prove every selected
   target/geometry exists exactly in Source; missing fields are not dropped.
   Internal whole-MID shards write original MFM3 LMDB transactions. Only the
   original encoder casts f64 to f32. Immutable schema pins bind candidate
   config refs, original D5 three-order/geometry/diagnostic manifests and Source
   specification. Per-record f64 locators are source_index/RG/row/part into that
   exact Source specification, avoiding repeated 146-field JSON payloads.
6. Whole SHA/schema/record+MID counts for all stores, fixed seed20261025 exactly
  10000 unique exported records re-read from original Source and compare every
   leaf against the original one-f32-cast comparator (integers/masks/reasons and
   signed zero exact).16 actual spawn-owned readers each read every requested
   family/conformer of one actual MID; record/s and molecule/s include startup,
   and birth/PID/handle/process closure is checked. This is not a Model ACK.

r73 is a separate SOURCE_ORDERED_RECORDS_V1 transport: ordered atom endpoints,
ordered UTF-8 basis_i/basis_j, optional channel/onsite presence, explicit source
ordinal and duplicates survive. Onsite is never inferred from equal atoms.
NULL/unknown layout stays distinct from an empty actual record list. Invalid
UTF-8 offsets, lossy integer indices or unreconciled masks HOLD. Native S raw
rdkit_bond_index/order are transported with exact integer codes and original
order/direction/duplicates, not RDKit's deduplicated graph. r674's six original
components remain one symmetric tensor with original component/leaf masks and
source precision; no trace/scalar projection or exporter-selected loss rule.
Final partial policy is retained; an all_components local view is used only
for the old structural preflight and is never encoded as a replacement policy.
The same physical field is validated once per explicit(condition,geometry_source)
domain using the unchanged original preflight; Pprime is not a duplicate P row.

PM7 D4 audit is not a Pprime mask authority. Full (or a mapping containing
Pprime) additionally requires a real
ROOT_ACCEPTED_INDEPENDENT_PPRIME_FIELD_AND_MASK_AUTHORITY_V1 /
ACTUAL_FULL_SOURCE_HASH_BOUND_FIELD_GEOMETRY_AND_ORIGINAL_MASKS, reviewer=root:
actual_parent={manifest,proof,accounting,raw}, exact actual parent id/argv/schema,
D5_components_reference, full_Common_coverage, zero unknown/duplicate claims,
original input double SHA/actualchild binding, no PM7 mask/statistics substitution,
claim_database_reference (same explicit per-field source_cells/claim_bindings
schema), mask_release_reference (original compact mask_tables+geometry_id),
data_references/source_references. These must come from actual independently
accepted formal Pprime source products; this package does not invent such a
receipt or reinterpret QA as formal. The CPU separately merges those proved
claims for projection and loads those original masks; PM7 hook146counts remain
unchanged. The final family wrapper explicitly retains this independent
Pprime field/mask authority. If no real compatible product exists, this is an
honest remaining Source integration requirement and full stays NONEXECUTABLE.

Durability: dispatch, completed source references, per-shard immutable receipts
and last whole-MID cursors are fsynced. Near the900s wall drain or resource STOP,
no new work is accepted; already started processes join naturally. Partial SQL,
WRITING LMDB/orphans and exceptions remain evidence and cannot become accepted
cursors. No automatic retry or cleanup is implemented. Root may request a new
fresh day with explicit ROOT_FAMILY_SOURCE_CURSOR_ADOPTION_V1 only from actual
C0, errors[] prior output: exact same source policy/D5/purpose/directive,
closed task JSONL, prior immutable DATA refs and only_actual_closed_source_tasks_and_closed_stores.
The exact original candidate objects and existing store bytes are reused;
normalization/config SHA are not silently changed. Failed/TIMEOUT/UNKNOWN
output is not this automatic adoption path and needs separate Root disposition.
Full staging is bounded binary f64, not a claimed full-size forecast; actual
55k size/cost will determine whether a reviewed full cap and24h packing suffice.

After actual Parent C0:

```
PY -B -m workflows.data_v1_final.export.family_export_day_v1.metadata candidate --closure ACTUAL_THREE_REF_JSON --output FRESH_CANDIDATE
```

Closure aliases are receipt/startup_proof/accounting, all actual refs. Root
separately uses SB1 final_release metadata candidate/publish with the true
candidate-producing Parent/proof/raw/C0 (the earlier C0 if a cursor continuation
reuses its exact candidate). This produces ROOT_FINAL_LABEL_RELEASE_V1 with
original config-reference SHA, no changed scientific payload. Root then signs
ROOT_FAMILY_EXPORT_PUBLICATION_REVIEW_V1 /
APPROVED_EXACT_ACTUAL_C0_AND_SAME_OBJECTS, exact candidate_reference,
final_label_release_reference and stores_catalogue_reference:

```
PY -B -m workflows.data_v1_final.export.family_export_day_v1.metadata seal --root-review ACTUAL_REVIEW --output FRESH_RELEASE
```

The immutable inner store COMPLETE means transaction closure only. Final
consumers call store.open_accepted(external_release,store_name); that API requires
actual C0 and external release, compares exact embedded config refs, and checks
whole data/manifest SHA and real counts. Candidate Reader is for this Parent's
QA only. There is no cycle requiring current C0 before export, and no implicit
same-object claim for differing SHA. Root pilot acceptance schema is
ROOT_ACTUAL_FAMILY_D3_PILOT_ACCEPTANCE_V1 with status
APPROVED_ACTUAL55K_AND10000_SOURCE_PARITY, exact actual_closure_references,
joint_policy_reference and accepted_export_reference. Full requires a separate
ROOT_ACCEPTED_ACTUAL_MODEL_D3_LOADER_ACK_V1 / ACTUAL_MODEL_LOADER_ACCEPTED_EXACT_D3,
actual loader execution ref and that same accepted export; source-only/mock
or inferred ACK is rejected.

D6 `transfer --plan ACTUAL --startup-proof ACTUAL` is an independent finite
CPU-only data-copy/local-loader entry. It refuses to treat a generic analysis
node policy as CPU permission on GPU20/21. A genuine node-specific Root CPU
policy, fresh samePID/boot/ticks/allocation proof, original accepted export and
actual tmp capacity/reserve are mandatory; these do not exist merely because
this Source was written. No SSH/GPU allocation/training is added. It performs
O_EXCL .partial copy, EOF+whole SHA+local reopen, all store counts, then the same
actual16-spawn whole-MID benchmark. Partial copies remain, never overwrite.
Actual local receipts/Root acceptance remain separate from Model loader ACK.

Inverse: actual CPU proves full Source bytes+AST for old physical resolve (only
exact opaque-id SQL binding), old atomic Writer and Reader (only validator
call binding); ten original scientific codec/extract/mask/assembly/compare
objects are checked by identity. The new claim/transport/orchestration code is
explicitly new IO, not misrepresented as identical old function text. Three
new synthetic methods exercise real Arrow->ordered r73->LMDB close/reopen,
NULL/empty and bad offsets/index, native duplicate bond order, r674 partial
single-cast tensor with independently validated P/Pprime domains, and same-task
different-field geometry claims. Actual results remain pending Root CPU.
The public source_cells SQL interface is a lossless view over source_files and source_cell_rows. Immutable path/size/SHA is stored once per file; all agreed column names, original row keys and field lookups are unchanged. claim_bindings remains the explicit original-field-bitset/evidence table. This avoids repeating full source locators in each physical row; no owner/order/field values are dropped.

The unchanged MemoryObserver starts after all temporary fixtures. Its explicit512MiB evidence output is included in scope_parameters under artifacts/labels/source_status_v1/family_export_day_v1_resources/<output-path-hash>, as required by the frozen observer's literal-path guard. This retained original path rule is not bypassed. The whole parent cap includes this evidence inside the original16GiB drain reserve; final closure checks both. RSS/MemAvailable STOP and /proc process birth checks are therefore active and latched across spawned workers. No memory is requested from Slurm.

IO batching is internal only: source SQL commits at most16 streamed rows, without aggregating source arrays in RAM; MFM3 Writer receives at most64 records/128MiB buffered arrays per original atomic batch. The Writer transaction/codec function itself is unchanged. This avoids a separate fsync transaction for every scientific row. The already accepted D5 full canonical child rows supply their exact input-file/bundle/protocol/occurrence binding directly; unchanged parent rendering is cached only within the same input-hash row. Native-parent printing relation still requires explicit Root/Model policy. No verified input binding is recomputed merely to satisfy a scheduler chunk.

## Pre-registration Source revision R2

R1 ZIP67,577B SHA a48453a51935f0c610f4baca764a1dd3a6f597aa480a7e5e2d5f1625f2b96ffd
and Root's R1 install are preserved. R1 was not executed. R2 changes exactly three
IO/authority gates, their existing3-method boundaries and Source inverse/witness:

- writer.export_shard explicitly selects source_index,row_group,row_number from
  original PIECES_SCHEMA before emitting permanent f64 locators. The old query
  lacked those columns and would fail at the first real record.
- selection_database replays the original frozen diagnostic target exclusion
  after all independently accepted additional geometries enter selection. It
  follows each actual parent_geometry_id through the already hashed full
  geometry table; exact held bases/descendants, unknown lineage and cycles HOLD.
  Sampling, values, masks and old tables are not changed or silently filtered.
- metadata.seal and store.open_accepted both call the same read-only complete
  publication validator. Both independent Root reviews are actual SHA-pinned
  documents with required schema/status/reviewer and exact candidate/C0/output/
  configuration equality. The unchanged SB1 actual_family validates the real
  candidate-producing Parent (which may precede a reviewed continuation).
  All five published configuration wrapper contents, joint policy, scope and
  full actual Model/Pprime acceptance are checked. Neither C0 alone, a manually
  set consumer_release boolean, nor a Root-looking filename is sufficient.

The CPU inverse adds four entire-function byte+AST comparisons against embedded
whole-SHA R1 Source witnesses and seven unchanged whole Source leaves. New
helpers are explicitly new IO validation, not claimed old mathematics. The
existing3 methods now include actual synthetic f64 pieces→export_shard→LMDB
locator readback; held-base/new-child/unknown/cycle exclusion; and absent review/
substituted output rejection. Total same-Parent preflight remains15 methods.
PowerShell author checks were Source text/hash only; no Python/AST/tests/DATA
ran. Root must actualCPU-check these boundaries/inverses. No new resource,
queue, parent-C0 fiction, scientific retry, policy or data algorithm is added.