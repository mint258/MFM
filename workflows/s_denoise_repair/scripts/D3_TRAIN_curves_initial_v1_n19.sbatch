#!/bin/bash
#SBATCH --job-name=srepair_D3_TRAIN_curves_initial_v1_n19
#SBATCH --partition=cpu
#SBATCH --nodelist=compute-0-19
#SBATCH --cpus-per-task=16
#SBATCH --mem=32G
#SBATCH --time=00:05:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016/logs/D3_TRAIN_curves_initial_v1_n19_%j.log
set -euo pipefail
cd /share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016/source_v3
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1
export MPLCONFIGDIR=/share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016/cache/mpl_train_initial_job${SLURM_JOB_ID}
mkdir "$MPLCONFIGDIR"
srun --input=none --ntasks=1 --cpus-per-task=16 --cpu-bind=cores /share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage43_5090_environment/install_4511929/venv/bin/python -B /share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016/analysis/render_d3_training_curves_v1.py --phases d3_local_blocks_v1 --parent-snapshot /share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016/control/accounting_snapshots/stage3_gate_eval_initial_v1_v1.json --output-dir /share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016/reports/D3_TRAIN_initial_v1
pdftoppm -f 1 -singlefile -scale-to 2000 -png /share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016/reports/D3_TRAIN_initial_v1/D3_TRAIN_loss_curves.pdf /share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016/reports/D3_TRAIN_initial_v1/D3_TRAIN_loss_curves_actual_pdf
