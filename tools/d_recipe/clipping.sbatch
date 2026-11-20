#!/bin/bash
#SBATCH --job-name=D-native-TRAIN-clipping
#SBATCH --partition=cpu
#SBATCH --exclude=compute-0-[0-7,18,20-22]
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=0
#SBATCH --time=08:00:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/d_recipe_20261120/%x_%j.log
set -euo pipefail
configuration=${1:?absolute native reference configuration required}
collection=${2:?closed same-TRAIN collection required}
output=${3:?owned clipping report output required}
root=/share/home/zixiao/descriptor_analysis
cd "$root/MFM_d_recipe"
export CUDA_VISIBLE_DEVICES="" PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH="$PWD:$PWD/current:$root/MFM_d_descriptors_20261120:$root/MFM_d_descriptors_20261120/current:$root/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
exec /share/home/zixiao/.conda/envs/chemprop/bin/python -B -m tools.d_recipe.clip_report --configuration "$configuration" --collection "$collection" --output "$output"
