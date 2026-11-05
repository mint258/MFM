#!/bin/bash
#SBATCH --job-name=routing7_closed_R2_metadata
#SBATCH --partition=cpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --time=00:20:00
set -euo pipefail
: "${MODEL_V3_EXPECTED_NODE:?Actual Root-selected CPU node}"
: "${MODEL_V3_R7_AUDIT_SOURCE_SHA:?Frozen audit source pins SHA}"
: "${MODEL_V3_R7_AUDIT_PARENT_JSON:?Actual selected GPU C0 seven-column accounting JSON}"
: "${MODEL_V3_R7_AUDIT_PARENT_SHA:?Actual accounting raw SHA}"
: "${MODEL_V3_R7_AUDIT_OUTPUT:?Fresh independent N output}"
test "$#" -ge 1
test "$#" -le 6
export CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
py=/share/home/zixiao/.conda/envs/chemprop/bin/python
p=/share/home/zixiao/descriptor_analysis
s=$p/runs/model_v3_20261026/performance_remaining_Av2_routing_v7_metadata_audit_v3_source
exec "$py" -u -B "$p/runs/model_v3_20261025/run_cpu_supervised_v3.py" \
 --output-root "$MODEL_V3_R7_AUDIT_OUTPUT" --record "$MODEL_V3_R7_AUDIT_OUTPUT.supervisor.json" \
 --wall-seconds 900 --rss-limit-bytes 12884901888 -- \
 "$py" -u -B "$s/audit_closed.py" \
 --source-pins-sha256 "$MODEL_V3_R7_AUDIT_SOURCE_SHA" --old-job-id "$@" \
 --parent-sacct-json "$MODEL_V3_R7_AUDIT_PARENT_JSON" --parent-sacct-sha256 "$MODEL_V3_R7_AUDIT_PARENT_SHA" \
 --expected-node "$MODEL_V3_EXPECTED_NODE" --output-root "$MODEL_V3_R7_AUDIT_OUTPUT"
