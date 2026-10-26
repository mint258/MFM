#!/bin/bash
#SBATCH --job-name=model_v3_C4_GPU_layers
#SBATCH --partition=all
#SBATCH --cpus-per-task=16
#SBATCH --mem=32G
#SBATCH --time=00:20:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/model_v3_20261025/fixed_h0_capture_GPU_v2_launch_v1_%j.log
set -euo pipefail
: "${MODEL_V3_EXPECTED_NODE:?Root node binding required}"
: "${MODEL_V3_GPU_UUID:?Root physical UUID required}"
: "${MODEL_V3_NUMERIC_GPU_REQUEST_SHA:?Frozen C4 diagnostic manifest required}"
: "${MODEL_V3_NUMERIC_GPU_LAUNCH_PINS_SHA:?Frozen launch manifest required}"
: "${MODEL_V3_NUMERIC_GPU_ADMISSION_FRAME:?This attempt Root frame required}"
: "${MODEL_V3_NUMERIC_GPU_ADMISSION_SHA:?Root frame raw SHA required}"
: "${MODEL_V3_NUMERIC_GPU_SUBMISSION_RECEIPT:?This actual sbatch receipt required}"
[[ "$(hostname -s)" == compute-0-21 && "$MODEL_V3_EXPECTED_NODE" == compute-0-21 ]]
[[ "$MODEL_V3_GPU_UUID" == GPU-c35f2434-9137-9723-1af5-dc69b6295243 ]]
task_base=/share/home/zixiao/descriptor_analysis
task_eq=$task_base/MFM_model_v3_numeric_stability_v1
task_source=$task_base/runs/model_v3_20261026/numeric_fixed_h0_shadow_v2_source
task_python=$task_base/docs/phase1/evidence/stage43_5090_environment/install_4511929/venv/bin/python
export CUDA_VISIBLE_DEVICES="$MODEL_V3_GPU_UUID" PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
export PYTHONPATH="$task_eq/current:$task_base/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps"
export MODEL_V3_NUMERIC_TEST_DEVICE=cuda:0 MODEL_V3_NUMERIC_TEST_MODE=compensated_fp32_v1 MODEL_V3_NUMERIC_TEST_THREADS=1
export PYTEST_ADDOPTS="-o tmp_path_retention_policy=all"
cd "$task_eq"
exec 9<>"$task_base/docs/phase1/evidence/stage46_shared_gpu_launch/.own_gpu_uuid_locks/$MODEL_V3_GPU_UUID.lock"
flock -n 9
export MODEL_V3_GPU_LOCK_FD=9
exec "$task_python" -u -B "$task_source/launch_capture_GPU_v1.py" worker \
  --submission-receipt "$MODEL_V3_NUMERIC_GPU_SUBMISSION_RECEIPT"
