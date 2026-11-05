# TRAIN-only native store sidecar

This is model-line metadata for consuming existing frozen downstream records.
It does not replace the data-line D-1 pretraining contract, define new labels,
change native atom identities, generate geometry or alter official roles.

The native P1DS1 decoding reference is
`workflows/phase1_downstream/stage60_downstream_binding_v3/downstream_binding_data.py`
at baseline commit `037546cd7f07b32dbb46bc21a69109dfd273f8da`, SHA256
`2d79d1e73f07c2e277b28724225d64b138c7050d3a54a29de474d462c4bf5766`.
The Phase1 protocol reference is recorded in `configs/dev_panel_v1.json`.

Before an actual panel evaluation, the root coordinator must supply one
ordinary, byte-bound external JSON file with the following fields. The
projection must use the authoritative native source-member and role metadata;
it must not read, decode or copy excluded target frames to construct the file.
Missing group identity or authority is an execution error, not permission to
substitute record IDs, infer chemical identity or reassign source membership.

| Field | Required meaning |
| --- | --- |
| schema | `model_v3_training_role_store_v1` |
| source_complete | True only for a closed, accepted native source export |
| targets_in_metadata | False; do not copy target values or annotation/provenance text |
| native_record_hashes_preserved | True; each offset/shape/hash comes from the original source index |
| source_store_manifest_sha256 | Exact SHA of the original accepted source-store manifest |
| data_version | Immutable source version used by the request and every result |
| records_file | Original physical payload path and byte size; retain its original whole-file SHA as a source reference if available, without remeasuring excluded target bytes |
| records | Only the native records belonging to the declared TRAIN-source roles |
| contracts | Authoritative task/output declarations and ordered native TRAIN/inner-validation membership, with original source-contract SHA |
| molecule_groups | Every allowed source member mapped to its source `member_uid` and complete, authoritative original InChIKey |

Each `records` item has exactly:

```
dataset_id, member_index, member_uid, native_n_atoms, target_rows,
tasks, geometry_ready, offset, bytes, sha256
```

No `_targets`, annotations, target-bearing provenance or extra fields are
accepted in a record item. Counts and offsets are bounded. The original
closed payload is not rewritten or repacked by this adapter.

Each `contracts` item identifies `dataset_id`, `fold_id`, `tasks`,
`output_level`, `source_contract_sha256`, `member_indices` and
`ordered_members`. The latter two mappings contain only `train` and
`train_inner_validation`. These are original source roles; for ExpansionRx
the second original role stays empty. `GroupedTrainingView` derives its new
inner split solely from official TRAIN molecule groups. For the scaffold
datasets use the original fold-0 contract; do not union other outer rotations
to enlarge this panel's population.

Each `molecule_groups` item contains `dataset_id`, `member_index`,
`member_uid`, `full_inchikey`. InChIKey uses the complete original 27-character
key; no 14-character truncation, scaffold proxy or source UID fallback.
Multiple isoform records of one molecule retain separate native records but
share this chemical grouping for caps, CV and bootstrap.

The source sidecar's exact SHA is required by `training_store` in the
evaluation request. The request also binds model JSON, checkpoint,
panel JSON, code inventory, original pretraining seed, actual code commit and
the panel's published preregistration commit. The root coordinator prepares
the request and sbatch with `tools/model_v3/prepare_dev_evaluation.py`; the
tool prints `PREPARED_NOT_SUBMITTED` and does not submit a job.

`evaluate_dev_panel.py --validate-only` checks these metadata bindings and
computes prospective molecular membership and H0 packing hashes without
decoding a target record. `--plan-output` may persist a new external packing
artifact. The default H0 export limits are max_graphs=32,
max_native_atoms=65536, max_padded_pairs=1000000 and atom_bucket_width=16;
they are unmeasured presets, separate from the fixed B32 readout.

Initial requests without per-dataset packing hashes are explicitly marked
`METADATA_PLANNING_REQUIRED` and cannot execute. Feed the printed plan hashes
back into a new prepared request as `h0_packing_plan_sha256`; this binds its
actual metadata-only plan before any encoding. Both encoders use that same
plan. H0 cache v3 binds the full budget and actual plan SHA, restores source
record order after label-free bucketing, and rejects request/plan drift. A
native member beyond a declared preset stays in the complete singleton plan
and fails without being dropped or reported as a measured GPU-capacity limit.

The request's model configuration is the original source configuration, not
an architecture inferred from weight shapes. The encoder bridge safely loads
only known S/generic-training/full-corpus checkpoint schemas, verifies their
native raw/semantic/typed bindings, and rejects unverified historical identity.
Historical B3 additionally needs the byte-bound physical reference and frozen
receipt in `configs/model_v3/historical_B3_H0_reference_v1.json`; its checkpoint
SHA is presently an inherited receipt claim until a real load verifies it.
Both the 384-dimensional candidate and random reference use the same frozen
row-tiling helper and full configuration.

Cache v3 also binds the actual loader/source inventory, separate checkpoint
or random initialization origin, physical custom-module source hashes and the
effective Torch/device/driver/TF32/matmul/runtime policy. FP32 export locally
disables ambient autocast without changing global precision settings. Runtime,
source, weight or native geometry changes cannot reuse the earlier identity.
No real GPU capacity or complete development-panel result is implied.

Actual execution writes the membership manifest before encoding, then reads
only authorized offsets; it verifies each selected frame's exact SHA and
preserves native x/coordinates/target units/masks. It never calls the original
full-store initializer and does not claim whole-payload or full historical
store validation. Incomplete caches/output runs remain on disk and are not
relabelled as successful or deleted.

All sidecars, selected member lists, payloads, checkpoints, H0, journals and
SDK files stay outside Git. Only configurations, code, synthetic tests and
small typed aggregate result rows may enter the repository.
