#!/bin/bash
#SBATCH --job-name=bq_hess_scope
#SBATCH --partition=cpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --mem=32G
#SBATCH --time=00:30:00
set -euo pipefail
cd /share/home/zixiao/descriptor_analysis
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export PYTHONPATH=/share/home/zixiao/descriptor_analysis/runs/phase1_dataset_rebuild_20261010/docs/deps:/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps${PYTHONPATH:+:$PYTHONPATH}
exec /share/home/zixiao/.conda/envs/chemprop/bin/python runs/phase1_screening_20261011/scripts/b_quantum_hessian_requested_scope.py --input-report runs/phase1_screening_20261011/b_quantum/hessian_analysis/job_4513568/report.json --out runs/phase1_screening_20261011/b_quantum/hessian_analysis/requested_scope_repair --workers 16
