#!/bin/bash
#SBATCH --job-name=wp5_g5_parser
#SBATCH --partition=cpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=24
#SBATCH --mem=32G
#SBATCH --time=48:00:00
set -euo pipefail
cd /share/home/zixiao/descriptor_analysis
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 BLIS_NUM_THREADS=1
export PYTHONPATH=/share/home/zixiao/descriptor_analysis/runs/phase1_dataset_rebuild_20261010/docs/deps:/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps:/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/scripts/deps${PYTHONPATH:+:$PYTHONPATH}
exec /share/home/zixiao/.conda/envs/chemprop/bin/python runs/phase1_wp5_20261011/scripts/wp5_parser_regression.py --workers 24 --config runs/phase1_wp5_20261011/configs/protocol.json

