#!/bin/bash
#SBATCH --job-name=wp5_node14_preserve_clean
#SBATCH --chdir=/share/home/zixiao/descriptor_analysis
#SBATCH --partition=cpu
#SBATCH --nodelist=compute-0-14
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=24
#SBATCH --mem=32G
#SBATCH --time=48:00:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/logs/node14_preserve_clean_%j.out
#SBATCH --error=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/logs/node14_preserve_clean_%j.err
set -euo pipefail
ROOT=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011
F="$ROOT/acceptance/final_20261016_v1"
PY=/share/home/zixiao/.conda/envs/chemprop/bin/python
export PYTHONPATH=/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps:"$ROOT/scripts":${PYTHONPATH:-}
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
OWN_TMP="/tmp/wp5node14cleanup_${UID}_${SLURM_JOB_ID}"
if [[ -e "$OWN_TMP" ]];then printf 'Own temp exists; inspect before rerun\n' >&2;exit 2;fi
mkdir -m 700 -- "$OWN_TMP"
export TMPDIR="$OWN_TMP"
# This separate dispatcher temp remains empty; no recursive scratch deletion.
trap 'rmdir -- "$OWN_TMP"' EXIT
cd /share/home/zixiao/descriptor_analysis
timeout --preserve-status --signal=TERM --kill-after=120s 46h "$PY" -B "$ROOT/scripts/wp5_node14_preserve_then_clean_v1.py" --plan "$F/node14_5292_scratch_classification_v3.json" --accounting "$F/formal541_terminal_accounting.json" --out "$F/node14_5292_preserve_then_clean_v1" --execute
