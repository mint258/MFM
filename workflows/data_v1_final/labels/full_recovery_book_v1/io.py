"""Small controls and strict actual-account/admission; DATA only after fixtures."""
from __future__ import annotations
import csv,datetime,hashlib,io,json,os,socket,stat,sys,time,unittest
from pathlib import Path
from . import contract as C
from workflows.data_v1_final.labels.full_timeout_inventory_v1 import io as OLD
load=OLD.load;pin=OLD.pin;require=OLD.require;write_new=OLD.write_new
frame=OLD.frame;reader=OLD.reader;hash_stream=OLD.hash_stream;read_json=OLD.read_json;SoftStop=OLD.SoftStop


def sources():return [pin(C.HERE/n) for n in C.FILES]


def actual(refs,module,jid=None):
    account=load(require(refs['accounting']));raw=OLD.small(require(refs['raw'])).decode('utf-8-sig');proof=load(require(refs['proof']))
    req=load(require(proof['request_reference']));sub=load(require(refs['submission']))
    C.need(account['schema']=='DATA_V1_PARENT_ACCOUNTING_CLOSURE_V1' and account['status']=='ACTUAL_PARENT_ACCOUNTING_CLOSED'
      and account['endpoint']=='202.38.247.57:22' and account['uid']==1278 and account['query_returncode']==0
      and account.get('raw_sacct_reference',account.get('raw_sacct_ref'))==refs['raw'] and req==proof['request']==sub['request']
      and sub['sbatch_returncode']==0 and str(sub['job_id'])==str(proof['job_id']),'REAL_REGISTERED_MAIN_PARENT_CHAIN')
    ps=[p for p in account['parents'] if str(p['job_id'])==str(proof['job_id'])]
    C.need(len(ps)==1,'ONE_EXACT_PARENT');p=ps[0]
    C.need((jid is None or str(p['job_id'])==str(jid)) and p['state']=='COMPLETED' and p['exit_code']=='0:0' and p['alloc_cpus']==16,
      'ACTUAL16_C0_REQUIRED_TIMEOUT_ZERO_EXIT_NEVER_C0')
    rows=[r for r in csv.DictReader(raw.splitlines(),delimiter='|') if r.get('JobIDRaw')==str(p['job_id'])]
    C.need(len(rows)==1 and [rows[0][k] for k in ('UID','State','ExitCode','ElapsedRaw','AllocCPUS')]
      ==['1278','COMPLETED','0:0',str(p['elapsed_raw_seconds']),'16'],'RAW_ACTUAL_C0_PARENT_FIELDS')
    C.need(req['execution_argv'][:4]==[C.PY,'-B','-m',module] and proof['request_reference']==sub['request_reference'],
      'EXACT_PRODUCER_MODULE_AND_REQUEST_REFERENCE')
    C.need(proof['schema']=='FRESH_CPU_AUTO_MEMORY_EXECUTION_ADMISSION_V1' and proof['uid']==1278
      and proof['request']['node']=='compute-0-17' and str(proof['boot_id']).strip(),'ACTUAL_MAIN17_PRODUCER_IDENTITY')
    opt='--plan' if module.endswith(('.seed','.full_timeout_inventory_v1.run')) else '--config'
    argv=req['execution_argv'];C.need(len(argv)==10 and argv[4]==opt and argv[6]=='--startup-proof' and argv[8]=='--output'
      and argv[7]==refs['proof']['path'],'EXACT_HISTORICAL_PRIMARY_FULL_OPTIONS')
    declared={r['path']:r for r in req['source_references']}
    C.need(argv[5] in declared,'ACTUAL_CONFIG_OR_PLAN_EXPLICIT_SOURCE_PIN');require(declared[argv[5]])
    args=req['execution_argv'];C.need(args.count('--output')==1 and Path(args[args.index('--output')+1])==Path(refs['receipt']['path']).parent,
      'ACTUAL_RECEIPT_ROOT_AND_REGISTERED_OUTPUT')
    return p,req,proof


