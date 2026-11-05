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

Future D6 and transport writes require `disk_protection` in the runtime plan.
`disk_guard --plan PLAN preflight` resolves every actual target with findmnt -T,
df -B1, df -Pi and statvfs. Group all paths on the same filesystem in one target
budget; include all windows' concurrent growth. Each target must explicitly set
`paths`, `peak_additional_bytes`, `peak_additional_inodes`, `reserve_bytes`,
`reserve_inodes`, `concurrent_bytes`, `concurrent_inodes`,
`runtime_margin_bytes`, `runtime_margin_inodes`, and `quota_scope` (limited or
not_applicable). Root filesystems automatically retain at least max(10 GiB,
10 percent). Other reserves come from the actual site and shared allocation.
The additional peak is future physical growth, not the existing source size:
existing sources, failed partials and old/new coexistence are already charged
to current availability, while future source spools, raw LMDB, compact copy,
rsync partial/temp, ID maps and concurrent writes must all be included in the
peak. Never count a planned future cleanup as available space.

Limited quota targets additionally require `quota_probe_argv` (actual command
printing current available bytes as one integer), `quota_peak_additional_bytes`,
`quota_concurrent_bytes`, and `quota_reserve_bytes` (at least 100 GB). Unknown
capacity/quota cannot start a new write. Runtime checks use actual statvfs and
refresh the quota probe at most each `poll_seconds` (positive, at most five).
Runtime margins must cover all workers' write bursts/SQLite rollback, LMDB
page growth, metadata-ref transactions and monitor latency between checks.
This is a storage safety reserve, not a wallclock/RSS/scientific stopping gate.

Before each source-piece/spool-MID and writer-MID write, guards check reserves
and wait without deleting any data. Compaction and optional metadata rsync run
as owned subprocess groups: lack of bytes/inodes/quota pauses only that group
before the reserve, then continues the same process after capacity returns.
For future cache/transport control scripts, execute on the actual destination
node (local paths must resolve there):
`python -m workflows.data_v1_final.export.v31_stream_v1.disk_guard --plan PLAN transport --destination TARGET --remaining-bytes N --new-inodes N -- rsync -a --sparse SOURCE TARGET`.
No GPU-node copy is introduced; final TRAIN/FULL compact copies remain shared.
The sole new `test_disk_guard` toy FS/subprocess fixture includes admission,
root/quota/inode reserves, pause/continue and a closed producer-check cache.
Do not rerun the old suites or dataset QA for transport recovery.

Ordinary disk pressure waits in-process. A passed producer-end sample check is
immediately atomically cached before final output metadata writes, so a later
storage-only continuation reuses that check.

Source spools are a bounded pending window, not a retained full-dataset copy.
Each task remains exactly one original source-job/split, with original MID order.
`streaming_buffer_blocks` optionally reduces the pending window (1..workers);
its default is the original worker count. No new pilot or target pass is added.

At the last MID of a block, producer-only `_source_block_end` control metadata
requests LMDB.sync, closure of the block's external-ID Parquet fragment, then
an atomic writer checkpoint. Only after that successful checkpoint does the
producer acknowledge consumption. The stream closes its SQLite reader before
unlinking that exact private F32 spool. These control fields never enter MFM4.
A lost acknowledgement after checkpoint can leave a harmless closed spool;
completed source-job ordinals are skipped before enqueue on continuation.

The checkpoint preserves the molecule cursor, global r73 codebook, RNG state,
samples, counts/bytes and closed ID-fragment refs. Cold continuation opens the
same owned raw LMDB and removes only keys in its uncheckpointed MID tail (M/P/U
key ordinals only; no numeric values are read). The committed prefix is left
untouched. The current unacknowledged block reuses its closed F32 spool, while
all acknowledged blocks are skipped. Unregistered partial ID fragments are
preserved; a fresh fragment attempt is used for the unclosed block. Split-end
ID merging reads only external identity metadata in original fragment/row order
and retains the exact original Parquet schema. Raw LMDB, final IDmap and original
counts close into a `raw_closed` checkpoint before compaction, so a cold restart
at that phase does not re-encode the split or reopen original labels. Completed
compaction has its own checkpoint stage. Original science, seed/order, target
arrays, masks, F64 cast and single producer-end QA remain unchanged. The only
new `test_block_checkpoint` fixture uses tiny owned LMDB/ID metadata and mocked
source jobs/compaction/QA, including an interrupted MID and interrupted compact.

Optional shared external IDmap: `id_map_storage="external_symlink"` retains the
single closed ID Parquet in the central NFS output root; the Lustre split's
`id_map.parquet` is an absolute symlink, so ordinary relative-path readers keep
working. Manifest `id_map_physical_paths` states its actual shared location.
The target's original bytes/schema/identity order are unchanged. After the
merged IDmap and raw_closed checkpoint are durable, registered fresh input
ID fragments are consumed and reclaimed; unknown/partial files are preserved.

Optional TRAIN compact streaming uses `chunk_compaction` with `enabled=true`,
`splits=["TRAIN"]` (default), `chunk_bytes` (default 4 GiB), and `targets`.
Each target supplies `directory` and positive `capacity_bytes`; remote targets
also supply `node`, `repository`, `python`, and `guard_plan`. Targets are storage
allocations, not scientific thresholds. Their combined admitted capacity must
cover the actual closed raw data.mdb file-size upper bound; descriptive pilot
means are never used as a hard bound. All target paths must be covered by an
actual-node disk_guard plan with system/site/concurrent/quota reserves. NFS or
Lustre targets visible on the producer omit node. A node20/node21 local target
always uses its actual guarded SSH receiver, never the producer's /tmp. SSH
retains stdin, receiver admission validates a clean JSON protocol before any
stream begins, and each receiver checks its own statvfs/quota before writes.
No new Slurm allocation, undrain or model-node LMDB distribution is introduced.

