#!/bin/bash
#SBATCH --job-name=dv1_window2_B6_descriptors
#SBATCH --partition=all
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --nice=10000
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/window2_20261105/B6_%j.out
set -euo pipefail
# Root alone selects an idle CPU node and submits this template; B1--B5 retain priority.
# This template has no GPU request, memory request, task wall limit or approval stage.
export CUDA_VISIBLE_DEVICES="" PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
B6_REPO=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/repository
B6_PYTHON=/share/home/zixiao/.conda/envs/chemprop/bin/python
export PYTHONPATH="$B6_REPO:$B6_REPO/current:/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps"
cd "$B6_REPO"
# Default is one parent: exactly14 tests, then all150770 source records,16 workers.
# For resume/other disjoint shards after these tests passed, Root sets B6_RUN_TESTS=0.
if [[ "${B6_RUN_TESTS:-1}" == 1 ]]; then
    "$B6_PYTHON" -B -m unittest \
        workflows.data_v1_final.downstream_descriptors_v2.test_v1 \
        workflows.data_v1_final.downstream_descriptors_v2.test_geometry
fi
B6_SHARD_INDEX=${B6_SHARD_INDEX:-0}
B6_SHARDS=${B6_SHARDS:-1}
B6_OUTPUT_ROOT=${B6_OUTPUT_ROOT:-/lfshome/zixiao/data_v1_20261025/window2_B6_descriptors_20261105_v2}
printf -v B6_SHARD_NAME 'shard-%03d-of-%03d' "$B6_SHARD_INDEX" "$B6_SHARDS"
exec "$B6_PYTHON" -B -m workflows.data_v1_final.downstream_descriptors_v2.run \
    --config configs/data_v1/downstream_descriptors_v2.json \
    --output "$B6_OUTPUT_ROOT/$B6_SHARD_NAME" \
    --workers 16 --shard-index "$B6_SHARD_INDEX" --shards "$B6_SHARDS"
