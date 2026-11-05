# Full TRAIN/FULL v3.1 source producer

This is the actual full source bridge, sharing the existing MFM4 codec and
assembler. Root is the only Slurm submitter. Fill the final paths in
`plan.template.json`; do not label a still-running Common/Pprime source closed.

```
python -B -m unittest workflows.data_v1_final.export.v31_stream_v1.test_stream
python -B -m workflows.data_v1_final.export.v31_stream_v1.uff_d3 --plan PLAN
python -B -m workflows.data_v1_final.export.v31_stream_v1.run --plan PLAN
```

The UFF D3 producer can start as soon as final Common/physical maps close. It
needs `common`, `coverage`, `extra_geometry_tables`, `source_working_root`,
`uff_d3_cache_root`, `workers`, and optionally `molecules_per_block`; it does not
wait for D7 or D4. It reads the original native graph/SMILES and calls the
unchanged `c_engineering_wire.corrected_base` once on each actual F64 UFF
geometry. D20 is consumed from its original PM7 molecule source at export; it
is not substituted for UFF D3. Closed per-MID D3 commits resume without native
recomputation. SQLite cache files have `(mid,conf,gid,atomic_numbers,entries,
issues)` and a graph table shared by the actual original native anchor. `entries` is the original
K.pack_entries binary F64 values/masks/reasons, pickled without a new hash.
The cache is reusable by UFF D statistics and D6; no second D3 call is needed.

For the export, `protocol_map` consumes the existing production-contract map directly (including original refs without a bytes field). Additional `protocols` entries can extend exact original call bindings:
`{"package_sha256":"existing raw reproduction_package_sha256",
"protocol_reference":{"path":"original protocol.json","bytes":...}}`.
This includes both WP5 and Pprime packages. The original renderer uses each
original RID/protocol, including the original scientific perturbation seed;
its input coordinates are parsed with the original input-coordinate parser.
No input file/content hashes are newly computed. The raw existing bundle and
input-file witnesses are retained. Do not supply one guessed protocol for
all packages or infer input views from a task name.

PM7 uses the full original numeric catalog entries and D4's already produced
sparse mask overrides, with no independent EA reclassification. Pprime uses
all-role Pprime typed cache plus its exact original raw CELL locations; new
first-two producer batches are already incorporated by that cache. The raw
r73 ordered endpoint/basis/channel/onsite/value records remain complete.

TRAIN is final Common TRAIN. FULL retains every original FULL molecule and
Common VAL/ROUTINE. M15 marks ROUTINE; M16 marks Common. M6 counts addressable
P/U records. M17 is aligned with all addressable U records and marks ordinary
Sprime membership. Registered Pprime-only extras are retained as real U
records with M17=0 and are excluded from ordinary fixed-random/energy/diversity
orders and the default ordinary count/k-grid. Explicit D7 null availability
remains unavailable; no energy/diversity rank or absent geometry is filled.
D5 uses frozen actual physical IDs, including all corresponding task views.

Numerical source projection runs in original canonical owner-job groups, using the same forward typed/raw reader as D4; full-index file metadata is loaded once per worker. transient block SQLite
contains only training F32 arrays, and is removed after closed consumption.
The accepted N1 physical component has an explicit accepted type for absent status columns; present NULL/False statuses are not promoted. Actual UFF Z and the source native graph order must align. Each split is written, closed, compacted exactly once, then its fresh owned
write scratch is reclaimed. `working_roots` and `compact_roots` can override
TRAIN/FULL paths on different real filesystems. Producer checkpoints preserve
a completed split on ordinary transport or later-split recovery. Prior failed
attempts and all old D3/original sources are preserved.

The one producer-end check uses a seeded 1000-physical-record selection over
P and U: source F64 projection to the sole F32 cast is compared in the original
stream, and compact output has the same shape/index/integer/NaN and abs+relative
1e-6 comparisons at the end. No original numerical reread is performed; old
v30 was historically deleted and is not reconstructed as a comparison source.
Counts come from the final physical maps, including addressable extras.

Distribution uses `rsync --sparse` for each actual split root and the common
schema/manifest. Determine destinations after completed product sizes exist;
set gpu_nodes then rerun the same CLI to resume distribution without repeating
projection, compaction or the final numerical check. No new SHA, receipt,
independent QA, throughput experiment, or artificial capacity/time stop is added.
The approved r73 sigma/pi pair targets reuse the PM7 D4 or Pprime cache F64 sums and masks, bound to the same raw directed K endpoint first-occurrence order. Two additive pair_labels columns are cast once to F32; schema.derived_r73_pair_targets exposes their selectors. All original r73 arrays31–34 remain complete. The selected1000 F64 cast comparisons include these two target columns. Historical stores without these columns retain their raw-F32 aggregation fallback precision.

`prepare_runtime --plan PLAN` binds the closed Common and Pprime metadata once.
Actual Pprime rows without a registered GID keep their original NULL source
GID; a literal `pprime-source:<opaque RID>` addresses the existing physical
source row only, with ordinary membership and training eligibility false.
No coordinates are copied and no scientific conformer index is minted.
Already produced UFF D3 GIDs are reused; only these additional real source
points invoke the original D3 callable. The combined cache references old and
new files without F64 duplication. M18 copies exact Pprime fit_eligible flags.

The concrete external full plan is
`control/window2_20261105/D6_full_20261105_v1.plan.json`; its Slurm script is
`full_d6.sbatch` (32 CPUs on compute-0-20/all, no GPU, no artificial memory or
wall-time limit). It runs no repeated unit/QA job. Lustre `/lfshome` holds fresh
source/write scratch; XFS `/share` holds the final compact outputs. Parent
submits after final D4/Pprime/cache dependencies close, then observes actual
RSS and sizes. GPU destinations remain empty until actual products exist.