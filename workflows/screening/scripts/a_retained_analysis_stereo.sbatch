#!/bin/bash
#SBATCH --job-name=p1_A_stereo
#SBATCH --partition=cpu
#SBATCH --cpus-per-task=32
#SBATCH --mem=128G
#SBATCH --time=04:00:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/phase1_screening_20261011/logs/a_stereo_%j.out
#SBATCH --error=/share/home/zixiao/descriptor_analysis/runs/phase1_screening_20261011/logs/a_stereo_%j.err
set -euo pipefail
cd /share/home/zixiao/descriptor_analysis
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 BLIS_NUM_THREADS=1
export PYTHONPATH=/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps:${PYTHONPATH:-}
exec /share/home/zixiao/.conda/envs/chemprop/bin/python /share/home/zixiao/descriptor_analysis/runs/phase1_screening_20261011/scripts/a_retained_analysis_stereo.py --workers 32 --memory-gb 96
