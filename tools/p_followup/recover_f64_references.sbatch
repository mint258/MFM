#!/bin/bash
#SBATCH --job-name=p-followup-B1-ref
#SBATCH --nodelist=compute-0-20
#SBATCH --partition=all
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=5
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/p_followup_20261116/B1_ref_%j.log
set -euo pipefail
cd /share/home/zixiao/descriptor_analysis/MFM_p_followup_20261117
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 CUDA_VISIBLE_DEVICES=
export PYTHONPATH=$PWD/current:/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/repository:/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps
exec /share/home/zixiao/.venvs/model_v2_cu118_20261105/bin/python -B -u tools/p_followup/recover_f64_references.py --workers 4
