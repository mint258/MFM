#!/bin/bash
#SBATCH --job-name=model_v3_closed_native_long_archive
#SBATCH --partition=cpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --mem=16G
#SBATCH --time=00:20:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/model_v3_20261025/closed_native_long_archive_%j.log
set -euo pipefail
umask 077
test -n "$MODEL_V3_EXPECTED_NODE"
test -n "$MODEL_V3_CLOSED_LONG_ARCHIVE_RECEIPT"
test -n "$MODEL_V3_CLOSED_LONG_ARCHIVE_RECEIPT_SHA"
test -n "$MODEL_V3_CLOSED_LONG_ARCHIVE_PIN"
test -n "$MODEL_V3_CLOSED_LONG_ARCHIVE_OUTPUT"
export CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
task_project=/share/home/zixiao/descriptor_analysis
task_py=/share/home/zixiao/.conda/envs/chemprop/bin/python
exec "$task_py" -u -B "$task_project/runs/model_v3_20261025/run_cpu_supervised_v3.py" \
  --output-root "$MODEL_V3_CLOSED_LONG_ARCHIVE_OUTPUT" --record "$MODEL_V3_CLOSED_LONG_ARCHIVE_OUTPUT.supervisor.json" \
  --wall-seconds 900 --rss-limit-bytes 12884901888 -- \
  "$task_py" -u -B "$task_project/runs/model_v3_20261026/native_closed_long_archive_v1/archive_closed_long.py" \
  --source-pins-sha256 "$MODEL_V3_CLOSED_LONG_ARCHIVE_PIN" run --expected-node "$MODEL_V3_EXPECTED_NODE" \
  --root-receipt "$MODEL_V3_CLOSED_LONG_ARCHIVE_RECEIPT" --root-receipt-sha256 "$MODEL_V3_CLOSED_LONG_ARCHIVE_RECEIPT_SHA"

