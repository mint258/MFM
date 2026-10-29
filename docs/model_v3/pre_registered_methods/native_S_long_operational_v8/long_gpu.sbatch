#!/bin/bash
#SBATCH --partition=all
#SBATCH --nodelist=compute-0-21
#SBATCH --cpus-per-task=16
#SBATCH --time=02:00:00
set -euo pipefail
export PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=8 MKL_NUM_THREADS=8 OPENBLAS_NUM_THREADS=8 NUMEXPR_NUM_THREADS=8
export CUDA_VISIBLE_DEVICES=GPU-22e21021-e572-4562-fc51-cd8c83e74141
task_project=/share/home/zixiao/descriptor_analysis
task_source=$task_project/runs/model_v3_20261026/native_S_long_operational_v8
task_runtime=$task_project/MFM_model_v3_native_s_runtime_v1
export PYTHONPATH=$task_source:$task_project/runs/model_v3_20261026/native_s_profile_launch_v8:$task_project/runs/model_v3_20261026/native_s_precision_storage_adapter_v2:$task_runtime/current:$task_runtime/current/tests:$task_runtime/tools/model_v3:$task_runtime/workflows/sprime_s/scripts:$task_project/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps
cd "$task_runtime"
exec "$task_project/docs/phase1/evidence/stage43_5090_environment/install_4511929/venv/bin/python" -u -B "$task_source/long_worker.py" --phase "$1" --submission "$2" --pins-sha256 "$3"
