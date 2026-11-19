#!/bin/bash
#SBATCH --job-name=B0-reference-D20-reuse
#SBATCH --partition=cpu
#SBATCH --nodelist=compute-0-13
#SBATCH --cpus-per-task=1
#SBATCH --ntasks=1
#SBATCH --time=00:30:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/B0_reference_D20_reuse_%j.log
set -euo pipefail
repo=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/worktrees/benchmark_data_20261119
data=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B0_20261119
export PYTHONPATH="$repo:/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 BLIS_NUM_THREADS=1 CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1
cd "$repo"
exec /share/home/zixiao/.conda/envs/chemprop/bin/python -B -u -m workflows.benchmark_data.reference_d20 \
 --root "$data" --attempt "job_${SLURM_JOB_ID}" \
 --input "C7H10O2=$data/reference/C7H10O2/job_4536463/all_rows.parquet" \
 --input "NMRShiftDB2_13C=$data/domain/NMRShiftDB2/job_4536470/carbon.parquet" \
 --input "NMRShiftDB2_1H=$data/domain/NMRShiftDB2/job_4536470/hydrogen.parquet" \
 --input "PPE1694=$data/domain/PPE1694/job_4536507/all_rows.parquet" \
 --reuse-D20 "$data/labels/reference_D20/job_4536481/C7H10O2.parquet" \
 --reuse-D20 "$data/labels/reference_D20/job_4536481/NMRShiftDB2_13C.parquet" \
 --reuse-D20 "$data/labels/reference_D20/job_4536481/NMRShiftDB2_1H.parquet" \
 --reuse-D20 "$data/labels/reference_D20/job_4536481/PPE1694.parquet" \
 --quota-snapshot /share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/benchmark_B0_quota_20261119.json