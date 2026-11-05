#!/bin/bash
#SBATCH --partition=all
#SBATCH --nodelist=compute-0-21
#SBATCH --cpus-per-task=16
#SBATCH --mem=32G
#SBATCH --time=00:20:00
set -euo pipefail
export PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=8 MKL_NUM_THREADS=8 OPENBLAS_NUM_THREADS=8 NUMEXPR_NUM_THREADS=8
export CUDA_VISIBLE_DEVICES=GPU-22e21021-e572-4562-fc51-cd8c83e74141
export PYTHONPATH=/share/home/zixiao/descriptor_analysis/runs/model_v3_20261026/native_s_profile_launch_v8:/share/home/zixiao/descriptor_analysis/runs/model_v3_20261026/native_s_precision_storage_adapter_v2:/share/home/zixiao/descriptor_analysis/MFM_model_v3_native_s_runtime_v1/current:/share/home/zixiao/descriptor_analysis/MFM_model_v3_native_s_runtime_v1/current/tests:/share/home/zixiao/descriptor_analysis/MFM_model_v3_native_s_runtime_v1/tools/model_v3:/share/home/zixiao/descriptor_analysis/MFM_model_v3_native_s_runtime_v1/workflows/sprime_s/scripts:/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps
cd /share/home/zixiao/descriptor_analysis/MFM_model_v3_native_s_runtime_v1
exec /share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage43_5090_environment/install_4511929/venv/bin/python -u -B /share/home/zixiao/descriptor_analysis/runs/model_v3_20261026/native_s_profile_launch_v8/gpu_worker.py --phase "$1" --precision "$2" --pins-sha256 "$3"
