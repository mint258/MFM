# Direct full Common TRAIN normalization

One Main CPU Slurm producer, after Common and D5 manifests close:

```bash
export CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
/share/home/zixiao/.conda/envs/chemprop/bin/python -B -m unittest workflows.data_v1_final.labels.window2_normalization_v1.test_normalization
/share/home/zixiao/.conda/envs/chemprop/bin/python -B -m workflows.data_v1_final.labels.window2_normalization_v1.run --coverage /lfshome/zixiao/data_v1_20261025/full_projection_coverage_20261105_r2/manifest.json --common CLOSED_COMMON_MANIFEST --d5 CLOSED_FINAL_D5_MANIFEST --output /lfshome/zixiao/data_v1_20261025/window2_full_TRAIN_normalization_20261105_v1 --workers 16
```

Root supplies actual Common and D5 paths and the standard pyarrow dependency
path for the chemprop environment. No startup proof, provider, receipt, ACK,
source hash, independent reread/QA or second complete statistics fit is used.
The same CLI resumes the original active exact radix query using its committed
per-group checkpoint; completed groups of that query are reused. Prior failed
attempt outputs are retained. No memory/time/cost stop is added.

Scientific functions are the original RadixCounts/advance/initial_queries,
TSQR256/merge_qr, WinsorMoments, JointMoments, inventory/views and Chan reduction.
The original 171 logical owner groups and their file/physical row order remain.
One full element-reference fit is followed by exact .001/.999 type-7 tail
refinement, winsorized mean/std and per-element/physical-invariant statistics,
and exact field median/MAD. Algorithmic radix refinement passes are part of
this one fit, not independent validation. The original scientific source cache
and masks, including EA physical-range masks, are consumed unchanged. New-mask
fractions are reported; no manual-review list or mask-percentage stop is added.

Eligibility is final Common AND effective TRAIN AND not an explicit original
D5 PM7 native-record ID. Excluding that actual conformer excludes all its
original task/input-view labels. VAL/FULL are never fitted. The reader checks
original typed record/ordinal/role, original base owner alignment and full
14-task mass when producing the statistics. It caches only the current logical
group's canonical owner and base-Z lookups to avoid repeated SQLite queries;
float64 scientific payload/masks remain original.

The manifest declares full PM7 P/D TRAIN statistics. Pprime is a separate
independent dataset and is not represented by PM7 statistics. Completing U
normalization must follow the original D1 condition policy and actual Pprime
source, rather than relabelling this PM7 output. Publication/model wiring can
use the four exact numerical result references in `manifest.json`.
