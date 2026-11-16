#!/bin/bash
#SBATCH --job-name=M3-P-following-published-D6
#SBATCH --partition=all
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/model_v31_20261105/M3_P_%j.log
set -euo pipefail
template=${1:?unchanged P candidate template}
gpu_uuid=${2:?actual GPU UUID}
python=${3:?existing compatible Python}
root=/share/home/zixiao/descriptor_analysis
cd "$root/MFM_model_v3"
export CUDA_VISIBLE_DEVICES="$gpu_uuid" PYTHONDONTWRITEBYTECODE=1 PYTHONIOENCODING=utf-8
export PYTHONPATH=$PWD/current:$root/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export PYTORCH_ALLOC_CONF=expandable_segments:True
configuration=${template%.template.json}.json
binding=$root/runs/data_v1_20261025/artifacts/export/S240k_PD_input_binding_20261108_v1/manifest.json
output=$("$python" -B -c 'import json,sys; from pathlib import Path; p=Path(json.loads(Path(sys.argv[1]).read_text())["output"]); assert p.is_absolute() and p.is_relative_to(Path("/lfshome/zixiao/model_v31_20261105")); print(p)' "$template")
findmnt -T /lfshome/zixiao
df -B1 / /lfshome/zixiao "$root"
df -Pi / /lfshome/zixiao "$root"
free -b
state=$root/runs/model_v31_20261105/M3_controlled_${SLURM_JOB_ID}.state.json
"$python" -B tools/model_v3/v2_diagnosis_disk.py --once --output "$output" --node "$(hostname -s)" --job "$SLURM_JOB_ID" --state "$state"
"$python" -B tools/model_v3/v2_bind_published_pd.py --template "$template" --binding "$binding" --output "$configuration"
exec 9>"$root/docs/phase1/evidence/stage46_shared_gpu_launch/.own_gpu_uuid_locks/${gpu_uuid}.lock"
flock -n 9
"$python" -B - "$gpu_uuid" <<'PY'
import csv,subprocess,sys
result=subprocess.run(['nvidia-smi','--query-compute-apps=gpu_uuid,pid','--format=csv,noheader,nounits'],capture_output=True,text=True,check=True)
if any(row and row[0].strip()==sys.argv[1] for row in csv.reader(result.stdout.splitlines())):
    raise RuntimeError('Assigned GPU has another compute context; no training started')
PY
"$python" -B -u tools/model_v3/v2_diagnosis_disk.py --output "$output" --state "$state" --node "$(hostname -s)" --job "$SLURM_JOB_ID" &
guard=$!
trap 'kill "$guard" 2>/dev/null || true; wait "$guard" 2>/dev/null || true' EXIT
"$python" -B -u tools/model_v3/v2_train_v31.py --configuration "$configuration"
