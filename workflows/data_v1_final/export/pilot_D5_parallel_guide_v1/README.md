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
