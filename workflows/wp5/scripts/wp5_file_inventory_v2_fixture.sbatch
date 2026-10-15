#!/bin/bash
#SBATCH --job-name=wp5_stat_fixture_v2
#SBATCH --partition=all
#SBATCH --nodelist=compute-0-20
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --mem=8G
#SBATCH --time=00:10:00
#SBATCH --chdir=/share/home/zixiao/descriptor_analysis
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/logs/home_stat_fixture_v2_%j.out
#SBATCH --error=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/logs/home_stat_fixture_v2_%j.err
set -euo pipefail
cd /share/home/zixiao/descriptor_analysis
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 CUDA_VISIBLE_DEVICES=""
ROOT=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011
export PYTHONPATH="$ROOT/scripts${PYTHONPATH:+:$PYTHONPATH}"
exec /share/home/zixiao/.conda/envs/chemprop/bin/python -B "$ROOT/scripts/wp5_file_inventory_v2_fixture.py" --out "$ROOT/reports/home_stat_inventory_v2_fixture_job_${SLURM_JOB_ID}.json" --cleanup