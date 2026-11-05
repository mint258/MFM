#!/bin/bash
#SBATCH --job-name=projection_passive_stage_offline
#SBATCH --partition=cpu
#SBATCH --cpus-per-task=16
#SBATCH --mem=16G
#SBATCH --time=00:15:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/model_v3_20261025/projection_passive_stage_offline_CPU_v1_%j.log
set -euo pipefail
: "${MODEL_V3_EXPECTED_NODE:?Fresh actual CPU node binding}"
: "${MODEL_V3_TERMINAL_INPUTS_SHA:?Exact new inputs raw SHA}"
: "${MODEL_V3_TERMINAL_PINS_SHA:?Exact new source pins raw SHA}"
base=/share/home/zixiao/descriptor_analysis
scope=$base/runs/model_v3_20261026/projection_passive_stage_offline_CPU_v1_source
runs=$base/runs/model_v3_20261025
python=$base/docs/phase1/evidence/stage43_5090_environment/install_4511929/venv/bin/python
export CUDA_VISIBLE_DEVICES="" PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4
export PYTHONPATH="$base/MFM_model_v3_projection_fp32_candidate_v1/current:$base/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps"
cd "$base/MFM_model_v3_projection_fp32_candidate_v1"
output=$runs/projection_passive_stage_offline_CPU_v1_${SLURM_JOB_ID}
"$python" -u -B "$runs/run_cpu_supervised_v3.py" --output-root "$output" \
  --record "$runs/projection_passive_stage_offline_CPU_v1_supervisor_${SLURM_JOB_ID}.json" \
  --wall-seconds 800 --rss-limit-bytes 12884901888 --output-budget-bytes 2147483648 -- \
  "$python" -u -B "$scope/analyze_saved_stages.py" --output-root "$output" \
  --inputs "$scope/inputs.json" --inputs-sha256 "$MODEL_V3_TERMINAL_INPUTS_SHA" \
  --source-pins-sha256 "$MODEL_V3_TERMINAL_PINS_SHA" --expected-node "$MODEL_V3_EXPECTED_NODE"
