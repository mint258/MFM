#!/bin/bash
set -euo pipefail
ROOT=/share/home/zixiao/descriptor_analysis/runs/phase1_dataset_rebuild_20261010
export PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES=''
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
cd /share/home/zixiao/descriptor_analysis
set +e
/share/home/zixiao/.conda/envs/chemprop/bin/python -B "$ROOT/scripts/select_bounded_native_panel.py" --records 160 --min-molecules 16 --workers "$SLURM_CPUS_PER_TASK"
task_rc=$?
printf '%s\n' "$task_rc" > "$ROOT/logs/select_bounded_native_panel_${SLURM_JOB_ID}.exitcode"
exit "$task_rc"
