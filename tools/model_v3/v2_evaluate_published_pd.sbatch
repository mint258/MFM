#!/bin/bash
#SBATCH --job-name=M3-P-TRAIN-dev-panel
#SBATCH --partition=all
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/model_v31_20261105/M3_P_dev_%j.log
set -euo pipefail
directory=${1:?registered P training output}
gpu_uuid=${2:?actual GPU UUID}
python=${3:?existing compatible Python}
root=/share/home/zixiao/descriptor_analysis
cd "$root/MFM_model_v3"
export CUDA_VISIBLE_DEVICES="$gpu_uuid" PYTHONDONTWRITEBYTECODE=1 PYTHONIOENCODING=utf-8
export PYTHONPATH=$PWD/current:$root/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export PYTORCH_ALLOC_CONF=expandable_segments:True
output=$directory/dev_eval
"$python" -B -c 'from pathlib import Path; import sys; p=Path(sys.argv[1]); assert p.is_absolute() and p.is_relative_to(Path("/lfshome/zixiao/model_v31_20261105"))' "$directory"
findmnt -T /lfshome/zixiao
df -B1 / /lfshome/zixiao "$root"
df -Pi / /lfshome/zixiao "$root"
state=$root/runs/model_v31_20261105/M3_controlled_${SLURM_JOB_ID}.state.json
"$python" -B tools/model_v3/v2_diagnosis_disk.py --once --output "$output" --node "$(hostname -s)" --job "$SLURM_JOB_ID" --state "$state"
exec 9>"$root/docs/phase1/evidence/stage46_shared_gpu_launch/.own_gpu_uuid_locks/${gpu_uuid}.lock"
flock -n 9
"$python" -B - "$gpu_uuid" <<'PY'
import csv,subprocess,sys
result=subprocess.run(['nvidia-smi','--query-compute-apps=gpu_uuid,pid','--format=csv,noheader,nounits'],capture_output=True,text=True,check=True)
if any(row and row[0].strip()==sys.argv[1] for row in csv.reader(result.stdout.splitlines())):
    raise RuntimeError('Assigned GPU has another compute context; evaluation not started')
PY
"$python" -B -u tools/model_v3/v2_diagnosis_disk.py --output "$output" --state "$state" --node "$(hostname -s)" --job "$SLURM_JOB_ID" &
guard=$!
trap 'kill "$guard" 2>/dev/null || true; wait "$guard" 2>/dev/null || true' EXIT
"$python" -B -u tools/model_v3/v2_evaluate_s.py --checkpoint "$directory/samples_6000000.pt" --output "$output"
