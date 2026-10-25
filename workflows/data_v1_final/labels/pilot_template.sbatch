#!/bin/bash
#SBATCH --job-name=data_v1_label_pilot
#SBATCH --partition=all
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --mem=64G
#SBATCH --time=00:30:00
#SBATCH --nodelist=compute-0-20
#SBATCH --chdir=/share/home/zixiao/descriptor_analysis

# Root must materialize a new reviewed script with the actually admitted node,
# output/error paths, plan pin and unique output directory before sbatch.
set -euo pipefail
: "${LABEL_PILOT_PLAN:?Root must supply a reviewed pilot plan}"
: "${LABEL_PILOT_OUTPUT:?Root must supply a new external output directory}"
LABEL_CODE_ROOT="${LABEL_CODE_ROOT:-/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/repository}"
export CUDA_VISIBLE_DEVICES=""
export PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1
export PYTHONPATH=/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps
srun --input=none --ntasks=1 --cpus-per-task=16 \
  /share/home/zixiao/.conda/envs/chemprop/bin/python -B \
  "${LABEL_CODE_ROOT}/workflows/data_v1_final/labels/pilot_masks.py" \
  --plan "${LABEL_PILOT_PLAN}" --output "${LABEL_PILOT_OUTPUT}" </dev/null
