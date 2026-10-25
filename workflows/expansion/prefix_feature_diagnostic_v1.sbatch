#!/bin/bash
#SBATCH --job-name=data_v1_prefix_feature_diag
#SBATCH --partition=all
#SBATCH --nodelist=compute-0-20
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --mem=4G
#SBATCH --time=01:00:00
set -eu
: "${EXPANSION_REPO:?Root must bind the reviewed repository}"
: "${PREFIX_FEATURE_DIAGNOSTIC_PLAN:?Root must bind a READY diagnostic plan}"
: "${PREFIX_FEATURE_DIAGNOSTIC_ROOT_INTENT:?Root must bind the actual reviewed intent}"
export CUDA_VISIBLE_DEVICES=""
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH="${EXPANSION_REPO}${PYTHONPATH:+:${PYTHONPATH}}"
cd /share/home/zixiao/descriptor_analysis
exec /share/home/zixiao/.conda/envs/chemprop/bin/python -B -m workflows.expansion.prefix_feature_diagnostic_v1 --plan "${PREFIX_FEATURE_DIAGNOSTIC_PLAN}" --root-submit-intent "${PREFIX_FEATURE_DIAGNOSTIC_ROOT_INTENT}"
