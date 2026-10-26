#!/bin/bash
#SBATCH --job-name=dv1_alpha_queue_metadata_v1
#SBATCH --partition=cpu
#SBATCH --nodelist=compute-0-6
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --time=00:10:00
#SBATCH --output=/gfshome/alpha/codex_data_v1_20261026/secondary_queue_metadata_%j.out
set -euo pipefail
export CUDA_VISIBLE_DEVICES="" PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
cd /gfshome/alpha/codex_data_v1_20261026/code
exec /share/home/alpha/miniconda3/bin/python -B /gfshome/alpha/codex_data_v1_20261026/code/secondary_queue_checks_v1.py
