#!/bin/bash
#SBATCH --job-name=srepair_formal_config_qa_v1
#SBATCH --partition=cpu
#SBATCH --nodelist=compute-0-8
#SBATCH --cpus-per-task=16
#SBATCH --mem=32G
#SBATCH --time=00:10:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016/logs/formal_config_qa_v1_%j.log
set -euo pipefail
cd /share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016/formal_workflows_v3
export OMP_NUM_THREADS=16 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=16 PYTHONDONTWRITEBYTECODE=1
srun --input=none --ntasks=1 --cpus-per-task=16 --cpu-bind=cores /share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage43_5090_environment/install_4511929/venv/bin/python -B -m pytest test_formal_config_v3.py -q --junitxml=/share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016/reports/formal_config_tests_v1.xml
