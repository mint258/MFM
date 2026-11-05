#!/bin/bash
#SBATCH --job-name=model_v3_equivariance_v2_FP64_math
#SBATCH --partition=cpu
#SBATCH --cpus-per-task=16
#SBATCH --time=00:20:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/model_v3_20261026/equivariance_v2_FP64_math_20261029/math_%j.log
set -euo pipefail
: "${MODEL_V3_EXPECTED_NODE:?Root must bind the actual authorized CPU node}"
[[ "$(hostname -s)" == "$MODEL_V3_EXPECTED_NODE" ]]
# Automatic/default Slurm memory. No --mem or implicit SBATCH memory override.
for task_option in SBATCH_MEM_PER_NODE SBATCH_MEM_PER_CPU SBATCH_MEM_PER_GPU; do
  [[ -z "${!task_option-}" ]] || { echo "Unexpected memory override: $task_option" >&2; exit 1; }
done
task_base=/share/home/zixiao/descriptor_analysis
task_source=$task_base/runs/model_v3_20261026/equivariance_v2_FP64_math_20261029
task_runs=$task_base/runs/model_v3_20261025
task_python=$task_base/docs/phase1/evidence/stage43_5090_environment/install_4511929/venv/bin/python
task_output=$task_source/math_parent_${SLURM_JOB_ID}
export CUDA_VISIBLE_DEVICES="" PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 NUMEXPR_NUM_THREADS=4
export PYTHONPATH="$task_base/MFM_model_v3_composed_equivariance_runtime_v3/current:$task_base/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps"
cd "$task_base"
printf 'FP64_math CPU16 automatic_memory software_RSS_limit_bytes=25769803776 SLURM_MEM_PER_NODE=%s allocation_guarantee=NOT_ASSERTED\n' "${SLURM_MEM_PER_NODE-}"
"$task_python" -u -B "$task_runs/run_cpu_supervised_v3.py" \
  --output-root "$task_output" --record "$task_source/supervisor_${SLURM_JOB_ID}.json" \
  --wall-seconds 1100 --rss-limit-bytes 25769803776 --output-budget-bytes 2147483648 -- \
  "$task_python" -u -B "$task_source/math_check.py" \
    --expected-node "$MODEL_V3_EXPECTED_NODE" --output "$task_output/math"
