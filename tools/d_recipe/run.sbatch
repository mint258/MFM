#!/bin/bash
#SBATCH --job-name=D-registered-arm
#SBATCH --partition=gpu
#SBATCH --exclude=compute-0-[8-19,21]
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=5
#SBATCH --mem=0
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/d_recipe_20261120/%x_%j.log
set -euo pipefail
configuration=${1:?absolute registered configuration required}
gpu_uuid=${2:?actual GPU UUID required}
command=${3:-train}
case "$command" in train|diagnostic_forward|layer_readouts|development_panel) ;; *) exit 2 ;; esac
root=/share/home/zixiao/descriptor_analysis
cd "$root/MFM_d_recipe"
export CUDA_VISIBLE_DEVICES="$gpu_uuid" PYTHONDONTWRITEBYTECODE=1 PYTHONIOENCODING=utf-8
export PYTHONPATH="$PWD:$PWD/current:$root/MFM_d_descriptors_20261120:$root/MFM_d_descriptors_20261120/current:$root/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export PYTORCH_ALLOC_CONF=expandable_segments:True NVIDIA_TF32_OVERRIDE=0 TORCH_ALLOW_TF32_CUBLAS_OVERRIDE=0
python="$root/docs/phase1/evidence/stage43_5090_environment/install_4511929/venv/bin/python"
exec 9>"$root/docs/phase1/evidence/stage46_shared_gpu_launch/.own_gpu_uuid_locks/${gpu_uuid}.lock"
flock -n 9
"$python" -B - "$configuration" "$gpu_uuid" <<'PY'
import csv,json,os,platform,subprocess,sys
c=json.load(open(sys.argv[1])); gpu=sys.argv[2]; node=platform.node().split('.')[0]
if int(os.environ['SLURM_CPUS_PER_TASK']) < c['workers']+2:
    raise RuntimeError('Allocate the readers, trainer and storage monitor CPUs')
rows=csv.reader(subprocess.check_output(['nvidia-smi','--query-gpu=uuid,memory.used,memory.total','--format=csv,noheader,nounits'],text=True).splitlines())
row=next(row for row in rows if row[0].strip()==gpu);used,total=map(float,row[1:])
contexts=csv.reader(subprocess.check_output(['nvidia-smi','--query-compute-apps=gpu_uuid,pid','--format=csv,noheader,nounits'],text=True).splitlines())
if node in ('compute-0-20','compute-0-22'):
    if used/total>.30:raise RuntimeError('Current GPU occupancy exceeds the user30% rule')
elif any(row and row[0].strip()==gpu for row in contexts):
    raise RuntimeError('Assigned small-task GPU already has a compute context')
if total-used<c['minimum_free_gpu_mib']:raise RuntimeError('Actual free GPU memory is below this arm allowance')
print(json.dumps(dict(node=node,job_id=os.environ['SLURM_JOB_ID'],gpu_uuid=gpu,used_mib=used,total_mib=total)),flush=True)
PY
exec "$python" -B -m tools.d_recipe.resources "$command" --configuration "$configuration"
