#!/bin/bash
#SBATCH --job-name=perf-sync-input-equivalence
#SBATCH --partition=cpu
#SBATCH --nodelist=compute-0-16
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --time=02:00:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/MFM_perf_sync_20261117/results/perf_sync/input_%j.log
set -euo pipefail
base=/share/home/zixiao/descriptor_analysis
cd "$base/MFM_perf_sync_20261117"
export CUDA_VISIBLE_DEVICES="" PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export PYTHONPATH="$PWD/current:$PWD/tools/model_v3:$base/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps"
export PATH="$base/runs/model_v3_20261025/cpu_git_tools_v1/bin:$PATH"
export TMPDIR="$base/.perf_sync_scratch_20261117"
export PHASE1_NATIVE_TRANSPORT_PATH="$base/docs/phase1/evidence/stage48_full_corpus_qa/native_qa_stats_v3.py"
export PHASE1_JOINT_REFERENCE_PATH="$base/docs/phase1/evidence/stage50_full_corpus_training/actual_api_reference/full_corpus_training.py"
findmnt -T /dev/shm
df -B1 / /dev/shm "$PWD"
df -Pi / /dev/shm "$PWD"
exec /share/home/zixiao/.venvs/model_v2_cu118_20261105/bin/python -B -u tools/perf_sync/input_equivalence.py
