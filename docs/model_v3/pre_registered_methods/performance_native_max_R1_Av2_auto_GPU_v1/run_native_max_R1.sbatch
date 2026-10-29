#!/bin/bash
#SBATCH --job-name=native_S_max712_Av2_auto_R1_capacity
#SBATCH --partition=all
#SBATCH --cpus-per-task=16
#SBATCH --time=02:00:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/model_v3_20261026/native_S_max712_Av2_auto_R1_%j.log
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
: "${MODEL_V3_CURRENT_AV2_R1_PUBLICATION_PATH:?Actual published current A-v2 R1 source required}"
: "${MODEL_V3_CURRENT_AV2_R1_PUBLICATION_SHA256:?Actual current R1 publication rawSHA required}"
B=/share/home/zixiao/descriptor_analysis
CODE=$B/MFM_model_v3_A_acceptance_v2_candidate_v1
PKG=$B/runs/model_v3_20261026/performance_native_max_R1_Av2_auto_GPU_v1_source
PY=$B/docs/phase1/evidence/stage43_5090_environment/install_4511929/venv/bin/python
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=8 MKL_NUM_THREADS=8 OPENBLAS_NUM_THREADS=8
export PYTHONPATH="$CODE/current:$CODE/tools/model_v3:$B/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps"
export CUDA_VISIBLE_DEVICES="$MODEL_V3_GPU_UUID"
cd "$CODE"
# Source/path-only prelude. CPU selection and genuine native decoding then run
# inside the same6900s supervised child; no unmetered preparatory project process.
"$PY" -u -B - <<'PY'
import hashlib, importlib.util, json, os, signal, socket, subprocess
from pathlib import Path
signal.alarm(30)
base=Path('/share/home/zixiao/descriptor_analysis')
n=base/'runs/model_v3_20261026'
code=base/'MFM_model_v3_A_acceptance_v2_candidate_v1'
assert os.getuid()==1278 and int(os.environ['SLURM_CPUS_PER_TASK'])==16
assert socket.gethostname().split('.')[0]==os.environ['MODEL_V3_EXPECTED_NODE']=='compute-0-21'
assert os.environ['MODEL_V3_GPU_UUID']=='GPU-c35f2434-9137-9723-1af5-dc69b6295243'
out,record=[Path(os.environ[k]) for k in ('MODEL_V3_OUT','MODEL_V3_RECORD')]
family=n/'performance_native_max_R1_Av2_auto_v1'
assert out==family/'child' and record==family/'supervisor.json'
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
# Same frozen shared policy as routing6/Native8; no model/input/payload read.
pkg=n/'performance_native_max_R1_Av2_auto_GPU_v1_source'
deps=json.loads((pkg/'dependencies.json').read_bytes())
policyref=deps['raw_refs']['GPU_auto_memory_policy_source']
assert hashlib.sha256(Path(policyref['path']).read_bytes()).hexdigest()==policyref['sha256']
spec=importlib.util.spec_from_file_location('native_max_auto_shared_memory_policy',policyref['path'])
memory_policy=importlib.util.module_from_spec(spec);spec.loader.exec_module(memory_policy)
assert memory_policy.verify_package('cbb3d620f90768272abb2e135a11e928a861a896e9c51c80b5bea82ec6eca245')==deps['raw_refs']['GPU_auto_memory_policy_pins']
pubref=memory_policy.reference(os.environ['MODEL_V3_METHOD_PUBLICATION_PATH'])
assert pubref['sha256']==os.environ['MODEL_V3_METHOD_PUBLICATION_SHA256']
memory_policy.verify_publication(pubref)
memory_raw=[]
def observe_memory(argv):
    result=subprocess.run(argv,capture_output=True,text=True,timeout=10)
    assert len(result.stdout)+len(result.stderr)<=2<<20
    memory_raw.append(dict(argv=argv,returncode=result.returncode,stdout=result.stdout,stderr=result.stderr))
    assert result.returncode==0
    return result.stdout
node_raw=observe_memory(['scontrol','show','node','compute-0-21'])
queue_raw=observe_memory(['squeue','-h','-w','compute-0-21','-o','%i|%u|%t|%m|%C'])
mem_raw=Path('/proc/meminfo').read_text()
memory=memory_policy.assess(node_raw,queue_raw,mem_raw,node='compute-0-21',software_budget_bytes=64<<30,rss_limit_bytes=56<<30,
    registry_path=n/'native_S_profile_registered_reservations_v6.json',current_job_id=os.environ['SLURM_JOB_ID'],
    current_reservation_id='performance_native_max_R1_Av2_auto_v1')
job_raw=observe_memory(['scontrol','show','job','-o',os.environ['SLURM_JOB_ID']])
startup=dict(schema='model_v3_GPU_auto_memory_startup_actual_v1',job_id=os.environ['SLURM_JOB_ID'],memory=memory,
    raw_observations=memory_raw,actual_meminfo=mem_raw,actual_job_control=job_raw,
    actual_Slurm_memory_environment={k:v for k,v in os.environ.items() if k.startswith('SLURM_MEM_')},
    Slurm_memory_mode='automatic_default',fixed_memory_requested_bytes=None,finite_physical_guarantee_claimed=False)
startup_raw=(json.dumps(startup,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
assert len(startup_raw)<=2<<20
with (family/'control/GPU_auto_memory_startup_actual_v1.json').open('xb') as stream:
    stream.write(startup_raw);stream.flush();os.fsync(stream.fileno())
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
