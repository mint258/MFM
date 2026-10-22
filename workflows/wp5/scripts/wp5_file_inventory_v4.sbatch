#!/bin/bash
#SBATCH --job-name=wp5_home_stat_v4
#SBATCH --partition=cpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=24
#SBATCH --mem=32G
#SBATCH --time=48:00:00
#SBATCH --nodelist=compute-0-12
#SBATCH --signal=B:USR1@900
#SBATCH --chdir=/share/home/zixiao/descriptor_analysis
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/logs/home_stat_v4_%j.out
#SBATCH --error=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/logs/home_stat_v4_%j.err
# Prepared candidate only. Root must review actual small validation before use.
# Same STATE, only terminal predecessor's unfinished shard; DONE is never reset.
set -euo pipefail
cd /share/home/zixiao/descriptor_analysis
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 CUDA_VISIBLE_DEVICES=""
ROOT=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011
PY=/share/home/zixiao/.conda/envs/chemprop/bin/python
export PYTHONPATH="$ROOT/scripts${PYTHONPATH:+:$PYTHONPATH}"
state=${1:?same persistent inventory STATE required}
shard=${2:?explicit shard 0..5 required}
shift 2
[[ "$shard" =~ ^[0-5]$ ]] || exit 2
"$PY" -B -c 'import hashlib,sys; assert hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest()==sys.argv[2]' \
  "$ROOT/scripts/wp5_file_inventory_v4.py" "85cd785806b82f59afdb33436d4e083ef8240e2b49abf7f31224382ee3d3d5a7"
exec "$PY" -B "$ROOT/scripts/wp5_file_inventory_v4.py" --mode scan --state-dir "$state" \
  --shard "$shard" --workers 24 --hours 46 --directory-budget-seconds 165600 "$@"
