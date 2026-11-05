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
`D6_full_cached_20261105_v1.sbatch` (32 CPUs on compute-0-20/all, no GPU, no artificial memory or
wall-time limit). It runs no repeated unit/QA job. Lustre `/lfshome` holds fresh
source/write scratch; XFS `/share` holds the final compact outputs. Parent
submits after final D4/Pprime/cache dependencies close, then observes actual
RSS and sizes. GPU destinations remain empty until actual products exist.
Optional future node-20 Native IO reuse: set
`DATA_V1_COMPLETED_SOURCE_CACHE_PLAN` to Root's already closed cache plan.
`physical.native` changes only the `lmdb.open` filename on an exact complete
original-path match through the existing KeepSourceMap. No plan or missing key
keeps the original path; the handle key, source pointer, 09d transaction key,
open options, pickle/F64 contents and all scientific identities stay original.
The mapping is loaded once per worker, with no filesystem-content probe or
cache creation. Root's existing mapping tests already passed6100; only the new
`test_native_cache` in-memory reader fixture and original pending stream8
passed once in unused CPU20 allocation6106 (9 tests,4.014s). UFF/D6 do not repeat them.

Optional metadata-only local build: set `metadata_working_root` to a dedicated
node-20 `/tmp` root, separate from the Native-input cache. Geometry and
orders/D5 auxiliary SQLite, rollback journals and SQLite temporary files are
built below that root. Original source/ref order, values, IDs, primary keys,
conflict assertions and final count queries stay unchanged. Membership input
reads only its three consumed columns. Per-ref `build_progress` is committed
in the same transaction as the original rows; only a producer-owned build
checkpoint can resume. Legacy partial SQLite without it is preserved and is
never treated as a resumable prefix; its replacement is a fresh metadata
build, not a repeated descriptor/label calculation.

After the DB is closed, one `rsync --sparse` publishes a shared new-attempt
`.partial` then atomic rename, followed by the formal shared manifest. Its
references always name shared files. Runtime-only hints let this parent and
workers open their same-build closed local copies; an evicted local copy falls
back to the authoritative shared reference. Descriptor/label outputs remain
shared and are untouched. No source numerical readback, hash, benchmark or
extra QA is added. Root runs only the new `test_local_metadata` tiny fixture
once in an actual parent; do not repeat old42. No active process is switched by
merely preparing this optional implementation.
The same new metadata fixture also exercises the real N1 typed metadata_json shape through owned G.physical and the existing strict declared_geometry API: original status/convergence/native anchor are restored, false/NULL and conflicting declarations are rejected, and pprime_extra/ordinary=False are retained. No accepted-path default replaces the original N1 declaration.

Actual continuation on 2026-11-06: Slurm marked node20 DRAIN after its old
metadata-only task exited (Kill task failed); the running PM7 D4 stays there.
UFF 4526124 and pending D6 4526125 use idle 24 CPUs on compute-0-19/all.
The external plans use `/dev/shm/window2_export_metadata_20261106_v1` for
metadata, with shared authoritative references unchanged. The six principal
Native files were transported from the already closed node20 cache to node19;
its exact completed subset map is `control/window2_20261105/native_cache19_closed_plan.json`.
Unmapped sources use the original paths. Only the two new metadata/scratch
fixtures ran once (2 passed, 3.093s); no prior suite or scientific QA was repeated.

Parquet geometry IO keeps only one exact-source-path ParquetFile/footer with
rowgroup offsets and one full decoded Arrow rowgroup per worker. A different
rowgroup releases the preceding buffers before decoding; a different file also
closes its preceding handle. Binary-search lookup slices the original full row
without column selection, value conversion or ordering changes; strict N1 and
all original identity/status assertions still run on every returned row.
Memory scales with one source rowgroup's Arrow buffers plus its footer/offsets,
not the whole source file. Footer total_byte_size is only an uncompressed
encoded-size estimate, not an exact Arrow/RSS bound. The sole new
`test_parquet_cache` fixture uses in-memory Arrow rows and fake footers only.

UFF D3 continuation uses its existing per-MID transaction: labels, graphs and
molecules completion marker commit together. On cold reopen SQLite performs
normal rollback-journal recovery. Committed molecule rows with matching label
counts skip D3; a completed part JSON skips the whole part. Keep the exact
frozen membership/order, block width, part numbering, output root and existing
reuse configuration, and ensure the previous writer processes have exited
before a new writer opens those parts. Only an interrupted uncommitted MID has
no closed product and may be recalculated. No new resume mechanism is added.

Final D6 delivery follows the user's 2026-11-06 shared-storage amendment in
`docs/interfaces/training_format_v3_1_storage_revision_20261105.md`: retain one
shared compact LMDB per existing TRAIN/FULL split, with all model nodes reading
the same authoritative split_roots. The external plan fixes gpu_nodes=[] and
delivery_mode=SHARED_SINGLE_COPY. Do not populate node destinations or rerun the
node-copy distribution step for final data. Complete the original producer-end
check once and notify the model line of the shared manifest/schema paths.
