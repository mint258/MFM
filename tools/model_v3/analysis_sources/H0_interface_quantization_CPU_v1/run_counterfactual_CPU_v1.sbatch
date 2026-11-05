#!/bin/bash
#SBATCH --job-name=H0_interface_quantization
#SBATCH --partition=cpu
#SBATCH --cpus-per-task=16
#SBATCH --mem=16G
#SBATCH --time=00:03:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/model_v3_20261025/H0_interface_quantization_CPU_v1_%j.log
set -euo pipefail
: "${MODEL_V3_EXPECTED_NODE:?Fresh actual CPU node binding}"
: "${MODEL_V3_H0_QUANT_INPUTS_SHA:?Exact new inputs raw SHA}"
: "${MODEL_V3_H0_QUANT_PINS_SHA:?Exact new source pins raw SHA}"
base=/share/home/zixiao/descriptor_analysis
scope=$base/runs/model_v3_20261026/H0_interface_quantization_CPU_v1_source
runs=$base/runs/model_v3_20261025
python=$base/docs/phase1/evidence/stage43_5090_environment/install_4511929/venv/bin/python
export CUDA_VISIBLE_DEVICES="" PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4
export PYTHONPATH="$base/MFM_model_v3_attention_centering_v1/current:$base/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps"
cd "$base/MFM_model_v3_attention_centering_v1"
output=$runs/H0_interface_quantization_CPU_v1_${SLURM_JOB_ID}
"$python" -u -B "$runs/run_cpu_supervised_v3.py" --output-root "$output" \
  --record "$runs/H0_interface_quantization_CPU_v1_supervisor_${SLURM_JOB_ID}.json" \
  --wall-seconds 120 --rss-limit-bytes 12884901888 -- \
  "$python" -u -B "$scope/run_counterfactual_CPU.py" --output-root "$output" \
  --inputs "$scope/inputs_v1.json" --inputs-sha256 "$MODEL_V3_H0_QUANT_INPUTS_SHA" \
  --source-pins-sha256 "$MODEL_V3_H0_QUANT_PINS_SHA" --expected-node "$MODEL_V3_EXPECTED_NODE"