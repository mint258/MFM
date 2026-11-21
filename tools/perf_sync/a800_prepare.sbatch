#!/bin/bash
#SBATCH --job-name=perf-A800-package
#SBATCH --partition=cpu
#SBATCH --nodelist=compute-0-18
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --time=00:10:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/MFM_perf_sync_20261117/results/perf_sync/A800_prepare_%j.log
set -euo pipefail
base=/share/home/zixiao/descriptor_analysis
cd "$base/MFM_perf_sync_20261117"
export CUDA_VISIBLE_DEVICES="" PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export TMPDIR="$base/.perf_sync_scratch_20261117" PYTHONPATH="$PWD/current:$PWD/tools/perf_sync"
python="$base/docs/phase1/evidence/stage43_5090_environment/install_4511929/venv/bin/python"
findmnt -T "$TMPDIR"
df -B1 / "$TMPDIR"
df -Pi / "$TMPDIR"
"$python" -B -c 'from regression import capacity;capacity()'
"$python" -B -c 'import ast;from pathlib import Path;[ast.parse(p.read_text()) for p in Path("tools/perf_sync").glob("a800*.py")];import a800_final;assert a800_final.VARIANTS["baseline"]=={};assert a800_final.VARIANTS["S8"]==dict(sync_free=True,fused_optimizer=True,async_transfer=True);print("A800 harness syntax/import/options PASS")'
"$python" -B -m pytest tools/perf_sync/test_5090_measurement.py -k 'abba or quality' -q -p no:cacheprovider
export PATH="$base/runs/model_v3_20261025/cpu_git_tools_v1/bin:$PATH"
"$python" -B tools/check_repository.py --output results/perf_sync/A800_prepare_repository_check.json
tar --exclude=__pycache__ --exclude='*.pyc' -czf "$TMPDIR/A800_source_20261120.tar.gz" current configs/perf_sync/M2_5090.json tools/perf_sync/a800_final.py tools/perf_sync/a800_portable.py tools/perf_sync/a800_final.sbatch
ls -lh "$TMPDIR/A800_source_20261120.tar.gz"
