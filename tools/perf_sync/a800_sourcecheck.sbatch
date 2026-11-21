#!/bin/bash
#SBATCH --job-name=perf-A800-sourcecheck
#SBATCH --partition=cpuXeon6458
#SBATCH --account=a_xk
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --time=00:10:00
#SBATCH --output=/share/home/202264640132/perf_A800_sourcecheck_%j.log
set -euo pipefail
task_root=/share/home/202264640132/perf_A800_20261120
export PATH="$task_root/bin:$PATH"
task_python=/share/home/202264640132/precision_20261115/env/bin/python
cd "$task_root/source"
export CUDA_VISIBLE_DEVICES="" PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1
export TMPDIR="$task_root/tmp" PYTHONPATH="$PWD/tools/perf_sync"
"$task_python" -B -c 'from a800_final import capacity;print(capacity())'
validation="$task_root/validation_$SLURM_JOB_ID"
mkdir -p "$validation/docs"
cp -a "$task_root/validation_inputs/." "$validation/"
cp docs/SOURCE_MANIFEST.json "$validation/docs/SOURCE_MANIFEST.json"
git -C "$validation" init -q
git -C "$validation" add .
exec "$task_python" -B "$task_root/validation_inputs/tools/check_repository.py" --root "$validation" --output "$task_root/sourcecheck_$SLURM_JOB_ID.json"
