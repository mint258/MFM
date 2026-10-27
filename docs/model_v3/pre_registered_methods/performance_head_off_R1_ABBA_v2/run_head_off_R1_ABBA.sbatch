#!/bin/bash
#SBATCH --job-name=model_v3_head_off_R1_ABBA
#SBATCH --partition=all
#SBATCH --cpus-per-task=16
#SBATCH --mem=64G
#SBATCH --time=02:00:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/model_v3_20261026/performance_head_off_R1_ABBA_%j.log
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
: "${MODEL_V3_HEAD_OFF_R2_CLOSURE_PATH:?Actual head-off20/500 Root closure required}"
: "${MODEL_V3_HEAD_OFF_R2_CLOSURE_SHA256:?Explicit actual qualification rawSHA}"
: "${MODEL_V3_METHOD_PUBLICATION_PATH:?Actual new head-off R1 publication required}"
: "${MODEL_V3_METHOD_PUBLICATION_SHA256:?Actual publication rawSHA}"
CODE=/share/home/zixiao/descriptor_analysis/MFM_model_v3_performance_integration_v1
PKG=/share/home/zixiao/descriptor_analysis/runs/model_v3_20261026/performance_head_off_R1_ABBA_GPU_v2_source
PY=/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage43_5090_environment/install_4511929/venv/bin/python
export MODEL_V3_HEAD_OFF_R1_ABBA_PACKAGE="$PKG"
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=8 MKL_NUM_THREADS=8 OPENBLAS_NUM_THREADS=8
export PYTHONPATH="$CODE/current:$CODE/tools/model_v3:/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps"
export CUDA_VISIBLE_DEVICES="$MODEL_V3_GPU_UUID"
cd "$CODE"
# Metadata/source reads only, no project/Torch import. Alarm is inside the
# original 7200s Slurm envelope; the unchanged supervisor receives 6900s.
"$PY" -u -B - <<'PY'
import hashlib, importlib.util, json, os, re, signal, socket, stat
from pathlib import Path
signal.alarm(180)
base = Path('/share/home/zixiao/descriptor_analysis')
code = base / 'MFM_model_v3_performance_integration_v1'
n = base / 'runs/model_v3_20261026'
pkg = Path(os.environ['MODEL_V3_HEAD_OFF_R1_ABBA_PACKAGE'])
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
if not re.fullmatch(r'GPU-[0-9A-Fa-f-]+', os.environ['MODEL_V3_GPU_UUID']):
    raise ValueError('One full physical UUID required')
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
pub = json.loads(Path(refs['publication']['path']).read_text(encoding='utf-8'))
qa = json.loads(Path(refs['CPU_99_Root_closure']['path']).read_text(encoding='utf-8'))
pack = json.loads(Path(refs['packaging_Root_closure']['path']).read_text(encoding='utf-8'))
if (pub['local_code_sha'], pub['public_commit_sha'], pub['tree_sha']) != (d['code_sha'],d['public_prereg_sha'],d['tree_sha']):
    raise ValueError('Exact tested/public tree changed')
if pub['actual_readback'][d['branch']] != d['public_prereg_sha'] or pub['actual_public_git_tree'] != d['tree_sha'] or pub['force'] or pub['main_modified']:
    raise ValueError('Actual publication readback differs')
if pub['Root_CPU_closure'] != refs['CPU_99_Root_closure'] or pub['packaging_Root_closure'] != refs['packaging_Root_closure']:
    raise ValueError('Publication closure rawref differs')
if qa['status'] != 'ACTUAL_C0_99_TESTS_FOUR_GROUPS_AND_REPOSITORY_CHECKER' or qa['counts'] != {'tests':99,'passed':99,'failures':0,'errors':0,'skipped':0}:
    raise ValueError('Actual99-test closure required')
if pack['status'] != 'ACTUAL_C0_METADATA_ATTRIBUTE_ONLY_MODEL13_SOURCES_AND99_TESTS_PRESERVED' or pack['CPU_99_test_closure'] != refs['CPU_99_Root_closure']:
    raise ValueError('Actual packaging closure required')
if pack['actual_parent_sacct'] != '4523705|zixiao|COMPLETED|0:0|4|16|compute-0-12':
    raise ValueError('Original packaging actualC0 binding differs')
# Exact current full tested projection, including the four fixed outside helpers.
# Root also checks current HEAD/tree/clean before submission; no Git on compute.
for path, sha in pack['full_current_source_map'].items():
    checked(path, sha)
for ref in pub['source_files']:
    checked(code/ref['path'], ref['sha256'])
