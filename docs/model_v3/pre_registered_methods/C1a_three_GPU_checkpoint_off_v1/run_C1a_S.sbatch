#!/bin/bash
#SBATCH --job-name=model_v3_C1a_checkpoint_off
#SBATCH --partition=all
#SBATCH --cpus-per-task=16
#SBATCH --time=02:00:00
set -euo pipefail
for key in ${!SBATCH_@}; do unset "$key"; done
: "${MODEL_V3_GPU_UUID:?Root fresh physical UUID}"
: "${MODEL_V3_EXPECTED_NODE:?Root fresh admitted node}"
: "${MODEL_V3_EXPECTED_GPU:?Root selects3090/4090/5090}"
: "${MODEL_V3_AUTO_REGISTRATION_ID:?Root actual shared software budget registration}"
: "${MODEL_V3_SOURCE_ROOT:?Actual canonical runtime source}"
: "${MODEL_V3_CODE_SHA:?Actual runtime code SHA}"
: "${MODEL_V3_OUT:?Fresh independent child output}"
: "${MODEL_V3_RECORD:?Fresh disjoint supervisor record}"
: "${MODEL_V3_STARTUP_JSON:?Fresh independent small startup JSON}"
B=/share/home/zixiao/descriptor_analysis
S=$B/runs/model_v3_20261026/C1a_three_GPU_checkpoint_off_v1_source
PY=$B/docs/phase1/evidence/stage43_5090_environment/install_4511929/venv/bin/python
export CUDA_VISIBLE_DEVICES="$MODEL_V3_GPU_UUID" CUBLAS_WORKSPACE_CONFIG=:4096:8
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=8 MKL_NUM_THREADS=8 OPENBLAS_NUM_THREADS=8
export PYTHONPATH="$MODEL_V3_SOURCE_ROOT/current:$MODEL_V3_SOURCE_ROOT/tools/model_v3:$MODEL_V3_SOURCE_ROOT/workflows/sprime_s/scripts:$B/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps"
cd "$MODEL_V3_SOURCE_ROOT"
# Root admission/registration precedes sbatch; fresh worker rechecks the same
# shared policy. The benchmark is the sole GPU UUID lock holder.
exec "$PY" -u -B "$S/start_C1a_S.py"
