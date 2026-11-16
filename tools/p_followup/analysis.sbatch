#!/bin/bash
set -euo pipefail
cd /share/home/zixiao/descriptor_analysis/MFM_p_followup_20261117
export PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 MKL_NUM_THREADS=4 NUMEXPR_NUM_THREADS=4
export PYTHONPATH="$PWD/current:/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/repository:/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps"
export CUDA_VISIBLE_DEVICES=GPU-ec788ed1-7da1-8f93-bb23-b4fdb2018b02
exec /share/home/zixiao/.venvs/model_v2_cu118_20261105/bin/python -B -u tools/p_followup/collapse_composition.py --device cuda