The original installed LMDB0.9.31 `mdb_copy -c SOURCE` emits one compact stream
to stdout when destination is omitted. That single stream is split into exact
ordered binary chunks with one-MiB memory buffering, no compression/hash or
scientific interpretation. Each chunk closes by fsync and atomic rename; only
path/bytes/ordinal/target checkpoint metadata is recorded. Disk pressure blocks
the sink; pipe backpressure keeps the same compact process alive without more
writes. CHUNKS_CLOSED requires every chunk plus the one mdb_copy process C0.
Only then may the checkpoint-owned fresh raw LMDB be consumed/reclaimed.
Concatenation writes one actual final data.mdb, checkpointing/fsyncing per chunk.
Cold continuation truncates only its uncheckpointed output tail and resumes at
the next chunk, without repeating compact or QA. COMPLETE then allows normal
lifecycle cleanup of only that attempt's private temporary chunks. Final TRAIN
and FULL still each have exactly one shared LMDB; schema/checkpoints may stay
on NFS while compact_roots point to Lustre.

A dead mid-stream compact prefix is INCOMPLETE, not CHUNKS_CLOSED. Raw and all
partial/closed chunks are preserved. No new attempt is automatically launched.
Root may select ordinary failed-attempt recovery after confirming the exact
old PID/attempt is dead and raw is still closed, using
`recover_incomplete_attempt={"attempt":OLD_TOKEN,"confirmed_old_pid_dead":true}`
after renewed target admission. Existing complete chunks/concat are always
reused and never re-compacted. Earlier failed attempt metadata/chunks remain
preserved. This is an execution recovery, not a scientific change.

Limited shared quota targets may use `quota_available_reference`,
`quota_expected_uid`, `quota_expected_filesystem` and `quota_max_age_seconds`
(at most five) instead of quota_probe_argv. Every check validates the fresh
small snapshot through quota_snapshot.read_available; unknown/stale/future or
identity mismatch waits fail-closed. Mount inspection first triggers autofs,
then requires exactly one matching non-autofs actual filesystem/device.

The only new `test_chunk_compaction` fixture uses toy bytes, fake SSH/mdb_copy,
concat interruption and tiny external-ID metadata. It adds no dataset QA or
numeric replay; already passed guard/block suites need not be repeated.

Checkpoint I/O uses owned append-only `producer_seen_journal.bin` and
`producer_samples_journal.bin` ledgers. Only new MID strings and dirty sample
append/replacement events are serialized, with framed protocol5 payloads that
preserve the existing F32 array bytes. In-memory seen/sample algorithms, RNG,
source order and the chosen 1000 physical sample keys are unchanged. The main
checkpoint stores closed byte offsets, event counts and set/list counts instead
of repeatedly storing the entire seen set and every sampled array. A checkpoint
with no dirty events appends no ledger bytes. This avoids rewriting stable
sample payloads and the growing full MID set at every source-block boundary.

Closure remains LMDB.sync -> ID fragment closed -> both journal fsyncs -> atomic
checkpoint -> acknowledgement -> spool-reader close/unlink. Cold continuation
reconstructs the in-memory set and sample slots from only closed journal prefixes
and truncates only those owned ledgers' uncheckpointed tails. It reopens no
numerical source, recasts no target, and performs no QM/D3/QA. Existing legacy
checkpoints with full seen/samples are migrated once from their already loaded
objects into fresh ledgers, then atomically published with journal references;
legacy or unrelated journal files are never adopted or overwritten. The sole
new test_state_journal fixture covers dirty replacements, append-only prefixes,
truncated tail recovery, legacy migration and tiny writer cold continuation.
Previously passed chunk/guard/block fixtures are not rerun for this change.

Root executed only the new chunk/external-ID fixture (1 PASS, 1.604s) and dirty-state journal fixture (1 PASS, 6.096s) once successfully in the production Python environment. Prior guard/block fixtures are not repeated. Actual D6 data writes remain unadmitted pending closed producer sizes and combined storage budgets.
Optional `source_spool_root` routes only newly created private F32 block SQLite
files to a producer-visible, actually admitted mount. Missing/empty keeps the
original source_working_root behavior. Canonical block JSON markers, identity
and auxiliary/cache indexes, source_molecule_groups and source cursor remain
under source_working_root. A marker's existing closed payload is reused before
any new spool directory is guarded/created, even when the storage hint changes;
no closed block is migrated or recomputed by changing this parameter. Markers
retain the actual payload path and original MID order. Reader closure and
checkpoint acknowledgement still precede unlink of that exact private payload.
prepare_runtime and cold writer-plan comparison permit updating this storage
hint without changing frozen science. Both canonical metadata and physical
spool destinations require actual disk_guard coverage. A remote node's /tmp is
not visible scratch on this producer; no remote SQLite/sshfs layer is added.
The sole test_spool_path toy fixture covers default/override paths, original
closed-ref reuse, admission before new directories and bound-plan hint update.
No previously passed suite or scientific data is read or replayed.

The new optional spool-path/closed-ref fixture passed once in the production environment (1 test, 0.179s); existing successful suites were not repeated. No real D6 spool/compact stream has started.
