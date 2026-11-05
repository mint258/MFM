# One shared v3.1 writer for D6 and later data

This package reuses the delivered `pilot_v31_compact_v1.codec`, schema compiler,
assembler, LMDB writer, ID map and `mdb_copy -c`. It writes one default LMDB for
TRAIN and one for FULL. Original ROUTINE/VAL belongs to FULL, with M array 15=1;
other FULL molecules have array 15=0. The source role and held-out selections
must come from final Common/D5. Original D5 flags remain in M arrays 13/14.

`projected_source.assemble_entries(mid, entries, schema)` accepts already
projected original scientific arrays, their original GID and metadata. It uses
original atom-order/graph alignment, original physical conformer identities and
validity masks, and casts floating arrays once to F32. It enables the same full
P-label layout on U, so U retains real Pprime values, pair arrays and ordered
r73. It never substitutes PM7 values on U. The delivered pilot's default
geometry-only U behavior remains unchanged.

`run.export(plan, molecules, schema)` consumes those whole-molecule outputs.
Before encoding, its deterministic reservoir retains 1,000 projected source
conformers (or all when fewer); at the end it compares emitted MFM4 arrays and
M topology/roles/holdout marks once against those producer source values, using
`1e-6 + 1e-6*abs(reference)` and exact NaN/index agreement. It does not reread or
reproject original scientific files. Alignment/topology is checked by the
producer assembler. Final molecule/conformer counts must equal the supplied
closed Common/geometry counts. It compacts once per split and distributes with
`rsync --sparse`, without a benchmark, SHA, receipt, F64 copy or second QA job.
The final `manifest.json` lists path/size/records and the one producer check.

The CLI is `python -B -m workflows.data_v1_final.export.v31_stream_v1.run --plan PLAN`.
Its plan requires `source_factory=module:function`. That real source factory
returns `(schema, iterable_of_whole_molecule_assembler_outputs)`. Additional
required keys: output_root, working_root, sample_seed, expected_molecules
(TRAIN/FULL), expected_conformers (TRAIN_P/TRAIN_U/FULL_P/FULL_U), data_version.
Optional keys: estimated_split_bytes, gpu_nodes, node_destination_root,
source_dependencies. Estimated sizes are LMDB initial map sizes only; they grow
when needed. No memory/time/cost stop is introduced. If the closed manifest
already exists, a repeated CLI invocation resumes distribution only.

The actual full scientific source factory must still join completed final
Common/D5, physical geometry tables, original WP5 and Pprime values/masks,
all final conformer orders and full TRAIN D4. It must use the existing original
source projection functions; this writer does not fabricate those dependencies.
`full_physical_index_v3` supplies exact raw source row locations and grouped
numerical reads for that factory and D4. Root owns its actual execution.

Necessary new unit tests (one execution in a real CPU allocation):
`python -B -m unittest workflows.data_v1_final.export.v31_stream_v1.test_stream`.
