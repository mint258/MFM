#!/bin/bash
set -euo pipefail
# Root-only: >=16 CPU, suggested48GiB/02:00:00. Depend on closed A and B6 registry.
ROOT=/share/home/zixiao/descriptor_analysis/runs/phase1_screening_20261011
export PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES=''
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
cd /share/home/zixiao/descriptor_analysis
set +e
/share/home/zixiao/.conda/envs/chemprop/bin/python -B "$ROOT/scripts/c_engineering_storage.py" --workers "$SLURM_CPUS_PER_TASK"
task_rc=$?
printf '%s\n' "$task_rc" > "$ROOT/logs/c_engineering_storage_${SLURM_JOB_ID}.exitcode"
exit "$task_rc"
