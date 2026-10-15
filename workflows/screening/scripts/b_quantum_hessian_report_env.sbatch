#!/bin/bash
#SBATCH --job-name=bq_hess_report
#SBATCH --partition=cpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --mem=32G
#SBATCH --time=00:30:00
set -euo pipefail
cd /share/home/zixiao/descriptor_analysis
export PYTHONPATH=/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps:${PYTHONPATH:-}
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
exec /share/home/zixiao/.conda/envs/chemprop/bin/python runs/phase1_screening_20261011/scripts/b_quantum_report.py --mode hessian --run-root runs/phase1_screening_20261011/b_quantum/hessian/job_4513528 --out runs/phase1_screening_20261011/b_quantum/hessian_analysis/job_${SLURM_JOB_ID} --workers 16
