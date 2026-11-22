#!/bin/bash
#SBATCH --job-name=D-managed-TRAIN-clipping
#SBATCH --partition=cpu
#SBATCH --exclude=compute-0-[0-8,10,14-18,20-22]
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=0
#SBATCH --time=08:00:00
#SBATCH --signal=B:USR1@900
#SBATCH --no-requeue
#SBATCH --chdir=/
#SBATCH --output=/tmp/d_recipe_managed_%x_%j.log
set -euo pipefail
if [ "${D_EXIT_OUTER_SUPERVISION:-}" != "1" ]; then
    echo "Staged entry: source-independent outer supervision is required." >&2
    exit 64
fi
root=/share/home/zixiao/descriptor_analysis
export PYTHONPATH="$root/MFM_d_recipe:$root/MFM_d_recipe/current:$root/MFM_d_descriptors_20261120:$root/MFM_d_descriptors_20261120/current:$root/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps"
export PYTHONDONTWRITEBYTECODE=1 PYTHONIOENCODING=utf-8
export PATH="/usr/bin:/bin:/usr/sbin:/sbin:$PATH"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export CUDA_VISIBLE_DEVICES=""
configuration=${1:?original reference configuration required}
collection=${2:?original closed collection required}
output=${3:?original clipping report directory required}
joint_local_future_bytes=${4:?joint node-local future including this log required}
exec /usr/bin/python3 -B -m tools.d_recipe.clipping_managed --configuration "$configuration" --collection "$collection" --output "$output" --joint-local-future-bytes "$joint_local_future_bytes" --cleanup-seconds 900

