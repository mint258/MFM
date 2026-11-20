#!/bin/bash
#SBATCH --job-name=D-stage0-cost5000
#SBATCH --partition=cpu
#SBATCH --exclude=compute-0-[0-7,18,20-22]
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=5
#SBATCH --output=/share/home/zixiao/descriptor_analysis/MFM_d_descriptors_20261120_pilot_%j.out
set -euo pipefail
export CUDA_VISIBLE_DEVICES="" PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
cd /share/home/zixiao/descriptor_analysis/MFM_d_descriptors_20261120
export PYTHONPATH="$PWD:$PWD/current"
python_bin=/share/home/zixiao/.conda/envs/chemprop/bin/python
findmnt -T /share/home/zixiao/descriptor_analysis
df -B1 / /share/home/zixiao/descriptor_analysis
df -Pi / /share/home/zixiao/descriptor_analysis
quota -w
"$python_bin" -B -m unittest workflows.data_d_descriptors.test_statistics
"$python_bin" -B -m py_compile workflows/data_d_descriptors/pilot.py
"$python_bin" -B -m workflows.data_d_descriptors.pilot --config configs/data_d_descriptors/pilot.json --workers 4
