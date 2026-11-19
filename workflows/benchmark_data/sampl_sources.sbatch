#!/bin/bash
#SBATCH --job-name=B0-SAMPL-source-links
#SBATCH --partition=cpu
#SBATCH --nodelist=compute-0-17
#SBATCH --cpus-per-task=1
#SBATCH --ntasks=1
#SBATCH --nodes=1
#SBATCH --time=00:30:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/B0_SAMPL_sources_%j.log
set -euo pipefail
repo=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/worktrees/benchmark_data_20261119
data=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B0_20261119
export PYTHONPATH="$repo:/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 BLIS_NUM_THREADS=1 CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1
cd "$repo"
export TMPDIR=/tmp
/share/home/zixiao/.conda/envs/chemprop/bin/python -B - <<'PY'
import os
s=os.statvfs('/tmp')
assert s.f_bavail*s.f_frsize>=max(10*1024**3,int(s.f_blocks*s.f_frsize*.1))+1048576
assert s.f_favail>=1024
print('ACTUAL_TEST_TMP_ROOT_BYTES_INODES_ADMITTED')
PY
/share/home/zixiao/.conda/envs/chemprop/bin/python -B -m unittest workflows.benchmark_data.test_sampl_sources -v
/share/home/zixiao/.conda/envs/chemprop/bin/python -B - <<'PY'
import ast
from pathlib import Path
for name in ('sampl_sources.py','test_sampl_sources.py'):
    ast.parse((Path('workflows/benchmark_data')/name).read_text(),filename=name)
    print('AST_OK',name)
PY
exec /share/home/zixiao/.conda/envs/chemprop/bin/python -B -u -m workflows.benchmark_data.sampl_sources \
 --root "$data" --domain-manifest "$data/domain/pKahub/job_4536428/manifest.json" --attempt "job_${SLURM_JOB_ID}" \
 --quota-snapshot /share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/benchmark_B0_quota_20261119.json