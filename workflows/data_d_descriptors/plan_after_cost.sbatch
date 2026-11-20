#!/bin/bash
#SBATCH --job-name=D-stage0-plan-after-cost
#SBATCH --partition=cpu
#SBATCH --exclude=compute-0-[0-7,18,20-22]
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=0
#SBATCH --time=00:20:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/MFM_d_descriptors_20261120_plan_%j.out
set -euo pipefail
export CUDA_VISIBLE_DEVICES="" PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
cd /share/home/zixiao/descriptor_analysis/MFM_d_descriptors_20261120
task_recipe=/share/home/zixiao/descriptor_analysis/MFM_d_recipe
task_run=/share/home/zixiao/descriptor_analysis/runs/d_recipe_20261120
task_configs="$PWD/configs/data_d_descriptors/full_20261120"
task_python=/share/home/zixiao/.conda/envs/chemprop/bin/python
export PYTHONPATH="$task_recipe/current:$PWD:$PWD/current:/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps"
# Both libraries' costs must be closed (or explicitly UNRESOLVED). This job
# reads existing cohort metadata and writes a forecast/configuration only.
# It neither calculates full descriptors nor reserves their future disk space.
"$task_python" -B -m workflows.data_d_descriptors.full_plan population_summary \
  --pilot-config configs/data_d_descriptors/pilot.json \
  --summary-output "$task_run/full_population.json" --recipe-root "$task_recipe"
"$task_python" -B -m workflows.data_d_descriptors.full_plan plan \
  --pilot-config configs/data_d_descriptors/pilot.json \
  --population-summary "$task_run/full_population.json" \
  --training-view /share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/repository/configs/data_v1/training_view_v1.json \
  --run-root "$task_run/full" --config-output "$task_configs" \
  --workers 4 --recipe-root "$task_recipe"
