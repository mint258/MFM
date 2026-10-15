#!/bin/bash
#SBATCH --job-name=sconv_resume_proof_v8
#SBATCH --partition=all
#SBATCH --nodelist=compute-0-21
#SBATCH --cpus-per-task=16
#SBATCH --mem=64G
#SBATCH --time=02:30:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/sprime_s_convergence_20261013/logs/s_runner_resume_proof_v8_%j.log
set -euo pipefail
cd /share/home/zixiao/descriptor_analysis
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1
export PYTORCH_ALLOC_CONF=expandable_segments:True
export PYTHONPATH=/share/home/zixiao/PhyChem_MFM_stage59_three_epoch_runtime:/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps
S_PROOF_PY=/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage43_5090_environment/install_4511929/venv/bin/python
S_PROOF_RUNNER=runs/sprime_s_convergence_20261013/scripts/s_convergence_runner_v8.py
S_PROOF_CFG=/share/home/zixiao/descriptor_analysis/runs/sprime_s_convergence_20261013/configs/s_runner_development_v8.json
srun --ntasks=1 --cpus-per-task=16 --cpu-bind=cores "$S_PROOF_PY" -B "$S_PROOF_RUNNER" --configuration "$S_PROOF_CFG" --development-steps 4 --segment-tag uninterrupted
srun --ntasks=1 --cpus-per-task=16 --cpu-bind=cores "$S_PROOF_PY" -B "$S_PROOF_RUNNER" --configuration "$S_PROOF_CFG" --development-steps 3 --segment-tag sliced
srun --ntasks=1 --cpus-per-task=16 --cpu-bind=cores "$S_PROOF_PY" -B "$S_PROOF_RUNNER" --configuration "$S_PROOF_CFG" --resume "/share/home/zixiao/descriptor_analysis/runs/sprime_s_convergence_20261013/development_s_runner/B1_seed0/segment_${SLURM_JOB_ID}_sliced/segment_final.pt" --development-steps 1 --segment-tag resumed
srun --ntasks=1 --cpus-per-task=16 --cpu-bind=cores "$S_PROOF_PY" -B runs/sprime_s_convergence_20261013/scripts/compare_s_runner_resume_v3.py
