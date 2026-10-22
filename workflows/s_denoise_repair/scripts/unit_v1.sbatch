#!/bin/bash
#SBATCH --job-name=srepair_unit_v1
#SBATCH --partition=cpu
#SBATCH --nodelist=compute-0-8
#SBATCH --cpus-per-task=16
#SBATCH --mem=64G
#SBATCH --time=01:30:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016/logs/unit_v1_%j.log
set -euo pipefail
cd /share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016/source
export OMP_NUM_THREADS=16 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=16 PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH=/share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016/source/current:/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps
export PHASE1_NATIVE_TRANSPORT_PATH=/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage48_full_corpus_qa/native_qa_stats_v3.py
S_REPAIR_PY=/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage43_5090_environment/install_4511929/venv/bin/python
srun --input=none --ntasks=1 --cpus-per-task=16 --cpu-bind=cores "$S_REPAIR_PY" -B -m pytest current/tests/test_equivariant_denoising.py -q --junitxml=/share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016/reports/unit_v1.xml
