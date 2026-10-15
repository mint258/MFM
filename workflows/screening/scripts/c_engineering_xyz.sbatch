#!/bin/bash
set -euo pipefail
# Root-only: >=16CPU, suggested32GiB/00:30:00, any currently available CPU node.
ROOT=/share/home/zixiao/descriptor_analysis/runs/phase1_screening_20261011
export PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES=''
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
cd /share/home/zixiao/descriptor_analysis
set +e
/share/home/zixiao/.conda/envs/chemprop/bin/python -B "$ROOT/scripts/c_engineering_xyz.py" --workers "$SLURM_CPUS_PER_TASK"
task_rc=$?
printf '%s\n' "$task_rc" > "$ROOT/logs/c_engineering_xyz_${SLURM_JOB_ID}.exitcode"
exit "$task_rc"
