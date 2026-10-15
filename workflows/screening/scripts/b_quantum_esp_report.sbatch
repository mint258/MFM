#!/bin/bash
#SBATCH --job-name=bq_esp_report
#SBATCH --partition=cpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --mem=32G
#SBATCH --time=00:30:00
set -euo pipefail
cd /share/home/zixiao/descriptor_analysis
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
exec /share/home/zixiao/.conda/envs/chemprop/bin/python runs/phase1_screening_20261011/scripts/b_quantum_report.py --mode esp --run-root runs/phase1_screening_20261011/b_quantum/esp/job_4513527 --out runs/phase1_screening_20261011/b_quantum/esp_analysis/job_${SLURM_JOB_ID} --workers 16
