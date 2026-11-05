#!/bin/bash
#SBATCH --job-name=dv1_routine_roles_v1
#SBATCH --partition=all
#SBATCH --nodelist=compute-0-20
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --mem=32G
#SBATCH --time=01:00:00
#SBATCH --chdir=/share/home/zixiao/descriptor_analysis
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/routine_roles_v1_%j.out
#SBATCH --error=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/routine_roles_v1_%j.err
set -euo pipefail
ROOT=/share/home/zixiao/descriptor_analysis
REPOSITORY=$ROOT/runs/data_v1_20261025/repository
OUTPUT=$ROOT/runs/data_v1_20261025/roles/routine_v1_job$SLURM_JOB_ID
export PYTHONDONTWRITEBYTECODE=1
export CUDA_VISIBLE_DEVICES=''
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export PYTHONPATH="$ROOT/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps"
PYTHON=/share/home/zixiao/.conda/envs/chemprop/bin/python
srun --input=none --ntasks=1 --cpus-per-task=16 --cpu-bind=cores "$PYTHON" -B \
    "$REPOSITORY/workflows/data_v1_final/export/freeze_routine_roles.py" \
    --config "$REPOSITORY/configs/data_v1/export/routine_roles_v1.json" \
    --output "$OUTPUT" </dev/null
