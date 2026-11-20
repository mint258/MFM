#!/bin/bash
#SBATCH --job-name=D-development-native-D3
#SBATCH --partition=cpu
#SBATCH --exclude=compute-0-[0-7,18,20-22]
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=0
#SBATCH --time=1-00:00:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/D_development_D3_%j.out
set -euo pipefail
stage=${1:?produce or merge required}
config=${2:?absolute native D3 configuration required}
export CUDA_VISIBLE_DEVICES="" PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
cd /share/home/zixiao/descriptor_analysis/MFM_d_descriptors_20261120
task_recipe=/share/home/zixiao/descriptor_analysis/MFM_d_recipe
export PYTHONPATH="$task_recipe/current:$PWD:$PWD/current:/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps"
task_python=/share/home/zixiao/.conda/envs/chemprop/bin/python
case "$stage" in
  produce) exec "$task_python" -B -m workflows.data_d_descriptors.development_d3 --config "$config" ;;
  merge) exec "$task_python" -B -m workflows.data_d_descriptors.merge_development_d3 --config "$config" ;;
  *) exit 2 ;;
esac
