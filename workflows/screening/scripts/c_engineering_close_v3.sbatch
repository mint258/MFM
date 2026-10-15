#!/bin/bash
set -euo pipefail
# Root alone submits afterok:4513516:4513519:4513520:4513521:4513633:4513634.
# One16-worker metadata-only read; no QM, repacking, raw removal, or LMDB writes.
ROOT=/share/home/zixiao/descriptor_analysis/runs/phase1_screening_20261011
PYTHON=/share/home/zixiao/.conda/envs/chemprop/bin/python
export PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES=''
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
cd /share/home/zixiao/descriptor_analysis
"$PYTHON" -B "$ROOT/scripts/c_engineering_archive_recheck.py" --workers 16
"$PYTHON" -B "$ROOT/scripts/c_engineering_report_v3.py" --collect-sacct
"$PYTHON" -B "$ROOT/scripts/c_engineering_appendix_v2.py"
