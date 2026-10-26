#!/bin/bash
# Root passes an available authorized CPU node with sbatch --nodelist=...
#SBATCH --partition=all
#SBATCH --cpus-per-task=16
#SBATCH --mem=32G
#SBATCH --time=00:18:00
set -euo pipefail
export CUDA_VISIBLE_DEVICES=''
export PYTHONDONTWRITEBYTECODE=1 TMPDIR=/tmp
export OMP_NUM_THREADS=8 MKL_NUM_THREADS=8 OPENBLAS_NUM_THREADS=8
export MODEL_V3_EXPECTED_NODE="${SLURMD_NODENAME:?}"
exec /share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage43_5090_environment/install_4511929/venv/bin/python -B /share/home/zixiao/descriptor_analysis/runs/model_v3_20261026/native_s_profile_launch_v8/operations.py qa --pins-sha256 "$1"
