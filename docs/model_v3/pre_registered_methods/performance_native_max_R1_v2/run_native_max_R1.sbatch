#!/bin/bash
#SBATCH --job-name=native_S_max712_R1_capacity
#SBATCH --partition=all
#SBATCH --cpus-per-task=16
#SBATCH --mem=64G
#SBATCH --time=02:00:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/model_v3_20261026/native_S_max712_R1_%j.log
set -euo pipefail
# Root alone admits/submits one new job after actual public source review,
# all-user CPU/RAM85%+MemAvailable, C35 empty/UUID lock, quota and independent2G hold.
: "${SLURM_JOB_ID:?Existing owned Root-submitted GPU allocation required}"
: "${MODEL_V3_GPU_UUID:?Exactly admitted physical GPU UUID required}"
: "${MODEL_V3_EXPECTED_NODE:?Actual admitted node required}"
: "${MODEL_V3_OUT:?Fresh independent child output root required}"
: "${MODEL_V3_RECORD:?Fresh disjoint supervisor record required}"
: "${MODEL_V3_PACKAGE_PINS_SHA256:?Actual reviewed package SHA required}"
: "${MODEL_V3_ROOT_ADMISSION_PATH:?Actual fresh Root admission rawref required}"
: "${MODEL_V3_ROOT_ADMISSION_SHA256:?Actual Root admission SHA required}"
: "${MODEL_V3_QUOTA_PATH:?Actual account quota rawref required}"
: "${MODEL_V3_QUOTA_SHA256:?Actual quota SHA required}"
: "${MODEL_V3_HOLD_PATH:?Actual independent persistent2G hold rawref required}"
: "${MODEL_V3_HOLD_SHA256:?Actual independent hold SHA required}"
: "${MODEL_V3_METHOD_PUBLICATION_PATH:?Actual new probe prereg/source publication required}"
: "${MODEL_V3_METHOD_PUBLICATION_SHA256:?Actual new publication rawSHA required}"
B=/share/home/zixiao/descriptor_analysis
CODE=$B/MFM_model_v3_performance_integration_v1
PKG=$B/runs/model_v3_20261026/performance_native_max_R1_GPU_v2_source
PY=$B/docs/phase1/evidence/stage43_5090_environment/install_4511929/venv/bin/python
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=8 MKL_NUM_THREADS=8 OPENBLAS_NUM_THREADS=8
export PYTHONPATH="$CODE/current:$CODE/tools/model_v3:$B/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps"
export CUDA_VISIBLE_DEVICES="$MODEL_V3_GPU_UUID"
cd "$CODE"
# Source/path-only prelude. CPU selection and genuine native decoding then run
# inside the same6900s supervised child; no unmetered preparatory project process.
"$PY" -u -B - <<'PY'
import hashlib, os, signal, socket
from pathlib import Path
signal.alarm(30)
base=Path('/share/home/zixiao/descriptor_analysis')
n=base/'runs/model_v3_20261026'
code=base/'MFM_model_v3_performance_integration_v1'
assert os.getuid()==1278 and int(os.environ['SLURM_CPUS_PER_TASK'])==16
assert socket.gethostname().split('.')[0]==os.environ['MODEL_V3_EXPECTED_NODE']=='compute-0-21'
assert os.environ['MODEL_V3_GPU_UUID']=='GPU-c35f2434-9137-9723-1af5-dc69b6295243'
out,record=[Path(os.environ[k]) for k in ('MODEL_V3_OUT','MODEL_V3_RECORD')]
for path in (out,record):
    assert path.is_absolute() and not path.exists() and not path.is_symlink()
    assert path.resolve().is_relative_to(n.resolve())
    assert not path.resolve().is_relative_to((n/'native_S_B20k_v3').resolve())
assert out!=record and not record.resolve().is_relative_to(out.resolve())
assert not out.resolve().is_relative_to(record.resolve())
for suffix in ('.jsonl','.storage.json'):
    assert not Path(str(record)+suffix).exists()
# Existing original supervisor must remain the reviewed exact source.
p=code/'tools/model_v3/run_supervised.py'
assert hashlib.sha256(p.read_bytes()).hexdigest()=='a1b16ea1af0400dd695a6b1e651b9f88a5ed88bcabe4ed718d5e19ad11abd7bd'
# Root binds actual method/source readback and actual live frames before sbatch.
# The child rehashes these rawrefs; raw integrity is not fabricated admission.
print('NATIVE_MAX_R1_PATH_AND_SUPERVISOR_SOURCE_BOUND_NO_MODEL_OR_INPUT_READ',flush=True)
PY
# No outer fd9/flock. The new child alone holds the original public UUID lock.
exec "$PY" -u -B tools/model_v3/run_supervised.py \
  --output-root "$MODEL_V3_OUT" --record "$MODEL_V3_RECORD" \
  --gpu-uuid "$CUDA_VISIBLE_DEVICES" --wall-seconds 6900 \
  --rss-limit-bytes 60129542144 --output-budget-bytes 2147483648 \
  --private-scratch-root "/tmp/mv3n_${SLURM_JOB_ID}" \
  --private-storage-budget-bytes 2147483648 -- \
  "$PY" -u -B "$PKG/run_native_max_R1.py" \
  --output "$MODEL_V3_OUT" --pins-sha256 "$MODEL_V3_PACKAGE_PINS_SHA256"
