#!/bin/bash
#SBATCH --job-name=srepair_stage3_gate_eval_initial_v1_n19
#SBATCH --partition=cpu
#SBATCH --nodelist=compute-0-19
#SBATCH --cpus-per-task=16
#SBATCH --mem=32G
#SBATCH --time=00:05:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016/logs/stage3_gate_eval_initial_v1_n19_%j.log
set -euo pipefail
cd /share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016/source_v3
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH=/share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016/analysis:/share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016/source_v3/workflows/s_denoise
srun --input=none --ntasks=1 --cpus-per-task=16 --cpu-bind=cores /share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage43_5090_environment/install_4511929/venv/bin/python -B /share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016/analysis/stage3_gate_v4.py --phase d3_local_blocks_v1 --parent-snapshot /share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016/control/accounting_snapshots/stage3_gate_eval_initial_v1_v1.json --output /share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016/reports/Stage3_gate_initial_v1.json
