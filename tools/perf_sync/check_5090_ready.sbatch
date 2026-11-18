#!/bin/bash
#SBATCH --job-name=perf5090-ready
#SBATCH --partition=cpu
#SBATCH --nodelist=compute-0-16
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --time=00:15:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/MFM_perf_sync_20261117/results/perf_sync/5090_ready_%j.log
set -euo pipefail
base=/share/home/zixiao/descriptor_analysis
cd "$base/MFM_perf_sync_20261117"
export CUDA_VISIBLE_DEVICES="" PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export TMPDIR="$base/.perf_sync_scratch_20261117" XDG_CACHE_HOME="$base/.perf_sync_scratch_20261117/cache5090"
export PYTHONPATH="$PWD/current:$PWD/tools/perf_sync:$base/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps"
python="$base/docs/phase1/evidence/stage43_5090_environment/install_4511929/venv/bin/python"
findmnt -T "$TMPDIR"
df -B1 / /dev/shm "$TMPDIR"
df -Pi / /dev/shm "$TMPDIR"
"$python" -B -c 'from regression import capacity;capacity()'
"$python" -B -c 'import ast;from pathlib import Path;ast.parse(Path("tools/perf_sync/gpu_5090.py").read_text());import gpu_5090;assert gpu_5090.configuration()["workers"]==14'
"$python" -B -m pytest tools/perf_sync/test_5090_measurement.py -k 'scan_plan or boundary or streaming_trace or truncated_trace or main_thread' -q -p no:cacheprovider --basetemp="$TMPDIR/5090_cpu_unit_$SLURM_JOB_ID"
export PATH="$base/runs/model_v3_20261025/cpu_git_tools_v1/bin:$PATH"
exec "$python" -B tools/check_repository.py --output results/perf_sync/5090_ready_repository_check.json
