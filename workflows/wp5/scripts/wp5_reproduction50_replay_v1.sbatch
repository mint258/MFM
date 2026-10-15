#!/bin/bash
#SBATCH --job-name=wp5_50replay1
#SBATCH --partition=cpu
#SBATCH --nodelist=compute-0-17
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=24
#SBATCH --mem=32G
#SBATCH --time=48:00:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/logs/%x_%j.out
#SBATCH --error=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/logs/%x_%j.err
set -euo pipefail
WP5_ROOT=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011
export PYTHONPATH=/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps:$WP5_ROOT/scripts:${PYTHONPATH:-}
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
exec timeout --preserve-status --signal=TERM --kill-after=120s 46h /share/home/zixiao/.conda/envs/chemprop/bin/python "$WP5_ROOT/scripts/wp5_reproduction50_replay_v1.py" \
 --plan "$WP5_ROOT/gates/reproduction50/job_4513962/plan.json" --workers 24 "$@"
