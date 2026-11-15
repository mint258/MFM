#!/bin/bash
#SBATCH --job-name=p-step-overhead
#SBATCH --partition=gpu
#SBATCH --nodelist=compute-0-7
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --time=01:55:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/MFM_step_overhead_20261114/results/perf_step_overhead_20261114/job_%j.log
set -euo pipefail
base=/share/home/zixiao/descriptor_analysis
cd "$base/MFM_step_overhead_20261114"
export PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export PYTHONPATH="$PWD/current:$PWD/tools/model_v3:$base/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps"
export PHASE1_NATIVE_TRANSPORT_PATH="$base/docs/phase1/evidence/stage48_full_corpus_qa/native_qa_stats_v3.py"
export PHASE1_JOINT_REFERENCE_PATH="$base/docs/phase1/evidence/stage50_full_corpus_training/actual_api_reference/full_corpus_training.py"
export CUDA_VISIBLE_DEVICES=${STEP_GPU_UUID:-GPU-9db54192-dd3f-3177-e56f-dcd161ff932c}
python=${STEP_PYTHON:-/share/home/zixiao/.venvs/model_v2_cu118_20261105/bin/python}
findmnt -T "$PWD"
df -B1 / "$PWD" /dev/shm
df -Pi / "$PWD" /dev/shm
/usr/bin/python3 -B -c 'import v2_diagnosis_disk as d; d.m.require_capacity(d.m.filesystem_status("/"),0); d.m.require_capacity(d.m.filesystem_status(d.ROOT),4000000000,10000); d.m.quota_headroom(d.CONTROL/"share_quota_available_v3.json","/share",4000000000,d.remaining_nfs_other())'
if [[ "${STEP_MODE:-capacity}" != input ]]; then
 gpu_state=$(nvidia-smi -i "$CUDA_VISIBLE_DEVICES" --query-gpu=memory.used,memory.total --format=csv,noheader,nounits)
 awk -F, '{if ($1/$2>0.30) exit 1}' <<< "$gpu_state"
 while read -r pid; do
  command=$(ps -p "$pid" -o args= || true)
  if [[ "$command" == *tools/p_recipe/train.py* ]]; then echo "P study owns GPU $CUDA_VISIBLE_DEVICES PID $pid"; exit 1; fi
 done < <(nvidia-smi -i "$CUDA_VISIBLE_DEVICES" --query-compute-apps=pid --format=csv,noheader,nounits)
fi
root="$PWD/results/perf_step_overhead_20261114"
export TMPDIR="$base/.st_$SLURM_JOB_ID"
mkdir "$TMPDIR"
/usr/bin/python3 -B tools/model_v3/v2_watch_disk.py --output "$root" --state "$root/disk_$SLURM_JOB_ID.json" --node "$(hostname -s)" --jobs "$SLURM_JOB_ID" --growth-bytes 4000000000 --quota-reference "$base/runs/data_v1_20261025/control/window2_20261105/share_quota_available_v3.json" --quota-filesystem /share --quota-concurrent-bytes 23179869184 &
observer=$!
trap 'kill "$observer" 2>/dev/null || true' EXIT
options='{}'
if [[ -n "${STEP_OPTIONS:-}" ]]; then options="$STEP_OPTIONS"; fi
"$python" -B -u tools/model_v3/step_overhead.py "${STEP_MODE:-capacity}" --output "$root/${STEP_LABEL:-capacity3090}_$SLURM_JOB_ID" --options "$options"
