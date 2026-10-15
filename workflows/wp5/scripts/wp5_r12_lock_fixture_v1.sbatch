#!/bin/bash
#SBATCH --job-name=wp5_r12_lock_fixture
#SBATCH --partition=cpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --mem=8G
#SBATCH --time=00:10:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/logs/%x_%j.out
#SBATCH --error=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/logs/%x_%j.err
set -euo pipefail
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
WP5_LOCK_ROOT=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011
export PYTHONPATH="$WP5_LOCK_ROOT/scripts:/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps${PYTHONPATH:+:$PYTHONPATH}"
if [[ $# == 0 ]]; then
  : "${WP5_LOCK_RUNNER:?Exact independently prepared candidate path required}"
  : "${WP5_LOCK_RUNNER_SHA256:?Exact candidate SHA required}"
elif [[ $# == 2 ]]; then
  WP5_LOCK_RUNNER=$1
  WP5_LOCK_RUNNER_SHA256=$2
else
  echo "Expected zero arguments with strict env, or runner_path runner_sha" >&2
  exit 2
fi
exec /share/home/zixiao/.conda/envs/chemprop/bin/python -B "$WP5_LOCK_ROOT/scripts/wp5_r12_lock_fixture_v1.py" \
  --runner "$WP5_LOCK_RUNNER" --runner-sha256 "$WP5_LOCK_RUNNER_SHA256"
