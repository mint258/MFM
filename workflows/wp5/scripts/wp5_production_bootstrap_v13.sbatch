#!/bin/bash
#SBATCH --job-name=wp5_metadata_bootstrap13
#SBATCH --partition=cpu
#SBATCH --nodelist=compute-0-17
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=24
#SBATCH --mem=32G
#SBATCH --time=48:00:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/logs/wp5_bootstrap13_%j.out
#SBATCH --error=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/logs/wp5_bootstrap13_%j.err
set -euo pipefail
ROOT=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export PYTHONPATH="/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps:$ROOT/scripts${PYTHONPATH:+:$PYTHONPATH}"
exec /share/home/zixiao/.conda/envs/chemprop/bin/python -B "$ROOT/scripts/wp5_production_bootstrap_v13.py" --workers 24 "$@"
# Root only after all229 terminal and full reconciliation; no claims or QM.
