#!/bin/bash
#SBATCH --job-name=model_v3_A5_R2_v2
#SBATCH --partition=all
#SBATCH --cpus-per-task=16
#SBATCH --mem=64G
#SBATCH --time=02:00:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/model_v3_20261026/performance_A5_R2_v2_%j.log
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
: "${MODEL_V3_METHOD_PUBLICATION_PATH:?Root-verified actual new method/source publication rawref}"
: "${MODEL_V3_METHOD_PUBLICATION_SHA256:?Root-verified actual publication receipt rawSHA}"
CODE=/share/home/zixiao/descriptor_analysis/MFM_model_v3_A_acceptance_v2_candidate_v1
PKG=/share/home/zixiao/descriptor_analysis/runs/model_v3_20261026/performance_A5_R2_GPU_v2_source
PY=/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage43_5090_environment/install_4511929/venv/bin/python
export MODEL_V3_A5_R2_PACKAGE="$PKG"
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=8 MKL_NUM_THREADS=8 OPENBLAS_NUM_THREADS=8
export PYTHONPATH="$CODE/current:$CODE/tools/model_v3:/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps"
export CUDA_VISIBLE_DEVICES="$MODEL_V3_GPU_UUID"
cd "$CODE"
# Metadata/source reads only, no project/Torch import. Alarm is inside the
# original 7200s Slurm envelope; the unchanged supervisor receives 6900s.
"$PY" -u -B - <<'PY'
import hashlib, json, os, re, signal, socket, stat
from pathlib import Path
signal.alarm(180)
base = Path('/share/home/zixiao/descriptor_analysis')
code = base / 'MFM_model_v3_A_acceptance_v2_candidate_v1'
n = base / 'runs/model_v3_20261026'
pkg = Path(os.environ['MODEL_V3_A5_R2_PACKAGE'])
def checked(path, expected, limit=None):
    p = Path(path)
    before = p.stat(follow_symlinks=False)
    if not stat.S_ISREG(before.st_mode) or before.st_uid != 1278 or before.st_nlink != 1:
        raise ValueError('Owned ordinary stable source/metadata required: ' + str(p))
    if limit is not None and before.st_size > limit:
        raise ValueError('Metadata bound exceeded: ' + str(p))
    h = hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda: f.read(65536), b''):
            h.update(block)
    after = p.stat(follow_symlinks=False)
    fields = ('st_dev','st_ino','st_size','st_mtime_ns','st_nlink','st_uid')
    if any(getattr(before,k) != getattr(after,k) for k in fields) or h.hexdigest() != expected:
        raise ValueError('Raw source/metadata binding changed: ' + str(p))
    return p
if os.getuid() != 1278 or not os.environ.get('SLURM_JOB_ID') or int(os.environ.get('SLURM_CPUS_PER_TASK','0')) != 16:
    raise RuntimeError('Owned exact16CPU Slurm allocation required')
if socket.gethostname().split('.')[0] != os.environ['MODEL_V3_EXPECTED_NODE']:
    raise RuntimeError('Actual node differs from fresh Root admission')
if os.environ['MODEL_V3_GPU_UUID'] != 'GPU-c35f2434-9137-9723-1af5-dc69b6295243' or os.environ['MODEL_V3_EXPECTED_NODE'] != 'compute-0-21':
    raise ValueError('This explicit A5 experiment is restricted to the original node21/C35')
paths = []
for key in ('MODEL_V3_OUT','MODEL_V3_RECORD'):
    p = Path(os.environ[key])
    if not p.is_absolute() or p.exists() or p.is_symlink():
        raise ValueError('Fresh absolute path required: ' + key)
    q = p.resolve()
    if not q.is_relative_to(n.resolve()) or q.is_relative_to((n/'native_S_B20k_v3').resolve()):
        raise ValueError('Independent external N output required: ' + key)
    paths.append(q)
if paths[0] == paths[1] or paths[1].is_relative_to(paths[0]) or paths[0].is_relative_to(paths[1]):
    raise ValueError('Child output and management record must be disjoint')
for suffix in ('.jsonl','.storage.json'):
    if Path(str(paths[1])+suffix).exists():
        raise FileExistsError('Fresh supervision sidecar required')
pins_path = checked(pkg/'source_pins.json', os.environ['MODEL_V3_PACKAGE_PINS_SHA256'], 2*1024**2)
pins = json.loads(pins_path.read_text(encoding='utf-8'))
for ref in pins['files']:
    checked(ref['path'], ref['sha256'], 2*1024**2)
