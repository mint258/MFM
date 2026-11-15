#!/bin/bash
#SBATCH --job-name=precision-env
#SBATCH --partition=cpuXeon6458
#SBATCH --account=a_xk
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --time=02:00:00
#SBATCH --output=/share/home/202264640132/precision_prepare_%j.log
set -euo pipefail
school_home=/share/home/202264640132
export PYTHONDONTWRITEBYTECODE=1
findmnt -T "$school_home"
df -B1 / "$school_home"
df -Pi / "$school_home"
exec "$school_home/.conda/envs/torchgpu/bin/python" -B "$school_home/precision_school_guard.py" -- bash "$school_home/precision_school_prepare.sh"
