#!/bin/bash
#SBATCH --job-name=phase1-id-audit
#SBATCH --partition=cpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:15:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/full_identity_%j.log

# Identity-only preprocessing; no GPU or model training.
set -euo pipefail
cd /share/home/zixiao/PhyChem_MFM_ICLR2027
export CUDA_VISIBLE_DEVICES=""
export OMP_NUM_THREADS=2
export MKL_NUM_THREADS=2
export PYTHONPATH=/share/home/zixiao/PhyChem_MFM_ICLR2027
printf 'Slurm job=%s node=%s user=%s\n' "$SLURM_JOB_ID" "$(hostname)" "$(id -un)"
/share/home/zixiao/.conda/envs/chemprop/bin/python tools/phase1_audit_manifest_identities.py \
    --train-manifest manifests/discovery_v3_quality/train_50000.json \
    --validation-manifest manifests/discovery_v3_quality/validation.json \
    --output-dir "/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/full_identity_${SLURM_JOB_ID}" \
    --max-wall-seconds 840
