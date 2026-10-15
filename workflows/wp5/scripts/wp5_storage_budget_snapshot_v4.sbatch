#!/bin/bash
#SBATCH --job-name=wp5_g3_budget_snapshot
#SBATCH --partition=cpu
#SBATCH --nodelist=compute-0-17
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=24
#SBATCH --mem=32G
#SBATCH --time=48:00:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/logs/%x_%j.out
#SBATCH --error=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/logs/%x_%j.err
set -euo pipefail
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export PYTHONPATH=/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps:/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/scripts:${PYTHONPATH:-}
WP5_ROOT=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011
export WP5_QUOTA_PATH="$WP5_ROOT/gates/g3/quota_budget_${SLURM_JOB_ID}.json"
/share/home/zixiao/.conda/envs/chemprop/bin/python -B - <<'PY'
import json,os,time
from pathlib import Path
root=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011')
data=(root/'reports/observation_latest.json').read_bytes();obj=json.loads(data)
if obj['uid']!=1278 or obj['hostname'].split('.')[0]!='sonmi' or not -5<=time.time()-obj['time']<=180:
    raise ValueError('Actual fresh Root login quota required')
if obj['publisher']['sha256']!='fa03acc9dbb5ca3cc4ffe1b98f038a99d34734bbb313d9ab13408e528ae2cc7c' or obj['quota']['returncode']!=0:
    raise ValueError('Real publisher or quota failed')
rows=[s.split() for s in obj['quota']['stdout'].splitlines() if s.strip().startswith('/dev/')]
if len(rows)!=1 or (int(rows[0][3])-int(rows[0][1]))*1024!=obj['quota_parsed']['remaining_bytes']:
    raise ValueError('Quota numeric row differs')
with Path(os.environ['WP5_QUOTA_PATH']).open('xb') as f:f.write(data)
PY
exec timeout --signal=TERM --kill-after=120s 46h bash "$WP5_ROOT/scripts/wp5_storage_budget_v9.sbatch"
