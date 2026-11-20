#!/bin/bash
#SBATCH --job-name=p-heads-regression
#SBATCH --partition=cpu
#SBATCH --nodes=1
#SBATCH --exclude=compute-0-2,compute-0-14,compute-0-18
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --time=04:00:00
#SBATCH --nice=10000
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/p_heads_20261117/regression_%j.log
set -euo pipefail
cd /share/home/zixiao/descriptor_analysis/MFM_p_heads_20261117
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 CUDA_VISIBLE_DEVICES=
# Reuse the established test Git and native reference inputs, without copying them.
export PATH=/share/home/zixiao/descriptor_analysis/runs/p_followup_20261116/test_tools/git/bin:$PATH
export GIT_EXEC_PATH=/share/home/zixiao/descriptor_analysis/runs/p_followup_20261116/test_tools/git/git-core
export GIT_TEMPLATE_DIR=/share/home/zixiao/descriptor_analysis/runs/p_followup_20261116/test_tools/git/share/templates
export PHASE1_NATIVE_TRANSPORT_PATH=/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage48_full_corpus_qa/native_qa_stats_v3.py
export PHASE1_JOINT_REFERENCE_PATH=/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage50_full_corpus_training/actual_api_reference/full_corpus_training.py
export PYTHONPATH=$PWD/tools/p_heads:$PWD/current:/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/repository:/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps
# Submit only after all registered scientific work is complete.
exec srun --ntasks=1 --cpus-per-task="$SLURM_CPUS_PER_TASK" --cpu-bind=verbose,threads /share/home/zixiao/.venvs/model_v2_cu118_20261105/bin/python -B -u tools/p_heads/full_regression.py
