#!/bin/bash
set -euo pipefail
cd /share/home/zixiao/descriptor_analysis
export PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES=''
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export PYTHONPATH=/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps:${PYTHONPATH:-}
ROOT=/share/home/zixiao/descriptor_analysis/runs/phase1_screening_20261011
exec /share/home/zixiao/.conda/envs/chemprop/bin/python -B "$ROOT/scripts/b_quantum_esp_failure_refine.py" --report "$ROOT/b_quantum/esp_analysis/job_4513567/report.json" --out "$ROOT/b_quantum/esp_analysis/failure_refine_job_${SLURM_JOB_ID}.json" --workers 16
