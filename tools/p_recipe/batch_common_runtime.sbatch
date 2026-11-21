#!/bin/bash
#SBATCH --job-name=p-recipe
#SBATCH --partition=all
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/p_recipe_20261113/%x_%j.log
set -euo pipefail
root=/share/home/zixiao/descriptor_analysis
cd "$root/MFM_p_recipe"
configuration=${1:?configuration}
gpu_uuid=${2:?GPU UUID}
output=${3:?output}
export CUDA_VISIBLE_DEVICES="$gpu_uuid" PYTHONDONTWRITEBYTECODE=1 PYTHONIOENCODING=utf-8
export PYTHONPATH=$PWD/current:$root/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export PYTORCH_ALLOC_CONF=expandable_segments:True
python=/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage43_5090_environment/install_4511929/venv/bin/python
state=$root/runs/p_recipe_20261113/disk_${SLURM_JOB_ID}.json
"$python" -B tools/model_v3/v2_diagnosis_disk.py --once --output "$output" --node "$(hostname -s)" --job "$SLURM_JOB_ID" --state "$state"
exec 9>"$root/docs/phase1/evidence/stage46_shared_gpu_launch/.own_gpu_uuid_locks/${gpu_uuid}.lock"
flock -n 9
"$python" -B - "$gpu_uuid" <<'PY'
import csv,subprocess,sys
r=subprocess.run(['nvidia-smi','--query-compute-apps=gpu_uuid,pid','--format=csv,noheader,nounits'],capture_output=True,text=True,check=True)
if any(row and row[0].strip()==sys.argv[1] for row in csv.reader(r.stdout.splitlines())):
    raise RuntimeError('Assigned GPU already has a foreign context')
PY
"$python" -B -u tools/model_v3/v2_diagnosis_disk.py --output "$output" --state "$state" --node "$(hostname -s)" --job "$SLURM_JOB_ID" &
guard=$!
trap 'kill "$guard" 2>/dev/null || true; wait "$guard" 2>/dev/null || true' EXIT
"$python" -B -u tools/p_recipe/batch_capacity.py --batch 160 --maximum 256 --stress-batches 8
"$python" -B tools/p_recipe/fit_clip.py
"$python" -B -m pytest current/tests/test_p_recipe.py::test_inverse_composed_labels_uses_predicted_neutral_in_fp64 -q -p no:cacheprovider
export CUDA_VISIBLE_DEVICES=""
"$python" -B -u tools/p_recipe/repair_regression.py --source repair1 --destination repair3