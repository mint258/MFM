#!/bin/bash
#SBATCH --job-name=srepair_analysis_rules_v1
#SBATCH --partition=cpu
#SBATCH --nodelist=compute-0-8
#SBATCH --cpus-per-task=16
#SBATCH --mem=32G
#SBATCH --time=00:30:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016/logs/analysis_rules_v1_%j.log
set -euo pipefail
cd /share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016
export OMP_NUM_THREADS=16 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=16 PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH=/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps
S_REPAIR_PY=/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage43_5090_environment/install_4511929/venv/bin/python
srun --input=none --ntasks=1 --cpus-per-task=16 --cpu-bind=cores "$S_REPAIR_PY" -B -m pytest analysis/test_s_convergence_rules_v3.py -q --junitxml=reports/convergence_rule_tests_v1.xml
srun --input=none --ntasks=1 --cpus-per-task=16 --cpu-bind=cores "$S_REPAIR_PY" -B analysis/render_D1_D2.py
