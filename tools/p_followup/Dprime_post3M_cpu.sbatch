#!/bin/bash
set -euo pipefail
cd /share/home/zixiao/descriptor_analysis/MFM_p_followup_20261117
export PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
export CUDA_VISIBLE_DEVICES=""
export OMP_NUM_THREADS=16 OPENBLAS_NUM_THREADS=16 MKL_NUM_THREADS=16 NUMEXPR_NUM_THREADS=16
export PYTHONPATH="$PWD/current:/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/repository:/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps"
/share/home/zixiao/.venvs/model_v2_cu118_20261105/bin/python -B -u tools/p_followup/compare_dprime.py
/share/home/zixiao/.venvs/model_v2_cu118_20261105/bin/python -B -u tools/p_followup/directive_geometry.py --conditions Dprime C3 --device cpu
/share/home/zixiao/.venvs/model_v2_cu118_20261105/bin/python -B -u tools/p_followup/val_conformer_mae.py --comparison Dprime --device cpu
