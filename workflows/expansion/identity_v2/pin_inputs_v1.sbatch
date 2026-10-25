#!/bin/bash
#SBATCH --job-name=data_v1_identity_inputs
#SBATCH --partition=all
#SBATCH --nodelist=compute-0-20
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --mem=4G
#SBATCH --time=01:00:00
set -eu
: "${EXPANSION_REPO:?Root must bind reviewed repository}"
: "${IDENTITY_INPUT_PIN_PLAN:?Root must bind the READY input-pin plan}"
: "${IDENTITY_INPUT_PIN_ROOT_INTENT:?Root must bind actual reviewed intent}"
export CUDA_VISIBLE_DEVICES=""
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH="${EXPANSION_REPO}:/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps${PYTHONPATH:+:${PYTHONPATH}}"
cd /share/home/zixiao/descriptor_analysis
exec /share/home/zixiao/.conda/envs/chemprop/bin/python -B -m workflows.expansion.identity_v2.pin_inputs_v1 --plan "${IDENTITY_INPUT_PIN_PLAN}" --root-submit-intent "${IDENTITY_INPUT_PIN_ROOT_INTENT}"
