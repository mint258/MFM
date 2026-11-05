#!/bin/bash
#SBATCH --job-name=model_v3_C2_TRAIN_artifact_probe
#SBATCH --partition=cpu
#SBATCH --cpus-per-task=16
#SBATCH --mem=32G
#SBATCH --time=00:05:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/model_v3_20261025/C2_artifact_probe_%j.log
set -euo pipefail
: "${MODEL_V3_EXPECTED_NODE:?Bind actual available CPU node}"
: "${MODEL_V3_C2_ARTIFACT_INPUTS_SHA:?Bind publicly adopted prior-TRAIN method}"
[[ $(hostname -s) == "$MODEL_V3_EXPECTED_NODE" ]]
cd /share/home/zixiao/descriptor_analysis
export CUDA_VISIBLE_DEVICES="" PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=16 MKL_NUM_THREADS=16 OPENBLAS_NUM_THREADS=16
export PATH=/share/home/zixiao/descriptor_analysis/runs/model_v3_20261025/cpu_git_tools_v1/bin:$PATH
export PYTHONPATH=/share/home/zixiao/descriptor_analysis/MFM_model_v3_c2/current:/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps
task_python=/share/home/zixiao/.conda/envs/chemprop/bin/python
task_runs=/share/home/zixiao/descriptor_analysis/runs/model_v3_20261025
task_output=$task_runs/C2_artifact_probe_${SLURM_JOB_ID}
"$task_python" -u -B "$task_runs/run_cpu_supervised_128m_v1.py" \
  --output-root "$task_output" --record "$task_runs/C2_artifact_probe_supervisor_${SLURM_JOB_ID}.json" \
  --wall-seconds 240 --rss-limit-bytes 25769803776 --output-budget-bytes 134217728 -- \
  "$task_python" -u -B "$task_runs/C2_TRAIN_artifact_preflight_v1.py" \
  --inputs "$MODEL_V3_C2_ARTIFACT_INPUTS" --inputs-sha256 "$MODEL_V3_C2_ARTIFACT_INPUTS_SHA" \
  --expected-node "$MODEL_V3_EXPECTED_NODE" --output-root "$task_output"
