#!/bin/bash
#SBATCH --job-name=srepair_D3_interim_plot_v2
#SBATCH --partition=cpu
#SBATCH --nodelist=compute-0-8
#SBATCH --cpus-per-task=16
#SBATCH --mem=32G
#SBATCH --time=00:10:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016/logs/D3_interim_plot_v2_%j.log
set -euo pipefail
cd /share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016
export OMP_NUM_THREADS=16 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=16 PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH=/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps
srun --input=none --ntasks=1 --cpus-per-task=16 --cpu-bind=cores /share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage43_5090_environment/install_4511929/venv/bin/python -B -m pytest analysis/test_stage3_gate_v2.py -q --junitxml=/share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016/reports/stage3_gate_tests_v2.xml
srun --input=none --ntasks=1 --cpus-per-task=16 --cpu-bind=cores /share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage43_5090_environment/install_4511929/venv/bin/python -B analysis/render_d3_report_v2.py --phases d3_local_blocks_v1 --parent-snapshot /share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016/control/accounting_snapshots/D3_interim_v2.json --output-dir /share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016/reports/D3_interim_v2
srun --input=none --ntasks=1 --cpus-per-task=16 --cpu-bind=cores pdftoppm -f 1 -l 1 -singlefile -scale-to 1800 -png /share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016/reports/D1_D2_diagnostics.pdf /share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016/reports/D3_interim_v2/D1_D2_actual_pdf_page
srun --input=none --ntasks=1 --cpus-per-task=16 --cpu-bind=cores pdftoppm -f 1 -l 1 -singlefile -scale-to 1800 -png /share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016/reports/D3_interim_v2/D3_curves.pdf /share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016/reports/D3_interim_v2/D3_actual_pdf_page
