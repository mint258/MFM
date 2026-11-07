#!/bin/bash
#SBATCH --job-name=data_v1_pubchem_raw
#SBATCH --partition=all
#SBATCH --nodelist=compute-0-20
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --mem=4G
#SBATCH --time=01:00:00
# Root supplies unique --output/--error and the reviewed export values.
set -eu
: "${EXPANSION_REPO:?Root must bind the exact reviewed repository}"
: "${RAW_DOWNLOAD_PLAN:?Root must bind the physical acquisition plan}"
: "${RAW_ROOT_SUBMISSION_INTENT:?Root must bind the actual submit_reviewed intent}"
export CUDA_VISIBLE_DEVICES=""
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH="${EXPANSION_REPO}${PYTHONPATH:+:${PYTHONPATH}}"
cd /share/home/zixiao/descriptor_analysis
exec /share/home/zixiao/.conda/envs/chemprop/bin/python -B -m workflows.expansion.download_raw_v1 --plan "${RAW_DOWNLOAD_PLAN}" --root-submit-intent "${RAW_ROOT_SUBMISSION_INTENT}"
