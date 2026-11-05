#!/bin/bash
#SBATCH --job-name=model_v3_partitioned_regression
#SBATCH --partition=cpu
#SBATCH --cpus-per-task=16
#SBATCH --mem=32G
#SBATCH --time=00:20:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/model_v3_20261025/partitioned_regression_%j.log
set -euo pipefail
: "${MODEL_V3_EXECUTION_SHA:?Bind actual target commit}"
: "${MODEL_V3_CPU_EXECUTION_TREE:?Bind actual execution tree}"
: "${MODEL_V3_EXPECTED_NODE:?Bind actual allocated CPU node}"
: "${MODEL_V3_REGRESSION_RUNNER:?Bind fixed regression runner snapshot}"
: "${MODEL_V3_REGRESSION_RUNNER_SHA:?Bind exact runner bytes}"
: "${MODEL_V3_PARTITION_INDEX:?Bind this partition index}"
: "${MODEL_V3_PARTITION_COUNT:?Bind total partition count}"
cd "$MODEL_V3_CPU_EXECUTION_TREE"
export CUDA_VISIBLE_DEVICES="" PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
export PATH=/share/home/zixiao/descriptor_analysis/runs/model_v3_20261025/cpu_git_tools_v1/bin:$PATH
export PYTHONPATH="$MODEL_V3_CPU_EXECUTION_TREE/current:/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps"
export PHASE1_NATIVE_TRANSPORT_PATH=/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage48_full_corpus_qa/native_qa_stats_v3.py
export PHASE1_JOINT_REFERENCE_PATH=/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage50_full_corpus_training/actual_api_reference/full_corpus_training.py
export MODEL_V3_CPU_TEST_SCOPE=regression MODEL_V3_CPU_TEST_OUTPUT_PREFIX=integration_tests
task_python=/share/home/zixiao/.conda/envs/chemprop/bin/python
task_runs=/share/home/zixiao/descriptor_analysis/runs/model_v3_20261025
"$task_python" -B "$task_runs/assert_worktree_code_v1.py"
"$task_python" -B -c 'import hashlib,os; from pathlib import Path; assert hashlib.sha256(Path(os.environ["MODEL_V3_REGRESSION_RUNNER"]).read_bytes()).hexdigest()==os.environ["MODEL_V3_REGRESSION_RUNNER_SHA"]'
task_output=$task_runs/integration_tests_${SLURM_JOB_ID}
task_pin=$task_runs/integration_sources_${SLURM_JOB_ID}.sha256
sha256sum current/phychem_mfm/model/v3_*.py current/phychem_mfm/phase1/v3_*.py current/tests/test_model_v3_*.py tools/model_v3/*.py > "$task_pin"
task_exit=0
"$task_python" -u -B "$task_runs/run_cpu_test_supervised_v2.py" \
  --output-root "$task_output" --record "$task_runs/integration_supervisor_${SLURM_JOB_ID}.json" \
  --wall-seconds 1100 --rss-limit-bytes 30064771072 -- \
  "$task_python" -u -B "$MODEL_V3_REGRESSION_RUNNER" --root "$MODEL_V3_CPU_EXECUTION_TREE" \
  --output "$task_output" --code-commit "$MODEL_V3_EXECUTION_SHA" --workers 4 \
  --expected-node "$MODEL_V3_EXPECTED_NODE" --partitions "$MODEL_V3_PARTITION_COUNT" \
  --partition-index "$MODEL_V3_PARTITION_INDEX" --partition-plan "$MODEL_V3_PARTITION_PLAN" \
  --partition-plan-sha256 "$MODEL_V3_PARTITION_PLAN_SHA" || task_exit=$?
sha256sum --check "$task_pin"
"$task_python" -B "$task_runs/assert_worktree_code_v1.py"
exit "$task_exit"
