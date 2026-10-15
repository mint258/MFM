#!/bin/bash
#SBATCH --job-name=wp5_main
#SBATCH --partition=cpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=24
#SBATCH --mem=32G
#SBATCH --time=48:00:00
#SBATCH --nodelist=compute-0-17
#SBATCH --signal=B:USR1@900
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/logs/%x_%j.out
#SBATCH --error=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/logs/%x_%j.err
set -euo pipefail
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export PYTHONPATH=/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps:/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/scripts:${PYTHONPATH:-}
WP5_ROOT=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011
: "${WP5_DICTIONARIES:?G3 dictionary manifest required}"
: "${WP5_BASELINE:?closed pilot success_rates JSON required}"
: "${WP5_TASK_ID:?frozen task ID required; cleanup may use its node ID}"
WP5_MODE=${WP5_MODE:-main}
exec /share/home/zixiao/.conda/envs/chemprop/bin/python "$WP5_ROOT/scripts/wp5_runner_v6.py" \
  --plan "$WP5_ROOT/packing/node_assignment_v2/tasks.json" \
  --assignments "$WP5_ROOT/packing/molecule_assignments.parquet" \
  --task-id "$WP5_TASK_ID" --mode "$WP5_MODE" --dictionaries "$WP5_DICTIONARIES" \
  --baseline "$WP5_BASELINE" --policy "${WP5_POLICY:-ALL}" --hours 48 --workers 24 \
  --admit-hours 46 --export-reserve-hours 2
