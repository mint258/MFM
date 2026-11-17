#!/bin/bash
#SBATCH --job-name=perf-sync-final-check
#SBATCH --partition=cpu
#SBATCH --nodelist=compute-0-16
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --time=00:10:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/MFM_perf_sync_20261117/results/perf_sync/final_check_%j.log
set -euo pipefail
base=/share/home/zixiao/descriptor_analysis
cd "$base/MFM_perf_sync_20261117"
export CUDA_VISIBLE_DEVICES="" PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export PATH="$base/runs/model_v3_20261025/cpu_git_tools_v1/bin:$PATH"
python=/share/home/zixiao/.venvs/model_v2_cu118_20261105/bin/python
"$python" -B -c 'import sys;sys.path.insert(0,"tools/perf_sync");from regression import capacity;capacity()'
exec "$python" -B tools/check_repository.py --output results/perf_sync/final_repository_check_20261118.json
