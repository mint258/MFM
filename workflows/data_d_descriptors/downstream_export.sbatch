#!/bin/bash
#SBATCH --job-name=D-development-descriptor-export
#SBATCH --partition=cpu
#SBATCH --exclude=compute-0-[0-7,18,20-22]
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=3
#SBATCH --mem=0
#SBATCH --time=02:00:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/D_development_export_%j.out
set -euo pipefail
config=${1:?absolute descriptor export config required}
export CUDA_VISIBLE_DEVICES="" PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
cd /share/home/zixiao/descriptor_analysis/MFM_d_descriptors_20261120
task_recipe=/share/home/zixiao/descriptor_analysis/MFM_d_recipe
export PYTHONPATH="$task_recipe/current:$PWD:$PWD/current:/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps"
exec /share/home/zixiao/.conda/envs/chemprop/bin/python -B -m workflows.data_d_descriptors.export --config "$config"