def account_refs(receipt,proof,submission,accounting):
    a=load(accounting)
    return {'receipt':pin(receipt),'proof':pin(proof),'submission':pin(submission),'accounting':pin(accounting),'raw':a.get('raw_sacct_reference',a.get('raw_sacct_ref'))}


def fixtures(path):
    from .test_recovery import Boundaries
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(Boundaries);C.need(suite.countTestCases()==6,'EXACT_SIX_RECOVERY_BOUNDARIES')
    text=io.StringIO();r=unittest.TextTestRunner(stream=text,verbosity=2).run(suite)
    good=r.testsRun==6 and r.wasSuccessful() and not(r.skipped or r.expectedFailures or r.unexpectedSuccesses)
    ref=write_new(path,{'status':'PASS' if good else 'FAIL_NO_DATA','tests_run':r.testsRun,'transcript':text.getvalue(),
      'source_reference':pin(C.HERE/'test_recovery.py'),'scientific_DATA_opened':False})
    C.need(good,'PURE_RECOVERY_BOUNDARIES_BEFORE_DATA');return ref


def admit(proof_path,config_path,key,parameters,cap,wall,required):
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.runtime import require_startup
    proof=require_startup(proof_path,expected_kind='analysis',expected_source=Path(sys.modules['__main__'].__file__),
      expected_scope_key=key,expected_scope_parameters=parameters,required_references=[pin(config_path),*required])
    req=proof['request'];C.need(req['pilot'] is False and req['cpus']==16 and req['node']=='compute-0-17' and req['wall_seconds']==wall
      and req['estimated_peak_output_bytes']==cap and req['memory_policy']=='SLURM_DEFAULT_UNSPECIFIED','EXACT_RECOVERY_CPU16_NOMEM_WALL_CAP')
    declared={r['path']:r for r in req['source_references']}
    for r in sources():C.need(declared.get(r['path'])==r,'EXACT_ALL_TEN_NEW_SOURCE_PINS');require(r)
    return proof


def start(proof,root,resource,cap,wall):
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.slurm_format import fields
    review=load(require(resource));C.budget(review)
    C.need(proof['request']['queue_authority_reference']==review['resource_authority_reference'],'ROOT_CURRENT_RESOURCE_AUTHORITY')
    extra=review['other_storage_scope_unwritten_cap_upper_bound_bytes']
    C.need(proof['account_free_bytes']>=200000000000+cap+extra,'FRESH_ACCOUNT_QUOTA_CURRENT_STAGE_OTHER_CAPS_200GB')
    start_time=datetime.datetime.fromisoformat(fields(proof['job_metadata'])['StartTime']).timestamp()
    C.need(0<=time.time()-start_time<wall-120,'FRESH_ALLOCATION_START_AND_DRAIN_MARGIN')
    from workflows.data_v1_final.labels.source_status_cpu_auto_memory_v1.resource_runtime import start_observer
    start_observer(proof,{'memavailable_soft_floor_bytes':4<<30,'resource_evidence_local_cap_bytes':64<<20,
      'resource_evidence_output':str(root)+'_resource_observation','scope_key':proof['request']['scope_key']})
    return start_time+wall-120


def data_ref(path,deadline,expected=None):
    p=Path(path);st=frame(p.lstat())
    with reader(p,st,deadline) as (f,current):n,h=hash_stream(f,deadline)
    r={'path':str(p),'bytes':n,'sha256':h}
    if expected is not None:C.need(r=={k:expected[k] for k in ('path','bytes','sha256')},'ACTUAL_DATA_SHA_CHANGED')
    return r,current


def json_data(ref,deadline,cap=64<<20):
    p=Path(ref['path']);value,_=read_json(p,frame(p.lstat()),deadline,cap,known=ref);return value


def new_root(path):
    p=Path(path).absolute();C.need(C.RUN/'artifacts/labels/source_status_v1' in p.parents and C.OLD not in p.parents and p!=C.OLD
      and not any(q.is_symlink() for q in (p,*p.parents)),'NEW_EXTERNAL_RECOVERY_OUTPUT')
    p.mkdir(parents=True,exist_ok=False,mode=0o700);return p