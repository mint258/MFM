#!/bin/bash
#SBATCH --job-name=bq_hess100
#SBATCH --partition=cpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --mem=64G
#SBATCH --time=08:30:00
set -euo pipefail
cd /share/home/zixiao/descriptor_analysis
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
exec /share/home/zixiao/.conda/envs/chemprop/bin/python runs/phase1_screening_20261011/scripts/b_quantum_runner.py --mode hessian --sample runs/phase1_screening_20261011/b_quantum/plan/hessian_100.parquet --manifest runs/phase1_screening_20261011/b_quantum/plan/manifest.json --output runs/phase1_screening_20261011/b_quantum/hessian/job_${SLURM_JOB_ID} --workers 16 --wall-seconds 28800
