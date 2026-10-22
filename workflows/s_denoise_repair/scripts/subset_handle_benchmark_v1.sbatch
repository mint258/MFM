#!/bin/bash
#SBATCH --job-name=srepair_subset_handles_v1
#SBATCH --partition=cpu
#SBATCH --nodelist=compute-0-11
#SBATCH --cpus-per-task=16
#SBATCH --mem=64G
#SBATCH --time=01:00:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016/logs/subset_handles_v1_%j.log
set -euo pipefail
cd /share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH=/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps
S_REPAIR_PY=/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage43_5090_environment/install_4511929/venv/bin/python
srun --input=none --ntasks=1 --cpus-per-task=16 --cpu-bind=cores "$S_REPAIR_PY" -B analysis/benchmark_subset_handles.py
