#!/bin/bash
#SBATCH --job-name=p-followup-regression
#SBATCH --nodelist=compute-0-20
#SBATCH --partition=all
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/p_followup_20261116/regression_%j.log
set -euo pipefail
cd /share/home/zixiao/descriptor_analysis/MFM_p_followup_20261117
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 CUDA_VISIBLE_DEVICES=
# compute-0-20 lacks /usr/bin/git; use the existing login-node Git copied to own NFS tools.
export PATH=/share/home/zixiao/descriptor_analysis/runs/p_followup_20261116/test_tools/git/bin:$PATH
export GIT_EXEC_PATH=/share/home/zixiao/descriptor_analysis/runs/p_followup_20261116/test_tools/git/git-core
export GIT_TEMPLATE_DIR=/share/home/zixiao/descriptor_analysis/runs/p_followup_20261116/test_tools/git/share/templates
export PHASE1_NATIVE_TRANSPORT_PATH=/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage48_full_corpus_qa/native_qa_stats_v3.py
export PHASE1_JOINT_REFERENCE_PATH=/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage50_full_corpus_training/actual_api_reference/full_corpus_training.py
export PYTHONPATH=$PWD/current:/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/repository:/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps
exec /share/home/zixiao/.venvs/model_v2_cu118_20261105/bin/python -B -u tools/p_followup/full_regression.py --repair-from /share/home/zixiao/descriptor_analysis/MFM_p_followup_20261117/results/p_followup/REGRESSION_4535192.json
