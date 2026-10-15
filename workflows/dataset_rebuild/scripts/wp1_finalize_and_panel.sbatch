#!/bin/bash
set -euo pipefail
ROOT=/share/home/zixiao/descriptor_analysis/runs/phase1_dataset_rebuild_20261010
export PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES=''
export PYTHONPATH=/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
cd /share/home/zixiao/descriptor_analysis
/share/home/zixiao/.conda/envs/chemprop/bin/python -B "$ROOT/scripts/wp1_report.py" --index "$ROOT/record_index.parquet" --geometry "$ROOT/wp1_geometry_full" --output "$ROOT/wp1_results" --threads "$SLURM_CPUS_PER_TASK" --memory-gb 40
/share/home/zixiao/.conda/envs/chemprop/bin/python -B "$ROOT/scripts/check_wp1_complete.py"
/share/home/zixiao/.conda/envs/chemprop/bin/python -B "$ROOT/scripts/select_native_panel.py" --quality "$ROOT/wp1_results/quality_annotations_v1.parquet" --out "$ROOT/wp4_native_panel" --records 10000 --workers "$SLURM_CPUS_PER_TASK"
printf '0\n' > "$ROOT/logs/wp1_finalize_and_panel_${SLURM_JOB_ID}.exitcode"
