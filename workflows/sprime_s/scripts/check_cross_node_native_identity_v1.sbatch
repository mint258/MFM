#!/bin/bash
#SBATCH --job-name=sconv_cross_node_identity_v1
#SBATCH --partition=all
#SBATCH --nodelist=compute-0-21
#SBATCH --cpus-per-task=16
#SBATCH --mem=32G
#SBATCH --time=00:10:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/sprime_s_convergence_20261013/logs/cross_node_identity_v1_%j.log
set -euo pipefail
cd /share/home/zixiao/descriptor_analysis
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1
/share/home/zixiao/.conda/envs/chemprop/bin/python -B runs/sprime_s_convergence_20261013/scripts/check_cross_node_native_identity_v1.py
