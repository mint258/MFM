#!/bin/bash
#SBATCH --job-name=wp5_queue_stress_v1
#SBATCH --partition=cpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=24
#SBATCH --mem=32G
#SBATCH --time=02:00:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/logs/%x_%j.out
#SBATCH --error=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/logs/%x_%j.err
set -euo pipefail
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export PYTHONPATH=/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps:/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/scripts:${PYTHONPATH:-}
WP5_TEST_ROOT=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011
if [ "$#" -eq 0 ]; then
  : "${WP5_QUEUE_TEST_MODE:?TEST mode init/node/verify required}"
  : "${WP5_QUEUE_TEST_ROOT:?private TEST fixture root required}"
  : "${WP5_QUEUE_RUNNER_SHA256:?actual frozen R11 SHA required}"
  set -- "$WP5_QUEUE_TEST_MODE" "$WP5_QUEUE_TEST_ROOT" "$WP5_QUEUE_RUNNER_SHA256"
elif [ "$#" -ne 3 ]; then
  echo 'Expected: zero arguments plus three required TEST env vars, or MODE ROOT SHA' >&2
  exit 2
fi
exec /share/home/zixiao/.conda/envs/chemprop/bin/python -B "$WP5_TEST_ROOT/scripts/wp5_queue_metadata_stress_v1.py" \
  --mode "$1" --root "$2" --runner-sha256 "$3"
