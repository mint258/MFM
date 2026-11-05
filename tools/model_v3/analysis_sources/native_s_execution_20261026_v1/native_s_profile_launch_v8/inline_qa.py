"""CPU-hidden metadata preflight inside the real model PROFILE20 allocation.

It is never claimed to be an independent CPU parent C0. The same GPU job must
subsequently complete the requested real Native profile for a Root C0 scope.
"""
from __future__ import annotations
import resource
import subprocess
import time
import xml.etree.ElementTree as ET
from common import *

def verdict(returncode,counts,before,after,expected):
    require(returncode==0 and counts==dict(tests=expected,failures=0,errors=0,skipped=0)
        and before and before==after,'Inline metadata QA failed/skipped/changed; model profile forbidden')
    return 'CHILD_QA_PASS_PENDING_OUTER_TERMINAL'

def ensure(args):
    submission=binding(args.submission)
    require(submission['sha256']==args.submission_sha256,'Root submission raw SHA changed before QA')
    frame=read_ref(submission);mode=frame['launch_validation_mode']
    if mode=='INDEPENDENT_CPU_C0':return frame['actual_launch_QA']
    require(mode=='PROFILE_LAUNCH_VALIDATION' and frame['actual_launch_QA']['status']=='NOT_YET_EXECUTED',
        'Explicit pending inline validation mode required')
    job=os.environ['SLURM_JOB_ID'];require(frame['actual_sbatch_job_id']==job,'Inline QA allocation differs')
    directory=Path(args.phase)/f'job_{job}'/'management'
    manifest,pins=verify_package();contract=read(args.runtime_contract)
    expected=read(HERE/'CPU_test_request.json')['expected_parameterized_cases_from_static_review']
    paths=[HERE/x['path'] for x in pins['files']]+[HERE/'source_pins.json',Path(args.runtime_contract)]
    paths.extend(RUNTIME/x['relative_path'] for x in contract['files'])
    paths.extend(Path(x['path']) for x in read(HERE/'dependency_pins.json')['references'])
    def snapshot():return {str(path):binding(path)['sha256'] for path in sorted(set(paths))}
    before=snapshot();xml=directory/'launch_metadata_QA.xml';stdout=directory/'launch_metadata_QA.stdout';stderr=directory/'launch_metadata_QA.stderr'
    command=[str(PYTHON),'-B','-m','pytest',str(HERE/'test_launch_contract.py'),'-q','-p','no:cacheprovider',
        '-o','tmp_path_retention_policy=failed',
        '--junitxml='+str(xml),'--basetemp='+str(directory/'qa_tmp')]
    env=runtime_environment(cpu=True,contract=args.runtime_contract)
    require(env['MODEL_V3_STORAGE_BINDINGS_PATH']==os.environ['MODEL_V3_STORAGE_BINDINGS_PATH'],
        'Inline QA must retain actual supervisor private roots')
    # The tests create only tiny owned metadata fixtures. Each log/XML/fixture
    # file is independently kernel-bounded; no raw model/data is accessed.
    def limit_files():resource.setrlimit(resource.RLIMIT_FSIZE,(1<<20,1<<20))
    started=time.time();failure=None;code=None;counts=None
    try:
        with stdout.open('xb') as out,stderr.open('xb') as err:
            result=subprocess.run(command,stdin=subprocess.DEVNULL,stdout=out,stderr=err,env=env,
                timeout=120,preexec_fn=limit_files)
        code=result.returncode
        root=ET.parse(xml).getroot();suites=[root] if root.tag=='testsuite' else list(root.findall('testsuite'))
        counts={key:sum(int(suite.get(key,0)) for suite in suites) for key in ('tests','failures','errors','skipped')}
        after=snapshot();status=verdict(code,counts,before,after,expected)
    except BaseException as error:
        status='FAILED_MODEL_PROFILE_NOT_STARTED';failure=dict(type=type(error).__name__,message=str(error))
        try:after=snapshot()
        except BaseException as secondary:
            after={};failure['after_snapshot_error']=dict(type=type(secondary).__name__,message=str(secondary))
    ref=write(directory/'inline_launch_QA.json',dict(schema='native_S_inline_launch_metadata_QA_v1',status=status,
        mode=mode,job_id=job,actual_argv=command,returncode=code,counts=counts,sources_before=before,sources_after=after,
        sources_unchanged=before==after,started_unix=started,completed_unix=time.time(),
        actual_environment=dict(CUDA_VISIBLE_DEVICES=env['CUDA_VISIBLE_DEVICES'],PYTHONPATH=env['PYTHONPATH'],
            MODEL_V3_STORAGE_BINDINGS_PATH=env['MODEL_V3_STORAGE_BINDINGS_PATH']),
        metadata_only=True,Native_model_started=False,independent_CPU_parent_C0_claimed=False,actual_parent_C0=None,
        xml=None if not xml.exists() else binding(xml),stdout=binding(stdout),stderr=binding(stderr),failure=failure,
        production_20k_allowed=False))
    import runtime_monitor
    require(runtime_monitor.owned_output_bytes(directory)<=16<<20,'Inline QA management exceeds original96MiB reserve')
    require(failure is None,'Inline metadata QA failed before model; original receipt retained')
    return ref
