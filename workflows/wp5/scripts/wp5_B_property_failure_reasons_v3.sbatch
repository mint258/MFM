#!/bin/bash
#SBATCH --job-name=wp5_Bfailure_readonly
#SBATCH --chdir=/share/home/zixiao/descriptor_analysis
#SBATCH --partition=cpu
#SBATCH --nodelist=compute-0-14
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=24
#SBATCH --mem=32G
#SBATCH --time=48:00:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/logs/Bfailure_readonly_%j.out
#SBATCH --error=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/logs/Bfailure_readonly_%j.err
set -euo pipefail
ROOT=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011
PY=/share/home/zixiao/.conda/envs/chemprop/bin/python
OUT=${1:-$ROOT/acceptance/final_20261016_v1/pm7B_failure_reasons_readonly_v3}
DICTS=${2:-$ROOT/dictionaries/job_4513894/dictionary_manifest.json}
export PYTHONPATH=/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps:"$ROOT/scripts":${PYTHONPATH:-}
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
cd /share/home/zixiao/descriptor_analysis
timeout --preserve-status --signal=TERM --kill-after=120s 46h "$PY" -B "$ROOT/scripts/wp5_B_property_failure_reasons_v3.py" --workers 24 --dictionaries "$DICTS" --out "$OUT"
"$PY" -B "$ROOT/scripts/wp5_pilot_disclosure_semantic_fixture_v1.py" --out "$OUT/delivery3_semantic_fixture_report_v1.json"
