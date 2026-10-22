#!/bin/bash
#SBATCH --job-name=wp5_exact2_verify_v3
#SBATCH --chdir=/share/home/zixiao/descriptor_analysis
#SBATCH --partition=cpu
#SBATCH --nodelist=compute-0-13
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=24
#SBATCH --mem=32G
#SBATCH --time=48:00:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/logs/exact_two_verify_v3_%j.out
#SBATCH --error=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/logs/exact_two_verify_v3_%j.err
set -euo pipefail
ROOT=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011
PY=/share/home/zixiao/.conda/envs/chemprop/bin/python
PREPARED="${1:?frozen v2 prepared.json required}"
OUT="${2:?new write-once v3 verification JSON required}"
export PYTHONPATH=/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps:"$ROOT/scripts":${PYTHONPATH:-}
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
WP5_VERIFY_TMP="/tmp/wp5exactverify3_${UID}_${SLURM_JOB_ID}"
if [[ -e "$WP5_VERIFY_TMP" ]];then printf 'Own temporary directory already exists\n' >&2;exit 2;fi
mkdir -m 700 -- "$WP5_VERIFY_TMP"
export TMPDIR="$WP5_VERIFY_TMP"
cleanup() {
  if [[ "$WP5_VERIFY_TMP" == "/tmp/wp5exactverify3_${UID}_${SLURM_JOB_ID}" && -d "$WP5_VERIFY_TMP" ]];then
    rm -rf -- "$WP5_VERIFY_TMP"
  fi
}
trap cleanup EXIT
cd /share/home/zixiao/descriptor_analysis
# Read already completed SCI only. No runner, QM launch, queue write or adoption.
timeout --preserve-status --signal=TERM --kill-after=120s 46h "$PY" -B "$ROOT/scripts/wp5_exact_two_retry_validator_v3.py" validate --prepared "$PREPARED" --out "$OUT"
