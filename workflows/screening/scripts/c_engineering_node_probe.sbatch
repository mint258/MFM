#!/bin/bash
set -euo pipefail
# Root-only submission: exact node14..19, k24, 32GiB, 02:00:00.
ROOT=/share/home/zixiao/descriptor_analysis/runs/phase1_screening_20261011
NODE=${1:?node index 14..19 required}
export PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES=''
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
cd /share/home/zixiao/descriptor_analysis
mkdir -p "$ROOT/c_engineering/nodes"
set +e
/share/home/zixiao/.conda/envs/chemprop/bin/python -B "$ROOT/scripts/c_engineering_node_probe.py" --node-index "$NODE" --runtime-seconds 5400 --output "$ROOT/c_engineering/nodes/node_${NODE}_job_${SLURM_JOB_ID}"
task_rc=$?
printf '%s\n' "$task_rc" > "$ROOT/logs/c_engineering_node_${SLURM_JOB_ID}.exitcode"
exit "$task_rc"
