#!/bin/bash
#SBATCH --job-name=v3-cpu-perf-merge-check
#SBATCH --partition=all
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --output=/share/home/zixiao/descriptor_analysis/MFM_model_v3_cpu_perf_20261112/results/model_v3_perf_20261112/merge_%j.log
set -euo pipefail
base=/share/home/zixiao/descriptor_analysis
cd "$base/MFM_model_v3_cpu_perf_20261112"
export CUDA_VISIBLE_DEVICES="" PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export PATH="$base/runs/model_v3_20261025/cpu_git_tools_v1/bin:$PATH"
export PYTHONPATH="$PWD/current:$base/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps"
export PHASE1_NATIVE_TRANSPORT_PATH="$base/docs/phase1/evidence/stage48_full_corpus_qa/native_qa_stats_v3.py"
export PHASE1_JOINT_REFERENCE_PATH="$base/docs/phase1/evidence/stage50_full_corpus_training/actual_api_reference/full_corpus_training.py"
findmnt -T /tmp
df -B1 / /tmp "$base/runs"
df -Pi / /tmp "$base/runs"
python=$base/docs/phase1/evidence/stage43_5090_environment/install_4511929/venv/bin/python
"$python" -B -u tools/model_v3/cpu_perf_merge_check.py
