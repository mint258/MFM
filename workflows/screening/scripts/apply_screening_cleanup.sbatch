#!/bin/bash
set -euo pipefail
ROOT=/share/home/zixiao/descriptor_analysis/runs/phase1_screening_20261011
PYTHON=/share/home/zixiao/.conda/envs/chemprop/bin/python
export PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES=''
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
cd /share/home/zixiao/descriptor_analysis
"$PYTHON" -B "$ROOT/scripts/apply_screening_cleanup.py" --workers 16
