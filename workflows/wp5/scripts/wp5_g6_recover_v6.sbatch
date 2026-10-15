#!/bin/bash
#SBATCH --job-name=wp5_g6_recover6
#SBATCH --partition=cpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=24
#SBATCH --mem=32G
#SBATCH --time=48:00:00
#SBATCH --nodelist=compute-0-17
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/logs/%x_%j.out
#SBATCH --error=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/logs/%x_%j.err
set -euo pipefail
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export PYTHONPATH=/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps:/share/home/zixiao/descriptor_analysis/runs/phase1_dataset_rebuild_20261010/docs/deps:/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/scripts:${PYTHONPATH:-}
WP5_ROOT=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011
: "${WP5_DICTIONARIES:?G3 actual trained dictionaries required}"
arguments=(--dictionaries "$WP5_DICTIONARIES" --runner "${WP5_G6_RUNNER:-$WP5_ROOT/scripts/wp5_runner_v6.py}" --hours 48)
if [[ -n "${WP5_G6_SOURCE_RUN:-}" ]]; then arguments+=(--source-run "$WP5_G6_SOURCE_RUN"); fi
if [[ -n "${WP5_G6_RETRY_DIAGNOSIS:-}" ]]; then arguments+=(--retry-diagnosis "$WP5_G6_RETRY_DIAGNOSIS"); fi
exec /share/home/zixiao/.conda/envs/chemprop/bin/python "$WP5_ROOT/scripts/wp5_g6_recover_v6.py" "${arguments[@]}"
