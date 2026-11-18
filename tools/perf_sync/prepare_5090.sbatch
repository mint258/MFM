#!/bin/bash
#SBATCH --job-name=perf5090-preparation
#SBATCH --partition=cpu
#SBATCH --nodelist=compute-0-16
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --time=00:15:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/MFM_perf_sync_20261117/results/perf_sync/5090_preparation_%j.log
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
exec "$python" -B -m pytest tools/perf_sync/test_5090_measurement.py -q -p no:cacheprovider --basetemp="$TMPDIR/5090_cpu_unit_$SLURM_JOB_ID"
