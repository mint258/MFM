#!/bin/bash
set -euo pipefail
# Root-only scoped authorization: design15->actual12; design16->actual13.
# k24,32GiB,02:00:00 allocation;90min actual benchmark, same six hash cohorts.
ROOT=/share/home/zixiao/descriptor_analysis/runs/phase1_screening_20261011
DESIGN=${1:?design node index required}
ACTUAL=${2:?actual execution node index required}
export PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES=''
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
cd /share/home/zixiao/descriptor_analysis
mkdir -p "$ROOT/c_engineering/nodes"
set +e
/share/home/zixiao/.conda/envs/chemprop/bin/python -B "$ROOT/scripts/c_engineering_node_probe_v2.py" --design-node-index "$DESIGN" --actual-node-index "$ACTUAL" --runtime-seconds 5400 --output "$ROOT/c_engineering/nodes/design_${DESIGN}_actual_${ACTUAL}_job_${SLURM_JOB_ID}"
task_rc=$?
printf '%s\n' "$task_rc" > "$ROOT/logs/c_engineering_node_v2_${SLURM_JOB_ID}.exitcode"
exit "$task_rc"
