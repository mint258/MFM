#!/bin/bash
#SBATCH --job-name=model_v3_current_Av2_R1_ABBA
#SBATCH --partition=all
#SBATCH --cpus-per-task=16
#SBATCH --mem=64G
#SBATCH --time=02:00:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/model_v3_20261026/performance_current_Av2_R1_ABBA_%j.log
set -euo pipefail
# Root submits only after fresh all-user CPU/RAM85%, MemAvailable, UUID/foreign,
# quota and a separate 2GiB persistent hold. This script does not reserve/submit.
: "${SLURM_JOB_ID:?Existing Root-submitted GPU allocation required}"
: "${MODEL_V3_GPU_UUID:?Root binds one fresh physical GPU UUID}"
: "${MODEL_V3_EXPECTED_NODE:?Root binds the actual admitted node}"
: "${MODEL_V3_OUT:?Fresh Root-designated child output outside Git}"
: "${MODEL_V3_RECORD:?Fresh sibling supervision record outside child output}"
: "${MODEL_V3_PACKAGE_PINS_SHA256:?Root binds this source-only package}"
: "${MODEL_V3_ROOT_ADMISSION_PATH:?Actual Root admission rawref}"
: "${MODEL_V3_ROOT_ADMISSION_SHA256:?Actual Root admission SHA}"
: "${MODEL_V3_QUOTA_PATH:?Actual account quota observation rawref}"
: "${MODEL_V3_QUOTA_SHA256:?Actual quota observation SHA}"
: "${MODEL_V3_HOLD_PATH:?Actual independent persistent hold rawref}"
: "${MODEL_V3_HOLD_SHA256:?Actual independent hold SHA}"
: "${MODEL_V3_ABBA_ROLE:?Root binds reference or candidate for this one member}"
: "${MODEL_V3_ABBA_POSITION:?Root binds this explicit ABBA position}"
: "${MODEL_V3_ABBA_SERIES_ID:?Root binds the fixed four-member series}"
: "${MODEL_V3_R1_CASE:?Exactly a00_manual or head_off}"
: "${MODEL_V3_SDK_CLOSURE_PATH:?Actual same-job full SDK Root closure required}"
: "${MODEL_V3_SDK_CLOSURE_SHA256:?Actual SDK Root raw SHA required}"
: "${MODEL_V3_METHOD_PUBLICATION_PATH:?Exact newly published method required}"
: "${MODEL_V3_METHOD_PUBLICATION_SHA256:?Actual method receipt SHA}"
: "${MODEL_V3_CANDIDATE_OPTIONS:?Fixed selected candidate option absolute path}"
CODE=/share/home/zixiao/descriptor_analysis/MFM_model_v3_A_acceptance_v2_candidate_v1
PKG=/share/home/zixiao/descriptor_analysis/runs/model_v3_20261026/performance_current_Av2_R1_ABBA_v1_source
PY=/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage43_5090_environment/install_4511929/venv/bin/python
export MODEL_V3_CURRENT_AV2_R1_PACKAGE="$PKG"
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=8 MKL_NUM_THREADS=8 OPENBLAS_NUM_THREADS=8
export PYTHONPATH="$CODE/current:$CODE/tools/model_v3:/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps"
export CUDA_VISIBLE_DEVICES="$MODEL_V3_GPU_UUID"
cd "$CODE"
# Original benchmark/guard are unchanged. This bounded preflight reads only
# sources and closed metadata; no Torch/project/SDK payload import.
"$PY" -u -B - <<'PY'
import importlib.util, json, os, signal, socket
from pathlib import Path
signal.alarm(180)
pkg=Path(os.environ['MODEL_V3_CURRENT_AV2_R1_PACKAGE'])
spec=importlib.util.spec_from_file_location('current_Av2_R1_admission',pkg/'admission.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
m.verify_package(os.environ['MODEL_V3_PACKAGE_PINS_SHA256'])
method=m.reference(os.environ['MODEL_V3_METHOD_PUBLICATION_PATH'])
m.need(method['sha256']==os.environ['MODEL_V3_METHOD_PUBLICATION_SHA256'],'Actual method receipt SHA differs')
m.verify_method(method)
sdk=m.reference(os.environ['MODEL_V3_SDK_CLOSURE_PATH'])
m.need(sdk['sha256']==os.environ['MODEL_V3_SDK_CLOSURE_SHA256'],'Actual SDK receipt SHA differs')
qualified=m.qualify(os.environ['MODEL_V3_R1_CASE'],sdk);c=qualified['case']
m.need(os.getuid()==1278 and os.environ.get('SLURM_JOB_ID')
       and int(os.environ.get('SLURM_CPUS_PER_TASK','0'))==16
       and socket.gethostname().split('.')[0]==m.NODE==os.environ['MODEL_V3_EXPECTED_NODE']
       and os.environ['CUDA_VISIBLE_DEVICES']==os.environ['MODEL_V3_GPU_UUID']==m.GPU,
       'Exact owned16CPU/node21/C35 allocation required')
position=int(os.environ['MODEL_V3_ABBA_POSITION'])
m.need(1<=position<=4 and os.environ['MODEL_V3_ABBA_ROLE']==('reference','candidate','candidate','reference')[position-1]
       and os.environ['MODEL_V3_ABBA_SERIES_ID']==c['series_id']
       and os.environ['MODEL_V3_CANDIDATE_OPTIONS']==c['candidate_options']['path'],'Fixed selected member/options differ')
family=Path(c['family'])/('member_'+str(position))
m.need(Path(os.environ['MODEL_V3_OUT'])==family/'child'
       and Path(os.environ['MODEL_V3_RECORD'])==family/'supervisor.json','Independent exact selected family required')
for name in ('MODEL_V3_OUT','MODEL_V3_RECORD'):
    p=Path(os.environ[name])
    m.need(p.is_absolute() and not p.exists() and not p.is_symlink(),'Fresh output/record required')
for suffix in ('.jsonl','.storage.json'):
    m.need(not Path(os.environ['MODEL_V3_RECORD']+suffix).exists(),'Fresh supervision sidecar required')
root_refs={}
for prefix in ('MODEL_V3_ROOT_ADMISSION','MODEL_V3_QUOTA','MODEL_V3_HOLD'):
    r=m.reference(os.environ[prefix+'_PATH'])
    m.need(r['sha256']==os.environ[prefix+'_SHA256'],'Root frame raw SHA differs')
    root_refs[prefix]=r
# Root, using the original admission/quota/hold procedure, checks actual frame
# authority/freshness before sbatch. These raw bindings do not create authority.
print(json.dumps(dict(status='ACTUAL_CURRENT_AV2_NUMERIC_AND_SDK_METADATA_QUALIFIED_NOT_R1_ACCEPTANCE',
    case=os.environ['MODEL_V3_R1_CASE'],position=position,series_id=c['series_id'],
    numeric_closure=c['numeric_closure'],SDK_closure=sdk,method_publication=method,
    Root_actual_frames=root_refs,job_id=os.environ['SLURM_JOB_ID']),sort_keys=True),flush=True)
signal.alarm(0)
PY
# No outer flock. Only single_a_benchmark owns the shared physical UUID lock.
exec "$PY" -u -B tools/model_v3/run_supervised.py \
  --output-root "$MODEL_V3_OUT" --record "$MODEL_V3_RECORD" \
  --gpu-uuid "$CUDA_VISIBLE_DEVICES" --wall-seconds 6900 \
  --rss-limit-bytes 60129542144 --output-budget-bytes 2147483648 \
  --private-scratch-root "/tmp/mv3n_${SLURM_JOB_ID}" \
  --private-storage-budget-bytes 2147483648 -- \
  "$PY" -u -B tools/model_v3/single_a_benchmark.py \
  --candidate-options "$MODEL_V3_CANDIDATE_OPTIONS" \
  --performance-execution current/configs/model_v3/performance/a1_manual_capacity_observation_v1.json \
  --performance-execution-sha256 7cabbd4a0300d551154ffb9bcbed5466fc9886d0eb886a1ae37ee3e7f70db46e \
  --reference-config "$CODE/workflows/sprime_s/formal_s/B1_seed0_v2.json" \
  --input native_s --seed 0 --workers 8 --max-padded-cost 8000000 \
  --expected-gpu 5090 --code-sha 7ffe8a5557590b1481f4ca74073007f070dc6a50 \
  --prereg-sha 2b4a4df8636e5d65915d535472ba01084ea72dab \
  --shard-snapshot-sha256 d2e1ace1636485cd3dd0106b1177518dd37eb9741919195a9efcd846c1c2242f \
  --role "$MODEL_V3_ABBA_ROLE" --abba-position "$MODEL_V3_ABBA_POSITION" \
  --series-id "$MODEL_V3_ABBA_SERIES_ID" \
  --deterministic-controls --output "$MODEL_V3_OUT"
