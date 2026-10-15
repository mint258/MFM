#!/bin/bash
#SBATCH --job-name=wp5_main10
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
: "${WP5_NODE_AUTHORITY:?actual user-approved WP5 node substitution receipt required}"
: "${WP5_BASELINE:?closed pilot success_rates JSON required}"
: "${WP5_TASK_ID:?frozen task ID required; cleanup may use its node ID}"
: "${WP5_PRODUCTION_CONTRACT:?frozen new-policy production contract required}"
: "${WP5_AUDIT_MEMBERSHIP:?closed stratified RECORD membership required}"
: "${WP5_REPRODUCTION_PACKAGE:?permanent frozen reproduction package required}"
WP5_MODE=${WP5_MODE:-main}
exec /share/home/zixiao/.conda/envs/chemprop/bin/python "$WP5_ROOT/scripts/wp5_runner_v10.py" \
  --plan "$WP5_ROOT/packing/node_assignment_v3/tasks.json" \
  --node-authority "$WP5_NODE_AUTHORITY" --node-scope-plan "$WP5_ROOT/packing/node_assignment_v3/tasks.json" \
  --assignments "$WP5_ROOT/packing/molecule_assignments.parquet" \
  --task-id "$WP5_TASK_ID" --mode "$WP5_MODE" --dictionaries "$WP5_DICTIONARIES" \
  --baseline "$WP5_BASELINE" --policy FAILURES_PLUS_STRATIFIED_RECORD_AUDIT_NO_INPUT --hours 48 --workers 24 \
  --production-contract "$WP5_PRODUCTION_CONTRACT" --audit-membership "$WP5_AUDIT_MEMBERSHIP" --reproduction-package "$WP5_REPRODUCTION_PACKAGE" \
  --admit-hours 46 --export-reserve-hours 2
