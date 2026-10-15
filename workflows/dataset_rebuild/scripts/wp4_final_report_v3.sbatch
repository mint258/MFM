#!/bin/bash
set -euo pipefail
ROOT=/share/home/zixiao/descriptor_analysis/runs/phase1_dataset_rebuild_20261010
export PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES=''
export PYTHONPATH=/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
cd /share/home/zixiao/descriptor_analysis
set +e
/share/home/zixiao/.conda/envs/chemprop/bin/python -B "$ROOT/scripts/wp4_pilot_report_v3.py" --native-root "$ROOT/wp4_native_full_v4" --b-probe-root "$ROOT/wp4_polar_cost_v2" --quality "$ROOT/wp1_results/quality_annotations_v1.parquet" --output "$ROOT/reports/wp4_final_pilot" --workers "$SLURM_CPUS_PER_TASK"
task_rc=$?
printf '%s\n' "$task_rc" > "$ROOT/logs/wp4_final_report_v3_${SLURM_JOB_ID}.exitcode"
exit "$task_rc"
