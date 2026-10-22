#!/bin/bash
#SBATCH --job-name=srepair_complete_diagnostics_render_initial_v1_n19
#SBATCH --partition=cpu
#SBATCH --nodelist=compute-0-19
#SBATCH --cpus-per-task=16
#SBATCH --mem=32G
#SBATCH --time=00:10:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016/logs/complete_diagnostics_render_initial_v1_n19_%j.log
set -euo pipefail
cd /share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016/source_v3
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1
srun --input=none --ntasks=1 --cpus-per-task=16 --cpu-bind=cores /share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage43_5090_environment/install_4511929/venv/bin/python -B /share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016/analysis/render_complete_diagnostics_v1.py --phases d3_local_blocks_v1 --parent-snapshot /share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016/control/accounting_snapshots/stage3_gate_eval_initial_v1_v1.json --gate /share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016/reports/Stage3_gate_initial_v1.json --output-dir /share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016/reports/complete_diagnostics_initial_v1 --performance-reference /share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016/reports/preselection_performance_crossover_latest.json
