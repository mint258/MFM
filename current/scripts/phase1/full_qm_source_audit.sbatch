#!/bin/bash
#SBATCH --job-name=phase1-qm-struct
#SBATCH --partition=cpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:15:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/full_qm_sources_%j.log

set -euo pipefail
cd /share/home/zixiao/PhyChem_MFM_ICLR2027
export CUDA_VISIBLE_DEVICES=""
export OMP_NUM_THREADS=2
export MKL_NUM_THREADS=2
export PYTHONPATH=/share/home/zixiao/PhyChem_MFM_ICLR2027
printf 'Slurm job=%s node=%s user=%s\n' "$SLURM_JOB_ID" "$(hostname)" "$(id -un)"
sha256sum tools/audit_phase1_qm_sources.py tools/audit_phase1_som_structures.py phychem_mfm/phase1/downstream_structures.py
timeout 890s /share/home/zixiao/.conda/envs/chemprop/bin/python tools/audit_phase1_qm_sources.py \
    --benchmark-root /share/home/zixiao/benchmark_dataset --datasets qm7 qm9 \
    --output-dir "/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/full_qm_sources_${SLURM_JOB_ID}" \
    --max-records 200000 --max-wall-seconds 840
