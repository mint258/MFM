#!/bin/bash
#SBATCH --job-name=wp5_reproduction50
#SBATCH --partition=cpu
#SBATCH --nodelist=compute-0-17
#SBATCH --cpus-per-task=24
#SBATCH --mem=32G
#SBATCH --time=48:00:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/logs/reproduction50_%j.out
#SBATCH --error=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/logs/reproduction50_%j.err
set -euo pipefail
ROOT=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011
PYTHON=/share/home/zixiao/.conda/envs/chemprop/bin/python
export PYTHONPATH=/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps:$ROOT/scripts:${PYTHONPATH:-}
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
: "${WP5_AUDIT_MEMBERSHIP:?Actual closed audit membership required}"
: "${WP5_REPRODUCTION_PACKAGE:?Actual closed permanent package required}"
: "${WP5_PRODUCTION_CONTRACT:?Actual frozen user-override contract required}"
: "${WP5_DICTIONARIES:?Actual current-format dictionary manifest required}"
SCRATCH=$(mktemp -d /tmp/wp5_repeat50_${SLURM_JOB_ID}_XXXXXX)
export TMPDIR="$SCRATCH"
trap 'rm -rf -- "$SCRATCH"' EXIT
cd "$SCRATCH"
OUT="$ROOT/gates/reproduction50/job_${SLURM_JOB_ID}"
export ROOT PYTHON OUT
mkdir -p "$ROOT/gates/reproduction50"
timeout --signal=USR1 --kill-after=120s 46h bash -c '
 set -euo pipefail
 "$PYTHON" -B "$ROOT/scripts/wp5_reproduction50_v1.py" plan --workers 24 --audit-membership "$WP5_AUDIT_MEMBERSHIP" --reproduction-package "$WP5_REPRODUCTION_PACKAGE" --production-contract "$WP5_PRODUCTION_CONTRACT" --dictionaries "$WP5_DICTIONARIES" --out "$OUT"
 "$PYTHON" -B "$ROOT/scripts/wp5_reproduction50_v1.py" run --workers 24 --plan "$OUT/plan.json"
 "$PYTHON" -B "$ROOT/scripts/wp5_reproduction50_v1.py" compare --workers 24 --plan "$OUT/plan.json"
'
