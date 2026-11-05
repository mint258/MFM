"""Exact closed-long-sync fixture scope; original supervisor/child stay unchanged."""
from __future__ import annotations
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import socket
import stat
import sys
import time

HERE=Path(__file__).absolute().parent
BASE=Path('/share/home/zixiao/descriptor_analysis')
N=BASE/'runs/model_v3_20261026'
PYTHON=BASE/'docs/phase1/evidence/stage43_5090_environment/install_4511929/venv/bin/python'
ORIGINAL= N/'native_closed030_long_sync_v1_source'


def need(ok,message):
    if not ok:raise ValueError(message)


def raw_ref(path,maximum=2 << 20):
    path=Path(path).absolute();a=path.lstat()
    need(stat.S_ISREG(a.st_mode) and a.st_uid==os.getuid() and a.st_nlink==1
        and a.st_size<=maximum and not path.is_symlink(),'Owned bounded ordinary metadata/source required')
    raw=path.read_bytes();b=path.lstat()
    need((a.st_dev,a.st_ino,a.st_size,a.st_mtime_ns)==(b.st_dev,b.st_ino,b.st_size,b.st_mtime_ns),'Metadata/source changed during read')
    return {'path':str(path),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()},raw


def read(path,sha=None):
    ref,raw=raw_ref(path)
    need(sha is None or ref['sha256']==sha,'Exact explicit metadata/source SHA differs')
    def pairs(items):
        out={}
        for k,v in items:
            need(k not in out,'Duplicate metadata key');out[k]=v
        return out
    return json.loads(raw,object_pairs_hook=pairs,
        parse_constant=lambda v:(_ for _ in ()).throw(ValueError('Nonfinite metadata constant'))),ref


def verify_sources():
    expected=os.environ['MODEL_V3_LONGSYNC_FIXTURE_SOURCE_SHA']
    need(re.fullmatch('[a-f0-9]{64}',expected) is not None,'Actual frozen fixture manifest SHA required')
    pins,pin=read(HERE/'source_pins.json',expected)
    need(pins['schema']=='native_closed_long_sync_fixture_source_pins_v1','Fixture source schema differs')
    files=pins['files'];want={'supervise_fixture.py','native_long_sync_fixture_census.py',
        'native_long_sync_fixture_checks.py','dependencies.json','sync_cpu.sbatch','README.md'}
    need(len(files)==len(want) and {r['file'] for r in files}==want,'Exact six fixture source leaves required')
    refs=[pin]
    for row in files:
        need(Path(row['file']).name==row['file'],'Flat source leaf required')
        ref,_=raw_ref(HERE/row['file']);need(ref['bytes']==row['bytes'] and ref['sha256']==row['sha256'],'Fixture source changed')
        refs.append(ref)
    deps,_=read(HERE/'dependencies.json')
    for original in deps['source_refs']:
        ref,_=raw_ref(original['path']);need(ref==original,'Original sync/supervision dependency changed');refs.append(ref)
    original_sb=Path(deps['original_sbatch']['path']).read_bytes()
    before=b'$task_project/runs/model_v3_20261025/run_cpu_supervised_v3.py'
    after=b'$task_project/runs/model_v3_20261026/native_closed030_long_sync_fixture_v1_source/supervise_fixture.py'
    need(original_sb.count(before)==1 and (HERE/'sync_cpu.sbatch').read_bytes()==original_sb.replace(before,after),
        'SBATCH must be original bytes with only the supervision entry replaced')
    from native_long_sync_fixture_census import verify_derivation
    verify_derivation(deps['runtime_monitor']['path'])
    return deps,refs


def inputs():
    need(os.getuid()==1278 and os.environ.get('SLURM_JOB_ID','').isdigit()
        and os.environ.get('SLURM_JOB_PARTITION')=='cpu' and os.environ.get('SLURM_CPUS_PER_TASK')=='16'
        and os.environ.get('CUDA_VISIBLE_DEVICES')=='','Owned CPU16-only Slurm allocation required')
    job=os.environ['SLURM_JOB_ID'];node=socket.gethostname().split('.')[0]
    need(node==os.environ['MODEL_V3_EXPECTED_NODE'] and re.search(r'/job_'+job+r'(?:/|$)',Path('/proc/self/cgroup').read_text()),
        'Actual local Slurm node/kernel cgroup differs')
    manifest,mref=read(os.environ['MODEL_V3_LONGSYNC_MANIFEST'],os.environ['MODEL_V3_LONGSYNC_MANIFEST_SHA'])
    request,rref=read(os.environ['MODEL_V3_LONGSYNC_REQUEST'],os.environ['MODEL_V3_LONGSYNC_REQUEST_SHA'])
    original,oref=read(ORIGINAL/'source_pins.json',os.environ['MODEL_V3_LONGSYNC_SOURCE_SHA'])
    output=Path(os.environ['MODEL_V3_LONGSYNC_OUTPUT']).absolute()
    need(manifest['schema']=='native_closed_long_sync_manifest_v1'
        and request['schema']=='native_closed_long_sync_request_v1' and request['mode']=='batch'
        and request['eligible_manifest']==mref and request['source_manifest']==oref
        and request['job_output']==str(output) and output.parent==N
        and 1<=len(manifest['runs'])<=3 and request['selected_run_ids']==[r['run_id'] for r in manifest['runs']],
        'Only the explicit real closed-long manifest/request/output is a fixture scope')
    return request,{'manifest':mref,'request':rref,'original_source_manifest':oref,'job_id':job,'node':node,'output':str(output)}


