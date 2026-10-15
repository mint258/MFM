#!/bin/bash
#SBATCH --job-name=phase1-som-struct
#SBATCH --partition=cpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:15:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/full_som_structures_%j.log

# Structure/source-only preprocessing. No SoM targets, GPU or split repair.
set -euo pipefail
cd /share/home/zixiao/PhyChem_MFM_ICLR2027
export CUDA_VISIBLE_DEVICES=""
export OMP_NUM_THREADS=2
export MKL_NUM_THREADS=2
export PYTHONPATH=/share/home/zixiao/PhyChem_MFM_ICLR2027
printf 'Slurm job=%s node=%s user=%s\n' "$SLURM_JOB_ID" "$(hostname)" "$(id -un)"
if command -v git >/dev/null 2>&1; then
    git --no-pager log -1 --format='%H %s'
else
    printf 'Git unavailable in this batch environment; source SHA256 recorded below\n'
fi
sha256sum tools/audit_phase1_som_structures.py phychem_mfm/phase1/downstream_structures.py
timeout 180s /share/home/zixiao/.conda/envs/chemprop/bin/python tools/audit_phase1_som_structures.py \
    --benchmark-root /share/home/zixiao/benchmark_dataset \
    --expected-source-metadata /share/home/zixiao/descriptor_analysis/docs/phase1/evidence/som_source_git_tree_metadata.json \
    --output-dir "/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/full_som_structures_${SLURM_JOB_ID}" \
    --max-records 5000 --max-wall-seconds 120
