#!/bin/bash
#SBATCH --job-name=Native_S20000_dev9_auto
#SBATCH --partition=all
#SBATCH --nodelist=compute-0-21
#SBATCH --cpus-per-task=16
#SBATCH --time=01:00:00
# Prepared copy receives --output/--error inside its independent output_base.
set -euo pipefail
[[ -n "${SLURM_JOB_ID:-}" ]] || exit 2
: "${MODEL_V3_PANEL_SPEC:?Actual Native prepared spec}"
: "${MODEL_V3_PANEL_SPEC_SHA:?Spec raw SHA}"
: "${MODEL_V3_PANEL_ROOT_ADMISSION:?Fresh Root resource/quota/hold evidence}"
: "${MODEL_V3_PANEL_ROOT_ADMISSION_SHA:?Fresh Root evidence raw SHA}"
: "${MODEL_V3_PANEL_GPU_UUID:?Actual admitted full GPU UUID}"
: "${MODEL_V3_PANEL_OUTPUT_BASE:?Independent new N panel root}"
: "${MODEL_V3_PANEL_REPOSITORY:?CPU-tested and public exact-tree bridge root}"
B=/share/home/zixiao/descriptor_analysis
S=$B/runs/model_v3_20261026/native_S20000_dev_panel_auto_v1_source
PY=$B/docs/phase1/evidence/stage43_5090_environment/install_4511929/venv/bin/python
export CUDA_VISIBLE_DEVICES="$MODEL_V3_PANEL_GPU_UUID" PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=16 MKL_NUM_THREADS=16 OPENBLAS_NUM_THREADS=16
export PYTHONPATH="$MODEL_V3_PANEL_REPOSITORY/current:$B/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps"
cd "$MODEL_V3_PANEL_REPOSITORY"
# No fd9 lock here: evaluate_dev_panel.execute is the ONLY UUID-lock owner.
"$PY" -u -B "$B/MFM_model_v3_a_checkpoint/tools/model_v3/run_supervised.py" \
 --output-root "$MODEL_V3_PANEL_OUTPUT_BASE/evaluation" \
 --record "$MODEL_V3_PANEL_OUTPUT_BASE/supervisor_${SLURM_JOB_ID}.json" \
 --gpu-uuid "$CUDA_VISIBLE_DEVICES" --rss-limit-bytes 30064771072 --wall-seconds 3590 \
 --output-budget-bytes 2147483648 --private-scratch-root /tmp/mv3n_${SLURM_JOB_ID} \
 --private-storage-budget-bytes 2147483648 -- \
 "$PY" -u -B "$S/run_native_panel_guard.py" --spec "$MODEL_V3_PANEL_SPEC" \
 --spec-sha256 "$MODEL_V3_PANEL_SPEC_SHA" --node compute-0-21 --gpu-uuid "$CUDA_VISIBLE_DEVICES" \
 --root-admission "$MODEL_V3_PANEL_ROOT_ADMISSION" --root-admission-sha256 "$MODEL_V3_PANEL_ROOT_ADMISSION_SHA" \
 --guard-output "$MODEL_V3_PANEL_OUTPUT_BASE/guard_${SLURM_JOB_ID}"