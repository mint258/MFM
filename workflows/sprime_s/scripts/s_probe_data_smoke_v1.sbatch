#!/bin/bash
#SBATCH --job-name=sconv_probe_data_smoke_v1
#SBATCH --partition=cpu
#SBATCH --nodelist=compute-0-2
#SBATCH --cpus-per-task=16
#SBATCH --mem=32G
#SBATCH --time=01:00:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/sprime_s_convergence_20261013/logs/s_probe_data_smoke_v1_%j.log
set -euo pipefail
cd /share/home/zixiao/descriptor_analysis
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1
export CUDA_VISIBLE_DEVICES=''
export PYTHONPATH=/share/home/zixiao/PhyChem_MFM_stage59_three_epoch_runtime:/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps
for S_PROBE_DATASET in qm7 qm9 cyp_isoform az_exactsom expansionrx; do
  /share/home/zixiao/.conda/envs/chemprop/bin/python -B runs/sprime_s_convergence_20261013/scripts/prepare_s_probe_data_v1.py --dataset "$S_PROBE_DATASET" --limit 16
done
