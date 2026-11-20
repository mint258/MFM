#!/bin/bash
#SBATCH --job-name=D-stage0-reception64
#SBATCH --partition=cpu
#SBATCH --exclude=compute-0-[0-7,18,20-22]
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=0
#SBATCH --time=02:00:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/D_reception_%j.out
set -euo pipefail
export CUDA_VISIBLE_DEVICES="" PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
cd /share/home/zixiao/descriptor_analysis/MFM_d_recipe
export PYTHONPATH="$PWD:$PWD/current:/share/home/zixiao/descriptor_analysis/MFM_d_descriptors_20261120:/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps"
task_python=/share/home/zixiao/.conda/envs/chemprop/bin/python
"$task_python" -B -c 'from workflows.data_d_descriptors.storage import guard; guard("/share/home/zixiao/descriptor_analysis/runs/d_recipe_20261120", peak_bytes=36706053853)'
"$task_python" -B -m tools.d_recipe.acceptance --configuration configs/d_recipe/reception_L1.json
exec "$task_python" -B -m tools.d_recipe.acceptance --configuration configs/d_recipe/reception_L2.json
