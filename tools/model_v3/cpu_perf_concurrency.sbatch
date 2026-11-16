#!/bin/bash
#SBATCH --job-name=v3-cpu-perf-concurrency
#SBATCH --partition=all
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=48
#SBATCH --output=/share/home/zixiao/descriptor_analysis/MFM_model_v3_cpu_perf_20261112/results/model_v3_perf_20261112/concurrency_%j.log
set -euo pipefail
base=/share/home/zixiao/descriptor_analysis
cd "$base/MFM_model_v3_cpu_perf_20261112"
export PYTHONPATH="$PWD/current:$base/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export PYTHONDONTWRITEBYTECODE=1 PYTHONIOENCODING=utf-8 PYTHONHASHSEED=0
export PYTORCH_ALLOC_CONF=expandable_segments:True
python=${MFM_CPU_PYTHON:-$base/docs/phase1/evidence/stage43_5090_environment/install_4511929/venv/bin/python}
findmnt -T /lfshome/zixiao
df -B1 / /lfshome/zixiao "$PWD"
df -Pi / /lfshome/zixiao "$PWD"
"$python" -B -u tools/model_v3/cpu_perf_concurrency.py
