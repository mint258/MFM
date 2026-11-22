#!/bin/bash
#SBATCH --job-name=D-managed-CPU
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
configuration=${1:?registered configuration required}
command=${2:-cpu_statistics}
exec /usr/bin/python3 -I -S -B "$root/MFM_d_recipe/tools/d_recipe/managed_entry.py" --kind cpu --configuration "$configuration" --resource-command "$command" --cleanup-seconds 900

