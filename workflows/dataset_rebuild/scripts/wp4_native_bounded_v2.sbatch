#!/bin/bash
set -euo pipefail
ROOT=/share/home/zixiao/descriptor_analysis/runs/phase1_dataset_rebuild_20261010
export PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES=''
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
cd /share/home/zixiao/descriptor_analysis
set +e
/share/home/zixiao/.conda/envs/chemprop/bin/python -B "$ROOT/scripts/wp4_native_pilot_v2.py" --panel "$ROOT/bounded_native_panel/pilot_sample_manifest.parquet" --panel-manifest "$ROOT/bounded_native_panel/pilot_manifest.json" --record-index "$ROOT/record_index.parquet" --output "$ROOT/wp4_native_bounded_v2/job_${SLURM_JOB_ID}" --workers "$SLURM_CPUS_PER_TASK" --max-molecules 32 --wall-seconds 1800
task_rc=$?
printf '%s\n' "$task_rc" > "$ROOT/logs/wp4_native_bounded_v2_${SLURM_JOB_ID}.exitcode"
exit "$task_rc"
