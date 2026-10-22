#!/bin/bash
#SBATCH --job-name=srepair_interim_d3_plot_v2
#SBATCH --partition=cpu
#SBATCH --nodelist=compute-0-8
#SBATCH --cpus-per-task=16
#SBATCH --mem=32G
#SBATCH --time=00:20:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016/logs/interim_d3_plot_v2_%j.log
set -euo pipefail
cd /share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016
export OMP_NUM_THREADS=16 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=16 PYTHONDONTWRITEBYTECODE=1
export CUDA_VISIBLE_DEVICES=''
/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage43_5090_environment/install_4511929/venv/bin/python -B /share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016/analysis/render_d3_report_v3.py --phases d3_local_blocks_v1 --parent-snapshot /share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016/control/accounting_snapshots/interim_A0_A1_v2.json --output-dir /share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016/reports/D3_interim_A0_A1_v2
pdftoppm -f 1 -singlefile -scale-to 2000 -png /share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016/reports/D3_interim_A0_A1_v2/D3_curves.pdf /share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016/reports/D3_interim_A0_A1_v2/D3_curves_actual_pdf
