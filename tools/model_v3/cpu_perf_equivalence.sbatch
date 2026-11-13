#!/bin/bash
#SBATCH --job-name=v3-cpu-perf-equality200
#SBATCH --partition=all
#SBATCH --nodelist=compute-0-21
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --output=/share/home/zixiao/descriptor_analysis/MFM_model_v3_cpu_perf_20261112/results/model_v3_perf_20261112/equivalence_%j.log
set -euo pipefail
base=/share/home/zixiao/descriptor_analysis
cd "$base/MFM_model_v3_cpu_perf_20261112"
export PYTHONPATH="$PWD/current:$base/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export PYTHONDONTWRITEBYTECODE=1 PYTHONIOENCODING=utf-8 PYTHONHASHSEED=0
export PYTORCH_ALLOC_CONF=expandable_segments:True
export MFM_CPU_GPU_UUIDS=${MFM_CPU_GPU_UUIDS:-GPU-c35f2434-9137-9723-1af5-dc69b6295243}
python=${MFM_CPU_PYTHON:-$base/docs/phase1/evidence/stage43_5090_environment/install_4511929/venv/bin/python}
findmnt -T /lfshome/zixiao
df -B1 / /lfshome/zixiao "$PWD"
df -Pi / /lfshome/zixiao "$PWD"
"$python" -B -m pytest current/tests/test_cpu_perf_repository.py -q
"$python" -B -u tools/model_v3/cpu_perf_equivalence.py
