#!/bin/bash
#SBATCH --job-name=p-recipe-D4-repair
#SBATCH --partition=all
#SBATCH --nodelist=compute-0-20
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/p_recipe_20261113/D4_repair_%j.log
set -euo pipefail
root=/share/home/zixiao/descriptor_analysis
cd "$root/MFM_p_recipe"
export CUDA_VISIBLE_DEVICES="" PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH=$root/runs/data_v1_20261025/repository:$PWD/current:$root/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
python=/share/home/zixiao/.venvs/model_v2_cu118_20261105/bin/python
local_output=/tmp/zixiao_p_recipe_D4_20261113
shared_output=/lfshome/zixiao/model_v31_20261105/P_RECIPE_20261113/D4_REPAIRED
"$python" -B tools/p_recipe/watch_local_d4.py --root "$local_output" --peak 120000000000 --job "$SLURM_JOB_ID" --once
"$python" -B tools/model_v3/v2_diagnosis_disk.py --once --output "$shared_output" --node "$(hostname -s)" --job "$SLURM_JOB_ID" --state /dev/null
mkdir -p "$local_output"
chmod 700 "$local_output"
"$python" -B -u tools/p_recipe/watch_local_d4.py --root "$local_output" --peak 120000000000 --job "$SLURM_JOB_ID" &
local_guard=$!
"$python" -B -u tools/model_v3/v2_diagnosis_disk.py --output "$shared_output" --state "$root/runs/p_recipe_20261113/D4_disk_${SLURM_JOB_ID}.json" --node "$(hostname -s)" --job "$SLURM_JOB_ID" &
shared_guard=$!
trap 'kill "$local_guard" "$shared_guard" 2>/dev/null || true; wait "$local_guard" "$shared_guard" 2>/dev/null || true' EXIT
"$python" -B -u tools/p_recipe/refit_d4.py --dataset P_D --output "$local_output/P_D" --workers "$SLURM_CPUS_PER_TASK"
"$python" -B -u tools/p_recipe/refit_d4.py --dataset Pprime --output "$local_output/Pprime" --workers "$SLURM_CPUS_PER_TASK"
"$python" -B -u tools/p_recipe/refit_d4.py --publish
