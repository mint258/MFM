#!/bin/bash
#SBATCH --job-name=perf-sync-5090
#SBATCH --partition=gpu
#SBATCH --nodelist=compute-0-22
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=24
#SBATCH --output=/share/home/zixiao/descriptor_analysis/MFM_perf_sync_20261117/results/perf_sync/5090_gpu_%j.log
set -euo pipefail
base=/share/home/zixiao/descriptor_analysis
cd "$base/MFM_perf_sync_20261117"
export CUDA_VISIBLE_DEVICES=GPU-9b6008d0-35dd-4bff-f69a-0927b04b7eef
export PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export PYTHONPATH="$PWD/current:$PWD/tools/model_v3:$PWD/tools/perf_sync:$base/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps"
export PATH="$base/runs/model_v3_20261025/cpu_git_tools_v1/bin:$PATH"
export TMPDIR="$base/.perf_sync_scratch_20261117" XDG_CACHE_HOME="$base/.perf_sync_scratch_20261117/cache5090"
export TORCHINDUCTOR_CACHE_DIR="$TMPDIR/inductor_5090_20261118" TRITON_CACHE_DIR="$TMPDIR/triton_5090_20261118"
unset TRITON_PTXAS_PATH
export PHASE1_NATIVE_TRANSPORT_PATH="$base/docs/phase1/evidence/stage48_full_corpus_qa/native_qa_stats_v3.py"
export PHASE1_JOINT_REFERENCE_PATH="$base/docs/phase1/evidence/stage50_full_corpus_training/actual_api_reference/full_corpus_training.py"
python="$base/docs/phase1/evidence/stage43_5090_environment/install_4511929/venv/bin/python"
exec 9>"$base/docs/phase1/evidence/stage46_shared_gpu_launch/.own_gpu_uuid_locks/$CUDA_VISIBLE_DEVICES.lock"
flock -n 9
test -z "$(nvidia-smi -i "$CUDA_VISIBLE_DEVICES" --query-compute-apps=pid --format=csv,noheader,nounits)"
findmnt -T "$TMPDIR"
df -B1 / /dev/shm "$TMPDIR"
df -Pi / /dev/shm "$TMPDIR"
"$python" -B -c 'from regression import capacity;capacity()'
export PERF5090_LEASE_STARTED="$(date +%s)"
#24 covers the S7 maximum; every non-S7 child is restricted to16actualCPUs.
exec "$python" -B -u tools/perf_sync/gpu_5090.py drive
