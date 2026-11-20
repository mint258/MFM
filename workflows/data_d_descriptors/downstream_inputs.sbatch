#!/bin/bash
#SBATCH --job-name=D-target-free-downstream-inputs
#SBATCH --partition=cpu
#SBATCH --exclude=compute-0-[0-7,18,20-22]
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=8G
#SBATCH --time=02:00:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/MFM_d_downstream_inputs_%j.out
set -euo pipefail
stage=${1:?development or benchmark required}
config=${2:?absolute target-free input config required}
export CUDA_VISIBLE_DEVICES="" PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
cd /share/home/zixiao/descriptor_analysis/MFM_d_descriptors_20261120
recipe_root=/share/home/zixiao/descriptor_analysis/MFM_d_recipe
export PYTHONPATH="$recipe_root/current:$PWD:$PWD/current"
python_bin=/share/home/zixiao/.conda/envs/chemprop/bin/python
case "$stage" in
  development|benchmark) exec "$python_bin" -B -m "workflows.data_d_descriptors.prepare_$stage" --config "$config" ;;
  *) exit 2 ;;
esac
