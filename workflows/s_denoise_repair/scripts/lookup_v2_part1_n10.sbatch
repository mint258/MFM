#!/bin/bash
#SBATCH --job-name=srepair_lookup_v2_part1_n10
#SBATCH --partition=cpu
#SBATCH --nodelist=compute-0-10
#SBATCH --cpus-per-task=16
#SBATCH --mem=64G
#SBATCH --time=04:00:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016/logs/lookup_v2_part1_n10_%j.log
set -euo pipefail
cd /share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH=/share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016/analysis:/share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016/source/workflows/s_denoise:/share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016/source/current:/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps
srun --input=none --ntasks=1 --cpus-per-task=16 --cpu-bind=cores /share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage43_5090_environment/install_4511929/venv/bin/python -B analysis/lookup_refit_chunks_v2.py --part 1
