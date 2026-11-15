#!/bin/bash
set -euo pipefail
school_home=/share/home/202264640132
root="$school_home/precision_20261115"
python="$root/env/bin/python"
# SLURM_JOB_GPUS uses global device IDs; CUDA_VISIBLE_DEVICES can be remapped
# inside a device cgroup. Bind telemetry and the model to the allocated UUID.
gpu=${SLURM_JOB_GPUS:-${CUDA_VISIBLE_DEVICES:?Slurm GPU binding missing}}
gpu=${gpu%%,*}
export CUDA_VISIBLE_DEVICES=$(nvidia-smi -i "$gpu" --query-gpu=uuid --format=csv,noheader)
nvidia-smi -i "$CUDA_VISIBLE_DEVICES" --query-gpu=uuid,name,driver_version,memory.total --format=csv
"$python" -B -m pytest -q -p no:cacheprovider current/tests/test_p_precision_islands.py
for batch in 32 128; do
 for precision in fp32 tf32_islands bf16_islands; do
  "$python" -B -u tools/model_v3/precision_study.py benchmark --configuration configs/p_recipe/precision_20261115/school_speed.json --precision "$precision" --batch-size "$batch" --output "$root/speed_${precision}_B${batch}_$SLURM_JOB_ID"
 done
done