opt = json.loads(Path(refs['candidate_options']['path']).read_text(encoding='utf-8'))
if any(type(opt[k]) is not bool or opt[k] is not v for k,v in
       (('distance_checkpointing',True),('backbone_checkpointing',True),('head_checkpointing',False))):
    raise ValueError('Explicit head-off tuple distance/backbone/head=True/True/False required')
if opt['precision'] != 'fp32' or opt['fused_adamw'] or opt['tf32'] or opt['compile_backbone']:
    raise ValueError('This fixed manual control does not change precision/optimizer/TF32/compile')
if json.loads(Path(refs['manual_execution']['path']).read_text(encoding='utf-8')) != {'schema':'model_v3_performance_execution_v1','checkpoint_policy':'manual'}:
    raise ValueError('Fixed first-observation manual execution required')
root_refs = {}
for prefix in ('MODEL_V3_ROOT_ADMISSION','MODEL_V3_QUOTA','MODEL_V3_HOLD','MODEL_V3_HEAD_OFF_R2_CLOSURE','MODEL_V3_METHOD_PUBLICATION'):
    p = checked(os.environ[prefix+'_PATH'], os.environ[prefix+'_SHA256'], 2*1024**2)
    root_refs[prefix] = {'path':str(p),'sha256':os.environ[prefix+'_SHA256'],'bytes':p.stat().st_size}
# Rawref integrity is not fresh resource/quota/reservation authority. Root must
# validate these actual frames semantically before its sole sbatch submission.
position = os.environ['MODEL_V3_ABBA_POSITION']
role = os.environ['MODEL_V3_ABBA_ROLE']
series = os.environ['MODEL_V3_ABBA_SERIES_ID']
if position not in ('1','2','3','4') or role != ('reference','candidate','candidate','reference')[int(position)-1]:
    raise ValueError('Exact original A/B/B/A role/position required')
if series != d['series_id'] or series != 'A03_head_off_R1_C35_9e16_v1':
    raise ValueError('This fixed head-off standalone series identity differs')
if os.environ['MODEL_V3_EXPECTED_NODE'] != 'compute-0-21' or os.environ['MODEL_V3_GPU_UUID'] != d['gpu_uuid']:
    raise ValueError('This independent four-member family is fixed to the actual C35 physical card')
# Bind the actual new gate explicitly; old all-on is not numeric qualification.
helper = refs['head_off_R2_metadata_closer']
spec = importlib.util.spec_from_file_location('head_off_R1_bound_R2_gate', helper['path'])
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
qualification = root_refs['MODEL_V3_HEAD_OFF_R2_CLOSURE']
numeric = module.validate_closed_gate(qualification, require_current_sources=False)
cfg = json.loads(Path(numeric['artifact_refs']['configuration.json']['path']).read_bytes())
if cfg['candidate'] != opt or numeric['resolved_checkpoint_flags'] != {'distance':True,'backbone':True,'head':False}:
    raise ValueError('Actual numeric qualification is not the declared head-off option')
print(json.dumps({'status':'SOURCE_AND_CLOSED_METADATA_VERIFIED_NOT_CAPACITY_ACCEPTANCE',
    'job_id':os.environ['SLURM_JOB_ID'],'node':socket.gethostname(),
    'code_sha':d['code_sha'],'public_prereg_sha':d['public_prereg_sha'],
    'root_actual_frames':root_refs,'resident_models':1,'role':role,'abba_position':int(position),'series_id':series,'actual_head_off_R2_qualification':qualification,'operational_package_publication_semantics_checked_by_Root':True},sort_keys=True))
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
  --candidate-options current/configs/model_v3/performance/a03_head_off.json \
  --performance-execution current/configs/model_v3/performance/a1_manual_capacity_observation_v1.json \
  --performance-execution-sha256 7cabbd4a0300d551154ffb9bcbed5466fc9886d0eb886a1ae37ee3e7f70db46e \
  --reference-config "$CODE/workflows/sprime_s/formal_s/B1_seed0_v2.json" \
  --input native_s --seed 0 --workers 8 --max-padded-cost 8000000 \
  --expected-gpu 5090 --code-sha 9e16d4c5a15c558051499d3dc0c55c9bd3787734 \
  --prereg-sha 8147f44baa1ea1ecc3822af7affd0a95401ed248 \
  --shard-snapshot-sha256 d2e1ace1636485cd3dd0106b1177518dd37eb9741919195a9efcd846c1c2242f \
  --role "$MODEL_V3_ABBA_ROLE" --abba-position "$MODEL_V3_ABBA_POSITION" \
  --series-id "$MODEL_V3_ABBA_SERIES_ID" \
  --deterministic-controls --output "$MODEL_V3_OUT"
