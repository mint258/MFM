#!/bin/bash
#SBATCH --job-name=wp5_prodshape_metadata
#SBATCH --partition=cpu
#SBATCH --cpus-per-task=24
#SBATCH --mem=32G
#SBATCH --time=00:20:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/logs/%x_%j.out
#SBATCH --error=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/logs/%x_%j.err
set -euo pipefail
ROOT=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011
PYTHON=/share/home/zixiao/.conda/envs/chemprop/bin/python
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export PYTHONPATH="/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps:${ROOT}/scripts${PYTHONPATH:+:${PYTHONPATH}}"
: "${WP5_METADATA_MODE:?backup, node or verify required}"
: "${WP5_METADATA_FIXTURE:?new private fixture path required}"
exec "${PYTHON}" "${ROOT}/scripts/wp5_queue_production_shape_v2.py" "${WP5_METADATA_MODE}" --fixture "${WP5_METADATA_FIXTURE}" "$@"
