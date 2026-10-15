#!/bin/bash
#SBATCH --job-name=sconv_development_history_audit_v1
#SBATCH --partition=cpu
#SBATCH --nodelist=compute-0-2
#SBATCH --cpus-per-task=16
#SBATCH --mem=32G
#SBATCH --time=00:10:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/sprime_s_convergence_20261013/logs/development_history_audit_v1_%j.log
set -euo pipefail
cd /share/home/zixiao/descriptor_analysis
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1
/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage43_5090_environment/install_4511929/venv/bin/python -B runs/sprime_s_convergence_20261013/scripts/audit_s_development_history_v1.py
