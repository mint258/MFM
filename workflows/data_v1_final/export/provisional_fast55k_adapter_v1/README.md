# Provisional Fast55k actual-payload bridge

Source only, 2026-10-30. The author did not run Python, AST, tests, data readers,
SSH, Slurm or training. Shared Model source and frozen Data producers are
unchanged. No actual D3, GPU-local performance or payload ACK is claimed here.

The runtime family is `actual_pilot_provisional_fast55k_v1`, version
`v1-pilot-provisional`: actual 50,000 TRAIN / 5,000 ROUTINE VAL, D5 exclusion,
fixed-random order only. It is independent of final Common / D6 / D7. The D1
joint object signs policy/configuration, not actual payload acceptance. The
verifier preserves that distinction and verifies real D3 C0/raw accounting.

## Executable interfaces

These are in-process calls from an already admitted real GPU verification /
payload Parent. Its existing UUID lock and live resource guard remain active.
There is no new queue, proof, approval layer, benchmark threshold or test set.
Do not exec a second program to carry a context: the original guard and locks
would not survive. The local-I/O standalone CLI deliberately exits.

1. `host_context.capture_and_readback(plan_path, context_output,
   check_host_resources=existing_guard, **actual_host)` calls the existing
   `provisional_d3_local_readback_v1.run.run` in the same PID. `actual_host`
   consists of the original host startup/request references, actual GPU
   UUID/name, its existing GPU-binding evidence, the already verified
   `CUDA_VISIBLE_DEVICES` mapping, and actual remaining wall seconds. UUID
   visibility is accepted directly; numeric visibility needs that existing
   verified UUID mapping. No device zero is inferred. The callback is required.
2. After real D3/local-I/O receipt, call `prepare.build(inputs, fresh_output,
   check_host_resources=existing_guard, diagnostic_supplement_reference=None,
   diagnostic_local_copy_reference=None, include_native_bond_status=False)`.
   Output must be below the actual physical `/tmp/` copy root. Its
   `ACTUAL_PROVISIONAL_FAST55K_MODEL_BINDING_V1` binds all original stores,
   source metadata, actual D4 series, local file identities, typed targets,
   reason codebook, per-source indexes and source pins. It does not refit D4.
3. Set a Model request's rawref `provisional_fast55k_binding` to that binding
   and its `adapter` to this directory's `adapter.py`. Keep mode
   `authoritative_pilot`, scope `pilot_smoke`, original configuration and
   actual source/registration fields. For direct transport use
   `adapter.verify_and_bind_model_v3_provisional_payload_inputs(request)`;
   it returns `(LabelRegistry, ReaderFactory)`. `factory().read_geometry(gid)`
   loads an exact exported geometry and its actually present typed targets.
4. `adapter.payload_readback(request, explicit_actual_geometry_ids, fresh_json,
   check_host_resources=existing_guard)` invokes the actual Model typed
   constructors and writes an execution receipt. It binds D3, binding, local
   inventory, actual Model/reader source, IDs and target classes/audit hashes.
   `Model_payload_ACK` remains false: Model Root supplies its actual acceptance
   after reviewing the real load. Choose IDs from the actual catalog covering
   TRAIN and VAL and the actual families/input views; no synthetic IDs.
5. The original training hook is
   `adapter.verify_and_bind_model_v3_pilot_TRAIN_inputs(request)`. It reuses
   Model `VerifiedDataRelease`, `RealDataProvider`, `make_proxy_inputs`,
   normalization types and typed decoding. It requires the real third role;
   it never manufactures it. `mechanical_request_projection(request)` returns
   the original provider's exact input projection before Root seals the final
   request; its identity excludes request SHA in the original Model source,
   preventing a hash loop. Original Model request checks/registration remain.

`prepare.inputs` uses exact existing rawrefs (path/bytes/sha256):

```
D3_export_reference        configs/data_v1/v1-pilot-provisional/D3_export.json
D4_normalization_reference configs/data_v1/v1-pilot-provisional/D4_normalization.json
D5_delivery_reference     configs/data_v1/D5_v1_pilot_provisional_delivery.json
joint_contract_reference  D1_v3_0_joint_interface_freeze_20261029_v1.json
local_io_receipt_reference actual same-Parent GPU-local I/O receipt
reason_codebook_reference original producer reason codebook
model_field_pooling       explicit Model target_id -> pooling choice
structural_fields         original Model S atom/noise/bond FieldSpec dictionaries
structural_binding        original StructuralFieldBinding names
geometry_source           PM7 or Sprime_UFF (independent index, never merged IDs)
validation_batch_size     explicit existing Model batch size
source_references         actual 8 runtime .py files in this namespace plus all
                          actual dependency / Model source pins used by Parent
```

The actual producer constructs D2/configuration and D4 outputs; no future
statistics/hash/path is guessed. Full role indexes and the local catalog are
data artifacts, with small SHA-bound membership headers for the Model's
2-MiB metadata API. Parent budgets include these artifacts, opaque copies,
diagnostic copies if used, and its existing guard/whole owned-tree storage.

## Optional real diagnostic supplement

