#!/bin/bash
#SBATCH --job-name=p-precision
#SBATCH --partition=gpu
#SBATCH --nodelist=compute-0-0
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --time=08:00:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/MFM_precision_20261115/results/precision_20261115/job_%j.log
set -euo pipefail
[[ $(hostname -s) != compute-0-21 ]]
base=/share/home/zixiao/descriptor_analysis
cd "$base/MFM_precision_20261115"
export PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export PYTHONPATH="$PWD/current:$PWD/tools/model_v3:$base/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps"
export PHASE1_NATIVE_TRANSPORT_PATH="$base/docs/phase1/evidence/stage48_full_corpus_qa/native_qa_stats_v3.py"
export PHASE1_JOINT_REFERENCE_PATH="$base/docs/phase1/evidence/stage50_full_corpus_training/actual_api_reference/full_corpus_training.py"
export CUDA_VISIBLE_DEVICES=${PRECISION_GPU_UUID:-GPU-a967b766-fb5e-8db3-b09c-4ddc6c02b332}
exec 9> "$base/docs/phase1/evidence/stage46_shared_gpu_launch/.own_gpu_uuid_locks/$CUDA_VISIBLE_DEVICES.lock"
flock -n 9
python=${PRECISION_PYTHON:-/share/home/zixiao/.venvs/model_v2_cu118_20261105/bin/python}
findmnt -T "$PWD"
df -B1 / "$PWD" /dev/shm
df -Pi / "$PWD" /dev/shm
/usr/bin/python3 -B -c 'import v2_diagnosis_disk as d; d.m.require_capacity(d.m.filesystem_status("/"),0); d.m.require_capacity(d.m.filesystem_status(d.ROOT),18000000000,20000); print(d.m.quota_headroom(d.CONTROL/"share_quota_available_v3.json","/share",18000000000,d.remaining_nfs_other()))'
gpu_state=$(nvidia-smi -i "$CUDA_VISIBLE_DEVICES" --query-gpu=memory.used,memory.total --format=csv,noheader,nounits)
awk -F, '{if ($1/$2>0.30) exit 1}' <<< "$gpu_state"
while read -r pid; do
 command=$(ps -p "$pid" -o args= || true)
 if [[ "$command" == *tools/p_recipe/train.py* || "$command" == *native_run.py* || "$command" == *hybrid* ]]; then
  echo "P study owns GPU $CUDA_VISIBLE_DEVICES PID $pid"; exit 1
 fi
done < <(nvidia-smi -i "$CUDA_VISIBLE_DEVICES" --query-compute-apps=pid --format=csv,noheader,nounits)
root="$PWD/results/precision_20261115"
export TMPDIR="$base/.pr_$SLURM_JOB_ID"
mkdir "$TMPDIR"
/usr/bin/python3 -B tools/model_v3/v2_watch_disk.py --output "$root" --state "$root/disk_$SLURM_JOB_ID.json" --node "$(hostname -s)" --jobs "$SLURM_JOB_ID" --growth-bytes 18000000000 --quota-reference "$base/runs/data_v1_20261025/control/window2_20261105/share_quota_available_v3.json" --quota-filesystem /share --quota-concurrent-bytes 23179869184 &
observer=$!
trap 'kill "$observer" 2>/dev/null || true' EXIT
"$python" -B -m pytest -q -p no:cacheprovider current/tests/test_p_precision_islands.py
if [[ ${PRECISION_ACTION:-numerical} == numerical ]]; then
 "$python" -B -u tools/model_v3/precision_study.py numerical --output "$root/numerical_$SLURM_JOB_ID"
else
 for batch in 32 128; do
  for precision in fp32 tf32_islands bf16_islands; do
   "$python" -B -u tools/model_v3/precision_study.py benchmark --precision "$precision" --batch-size "$batch" --output "$root/speed_${precision}_B${batch}_$SLURM_JOB_ID"
  done
 done
fi
