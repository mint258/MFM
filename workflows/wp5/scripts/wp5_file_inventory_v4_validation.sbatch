#!/bin/bash
#SBATCH --job-name=wp5_stat_v4_probe
#SBATCH --partition=cpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=24
#SBATCH --mem=32G
#SBATCH --time=00:30:00
#SBATCH --nodelist=compute-0-14
#SBATCH --chdir=/share/home/zixiao/descriptor_analysis
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/logs/home_stat_v4_validation_%j.out
#SBATCH --error=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/logs/home_stat_v4_validation_%j.err
# Prepared only. Root reviews and submits; this batch never opens production STATE.
set -euo pipefail
cd /share/home/zixiao/descriptor_analysis
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 CUDA_VISIBLE_DEVICES=""
ROOT=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011
PY=/share/home/zixiao/.conda/envs/chemprop/bin/python
export PYTHONPATH="$ROOT/scripts${PYTHONPATH:+:$PYTHONPATH}"
profile_dir=${1:?explicit readonly directory required}
out=${2:?fresh existing-parent acceptance output directory required}
entries=${3:-4096}
[[ "$out" == "$ROOT/acceptance/"* && ! -e "$out" ]] || exit 2
"$PY" -B -c 'import hashlib,sys; assert hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest()==sys.argv[2]' \
  "$ROOT/scripts/wp5_file_inventory_v4_validation.py" "3dd9694888da811e8a4b60db7c9458225a716102e5b96743acda8c27f678616e"
mkdir -- "$out"
timeout --signal=TERM --kill-after=30s 3m "$PY" -B "$ROOT/scripts/wp5_file_inventory_v4_validation.py" \
  fixture --out "$out/private_semantics_fixture.json"
timeout --signal=TERM --kill-after=30s 20m "$PY" -B "$ROOT/scripts/wp5_file_inventory_v4_validation.py" \
  profile --path "$profile_dir" --entries "$entries" --out "$out/readonly_stat_profile.json"