Only an externally closed `ACTUAL_D3_DIAGNOSTIC_SUPPLEMENT_V1` is accepted,
not the producer's pending receipt. It must bind the same D3/D4/D5, real parent
C0/raw accounting, real selected-GID Parquet and seen-intersection MID Parquet.
Call `diagnostic_copy.copy(supplement_ref, base_local_root/'diagnostic',
check_host_resources=existing_guard, copy_cap_bytes=actual_host_budget,
local_disk_reserve_bytes=actual_host_reserve)` first. It copies original bytes
and full F64 authority. Pass its actual receipt to `prepare.build`.

The immutable writer name stays unchanged. Catalog aliases use manifest
`consumer_alias_prefix='diagnostic/'`; physical files use a separate diagnostic
subdirectory, preventing collisions with base D3. `effective_role='TRAIN'`
is the actual seen-molecule role; explicit supplement membership overrides
sample role to `TRAIN_UNSEEN_CONFORMATION`. Every GID must match the real
diagnostic index and have `training_excluded=true`, `diagnostic_only=true`.
Diagnostic MIDs must be a subset of actual pilot TRAIN. Only index `is_base`
enters UNSEEN sampling with its original zero-based random rank / original N;
children/input views do not add N. No held record is reinserted into TRAIN.

## Three-file Model patch, isolated copy only

Actual artifact:
`docs/interfaces/provisional_fast55k_model_v2_three_file_patch_v1.json`.
It contains full base SHA and exact one-occurrence before/after source
literals for only `v3_data_adapter.py`, `v3_pilot_smoke.py`,
`v3_physical_policy.py` in the reviewed `MFM_model_v3_delivery_integration_v2`.
It retains old final/fixture branches and original numeric/model logic. New
admission uses `provisional_population`, never an invented Common/final
release. D4 tensor helpers delegate to the same actual-series projection;
physical exposure delegates to the actual producer target policy plus the
unchanged signed Native30 decision. Pilot evidence aliases use the real
signed D1 `formal_design.md`, not a made-up final contract.

Root/Model first creates its own isolated copy/worktree named
`MFM_model_v3_provisional_*`. Only after static review, this source CLI applies
the artifact to that copy (the author has not run it):

```
PY -B -m workflows.data_v1_final.export.provisional_fast55k_adapter_v1.apply_model_patch \
  --model-copy /ABS/MFM_model_v3_provisional_fast55k_v1 \
  --patch /ABS/Data/docs/interfaces/provisional_fast55k_model_v2_three_file_patch_v1.json \
  --receipt /ABS/FRESH_model_patch_receipt.json
```

It checks all three base SHAs and all literal sites before any write, rejects
shared-tree names/symlinks and records actual output SHAs. No shared Model
source, Git registration, tests or training is performed by this utility.
Model Root still registers its exact resulting source and original request.
The actual Model CLI remains `tools/model_v3/run_proxy_experiment.py run
--request ... --request-sha256 ... --input authoritative_pilot --output ...
--lineage-root ... --lineage ... --segment-id ... --until-samples ...`;
this source task does not authorize or launch it. The existing smoke/2000
update requirements remain distinct from a real payload-load receipt.

## Exact numerical and consumer limits

All 146 original component definitions remain; physical heads group only as
the actual producer mapping specifies. Original F32 wire values/masks/reasons,
integer IDs, native atom order and source geometry anchors are retained.
The local copied F64 SQLite payload is SHA-bound to each original wire record;
the reader never falls back to the shared original path. r73 calls original
`ordered_entries_from_f64`, keeping both literal channels, order, duplicates,
onsite/source flag, reasons and one F64->F32 cast checked against actual wire
bytes. Tensor6 order stays xx,xy,yy,xz,yz,zz with original component / geometry
masks; r674 physical loss remains OFF. Degenerate scales are typed disabled
dispositions, never s=1. TRAIN actual D4 means/std/tail bounds and original
element models are copied, not refitted on VAL or diagnostics; Model losses
use the same affine transform for raw-unit prediction and target.

The current nonaxial r73 definition supplies no Source-proven numeric frame
origin/basis. It remains fully available for transport. Training requesting
that field fails precisely; no zero/identity frame, mask rewrite, global r73
disable or new QM is supplied. Arbitrary caller frame dictionaries are refused.

Different program-input/perturbed geometries remain separate GIDs. The current
Model collator requires each requested typed ordered/tensor target on the
sample's exact geometry. Missing requested typed targets fail explicitly;
the bridge does not invent placeholders or attach child labels to a parent.
This is a training-consumer routing limit, separate from loading all actual
payloads / the real diagnostic supplement. Energy/diversity/minimum-energy
requests are refused because this D3 exposes only fixed_random.

D3 retains native bond arrays but no literal native status. Optional preparation
`include_native_bond_status=True` reads only the existing original record-SHA
decoder's stored status/fail string, with source identity before/after; it does
not call graph/UFF/QM or worker_init. This historical readonly decoder may
decode legacy pickle; the new transport/catalog/training format never writes
pickle. A requested S bond head without a real literal status fails rather
than receiving guessed `ok`. Direct physical-payload readback does not require
this optional S status supplement.
