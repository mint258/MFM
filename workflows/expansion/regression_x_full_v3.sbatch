#!/bin/bash
#SBATCH --job-name=data_v1_X_full_v3
#SBATCH --partition=all
#SBATCH --nodelist=compute-0-20
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --mem=32G
#SBATCH --time=04:00:00
set -eu
: "${EXPANSION_REPO:?Root must bind the reviewed repository}"
: "${X_FULL_V3_PLAN:?Root must bind a READY full replay plan}"
: "${X_FULL_V3_ROOT_INTENT:?Root must bind the actual reviewed intent}"
export CUDA_VISIBLE_DEVICES=""
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH="${EXPANSION_REPO}:/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps${PYTHONPATH:+:${PYTHONPATH}}"
cd /share/home/zixiao/descriptor_analysis
exec /share/home/zixiao/.conda/envs/chemprop/bin/python -B -m workflows.expansion.regression_x_full_v3 --plan "${X_FULL_V3_PLAN}" --root-submit-intent "${X_FULL_V3_ROOT_INTENT}"
