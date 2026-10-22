#!/bin/bash
#SBATCH --job-name=wp5_exact2_budget1
#SBATCH --chdir=/share/home/zixiao/descriptor_analysis
#SBATCH --partition=cpu
#SBATCH --nodelist=compute-0-13
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=24
#SBATCH --mem=32G
#SBATCH --time=48:00:00
#SBATCH --signal=B:USR1@300
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/logs/exact_two_retry_%j.out
#SBATCH --error=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/logs/exact_two_retry_%j.err
set -euo pipefail
ROOT=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011
PY=/share/home/zixiao/.conda/envs/chemprop/bin/python
PREPARED="${1:?exact two retry prepared.json required}"
export PYTHONPATH=/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps:"$ROOT/scripts":${PYTHONPATH:-}
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
WP5_EXACT_RETRY_TMP="/tmp/wp5exactretry_${UID}_${SLURM_JOB_ID}"
if [[ -e "$WP5_EXACT_RETRY_TMP" ]];then printf 'Own temporary directory already exists\n' >&2;exit 2;fi
mkdir -m 700 -- "$WP5_EXACT_RETRY_TMP"
export TMPDIR="$WP5_EXACT_RETRY_TMP"
cleanup() {
  if [[ "$WP5_EXACT_RETRY_TMP" == "/tmp/wp5exactretry_${UID}_${SLURM_JOB_ID}" && -d "$WP5_EXACT_RETRY_TMP" ]];then
    rm -rf -- "$WP5_EXACT_RETRY_TMP"
  fi
}
trap cleanup EXIT
cd /share/home/zixiao/descriptor_analysis
# The unchanged frozen runner owns its existing 46-hour QM + 2-hour export budget.
"$PY" "$ROOT/scripts/wp5_exact_two_retry_v2.py" launch --prepared "$PREPARED"
# This verifies fresh immutable exports only; formal queue adoption is Root-only
# after the real Slurm parent is terminal and its sacct evidence is saved.
"$PY" "$ROOT/scripts/wp5_exact_two_retry_v2.py" validate --prepared "$PREPARED" --out "$(dirname -- "$PREPARED")/verified_240_slots.json"
