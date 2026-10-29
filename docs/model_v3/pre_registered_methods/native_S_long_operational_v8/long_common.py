"""Shared operational primitives; importing never reserves/submits/trains."""
from __future__ import annotations
from pathlib import Path
import os
import sys
import importlib

HERE=Path(__file__).absolute().parent
V8=HERE.parent/'native_s_profile_launch_v8'
V8_PIN='07357343417a9dbd774e207804b0f02067266fa39704cdc1bd47d90ef3e24405'
existing=sys.modules.get('common')
if existing is not None and Path(existing.__file__).absolute()!=V8/'common.py':
    raise RuntimeError('Foreign bare common namespace; use a fresh process')
sys.path.insert(0,str(V8))
from common import (PROJECT,N,OLD,V2,V2_PIN,RUNTIME,PYTHON,DEPS,CODE,TREE,PUBLIC,GPU,NODE,LOCK,
    OUTER,CHILD,PRIVATE,RSS,require,binding,read,read_ref,write,replace_feed,digest,actual,
    root_identity,terminal_rows,require_C0,verify_package as frozen_verify,fresh)

MEMBERS=((0,'fp32'),(0,'bf16'),(1,'fp32'),(1,'bf16'))
CHILD_SECONDS=6900
SUPERVISOR_SECONDS=7100
SLURM_SECONDS=7200


def environment(*,cpu=False,contract=None):
    value={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','OMP_NUM_THREADS':'8','MKL_NUM_THREADS':'8',
        'OPENBLAS_NUM_THREADS':'8','NUMEXPR_NUM_THREADS':'8','PYTEST_DISABLE_PLUGIN_AUTOLOAD':'1',
        'CUDA_VISIBLE_DEVICES':'' if cpu else GPU,
        'PYTHONPATH':':'.join(map(str,[HERE,V8,V2,RUNTIME/'current',RUNTIME/'current/tests',
            RUNTIME/'tools/model_v3',RUNTIME/'workflows/sprime_s/scripts',DEPS]))}
    if contract is not None:value['MODEL_V3_NATIVE_S_RUNTIME_CONTRACT']=str(contract)
    return value


def verify(expected=None):
    ref=binding(HERE/'source_pins.json')
    if expected is not None:require(ref['sha256']==expected,'Long launcher source manifest differs')
    manifest=read_ref(ref)
    for row in manifest['files']:
        path=Path(row['path']);require(not path.is_absolute() and '..' not in path.parts,'Relative source leaf required')
        found=binding(HERE/path)
        require(found['bytes']==row['bytes'] and found['sha256']==row['sha256'],'Long launcher source changed')
    if manifest.get('dependency_manifest'):
        for dependency_ref in read(HERE/manifest['dependency_manifest'])['references']:
            require(binding(dependency_ref['path'])==dependency_ref,'Frozen external source/evidence reference changed')
    frozen_verify(V8,V8_PIN);frozen_verify(V2,V2_PIN)
    return ref,manifest


def endpoint(update):
    require(type(update) is int and 0<=update<20000,'Advancing native B update required')
    return min(20000,(update//1000+1)*1000)


def slot_layout(phase,slot):
    require(type(slot) is int and 1<=slot<=108,'Finite1..108 attempt slot required')
    phase=Path(phase);root=phase/'slots'/f'slot_{slot:03d}'
    return dict(root=root,management=root/'management',child=root/'child',
        log=phase/'logs'/f'slot_{slot:03d}.log')


def initial_roots(phase):
    phase=Path(phase)
    rows=[dict(path=str(phase/'control'),kind='management',type='directory',must_exist=True)]
    for slot in range(1,109):
        layout=slot_layout(phase,slot)
        for key,kind,entry in (('child','training','directory'),('management','external_guard','directory'),
                ('log','external_guard','file')):
            rows.append(dict(path=str(layout[key]),kind=kind,type=entry,must_exist=False))
    for seed,precision in MEMBERS:
        rows.append(dict(path=str(phase/'lineages'/f'seed{seed}_{precision}'),kind='management',
            type='directory',must_exist=False))
    return dict(schema='model_v3_long_run_initial_roots_v1',roots=rows)


def policy():
    return dict(schema='model_v3_long_run_policy_v1',segment_bytes=OUTER,segment_seconds=SLURM_SECONDS,
        durable_bytes=128<<30,metadata_bytes=512<<20,metadata_records=32768,managed_roots=512,
        inode_limit=100000,quota_max_age_seconds=90,checkpoint_bytes=384<<20,
        counts=dict(launch_attempts=108,successful_segments=96,failed_attempts=12,checkpoint_attempts=216,
            complete_checkpoints=216,successful_panels=0,failed_panels=0,wsd_children=0,events=0,ack_attempts=0))


def operation_modules():
    """Bind THIS process, not merely a future subprocess environment.

    Only external operation modules are imported here. No Torch, model class,
    input constructor, namespace clearing or package __path__ editing occurs.
    """
    expected={'common':V8/'common.py','runtime_origin':V2/'runtime_origin.py',
        'root_coverage':V8/'root_coverage.py','native_s_storage':V2/'native_s_storage.py',
        'profile_lifecycle':V2/'profile_lifecycle.py','evidence_graph':V2/'evidence_graph.py',
        'resources':V8/'resources.py','root_phase':V8/'root_phase.py','operational':V8/'operational.py'}
    def check(name,module):
        actual=module.__dict__.get('__file__')
        require(isinstance(actual,str) and Path(actual).is_absolute()
            and Path(actual).absolute()==expected[name],'Foreign operational module origin: '+name)
        origin=getattr(module.__dict__.get('__spec__'),'origin',None)
        require(origin is None or Path(origin).absolute()==expected[name],
            'Foreign operational spec origin: '+name)
    for name in expected:
        if name in sys.modules:check(name,sys.modules[name])
    # V8 must precede V2 so the already-proven task_scratch extension wins.
    # Own long_* names remain distinct and script/HERE remains on sys.path.
    sys.path[:0]=[str(V8),str(V2)]
    for name in ('runtime_origin','root_coverage','profile_lifecycle','native_s_storage'):
        module=importlib.import_module(name);check(name,module)
    adapter=sys.modules['native_s_storage'];coverage=sys.modules['root_coverage']
    require(adapter.root_coverage is coverage,'Frozen NativeV2 coverage class/module identity differs')
    return sys.modules['runtime_origin'],coverage,adapter


def import_runtime(contract_path,*,metadata_only=False):
    runtime_origin,coverage,adapter=operation_modules()
    contract=runtime_origin.read_contract(contract_path,metadata_only=metadata_only,allow_candidate_profile=False)
    require((contract['combined_commit'],contract['combined_tree'],Path(contract['runtime_root']).absolute())
        ==(CODE,TREE,RUNTIME),'Single actual immutable runtime identity differs')
    if not metadata_only:
        require(contract['status']=='PUBLISHED_IMMUTABLE_RUNTIME' and contract['production_20k_allowed'] is True,
                'Published full-regression runtime required for native B')
    os.environ['MODEL_V3_NATIVE_S_RUNTIME_CONTRACT']=str(contract_path)
    runtime_origin.configure_paths(contract)
    # Use the exact explicit task_scratch compatibility extension actually
    # exercised by1331/1332, not the unchanged V2 legacy scratch literal.
    require(Path(coverage.__file__).absolute()==V8/'root_coverage.py'
        and adapter.root_coverage is coverage,'Frozen V8 coverage module identity differs')
    return contract,adapter
