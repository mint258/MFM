Final physical first-two P′ continuation
======================================

This module is source preparation until Root runs the unit tests and production
on a real Main Slurm allocation. It does not change the running
`window2_fill_v1` or the original twelve-task `engine_adapter.compute_pair`,
native software, parsers, F64 values, per-call 900-second timeout, masks or seeds.

Use `plan.template.json` after the final population, original full locator index
and earlier supplemental producer have closed. All supplemental roots must have
their final `manifest.json`; never inspect a live producer's claim database.
The original locator index's QC universe and base pointers identify closed old
records by actual `(molecule_id,sprime_conf_idx)`, with no record-ID parsing.
New closed QC/base publications are reused. Claims without closed QC are UNKNOWN,
including a prior producer's claimed-but-failed record, and are never retried.

Physical reuse additionally requires the same actual source geometry. Preparation
publishes `physical_bindings.sqlite`: real first-two geometries for all roles,
original native anchors/Z/F64 coordinates/existing witnesses, and registered UFF
address metadata. A QC/key match alone never reuses a label. Existing input
witnesses are used first; absent comparable witnesses require the original base
F64 and ordered Z/witness comparison. Any base publication read for this producer
check is cached in that same database, so downstream statistics reuse it rather
than rereading the original numerical source. No new content hash is computed.

Root's existing Python/dependency environment and repository PYTHONPATH suffice:

```sh
python -B -m unittest workflows.data_v1_final.pprime.window2_final_pprime_scope_v1.test_v1
python -B -m workflows.data_v1_final.pprime.window2_final_pprime_scope_v1.prepare --plan final_plan.json
python -B -m workflows.data_v1_final.pprime.window2_final_pprime_scope_v1.run --plan final_plan.json
```

Preparation consumes the finalizer's chosen first `min(2,actual_available)`
physical IDs, restricted to final Common TRAIN/VAL. Shortages remain explicit in
the existing state-table reference. Registered N1 extras are actual geometry
sources with `usage=PprimeOnly`; there is no new N1 generation, padding, rank≥2
or recomputation of a closed physical record. Existing source format/path/row/
member and source original conformer ID are retained. Missing native source
metadata is joined through its actual anchor and the formal record index plus
the unchanged eleven-shard source plan, with original Common file_group.

Actual selected geometries are consumed once in physical source order for the
producer binding; only missing-label tasks are scheduled. Their original
double-precision values are preserved in `physical_geometry_json` in tasks
Parquet. During actual production an existing atom-order witness is
checked; absent witnesses require equality of actual source ordered atomic
numbers and original native Z before reusing the native reader's witness. No
correspondence is guessed or new atom-order hash computed. The native source is
read once and cached at the original compute_pair read seam.

Preparation produces one scope manifest, tasks Parquet and an explicit UNKNOWN
intent file, and references the finalizer's existing shortage state table.
Production produces original family Parquet, raw-retention containers, necessary
record outcomes/checkpoints, claim state and one final manifest. A completed
scope is reusable. A partial scope publication requires a fresh output path;
existing files are retained. The selected-binding phase now commits its complete
bindings and `selected_complete` marker atomically. On the same frozen input
JSON, a retry skips this closed phase without reading its original geometries;
an interrupted partial phase is not marked complete. Later task publication
guards remain unchanged. Normal completion still closes the binding database.
Production resumes its same output and claims:
completed publications close claims; interrupted Native intents stay UNKNOWN.
No fresh hashes, independent QA, receipts, resource stopping gates, or second
numerical readback are added.

The new producer root can be appended to
`window2_pprime_statistics_v1`'s `additional_pprime_roots`; its manifest uses the
same family reference interface. Existing P′ labels outside the final selected
IDs remain preserved and available to the full label cache with fit disabled.