def fixture_counter(output,policy_file):
    from native_long_sync_fixture_census import owned_output_bytes
    output=Path(output).absolute();policy_file=Path(policy_file).absolute()
    def count(root):
        need(Path(root).absolute()==output,'Fixture census cannot measure an arbitrary output')
        info=policy_file.lstat()
        need(stat.S_ISREG(info.st_mode) and info.st_uid==os.getuid() and info.st_nlink==1
            and info.st_size<=128 << 10,'Owned bounded fixture policy required')
        # Sibling policy is new output too; count it once in the original joint cap.
        return owned_output_bytes(output)+info.st_size
    return count


def load_supervisor(path):
    spec=importlib.util.spec_from_file_location('original_cpu_supervisor_for_closed_long_fixture',path)
    module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
    return module


def main():
    begin=time.monotonic();deps,source_before=verify_sources();request,bound=inputs()
    args=sys.argv[1:]
    def arg(name):
        need(args.count(name)==1 and args.index(name)+1<len(args),'Exact supervisor argument required: '+name)
        return args[args.index(name)+1]
    output=Path(arg('--output-root')).absolute();record=Path(arg('--record')).absolute()
    need(output==Path(bound['output']) and record==Path(str(output)+'.supervisor.json')
        and arg('--wall-seconds')=='3300' and arg('--rss-limit-bytes')=='12884901888'
        and '--output-budget-bytes' not in args,'Original CPU3300s/RSS12GiB/joint2GiB envelope required')
    need(args.count('--')==1,'One exact supervised child command required')
    command=args[args.index('--')+1:]
    expected=[str(PYTHON),'-u','-B',str(ORIGINAL/'sync_selected_long.py'),'--request',bound['request']['path'],
        '--request-sha256',bound['request']['sha256'],'--pins-sha256',bound['original_source_manifest']['sha256'],'--output',str(output)]
    need(command==expected,'Original frozen sync child argv must remain exact')
    need(not os.path.lexists(output) and not os.path.lexists(record),'Fresh retry output/supervision records required')
    need(not os.environ.get('PYTEST_PLUGINS') and os.environ.get('PYTEST_DISABLE_PLUGIN_AUTOLOAD')=='1'
        and os.environ.get('PYTEST_ADDOPTS')=='-o tmp_path_retention_policy=failed','Only the explicit same-job fixture plugin is admitted')
    os.environ['PYTEST_PLUGINS']='native_long_sync_fixture_checks'
    old_pythonpath=os.environ.get('PYTHONPATH','')
    os.environ['PYTHONPATH']=str(HERE)+(os.pathsep+old_pythonpath if old_pythonpath else '')
    policy_file=record.with_suffix('.fixture_policy.json')
    policy={'schema':'native_closed_long_sync_metadata_fixture_policy_v1','status':'BOUND_BEFORE_ORIGINAL_SUPERVISOR',
        **bound,'declared_fixture_subtrees':['metadata_tmp'],'sources':source_before,
        'original_supervisor':deps['strict_supervisor'],'original_child_argv':command,
        'scope':'ONLY_METADATA_TMP_LINKS_ARE_NO_FOLLOW_FIXTURES',
        'production_WandB_rules_unchanged':True,'private_storage_census_modified':False,
        'shared_and_private_limits_bytes':2 << 30,'rss_limit_bytes':12 << 30,'original_wall_limit_seconds':3300,
        'selfchecks':'pytest_sessionstart inside original metadata4; original JUnit count stays4',
        'new_policy_sibling_counted_in_joint_output':True,'scientific_acceptance':False}
    encoded=(json.dumps(policy,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
    need(len(encoded)<=128 << 10,'Bounded fixture policy required')
    with policy_file.open('xb') as stream:stream.write(encoded);stream.flush();os.fsync(stream.fileno())
    module=load_supervisor(deps['strict_supervisor']['path'])
    module.owned_output_bytes=fixture_counter(output,policy_file)
    # Include metadata, original-module imports and counter installation in setup.
    spent=math.ceil(time.monotonic()-begin)
    need(0<=spent<=30,'Bounded adapter startup exceeded30s')
    effective=3300-spent;args[args.index('--wall-seconds')+1]=str(effective)
    sys.argv=[sys.argv[0],*args]
    try:return module.main()
    finally:
        # End-of-run source verification is outside the original supervisor clock.
        _,source_after=verify_sources()
        need(source_before==source_after,'Fixture adapter/original dependency changed during this job')


if __name__=='__main__':raise SystemExit(main())
