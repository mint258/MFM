#!/bin/bash
#SBATCH --job-name=perf-sync-profile-recovery
#SBATCH --partition=gpu
#SBATCH --nodelist=compute-0-5
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --time=02:00:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/MFM_perf_sync_20261117/results/perf_sync/gpu_%j.log
set -euo pipefail
base=/share/home/zixiao/descriptor_analysis
cd "$base/MFM_perf_sync_20261117"
export CUDA_VISIBLE_DEVICES=GPU-dac07d74-6269-c7db-8832-340dd3c0b377
export PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export PYTHONPATH="$PWD/current:$PWD/tools/model_v3:$base/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps"
export PATH="$base/runs/model_v3_20261025/cpu_git_tools_v1/bin:$PATH"
export TMPDIR="$base/.perf_sync_scratch_20261117"
export XDG_CACHE_HOME="$TMPDIR/cache" TORCHINDUCTOR_CACHE_DIR="$TMPDIR/inductor" TRITON_CACHE_DIR="$TMPDIR/triton"
export PHASE1_NATIVE_TRANSPORT_PATH="$base/docs/phase1/evidence/stage48_full_corpus_qa/native_qa_stats_v3.py"
export PHASE1_JOINT_REFERENCE_PATH="$base/docs/phase1/evidence/stage50_full_corpus_training/actual_api_reference/full_corpus_training.py"
python=/share/home/zixiao/.venvs/model_v2_cu118_20261105/bin/python
exec 9>"$base/docs/phase1/evidence/stage46_shared_gpu_launch/.own_gpu_uuid_locks/$CUDA_VISIBLE_DEVICES.lock"
flock -n 9
test -z "$(nvidia-smi -i "$CUDA_VISIBLE_DEVICES" --query-compute-apps=pid --format=csv,noheader,nounits)"
findmnt -T "$PWD"
df -B1 / /dev/shm "$PWD"
df -Pi / /dev/shm "$PWD"
"$python" -B -c 'import sys;sys.path.insert(0,"tools/perf_sync");from regression import capacity;capacity()'
"$python" -B -m pytest tools/perf_sync/test_disk_guard.py -k closed_trace -q -p no:cacheprovider --basetemp="$TMPDIR/archive_unit_$SLURM_JOB_ID"
"$python" -B -u tools/perf_sync/gpu_study.py archive_closed_profiles
"$python" -B -u tools/perf_sync/gpu_study.py resume_finish_2
test -f results/perf_sync/gpu_20261118/S8.json
test -f results/perf_sync/gpu_20261118/S8_profile_summary.json
test -f results/perf_sync/gpu_20261118/profile_S8_complete.json
test "$(grep -c '"status": "COMPLETE"' results/perf_sync/gpu_20261118/S7.json)" = 12
# All GPU outputs closed; exit now, never hold the card duringCPU regression.
