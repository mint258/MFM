#!/bin/bash
#SBATCH --job-name=p-step-overhead-regression
#SBATCH --partition=cpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --time=02:00:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/MFM_step_overhead_20261114/results/perf_step_overhead_20261114/regression_%j.log
set -euo pipefail
base=/share/home/zixiao/descriptor_analysis
cd "$base/MFM_step_overhead_20261114"
export CUDA_VISIBLE_DEVICES="" PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export PYTHONPATH="$PWD/current:$PWD/tools/model_v3:$base/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps"
export PATH="$base/runs/model_v3_20261025/cpu_git_tools_v1/bin:$PATH"
export PHASE1_NATIVE_TRANSPORT_PATH="$base/docs/phase1/evidence/stage48_full_corpus_qa/native_qa_stats_v3.py"
export PHASE1_JOINT_REFERENCE_PATH="$base/docs/phase1/evidence/stage50_full_corpus_training/actual_api_reference/full_corpus_training.py"
python=$base/docs/phase1/evidence/stage43_5090_environment/install_4511929/venv/bin/python
findmnt -T /tmp
findmnt -T "$PWD"
df -B1 /tmp "$PWD"
df -Pi /tmp "$PWD"
/usr/bin/python3 -B -c 'import v2_diagnosis_disk as d; d.m.require_capacity(d.m.filesystem_status("/tmp"),24000000000,20000); d.m.require_capacity(d.m.filesystem_status(d.ROOT),4000000000,20000); d.m.quota_headroom(d.CONTROL/"share_quota_available_v3.json","/share",4000000000,d.remaining_nfs_other())'
/usr/bin/python3 -B tools/model_v3/v2_watch_disk.py --output /tmp --state "$PWD/results/perf_step_overhead_20261114/local_guard_$SLURM_JOB_ID.json" --node "$(hostname -s)" --jobs "$SLURM_JOB_ID" --growth-bytes 24000000000 &
local_guard=$!
/usr/bin/python3 -B tools/model_v3/v2_watch_disk.py --output "$PWD/results/perf_step_overhead_20261114" --state "$PWD/results/perf_step_overhead_20261114/share_guard_$SLURM_JOB_ID.json" --node "$(hostname -s)" --jobs "$SLURM_JOB_ID" --growth-bytes 4000000000 --quota-reference "$base/runs/data_v1_20261025/control/window2_20261105/share_quota_available_v3.json" --quota-filesystem /share --quota-concurrent-bytes 23179869184 &
share_guard=$!
trap 'kill "$local_guard" "$share_guard" 2>/dev/null || true' EXIT
"$python" -B -u tools/model_v3/step_overhead_regression.py
