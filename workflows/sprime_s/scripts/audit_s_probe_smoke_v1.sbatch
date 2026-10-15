#!/bin/bash
#SBATCH --job-name=sconv_probe_smoke_audit_v1
#SBATCH --partition=cpu
#SBATCH --nodelist=compute-0-9
#SBATCH --cpus-per-task=16
#SBATCH --mem=32G
#SBATCH --time=00:10:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/sprime_s_convergence_20261013/logs/s_probe_smoke_audit_v1_%j.log
set -euo pipefail
cd /share/home/zixiao/descriptor_analysis
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH=/share/home/zixiao/PhyChem_MFM_stage59_three_epoch_runtime:/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps
/share/home/zixiao/.conda/envs/chemprop/bin/python -B runs/sprime_s_convergence_20261013/scripts/audit_s_probe_smoke_v1.py
