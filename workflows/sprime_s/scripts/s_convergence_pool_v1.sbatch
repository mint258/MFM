#!/bin/bash
#SBATCH --job-name=sconv_full_pool_v1
#SBATCH --partition=all
#SBATCH --nodelist=compute-0-21
#SBATCH --cpus-per-task=33
#SBATCH --mem=64G
#SBATCH --time=2-00:00:00
#SBATCH --signal=B:USR1@900
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/sprime_s_convergence_20261013/logs/s_convergence_pool_v1_%j.log
set -euo pipefail
cd /share/home/zixiao/descriptor_analysis
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1
export PYTORCH_ALLOC_CONF=expandable_segments:True
export PYTHONPATH=/share/home/zixiao/PhyChem_MFM_stage59_three_epoch_runtime:/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps
srun --ntasks=1 --cpus-per-task=33 --cpu-bind=cores /share/home/zixiao/.conda/envs/chemprop/bin/python -B runs/sprime_s_convergence_20261013/scripts/s_convergence_pool_v1.py --binding /share/home/zixiao/descriptor_analysis/runs/sprime_s_convergence_20261013/formal_s/pool_source_binding_v1.json
