#!/bin/bash
#SBATCH --job-name=fixed_h0_terminal_shadow
#SBATCH --partition=cpu
#SBATCH --cpus-per-task=16
#SBATCH --mem=16G
#SBATCH --time=00:03:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/model_v3_20261025/fixed_h0_shadow_cpu_v3_%j.log
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
scope=$base/runs/model_v3_20261026/numeric_fixed_h0_shadow_v3_source
runs=$base/runs/model_v3_20261025
python=$base/docs/phase1/evidence/stage43_5090_environment/install_4511929/venv/bin/python
export CUDA_VISIBLE_DEVICES="" PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4
export PYTHONPATH="$base/MFM_model_v3_numeric_stability_v1/current:$base/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps"
cd "$base/MFM_model_v3_numeric_stability_v1"
output=$runs/fixed_h0_shadow_cpu_v3_${SLURM_JOB_ID}
"$python" -u -B "$runs/run_cpu_supervised_v3.py" --output-root "$output" \
  --record "$runs/fixed_h0_shadow_cpu_v3_supervisor_${SLURM_JOB_ID}.json" \
  --wall-seconds 120 --rss-limit-bytes 12884901888 -- \
  "$python" -u -B "$scope/shadow_terminals_v1.py" --output-root "$output" \
  --source-pins-sha256 "$MODEL_V3_H0_SOURCE_PINS_SHA" --expected-node "$MODEL_V3_EXPECTED_NODE" \
  --capture-complete "$MODEL_V3_H0_CAPTURE_COMPLETE" --capture-complete-sha256 "$MODEL_V3_H0_CAPTURE_COMPLETE_SHA" \
  --capture-supervisor "$MODEL_V3_H0_CAPTURE_SUPERVISOR" --capture-supervisor-sha256 "$MODEL_V3_H0_CAPTURE_SUPERVISOR_SHA" \
  --capture-accounting "$MODEL_V3_H0_CAPTURE_ACCOUNTING" --capture-accounting-sha256 "$MODEL_V3_H0_CAPTURE_ACCOUNTING_SHA"
