#!/bin/bash
#SBATCH --job-name=perf-sync-final-check-retry
#SBATCH --partition=cpu
#SBATCH --nodelist=compute-0-16
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --time=00:10:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/MFM_perf_sync_20261117/results/perf_sync/final_check_retry_%j.log
set -euo pipefail
base=/share/home/zixiao/descriptor_analysis
cd "$base/MFM_perf_sync_20261117"
export CUDA_VISIBLE_DEVICES="" PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export PATH="$base/runs/model_v3_20261025/cpu_git_tools_v1/bin:$PATH"
python=/share/home/zixiao/.venvs/model_v2_cu118_20261105/bin/python
"$python" -B - <<'PY'
import os, sys
from pathlib import Path
sys.path.insert(0,'tools/perf_sync')
from regression import capacity, allocated_bytes, SCRATCH, REPO, LIMIT
capacity()
source=REPO/'results/perf_sync/final_regression_20261118'
destination=SCRATCH/'final_regression_20261118'
if source.is_symlink() or source.resolve().parent!=(REPO/'results/perf_sync').resolve() or source.stat().st_uid!=os.getuid() or destination.exists() or destination.is_symlink():
    raise OSError('Owned raw-test archive path/ownership differs')
if source.stat().st_dev!=SCRATCH.stat().st_dev:
    raise OSError('Archive must be a same-filesystem rename, not a copy')
if allocated_bytes((SCRATCH,REPO/'results/perf_sync/scratch',source))>LIMIT:
    raise OSError('Combined raw-test archive exceeds20GiB')
if os.popen('git ls-files -- results/perf_sync/final_regression_20261118').read().strip():
    raise OSError('Raw test artifacts unexpectedly tracked; preserve without moving')
source.rename(destination)
report=REPO/'results/perf_sync/final_repository_check_20261118.json'
attempt=REPO/'results/perf_sync/final_repository_check_20261118_attempt1.json'
if report.is_symlink() or report.stat().st_uid!=os.getuid() or attempt.exists() or attempt.is_symlink():
    raise OSError('Original source-check result archive differs')
report.rename(attempt)
capacity()
print('Raw XML/logs retained at',destination,flush=True)
PY
exec "$python" -B tools/check_repository.py --output results/perf_sync/final_repository_check_20261118.json
