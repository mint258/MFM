#!/bin/bash
set -euo pipefail
ROOT=/share/home/zixiao/descriptor_analysis/runs/phase1_dataset_rebuild_20261010
export PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES=''
export PYTHONPATH=/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
cd /share/home/zixiao/descriptor_analysis
set +e
/share/home/zixiao/.conda/envs/chemprop/bin/python -B "$ROOT/scripts/wp4_polar_cost_probe_v2.py" --panel "$ROOT/wp4_native_panel/pilot_panel.parquet" --panel-manifest "$ROOT/wp4_native_panel/pilot_panel_manifest.json" --record-index "$ROOT/record_index.parquet" --paired-pilot-root "$ROOT/wp4_native_full_v4"/bucket_* --output "$ROOT/wp4_polar_cost_v2" --engine "$ROOT/scripts/wp4_native_pilot_v4.py" --config "$ROOT/scripts/wp4_native_v4_config.json" --workers "$SLURM_CPUS_PER_TASK" --per-stratum 5 --wall-seconds 7200
task_rc=$?
printf '%s\n' "$task_rc" > "$ROOT/logs/wp4_polar_cost_v2_${SLURM_JOB_ID}.exitcode"
exit "$task_rc"
