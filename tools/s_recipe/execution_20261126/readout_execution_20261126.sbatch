#!/bin/bash
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --time=02:00:00
#SBATCH --signal=B:USR1@900
set -euo pipefail
cd /share/home/zixiao/descriptor_analysis/MFM_s_recipe
export TZ=UTC CUDA_VISIBLE_DEVICES="${2:?actual GPU UUID}" PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=16 MKL_NUM_THREADS=16 OPENBLAS_NUM_THREADS=16 NUMEXPR_NUM_THREADS=16
export PYTHONPATH=$PWD/current:$PWD/tools/s_recipe:/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/repository:/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps
exec "${3:?actual Python}" -B -u tools/s_recipe/readout_execution_20261126.py --task "$1" --mode "${4:?actual execution mode}"
