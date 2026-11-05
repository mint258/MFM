#!/bin/bash
#SBATCH --job-name=window2_full_D6
#SBATCH --partition=all
#SBATCH --nodelist=compute-0-20
#SBATCH --cpus-per-task=32
#SBATCH --ntasks=1
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/window2_20261105/D6_full_%j.log
set -euo pipefail
repo=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/repository
python=/share/home/zixiao/.conda/envs/chemprop/bin/python
plan=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/window2_20261105/D6_full_20261105_v1.plan.json
export PYTHONPATH="$repo/current:$repo:/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps${PYTHONPATH:+:$PYTHONPATH}"
export PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES=''
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
cd "$repo"
export D6_CODE_COMMIT=$(git rev-parse HEAD)
# This is the required descriptive P/Pprime comparison, reading only already
# produced molecule summaries; it never reopens original labels/geometries.
summary=/lfshome/zixiao/data_v1_20261025/window2_P_vs_Pprime_TRAIN_20261105_v1
if [ ! -f "$summary/manifest.json" ]; then
    "$python" -B -m workflows.data_v1_final.labels.window2_pprime_statistics_v1.compare \
        --pm7 /lfshome/zixiao/data_v1_20261025/window2_full_TRAIN_normalization_20261105_v1/manifest.json \
        --pprime /lfshome/zixiao/data_v1_20261025/window2_full_TRAIN_Pprime_statistics_20261105_v1/statistics/manifest.json \
        --output "$summary"
fi
# System telemetry only; no artificial capacity/RSS/time stopping threshold.
df -PT /share/home/zixiao/descriptor_analysis /lfshome/zixiao/data_v1_20261025
# No repeat unit suite or independent source QA. This binds closed extra
# pointers once; any genuinely unregistered old Pprime source point is kept.
# Its D3 alone is added, while every already closed D3 GID is reused.
"$python" -B -m workflows.data_v1_final.export.v31_stream_v1.prepare_runtime --plan "$plan"
"$python" -B -m workflows.data_v1_final.export.v31_stream_v1.run --plan "$plan"