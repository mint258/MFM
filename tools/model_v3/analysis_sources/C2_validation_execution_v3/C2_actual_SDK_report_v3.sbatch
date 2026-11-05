#!/bin/bash
#SBATCH --job-name=model_v3_C2_actual_SDK_report
#SBATCH --partition=cpu
#SBATCH --cpus-per-task=16
#SBATCH --mem=16G
#SBATCH --time=00:05:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/model_v3_20261025/C2_actual_SDK_report_%j.log
set -euo pipefail
: "${MODEL_V3_EXPECTED_NODE:?Bind actual CPU node}"
: "${MODEL_V3_C2_REPORT_INPUTS:?Bind actual C0 metadata}"
: "${MODEL_V3_C2_REPORT_INPUTS_SHA:?Bind exact input bytes}"
[[ $(hostname -s) == "$MODEL_V3_EXPECTED_NODE" ]]
cd /share/home/zixiao/descriptor_analysis
export CUDA_VISIBLE_DEVICES="" PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
export PATH=/share/home/zixiao/descriptor_analysis/runs/model_v3_20261025/cpu_git_tools_v1/bin:$PATH
task_python=/share/home/zixiao/.conda/envs/chemprop/bin/python
task_runs=/share/home/zixiao/descriptor_analysis/runs/model_v3_20261025
task_output=$task_runs/C2_actual_SDK_report_${SLURM_JOB_ID}
"$task_python" -u -B "$task_runs/run_cpu_supervised_64m_v1.py" \
 --output-root "$task_output" --record "$task_runs/C2_actual_SDK_report_supervisor_${SLURM_JOB_ID}.json" \
 --wall-seconds 180 --rss-limit-bytes 12884901888 --output-budget-bytes 67108864 -- \
 "$task_python" -B "$task_runs/c2_artifact_v3_report_source/c2_artifact_report.py" \
 --inputs "$MODEL_V3_C2_REPORT_INPUTS" --inputs-sha256 "$MODEL_V3_C2_REPORT_INPUTS_SHA" --output "$task_output"
