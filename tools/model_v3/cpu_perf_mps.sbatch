#!/bin/bash
#SBATCH --job-name=v3-cpu-perf-mps
#SBATCH --partition=all
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=32
#SBATCH --output=/share/home/zixiao/descriptor_analysis/MFM_model_v3_cpu_perf_20261112/results/model_v3_perf_20261112/mps_%j.log
set -euo pipefail
unset CUDA_MPS_PIPE_DIRECTORY CUDA_MPS_LOG_DIRECTORY
if [[ ${MFM_CPU_IDLE_TEST:-0} == 1 ]]; then
    unset MFM_CPU_BACKGROUND_JOB MFM_CPU_BACKGROUND_PIDS MFM_CPU_BACKGROUND_LOSSES MFM_CPU_BASELINE_JOB
fi
base=/share/home/zixiao/descriptor_analysis
cd "$base/MFM_model_v3_cpu_perf_20261112"
export PYTHONPATH="$PWD/current:$base/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export PYTHONDONTWRITEBYTECODE=1 PYTHONIOENCODING=utf-8 PYTHONHASHSEED=0
export PYTORCH_ALLOC_CONF=expandable_segments:True
findmnt -T /tmp
findmnt -T /lfshome/zixiao
df -B1 / /tmp /lfshome/zixiao "$PWD"
df -Pi / /tmp /lfshome/zixiao "$PWD"
python=$base/docs/phase1/evidence/stage43_5090_environment/install_4511929/venv/bin/python
"$python" -B -u tools/model_v3/cpu_perf_mps_suite.py
