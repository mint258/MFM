#!/bin/bash
#SBATCH --job-name=model_v3_identity_regression_v4
#SBATCH --partition=cpu
#SBATCH --cpus-per-task=16
#SBATCH --mem=32G
#SBATCH --time=00:20:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/model_v3_20261025/partitioned_regression_%j.log
set -euo pipefail
: "${MODEL_V3_CONTROL_ROOT:?Explicit frozen v4 control directory}"
: "${MODEL_V3_CONTROL_PLAN_SHA:?Explicit raw frozen control plan SHA}"
: "${MODEL_V3_CPU_EXECUTION_TREE:?Explicit execution tree}"
: "${MODEL_V3_EXPECTED_NODE:?Explicit allocated CPU node}"
: "${MODEL_V3_PHASE1_NATIVE_TRANSPORT_PATH:?Explicit external Python source}"
: "${MODEL_V3_PHASE1_JOINT_REFERENCE_PATH:?Explicit external Python source}"
cd "$MODEL_V3_CPU_EXECUTION_TREE"
export CUDA_VISIBLE_DEVICES="" PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
export PATH=/share/home/zixiao/descriptor_analysis/runs/model_v3_20261025/cpu_git_tools_v1/bin:$PATH
export PYTHONPATH="$MODEL_V3_CPU_EXECUTION_TREE/current:/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps"
export MODEL_V3_CPU_TEST_SCOPE=regression MODEL_V3_CPU_TEST_OUTPUT_PREFIX=integration_tests
export PHASE1_NATIVE_TRANSPORT_PATH="$MODEL_V3_PHASE1_NATIVE_TRANSPORT_PATH"
export PHASE1_JOINT_REFERENCE_PATH="$MODEL_V3_PHASE1_JOINT_REFERENCE_PATH"
task_python=/share/home/zixiao/.conda/envs/chemprop/bin/python
task_runs=/share/home/zixiao/descriptor_analysis/runs/model_v3_20261025
task_revision=/share/home/zixiao/descriptor_analysis/runs/model_v3_20261026/cpu_supervisor_revision_v4_source
task_pins_sha=$(sha256sum "$task_revision/source_pins_v1.json" | cut -d " " -f 1)
task_output=$task_runs/integration_tests_${SLURM_JOB_ID}
"$task_python" -u -B "$task_revision/run_cpu_supervised_v4.py" \
  --output-root "$task_output" --record "$task_runs/integration_supervisor_${SLURM_JOB_ID}.json" \
  --source-pins "$task_revision/source_pins_v1.json" --source-pins-sha256 "$task_pins_sha" --registration-mode pytest4 \
  --wall-seconds 1100 --rss-limit-bytes 30064771072 -- \
  "$task_python" -u -B "$MODEL_V3_REGRESSION_RUNNER" --root "$MODEL_V3_CPU_EXECUTION_TREE" \
  --output "$task_output" --code-commit "$MODEL_V3_EXECUTION_SHA" --workers 4 \
  --expected-node "$MODEL_V3_EXPECTED_NODE" --partitions "$MODEL_V3_PARTITION_COUNT" \
  --partition-index "$MODEL_V3_PARTITION_INDEX" --partition-plan "$MODEL_V3_PARTITION_PLAN" \
  --partition-plan-sha256 "$MODEL_V3_PARTITION_PLAN_SHA"