d = json.loads((pkg/'dependencies.json').read_text(encoding='utf-8'))
for ref in d['raw_refs'].values():
    checked(ref['path'], ref['sha256'], 2*1024**2)
refs = d['raw_refs']
# Same new source qualification as the Root driver; actual metadata only.
import importlib.util
spec = importlib.util.spec_from_file_location('A5_v2_metadata', pkg/'close_A5_R2_v2.py')
metadata = importlib.util.module_from_spec(spec)
spec.loader.exec_module(metadata)
metadata.verify_package(os.environ['MODEL_V3_PACKAGE_PINS_SHA256'])
metadata.validate_sources()
root_refs = {}
for prefix in ('MODEL_V3_ROOT_ADMISSION','MODEL_V3_QUOTA','MODEL_V3_HOLD','MODEL_V3_METHOD_PUBLICATION'):
    p = checked(os.environ[prefix+'_PATH'], os.environ[prefix+'_SHA256'], 2*1024**2)
    root_refs[prefix] = {'path':str(p),'sha256':os.environ[prefix+'_SHA256'],'bytes':p.stat().st_size}
# Rawref integrity is not fresh resource/quota/reservation authority. Root must
# validate these actual frames semantically before its sole sbatch submission.
print(json.dumps({'status':'SOURCE_AND_CLOSED_METADATA_VERIFIED_NOT_CAPACITY_ACCEPTANCE',
    'job_id':os.environ['SLURM_JOB_ID'],'node':socket.gethostname(),
    'code_sha':d['code_sha'],'public_prereg_sha':d['public_prereg_sha'],
    'root_actual_frames':root_refs,'resident_models':2,'new_A5_A_gate':'NOT_YET_RUN',
    'method_publication_scope':'actual rawref bound; semantic publication authority verified by Root before sole submission'},sort_keys=True))
signal.alarm(0)
PY
# No outer flock. Only paired_a_acceptance owns the shared physical UUID lock.
exec "$PY" -u -B tools/model_v3/run_supervised.py \
  --output-root "$MODEL_V3_OUT" --record "$MODEL_V3_RECORD" \
  --gpu-uuid "$CUDA_VISIBLE_DEVICES" --wall-seconds 6900 \
  --rss-limit-bytes 60129542144 --output-budget-bytes 2147483648 \
  --private-scratch-root "/tmp/mv3n_${SLURM_JOB_ID}" \
  --private-storage-budget-bytes 2147483648 -- \
  "$PY" -u -B tools/model_v3/paired_a_acceptance.py \
  --candidate-options current/configs/model_v3/performance/a00_control.json \
  --performance-execution current/configs/model_v3/performance/a5_logical_batch_chunks_v1.json \
  --performance-execution-sha256 30467f4ce4bfaf6b752fe697ff35614527575d3af799aa07f8b8673605d3ccbb \
  --reference-config "$CODE/workflows/sprime_s/formal_s/B1_seed0_v2.json" \
  --input native_s --seed 0 --workers 8 --max-padded-cost 8000000 \
  --expected-gpu 5090 --code-sha 7ffe8a5557590b1481f4ca74073007f070dc6a50 \
  --prereg-sha 2b4a4df8636e5d65915d535472ba01084ea72dab \
  --shard-snapshot-sha256 d2e1ace1636485cd3dd0106b1177518dd37eb9741919195a9efcd846c1c2242f \
  --acceptance-version v2 \
  --acceptance-rule-document /share/home/zixiao/descriptor_analysis/MFM_model_v3_reporting_v3/docs/model_v3/DECISION_RULES_A_ACCEPTANCE_V2_20261028.md \
  --acceptance-rule-document-sha256 78bd6ac4a4ebfa605cf668217ddd89d5443516d4977101444590321cb16175ae \
  --acceptance-prereg-sha 4f6ba16973ea4a30472c7fb33d3aadec974a4462 \
  --acceptance-rule-publication /share/home/zixiao/descriptor_analysis/runs/model_v3_20261026/A_gradient_rules_v2_publication_actual_v1.json \
  --acceptance-rule-publication-sha256 f5a8980fc0a4f11e4e6f9745f861147a0bd3a786b0da29078157ad91503f94d6 \
  --deterministic-controls --output "$MODEL_V3_OUT"
