#!/bin/bash
set -euo pipefail
# Root-only after chosen C3 scope closes; metadata pass16CPU/32GiB/00:30:00.
ROOT=/share/home/zixiao/descriptor_analysis/runs/phase1_screening_20261011
export PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES=''
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
cd /share/home/zixiao/descriptor_analysis
/share/home/zixiao/.conda/envs/chemprop/bin/python -B "$ROOT/scripts/c_engineering_archive_recheck.py" --workers "$SLURM_CPUS_PER_TASK"
