#!/bin/bash
#SBATCH --job-name=M2-plan-learnability-probe
#SBATCH --partition=all
#SBATCH --nodelist=compute-0-20
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/model_v31_20261105/M2_probe_plan_%j.log
set -euo pipefail
index=${1:?actual family index in the closed E3 plan}
root=/share/home/zixiao/descriptor_analysis
cd "$root/MFM_model_v3"
export CUDA_VISIBLE_DEVICES= PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH=$PWD/current:$root/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
python=/share/home/zixiao/.conda/envs/chemprop/bin/python
plan=/lfshome/zixiao/model_v31_20261105/M2_DIAG_FAMILY_PLAN_20261108/plan.json
"$python" -B tools/model_v3/v2_diagnosis_disk.py --once --output "$(dirname "$plan")" --node "$(hostname -s)" --job "$SLURM_JOB_ID" --state "$root/runs/model_v31_20261105/M2_probe_plan_${SLURM_JOB_ID}.state.json"
"$python" -B -u tools/model_v3/v2_overfit_attribution.py plan-probe --plan "$plan" --index "$index"
