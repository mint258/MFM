#!/bin/bash
#SBATCH --job-name=wp5_pack
#SBATCH --partition=cpu
#SBATCH --nodelist=compute-0-17
#SBATCH --cpus-per-task=24
#SBATCH --mem=32G
#SBATCH --time=02:00:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/logs/wp5_pack_%j.log
set -euo pipefail
cd /share/home/zixiao/descriptor_analysis
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1
export PYTHONPATH=/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps:/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/scripts
/share/home/zixiao/.conda/envs/chemprop/bin/python runs/phase1_wp5_20261011/scripts/wp5_pack_v2.py --threads 24 --memory-gb 20 --spill-root /tmp

