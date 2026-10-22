#!/bin/bash
#SBATCH --job-name=wp5_stat_s0_node18
#SBATCH --partition=cpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=24
#SBATCH --mem=32G
#SBATCH --time=48:00:00
#SBATCH --nodelist=compute-0-18
#SBATCH --signal=B:USR1@900
#SBATCH --chdir=/share/home/zixiao/descriptor_analysis
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/logs/home_stat_shard0_node18_%j.out
#SBATCH --error=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/logs/home_stat_shard0_node18_%j.err
# Fixed shard0 STATE, frozen V3; explicit execution-only migration from node12.
set -euo pipefail
cd /share/home/zixiao/descriptor_analysis
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 CUDA_VISIBLE_DEVICES=""
ROOT=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011
PY=/share/home/zixiao/.conda/envs/chemprop/bin/python
export PYTHONPATH="$ROOT/scripts${PYTHONPATH:+:$PYTHONPATH}"
"$PY" -B -c 'import hashlib,sys; assert hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest()==sys.argv[2]' \
  "$ROOT/scripts/wp5_inventory_shard0_node18_migration_v1.py" "2e5d867563a3ef219d7d0586cab0b3f57abca13205ed862a52171930ce63a4e0"
exec "$PY" -B "$ROOT/scripts/wp5_inventory_shard0_node18_migration_v1.py" "$@"
