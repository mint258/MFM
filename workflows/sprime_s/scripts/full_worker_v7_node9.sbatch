#!/bin/bash
#SBATCH --job-name=sprime_full_v7_node9
#SBATCH --partition=cpu
#SBATCH --nodelist=compute-0-9
#SBATCH --cpus-per-task=64
#SBATCH --mem=64G
#SBATCH --time=48:00:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/sprime_s_convergence_20261013/logs/full_v7_node9_%j.log
set -euo pipefail
cd /share/home/zixiao/descriptor_analysis
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH=/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps
/share/home/zixiao/.conda/envs/chemprop/bin/python -B runs/sprime_s_convergence_20261013/scripts/full_dataset_v7.py run --workers 63
