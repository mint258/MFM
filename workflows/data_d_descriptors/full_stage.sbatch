#!/bin/bash
#SBATCH --job-name=D-stage0-full
#SBATCH --partition=cpu
#SBATCH --exclude=compute-0-[0-7,18,20-22]
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
set -euo pipefail
# Submit only after a reviewed closed-cost plan exists. Override CPUs for
# produce with its plan.slurm.cpus_per_stage.produce: 4 workers + parent = 5.
# population_summary/prepare/finalize need 1 CPU.
stage=${1:?population_summary, prepare, produce, or finalize required}
config=${2:?absolute generated config path required}
export CUDA_VISIBLE_DEVICES="" PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
cd /share/home/zixiao/descriptor_analysis/MFM_d_descriptors_20261120
recipe_root=${D_RECIPE_ROOT:-/share/home/zixiao/descriptor_analysis/MFM_d_recipe}
export PYTHONPATH="$recipe_root/current:$PWD:$PWD/current"
python_bin=/share/home/zixiao/.conda/envs/chemprop/bin/python
case "$stage" in
  population_summary)
    summary=${3:?absolute metadata summary output path required}
    exec "$python_bin" -B -m workflows.data_d_descriptors.full_plan population_summary \
      --pilot-config "$config" --summary-output "$summary" --recipe-root "$recipe_root" ;;
  prepare) exec "$python_bin" -B -m workflows.data_d_descriptors.prepare --config "$config" ;;
  produce|finalize) exec "$python_bin" -B -m workflows.data_d_descriptors.produce "$stage" --config "$config" ;;
  *) exit 2 ;;
esac
