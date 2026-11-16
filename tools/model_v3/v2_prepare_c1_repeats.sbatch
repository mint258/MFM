#!/bin/bash
#SBATCH --job-name=M3-C1-top-two-repeat-preparation
#SBATCH --partition=all
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/model_v31_20261105/C1_repeats_%j.log
set -euo pipefail
root=/share/home/zixiao/descriptor_analysis
cd "$root/MFM_model_v3"
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
python=/share/home/zixiao/.conda/envs/chemprop/bin/python
findmnt -T "$root"
df -B1 / /lfshome/zixiao "$root"
df -Pi / /lfshome/zixiao "$root"
"$python" -B tools/model_v3/v2_diagnosis_disk.py --once --output /lfshome/zixiao/model_v31_20261105 --node "$(hostname -s)" --job "$SLURM_JOB_ID" --state "$root/runs/model_v31_20261105/M3_controlled_${SLURM_JOB_ID}.state.json"
"$python" -B tools/model_v3/v2_prepare_c1_repeats.py --inputs "$root/MFM_model_v3/configs/model_v3/c1_initial_results.json" --output "$root/runs/model_v31_20261105/M3_C1_TOP2_20261110"
