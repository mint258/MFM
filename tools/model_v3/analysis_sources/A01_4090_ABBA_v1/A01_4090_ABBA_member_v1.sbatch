#!/bin/bash
#SBATCH --job-name=model_v3_A01_4090_ABBA
#SBATCH --partition=all
#SBATCH --nodelist=compute-0-20
#SBATCH --cpus-per-task=16
#SBATCH --mem=64G
#SBATCH --time=00:20:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/model_v3_20261026/A01_4090_ABBA_outputs_v1/A01_%j.log
set -euo pipefail
: "${MODEL_V3_ABBA_SOURCE_PINS_SHA:?Frozen standalone launcher source required}"
: "${MODEL_V3_ABBA_RECORD:?Actual Root submission receipt required}"
: "${MODEL_V3_ABBA_POSITION:?Sequential A/B/B/A position required}"
: "${MODEL_V3_ABBA_NONCE:?Unique immutable Root submission intent required}"
[[ $(hostname -s) == compute-0-20 ]]
task_base=/share/home/zixiao/descriptor_analysis
task_tree=$task_base/MFM_model_v3_a_checkpoint
task_source=$task_base/runs/model_v3_20261026/A01_4090_ABBA_v1
task_python=/share/home/zixiao/.conda/envs/chemprop/bin/python
export PATH=$task_base/runs/model_v3_20261025/cpu_git_tools_v1/bin:$PATH
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=8 MKL_NUM_THREADS=8 OPENBLAS_NUM_THREADS=8
export PYTHONPATH=$task_tree/current:$task_tree/tools/model_v3:$task_tree/workflows/sprime_s/scripts:$task_base/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps
export CUDA_VISIBLE_DEVICES=GPU-ec788ed1-7da1-8f93-bb23-b4fdb2018b02
cd "$task_tree"
exec "$task_python" -u -B "$task_source/admit_abba.py" worker \
  --position "$MODEL_V3_ABBA_POSITION" --source-pins-sha256 "$MODEL_V3_ABBA_SOURCE_PINS_SHA" \
  --record "$MODEL_V3_ABBA_RECORD" --nonce "$MODEL_V3_ABBA_NONCE"
