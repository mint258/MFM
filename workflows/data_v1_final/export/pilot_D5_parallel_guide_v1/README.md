# D5 parallel pilot diagnostic payload

This producer runs concurrently with the D3 55,000-molecule export after the
same actual D4 first complete TRAIN statistics pass, including median/MAD.
It does not require a completed D3 payload or D3 C0.

The parent first projects only the already frozen D5-held bases, direct
children and original program-input views from the closed D4 geometry SQLite
database. It checks their original geometry and atom-order hashes, whole
molecule TRAIN roles, actual original N and last fixed-random base ranks,
and their exact intersection with the original 20,000-molecule D5 lists.
Counts are computed on the admitted CPU. The pilot intersection is reported
as such and is never presented as a newly computed 20,000-molecule payload.

D3 computes the required 69 molecule size correlations once and publishes an
early closed configuration marker. D5 reads that marker and verifies current
CPU hashes of the registry, mapping, projection recipe, target policy and
configuration header. It then uses the same original extraction, ordered r73
transport, permanent F64 authority and one F32 cast. No family is guessed and
no second size-correlation or normalization fit is performed.

The historical Source3 pass is retained and is not repeated in production.
One count and deterministic random sample pass checks at most 1,000 label
records, or all records when fewer are available. This sample is compared with
actual original Parquet fields using row-group-directed IO. Additional
independent replay, 16-reader passes and full F64 second scans are disabled under
the user's simplified export policy. r674 stays LOSS_DISABLED while numeric values and
scientific masks remain unchanged. All records are diagnostic-only and excluded
from pretraining loss and model selection.

The metadata distinguishes frozen selected TRAIN membership from an already
completed D3 export. Actual D3 seen status remains pending until its independent
payload closure; D5 never fabricates that closure or a parent C0. D5's own final
wrapper requires its real external Slurm C0 and complete closed-handle receipt.

Execution:

```text
PY -B -m workflows.data_v1_final.export.pilot_D5_parallel_guide_v1.run --plan ABS --startup-proof ABS
PY -B -m workflows.data_v1_final.export.pilot_D5_parallel_guide_v1.close --receipt ABS --accounting ABS --output ABS
```

The Root coordinator selects an available authorized CPU node, reserves the
existing D5 32-GiB output budget exactly once, omits SBATCH memory requests,
and retires the obsolete serial watcher before submission. The account reserve
is the user's current temporary 100-GB floor after all future budgets. This
producer performs no QM/UFF, new conformer generation, new sampling, training,
scientific filtering change or final Common/D6/D7 release.

The D5 resource adapter keeps the full own future output cap. It disables
active allocation credit for its mutable domain.sqlite and does not impose
an allocated-block monotonicity check on that database. The same database
stays excluded from immutable closed-output credit. Its report explicitly
records zero active credit, credit_disabled=true and whether the domain
actually exists. The original 32-GiB output cap, 100-GB account floor after
all future budgets, RSS/wall protection and scientific DATA checks remain.

The private source IO adapter applies a 3-GiB single-worker RSS soft bound in
both original nested worker checks; their other guards and bytecode remain
unchanged. Sixteen workers stay within the original 56-GiB aggregate RSS and
64-GiB software budget. `resource.one(work)` can also serve a future D3 parent
with the original D3 initializer and reader, without editing shared X.one.

One explicit Root review may authorize reuse of exactly the 101 source groups
recorded closed by failed parent 4525590 in day06. The new admitted CPU verifies
their full current hashes and exact frozen input/configuration/group identity.
Unlogged partial groups and the earlier concurrent-read parent 4525589 are
excluded. The small domain is rebuilt normally. Reused and newly closed groups
are merged only after all new source tasks close their domain handles. The
historical Source3 reference and the single count/sample check are retained.

The private writer adapter keeps `reason_granularity` restricted to actual
target IDs. All other original source projection annotations are retained
separately for each target in the permanent F64 authority metadata, including
the complete binary-JSON native cells, component reasons and None positions.
Training metadata contains a sidecar record/hash reference to those annotations.
No arrays, masks, causes, ordered records or scientific labels are changed.
The existing sampled readback checks the F64 annotation content and its training
reference in the same original QA pass.

A single writer-only continuation may use the complete merged domain of failed
parent 4525591. Its first whole-file hash and exact mutable copy are established
on the admitted CPU. The old domain and unfinished stores remain untouched; only
the new copy's exported/stores/partitions state is reset. All 113 closed group
keys, piece counts and shared configurations must match before writing. Source
projection is skipped. No readback worker pool or throughput diagnostic is
started by this writer-only D5 continuation.

The native bond reader also accepts the existing frozen readonly native root
`/share/home/zixiao/dataset/lmdb_new`. Canonical pointers already refer to these
original sibling-directory LMDB files. A private root binding corrects the old
project-directory-only rejection. The pointer is unchanged; the original '..',
symlink, UID, regular-file, FD/frame, payload-SHA, graph and atom-order checks
still execute. Shared transport/reader sources are unchanged.
