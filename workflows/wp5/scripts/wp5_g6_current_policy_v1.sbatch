#!/bin/bash
#SBATCH --job-name=wp5_g6_current_policy
#SBATCH --partition=cpu
#SBATCH --cpus-per-task=24
#SBATCH --mem=32G
#SBATCH --time=48:00:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/logs/g6_current_%j.out
#SBATCH --error=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/logs/g6_current_%j.err
set -euo pipefail
ROOT=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011
export PYTHONPATH=/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps:$ROOT/scripts:${PYTHONPATH:-}
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
: "${WP5_AUDIT_MEMBERSHIP:?Actual audit membership required}"
: "${WP5_REPRODUCTION_PACKAGE:?Actual package required}"
: "${WP5_PRODUCTION_CONTRACT:?Actual current contract required}"
: "${WP5_DICTIONARIES:?Actual current dictionary manifest required}"
SCRATCH=$(mktemp -d /tmp/wp5_g6_current_${SLURM_JOB_ID}_XXXXXX)
export TMPDIR="$SCRATCH"
trap 'rm -rf -- "$SCRATCH"' EXIT
cd "$SCRATCH"
timeout --signal=USR1 --kill-after=120s 46h /share/home/zixiao/.conda/envs/chemprop/bin/python -B "$ROOT/scripts/wp5_g6_current_policy_v1.py" --dictionaries "$WP5_DICTIONARIES" --audit-membership "$WP5_AUDIT_MEMBERSHIP" --reproduction-package "$WP5_REPRODUCTION_PACKAGE" --production-contract "$WP5_PRODUCTION_CONTRACT"
