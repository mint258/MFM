#!/bin/bash
#SBATCH --job-name=p-followup-final-validation
#SBATCH --partition=cpu
#SBATCH --exclude=compute-0-[0-7,20-22]
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/p_followup_20261116/final_validation_%j.log
set -euo pipefail
cd /share/home/zixiao/descriptor_analysis/MFM_p_followup_20261117
export PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 CUDA_VISIBLE_DEVICES=""
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export PATH=/share/home/zixiao/descriptor_analysis/runs/p_followup_20261116/test_tools/git/bin:$PATH
export GIT_EXEC_PATH=/share/home/zixiao/descriptor_analysis/runs/p_followup_20261116/test_tools/git/git-core
export GIT_TEMPLATE_DIR=/share/home/zixiao/descriptor_analysis/runs/p_followup_20261116/test_tools/git/share/templates
export PHASE1_NATIVE_TRANSPORT_PATH=/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage48_full_corpus_qa/native_qa_stats_v3.py
export PHASE1_JOINT_REFERENCE_PATH=/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage50_full_corpus_training/actual_api_reference/full_corpus_training.py
export PYTHONPATH="$PWD/current:/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/repository:/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps"
# Run once after the updated scientific scope closes; intentionally no --repair-from.
set +e
/share/home/zixiao/.venvs/model_v2_cu118_20261105/bin/python -B -u tools/p_followup/full_regression.py
regression_exit=$?
/share/home/zixiao/.venvs/model_v2_cu118_20261105/bin/python -B -u tools/check_repository.py --output results/p_followup/REPOSITORY_CHECK.json
repository_exit=$?
set -e
printf 'FOLLOWUP_FINAL_VALIDATION regression_exit=%s repository_exit=%s\n' "$regression_exit" "$repository_exit"
if (( regression_exit != 0 || repository_exit != 0 )); then exit 1; fi
