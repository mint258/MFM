#!/bin/bash
#SBATCH --job-name=v3-readonly-diagnostics
#SBATCH --partition=all
#SBATCH --nodelist=compute-0-20
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/model_v31_20261105/MODEL_V3_DIAGNOSTICS_%j.log
set -euo pipefail
root=/share/home/zixiao/descriptor_analysis
cd "$root/MFM_model_v3"
python=/share/home/zixiao/.venvs/model_v2_cu118_20261105/bin/python
export CUDA_VISIBLE_DEVICES=''
export PYTHONPATH=$PWD/current:$root/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export PYTHONDONTWRITEBYTECODE=1 PYTHONIOENCODING=utf-8
output=${DIAGNOSTICS_OUTPUT:-/lfshome/zixiao/model_v31_20261105/DIAGNOSTICS_20261112}
state=$root/runs/model_v31_20261105/MODEL_V3_DIAGNOSTICS_${SLURM_JOB_ID}.disk.json
findmnt -T /lfshome/zixiao/model_v31_20261105
df -B1 / /lfshome/zixiao "$root"
df -Pi / /lfshome/zixiao "$root"
"$python" -B -u tools/model_v3/v2_diagnosis_disk.py --output "$output" --state "$state" --node "$(hostname -s)" --job "$SLURM_JOB_ID" --once
"$python" -B -u tools/model_v3/v2_diagnosis_disk.py --output "$output" --state "$state" --node "$(hostname -s)" --job "$SLURM_JOB_ID" &
guard=$!
trap 'kill "$guard" 2>/dev/null || true; wait "$guard" 2>/dev/null || true' EXIT
"$python" -B -u tools/model_v3/v3_export_diagnostics_20261112.py --output "$output" --device cpu "$@"

