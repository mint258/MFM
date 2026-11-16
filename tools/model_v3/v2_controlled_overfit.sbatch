#!/bin/bash
#SBATCH --job-name=M2-controlled-overfit
#SBATCH --partition=all
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/model_v31_20261105/M2_controlled_%j.log
set -euo pipefail
configuration=${1:?one exact diagnostic configuration}
gpu_uuid=${2:?actual free GPU UUID}
python=${3:?existing compatible Python}
root=/share/home/zixiao/descriptor_analysis
cd "$root/MFM_model_v3"
export CUDA_VISIBLE_DEVICES="$gpu_uuid"
export PYTHONPATH=$PWD/current:$root/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export PYTHONDONTWRITEBYTECODE=1 PYTHONIOENCODING=utf-8
export PYTORCH_ALLOC_CONF=expandable_segments:True
output=$("$python" -B -c 'import json,sys; from pathlib import Path; p=Path(json.loads(Path(sys.argv[1]).read_text())["output"]); assert p.is_absolute() and p.is_relative_to(Path("/lfshome/zixiao/model_v31_20261105")); print(p)' "$configuration")
lustre_quota=$root/runs/data_v1_20261025/control/window2_20261105/lustre_quota_available_v2_20261107.json
nfs_quota=$root/runs/data_v1_20261025/control/window2_20261105/share_quota_available_v3.json
findmnt -T /lfshome/zixiao
df -B1 / /lfshome/zixiao "$root"
df -Pi / /lfshome/zixiao "$root"
state=$root/runs/model_v31_20261105/M2_controlled_${SLURM_JOB_ID}.state.json
"$python" -B -u "$root/MFM_model_v3/tools/model_v3/v2_diagnosis_disk.py" --output "$output" --state "$state" --node "$(hostname -s)" --job "$SLURM_JOB_ID" --once
exec 9>"$root/docs/phase1/evidence/stage46_shared_gpu_launch/.own_gpu_uuid_locks/${gpu_uuid}.lock"
flock -n 9
"$python" -B -u "$root/MFM_model_v3/tools/model_v3/v2_diagnosis_disk.py" --output "$output" --state "$state" --node "$(hostname -s)" --job "$SLURM_JOB_ID" &
guard=$!
trap 'kill "$guard" 2>/dev/null || true; wait "$guard" 2>/dev/null || true' EXIT
"$python" -B -u - "$configuration" <<'PY'
import json,sys
from pathlib import Path
from phychem_mfm.phase1.v31_overfit_diagnosis import run_controlled
run_controlled(**json.loads(Path(sys.argv[1]).read_text()))
PY
