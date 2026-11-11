#!/bin/bash
#SBATCH --job-name=model-v2-development
#SBATCH --partition=all
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/model_v31_20261105/development_%j.log
set -euo pipefail
mode=${1:?v31, native_s, dev or validation}
configuration=${2:?actual experiment configuration}
gpu_uuid=${3:?actual GPU UUID}
python=${4:?existing compatible Python}
root=/share/home/zixiao/descriptor_analysis
cd "$root/MFM_model_v3"
export CUDA_VISIBLE_DEVICES="$gpu_uuid" PYTHONDONTWRITEBYTECODE=1 PYTHONIOENCODING=utf-8
export PYTHONPATH=$PWD/current:$root/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export PYTORCH_ALLOC_CONF=expandable_segments:True
output=$("$python" -B tools/model_v3/v2_run_development.py --mode "$mode" --configuration "$configuration" --show-output)
findmnt -T /lfshome/zixiao
df -B1 / /lfshome/zixiao "$root"
df -Pi / /lfshome/zixiao "$root"
free -b
state=$root/runs/model_v31_20261105/M3_controlled_${SLURM_JOB_ID}.state.json
"$python" -B tools/model_v3/v2_diagnosis_disk.py --once --output "$output" --node "$(hostname -s)" --job "$SLURM_JOB_ID" --state "$state"
exec 9>"$root/docs/phase1/evidence/stage46_shared_gpu_launch/.own_gpu_uuid_locks/${gpu_uuid}.lock"
flock -n 9
"$python" -B - "$gpu_uuid" <<'PY'
import csv,subprocess,sys
result=subprocess.run(['nvidia-smi','--query-compute-apps=gpu_uuid,pid','--format=csv,noheader,nounits'],capture_output=True,text=True,check=True)
if any(row and row[0].strip()==sys.argv[1] for row in csv.reader(result.stdout.splitlines())):
    raise RuntimeError('Assigned GPU has another compute context; no experiment started')
PY
"$python" -B -u tools/model_v3/v2_diagnosis_disk.py --output "$output" --state "$state" --node "$(hostname -s)" --job "$SLURM_JOB_ID" &
guard=$!
trap 'kill "$guard" 2>/dev/null || true; wait "$guard" 2>/dev/null || true' EXIT
if [[ "$mode" == v31 || "$mode" == native_s ]]; then
    "$python" -B tools/model_v3/v2_wandb_tracking.py \
        --manifest "$root/runs/model_v31_20261105/M3_wandb_manifest_20261110.json" \
        --register-configuration "$configuration" --training-mode "$mode" \
        --job "$SLURM_JOB_ID" --node "$(hostname -s)" --gpu "$gpu_uuid"
fi
"$python" -B -u tools/model_v3/v2_run_development.py --mode "$mode" --configuration "$configuration"
