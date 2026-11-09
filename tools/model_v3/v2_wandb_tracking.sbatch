#!/bin/bash
#SBATCH --job-name=model-v2-wandb
#SBATCH --partition=all
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/model_v31_20261105/wandb_%j.log
set -euo pipefail
root=/share/home/zixiao/descriptor_analysis
cd "$root/MFM_model_v3"
python=/share/home/zixiao/.conda/envs/chemprop/bin/python
manifest=${1:?actual tracking manifest}
output=$(/usr/bin/python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["tracking_root"])' "$manifest")
export CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
state=$root/runs/model_v31_20261105/M3_wandb_disk_${SLURM_JOB_ID}.json
"$python" -B tools/model_v3/v2_diagnosis_disk.py --once --output "$output" --node "$(hostname -s)" --job "$SLURM_JOB_ID" --state "$state"
"$python" -B -u tools/model_v3/v2_diagnosis_disk.py --output "$output" --node "$(hostname -s)" --job "$SLURM_JOB_ID" --state "$state" &
guard=$!
trap 'kill "$guard" 2>/dev/null || true; wait "$guard" 2>/dev/null || true' EXIT
"$python" -B -u tools/model_v3/v2_wandb_tracking.py --manifest "$manifest"
