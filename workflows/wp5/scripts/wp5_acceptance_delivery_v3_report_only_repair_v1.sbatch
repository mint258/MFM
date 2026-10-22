#!/bin/bash
#SBATCH --job-name=wp5_delivery3_report_repair
#SBATCH --partition=cpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=24
#SBATCH --mem=32G
#SBATCH --time=48:00:00
#SBATCH --nodelist=compute-0-17
#SBATCH --chdir=/share/home/zixiao/descriptor_analysis
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/logs/delivery3_report_repair_%j.out
#SBATCH --error=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/logs/delivery3_report_repair_%j.err
set -euo pipefail
ROOT=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011
cd /share/home/zixiao/descriptor_analysis
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 CUDA_VISIBLE_DEVICES=""
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH="$ROOT/scripts:/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps${PYTHONPATH:+:$PYTHONPATH}"
PY=/share/home/zixiao/.conda/envs/chemprop/bin/python
"$PY" -B -c 'import hashlib,sys; assert hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest()==sys.argv[2]; import pyarrow, pyarrow.parquet; print("DELIVERY_DEPENDENCY_READY",pyarrow.__version__)' \
  "$ROOT/scripts/wp5_acceptance_delivery_v3.py" "d8af3311a0de17cec43df7f93a4613dfca99c69d6f5ca6af219fed6921516aaa"
# Report-only repair: the successful historical raw probe from actual4515672 is retained.
exec timeout --signal=TERM --kill-after=120s 46h "$PY" -B "$ROOT/scripts/wp5_acceptance_delivery_v3.py" \
  --workers 24 "$@" --out "$ROOT/acceptance/final_20261016_v1/delivery_$SLURM_JOB_ID"
