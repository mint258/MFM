#!/bin/bash
#SBATCH --job-name=data_v1_X_stop_diagnosis
#SBATCH --partition=all
#SBATCH --nodelist=compute-0-20
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --mem=4G
#SBATCH --time=01:00:00
set -eu
: "${EXPANSION_REPO:?Root must bind the reviewed repository}"
: "${X_STOP_DIAGNOSIS_PLAN:?Root must bind a READY diagnosis plan}"
: "${X_STOP_DIAGNOSIS_ROOT_INTENT:?Root must bind the real reviewed intent}"
export CUDA_VISIBLE_DEVICES=""
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH="${EXPANSION_REPO}:/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps${PYTHONPATH:+:${PYTHONPATH}}"
cd /share/home/zixiao/descriptor_analysis
exec /share/home/zixiao/.conda/envs/chemprop/bin/python -B -m workflows.expansion.diagnose_x_stop_v1 --plan "${X_STOP_DIAGNOSIS_PLAN}" --root-submit-intent "${X_STOP_DIAGNOSIS_ROOT_INTENT}"
