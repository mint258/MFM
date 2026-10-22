#!/bin/bash
#SBATCH --job-name=srepair_completed_d3_profiles_v1
#SBATCH --partition=cpu
#SBATCH --nodelist=compute-0-8
#SBATCH --cpus-per-task=16
#SBATCH --mem=32G
#SBATCH --time=00:20:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016/logs/completed_d3_profiles_v1_%j.log
set -euo pipefail
cd /share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016/source_v3
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH=/share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016/source_v3/current:/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps
export CUDA_VISIBLE_DEVICES=''
srun --input=none --ntasks=1 --cpus-per-task=16 --cpu-bind=cores /share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage43_5090_environment/install_4511929/venv/bin/python -B /share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016/analysis/profile_completed_d3_conditions_v1.py --phase d3_local_blocks_v1 --conditions A0 A1 A2 --parent-snapshot /share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016/control/accounting_snapshots/A2_pair_complete_v1.json --output /share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016/reports/completed_D3_profiles_A0_A1_A2_v1
