#!/bin/bash
#SBATCH --job-name=wp5_home_stat_v3
#SBATCH --partition=cpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=24
#SBATCH --mem=32G
#SBATCH --time=48:00:00
#SBATCH --nodelist=compute-0-17
#SBATCH --signal=B:USR1@900
#SBATCH --chdir=/share/home/zixiao/descriptor_analysis
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/logs/home_stat_v3_%j.out
#SBATCH --error=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/logs/home_stat_v3_%j.err
set -euo pipefail
cd /share/home/zixiao/descriptor_analysis
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 CUDA_VISIBLE_DEVICES=""
ROOT=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011
export PYTHONPATH="$ROOT/scripts${PYTHONPATH:+:$PYTHONPATH}"
if (( $# >= 2 )); then
  mode=$1; state=$2; shift 2
else
  mode=${WP5_INVENTORY_MODE:?init scan or collect required}
  state=${WP5_INVENTORY_STATE_DIR:?independent persistent state directory required}
fi
args=(--mode "$mode" --state-dir "$state" --workers 24 --hours 46 --directory-budget-seconds 1800)
if [[ "$mode" == scan ]]; then
  if (( $# )) && [[ "$1" =~ ^[0-5]$ ]]; then shard=$1; shift
  elif [[ -n "${WP5_INVENTORY_SHARD:-}" ]]; then shard=$WP5_INVENTORY_SHARD
  else
    case "$(hostname -s)" in
      compute-0-12) shard=0;; compute-0-13) shard=1;; compute-0-14) shard=2;;
      compute-0-17) shard=3;; compute-0-18) shard=4;; compute-0-19) shard=5;;
      *) echo 'Unauthorized shard hostname' >&2; exit 2;;
    esac
  fi
  args+=(--shard "$shard")
fi
if [[ "$mode" == scan ]]; then
  /share/home/zixiao/.conda/envs/chemprop/bin/python -B "$ROOT/scripts/wp5_file_inventory_commit_fixture_v3.py" \
    --out "$ROOT/reports/home_stat_inventory_commit_retry_v3_job_${SLURM_JOB_ID}.json"
fi
exec /share/home/zixiao/.conda/envs/chemprop/bin/python -B "$ROOT/scripts/wp5_file_inventory_v3.py" "${args[@]}" "$@"