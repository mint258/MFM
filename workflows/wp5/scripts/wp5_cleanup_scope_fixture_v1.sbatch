#!/bin/bash
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --mem=4G
#SBATCH --time=00:30:00
set -euo pipefail
cd /share/home/zixiao/descriptor_analysis
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export PYTHONPATH=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/scripts:/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps
exec /share/home/zixiao/.conda/envs/chemprop/bin/python -B runs/phase1_wp5_20261011/scripts/wp5_cleanup_scope_fixture_v1.py --workers 16 --out "/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/gates/cleanup_scope_fixture/job_${SLURM_JOB_ID}"
