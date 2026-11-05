#!/bin/bash
#SBATCH --job-name=centered_fixed_H0_shadow
#SBATCH --partition=cpu
#SBATCH --cpus-per-task=16
#SBATCH --mem=16G
#SBATCH --time=00:03:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/model_v3_20261025/centered_fixed_H0_shadow_CPU_v1_%j.log
set -euo pipefail
: "${MODEL_V3_EXPECTED_NODE:?Actual CPU node binding}"
: "${MODEL_V3_H0_CAPTURE_COMPLETE:?Actual capture complete}"
: "${MODEL_V3_H0_CAPTURE_COMPLETE_SHA:?Actual capture raw SHA}"
: "${MODEL_V3_H0_CAPTURE_SUPERVISOR:?Actual successful supervisor}"
: "${MODEL_V3_H0_CAPTURE_SUPERVISOR_SHA:?Supervisor raw SHA}"
: "${MODEL_V3_H0_CAPTURE_ACCOUNTING:?Root actual raw sacct observation}"
: "${MODEL_V3_H0_CAPTURE_ACCOUNTING_SHA:?Actual accounting raw SHA}"
: "${MODEL_V3_H0_SOURCE_PINS_SHA:?Exact CPU analysis source version, separate from capture v2}"
base=/share/home/zixiao/descriptor_analysis
scope=$base/runs/model_v3_20261026/centered_fixed_H0_diagnostic_v1_source
runs=$base/runs/model_v3_20261025
python=$base/docs/phase1/evidence/stage43_5090_environment/install_4511929/venv/bin/python
export CUDA_VISIBLE_DEVICES="" PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4
export PYTHONPATH="$base/MFM_model_v3_attention_centering_v1/current:$base/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps"
cd "$base/MFM_model_v3_attention_centering_v1"
output=$runs/centered_fixed_H0_shadow_CPU_v1_${SLURM_JOB_ID}
"$python" -u -B "$runs/run_cpu_supervised_v3.py" --output-root "$output" \
  --record "$runs/centered_fixed_H0_shadow_CPU_v1_supervisor_${SLURM_JOB_ID}.json" \
  --wall-seconds 120 --rss-limit-bytes 12884901888 -- \
  "$python" -u -B "$scope/analyze_centered_H0_CPU.py" --output-root "$output" \
  --source-pins-sha256 "$MODEL_V3_H0_SOURCE_PINS_SHA" --expected-node "$MODEL_V3_EXPECTED_NODE" \
  --capture-complete "$MODEL_V3_H0_CAPTURE_COMPLETE" --capture-complete-sha256 "$MODEL_V3_H0_CAPTURE_COMPLETE_SHA" \
  --capture-supervisor "$MODEL_V3_H0_CAPTURE_SUPERVISOR" --capture-supervisor-sha256 "$MODEL_V3_H0_CAPTURE_SUPERVISOR_SHA" \
  --capture-accounting "$MODEL_V3_H0_CAPTURE_ACCOUNTING" --capture-accounting-sha256 "$MODEL_V3_H0_CAPTURE_ACCOUNTING_SHA"
