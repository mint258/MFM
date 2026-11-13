#!/bin/bash
#SBATCH --job-name=v3-cpu-perf-opt1-retry
#SBATCH --partition=all
#SBATCH --nodelist=compute-0-21
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --output=/share/home/zixiao/descriptor_analysis/MFM_model_v3_cpu_perf_20261112/results/model_v3_perf_20261112/opt1_%j.log
set -euo pipefail
base=/share/home/zixiao/descriptor_analysis
cd "$base/MFM_model_v3_cpu_perf_20261112"
export PYTHONPATH="$PWD/current:$base/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export PYTHONDONTWRITEBYTECODE=1 PYTHONIOENCODING=utf-8
export PYTORCH_ALLOC_CONF=expandable_segments:True
export MFM_CPU_GPU_UUIDS=GPU-c35f2434-9137-9723-1af5-dc69b6295243
python=$base/docs/phase1/evidence/stage43_5090_environment/install_4511929/venv/bin/python
findmnt -T /lfshome/zixiao
findmnt -T "$PWD"
df -B1 / /tmp /lfshome/zixiao "$PWD"
df -Pi / /tmp /lfshome/zixiao "$PWD"
"$python" -B -c 'import sys;sys.path.insert(0,"tools/model_v3");from cpu_bottleneck_step1 import capacity;print(capacity())'
"$python" -B -m pytest current/tests/test_cpu_perf_recompute.py current/tests/test_cpu_perf_admission.py -q
export MFM_CPU_BASELINE_ONLY=1
export MFM_CPU_HEAD_NO_RECOMPUTE=1 MFM_CPU_RUN_PREFIX=opt1_no_recompute
"$python" -B -u tools/model_v3/cpu_bottleneck_step1.py
