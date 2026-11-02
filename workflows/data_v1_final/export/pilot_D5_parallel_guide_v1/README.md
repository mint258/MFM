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

The existing three Source methods, finite original source replay (all if fewer
than 10,000 available label records, otherwise deterministic 10,000), permanent
F64 readback and up to 16 actual independent whole-molecule readers run in this
same 16-CPU, 24-hour parent. r674 stays LOSS_DISABLED while numeric values and
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
are merged only after all new source tasks close their domain handles; original
Source3, source replay and reader checks still run in the new parent.
