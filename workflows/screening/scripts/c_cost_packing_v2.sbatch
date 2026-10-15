#!/bin/bash
set -euo pipefail
cd /share/home/zixiao/descriptor_analysis
export PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES=''
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
exec /share/home/zixiao/.conda/envs/chemprop/bin/python -B runs/phase1_screening_20261011/scripts/c_cost_packing_v2.py --workers 32
