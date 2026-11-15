#!/bin/bash
set -euo pipefail
school_home=/share/home/202264640132
root="$school_home/precision_20261115"
python="$root/env/bin/python"
# Preserve Slurm's CUDA visibility while asking CUDA for the allocated UUID.
# Do not treat scheduler/global IDs as NVML indexes inside a device cgroup.
# A separate assignment propagates failure instead of masking it with export.
allocated_uuid=$("$python" -B tools/model_v3/precision_allocated_gpu.py)
export CUDA_VISIBLE_DEVICES="$allocated_uuid"
nvidia-smi -i "$CUDA_VISIBLE_DEVICES" --query-gpu=uuid,name,driver_version,memory.total --format=csv
"$python" -B -m pytest -q -p no:cacheprovider current/tests/test_p_precision_islands.py
for batch in 32 128; do
 for precision in fp32 tf32_islands bf16_islands; do
  "$python" -B -u tools/model_v3/precision_study.py benchmark --configuration configs/p_recipe/precision_20261115/school_speed.json --precision "$precision" --batch-size "$batch" --output "$root/speed_${precision}_B${batch}_$SLURM_JOB_ID"
 done
done
