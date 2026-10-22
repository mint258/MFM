#!/bin/bash
#SBATCH --job-name=srepair_preselection_performance_crossover_v1
#SBATCH --partition=all
#SBATCH --nodelist=compute-0-21
#SBATCH --cpus-per-task=16
#SBATCH --mem=32G
#SBATCH --time=00:20:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016/logs/preselection_performance_crossover_v1_%j.log
set -euo pipefail
cd /share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016/source_v3
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1
export PYTORCH_ALLOC_CONF=expandable_segments:True
export PYTHONPATH=/share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016/source_v3/workflows/s_denoise:/share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016/source_v3/current:/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps
srun --input=none --ntasks=1 --cpus-per-task=16 --cpu-bind=cores /share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage43_5090_environment/install_4511929/venv/bin/python -B /share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016/analysis/preselection_performance_crossover_v1.py --candidate A4
