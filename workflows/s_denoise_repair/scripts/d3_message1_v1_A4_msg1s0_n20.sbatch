#!/bin/bash
#SBATCH --job-name=srepair_d3_message1_v1_A4_msg1s0_n20
#SBATCH --partition=all
#SBATCH --nodelist=compute-0-20
#SBATCH --cpus-per-task=16
#SBATCH --mem=64G
#SBATCH --time=05:00:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016/logs/d3_message1_v1_A4_msg1s0_n20_%j.log
set -euo pipefail
cd /share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016/source_v3
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1
export PYTORCH_ALLOC_CONF=expandable_segments:True
export PYTHONPATH=/share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016/source_v3/current:/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps
srun --input=none --ntasks=1 --cpus-per-task=16 --cpu-bind=cores /share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage43_5090_environment/install_4511929/venv/bin/python -B workflows/s_denoise/train_diagnostic.py --configuration /share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016/source_v3/workflows/s_denoise/configs/A4_msg1_seed0_v3.json --source-binding /share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016/configs/D3_source_binding_v4.json
