#!/bin/bash
#SBATCH --job-name=sprime_full_v7_node12_admission_v8
#SBATCH --partition=cpu
#SBATCH --nodelist=compute-0-12
#SBATCH --cpus-per-task=96
#SBATCH --mem=96G
#SBATCH --time=48:00:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/sprime_s_convergence_20261013/logs/full_v7_node12_admission_v8_%j.log
set -euo pipefail
cd /share/home/zixiao/descriptor_analysis
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH=/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps
/share/home/zixiao/.conda/envs/chemprop/bin/python -B runs/sprime_s_convergence_20261013/scripts/full_dataset_v8_extra_cpu.py run --workers 95
