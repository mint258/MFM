#!/bin/bash
set -euo pipefail
cd /share/home/zixiao/descriptor_analysis
export PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES=''
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export PYTHONPATH=/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps:${PYTHONPATH:-}
ROOT=/share/home/zixiao/descriptor_analysis/runs/phase1_screening_20261011
/share/home/zixiao/.conda/envs/chemprop/bin/python -B "$ROOT/scripts/a_retained_analysis_stereo.py" --workers 32 --memory-gb 96
/share/home/zixiao/.conda/envs/chemprop/bin/python -B "$ROOT/scripts/a_retained_analysis_examples.py" --workers 16 --memory-gb 8
