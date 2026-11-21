#!/bin/bash
#SBATCH --partition=all
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --nodelist=compute-0-20
#SBATCH --cpus-per-task=16
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/p_recipe_20261113/%x_%j.log
set -euo pipefail
root=/share/home/zixiao/descriptor_analysis
cd "$root/MFM_p_recipe"
export CUDA_VISIBLE_DEVICES="" PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0
export PYTHONPATH=$PWD/current:$root/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps
export PATH=$root/runs/model_v3_20261025/cpu_git_tools_v1/bin:$PATH
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export PHASE1_NATIVE_TRANSPORT_PATH=$root/docs/phase1/evidence/stage48_full_corpus_qa/native_qa_stats_v3.py
export PHASE1_JOINT_REFERENCE_PATH=$root/docs/phase1/evidence/stage50_full_corpus_training/actual_api_reference/full_corpus_training.py
python=/share/home/zixiao/.venvs/model_v2_cu118_20261105/bin/python
output=/lfshome/zixiao/model_v31_20261105/P_RECIPE_20261113
# D4 local future120GB plus this suite8GB, with the system reserve in the guard.
"$python" -B tools/p_recipe/watch_local_d4.py --root /tmp/zixiao_p_recipe_D4_20261113 --peak 128000000000 --job "$SLURM_JOB_ID" --once
"$python" -B tools/model_v3/v2_diagnosis_disk.py --once --output "$output" --node "$(hostname -s)" --job "$SLURM_JOB_ID" --state /dev/null
"$python" -B -u tools/p_recipe/watch_local_d4.py --root /tmp/zixiao_p_recipe_D4_20261113 --peak 128000000000 --job "$SLURM_JOB_ID" &
local_guard=$!
"$python" -B -u tools/model_v3/v2_diagnosis_disk.py --output "$output" --node "$(hostname -s)" --job "$SLURM_JOB_ID" --state "$root/runs/p_recipe_20261113/disk_${SLURM_JOB_ID}.json" &
shared_guard=$!
trap 'kill "$local_guard" "$shared_guard" 2>/dev/null || true; wait "$local_guard" "$shared_guard" 2>/dev/null || true' EXIT
"$python" -B -u tools/p_recipe/regression.py