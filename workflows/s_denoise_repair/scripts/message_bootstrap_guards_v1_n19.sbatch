#!/bin/bash
#SBATCH --job-name=srepair_message_bootstrap_guards_v1_n19
#SBATCH --partition=cpu
#SBATCH --nodelist=compute-0-19
#SBATCH --cpus-per-task=16
#SBATCH --mem=32G
#SBATCH --time=00:05:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016/logs/message_bootstrap_guards_v1_n19_%j.log
set -euo pipefail
cd /share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016/source_v4
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1
export PYTORCH_ALLOC_CONF=expandable_segments:True
export CUDA_VISIBLE_DEVICES=''
export PYTHONPATH=/share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016/analysis:/share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016/source_v4/workflows/s_denoise
export PHASE1_NATIVE_TRANSPORT_PATH=/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage48_full_corpus_qa/native_qa_stats_v3.py
export PHASE1_JOINT_REFERENCE_PATH=/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage50_full_corpus_training/actual_api_reference/full_corpus_training.py
S_REPAIR_PY=/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage43_5090_environment/install_4511929/venv/bin/python
srun --input=none --ntasks=1 --cpus-per-task=16 --cpu-bind=cores /share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage43_5090_environment/install_4511929/venv/bin/python -B /share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016/analysis/run_message_bootstrap_guards_v1.py
