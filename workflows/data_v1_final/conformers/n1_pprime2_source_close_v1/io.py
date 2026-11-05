"""Fresh central-v2 entry and immutable Main-only terminal evidence readers."""
from __future__ import annotations
import csv,hashlib,io,json,os,pathlib,socket,stat,sys,unittest
from . import contract as C
from workflows.data_v1_final.conformers.n1_pprime2_source_full_v1 import contract as F,io as V,planning

HERE=pathlib.Path(__file__).absolute().parent
FILES=('__init__.py','contract.py','io.py','close_batch.py','reduce.py','test_close.py','README.md','schemas.json')
ref=V.ref;read=V.read;request_ref=V.request_ref;authorized=V.authorized;Budget=V.Budget
write=V.write;json_new=V.json_new;source_check=V.source_check


def admit(script,args,options,stage,required):
    own=[ref(HERE/name) for name in FILES]
    key=C.KEY_CLOSE if stage=='close' else C.KEY_REDUCE
    proof,catalog,admission=V.admit(script,args,options,key,C.scope(stage),'analysis',[*required,*own])
    C.need(proof['uid']==1278 and proof['request']['node']==C.NODE and proof['request']['cpus']==16
        and proof['request']['pilot'] is False and 1200<=proof['request']['wall_seconds']<=172800,
        'FRESH_MAIN_CPU16_ANALYSIS_WITH_FINITE_METADATA_WALL_REQUIRED')
    return proof,catalog,admission


def new_output(path):
    path=pathlib.Path(path)
    C.need(path.is_absolute() and C.BASE in path.parents and '..' not in path.parts and not path.exists()
        and not any(p.is_symlink() for p in (path,*path.parents)),'NEW_OWN_CLOSE_OUTPUT_ONLY')
    path.mkdir(parents=True,exist_ok=False,mode=0o700);V.fsync_directory(path.parent);return path


def tests():
    inherited=V.test10()
    from .test_close import TerminalCloseBoundaries
    result=unittest.TestResult();suite=unittest.defaultTestLoader.loadTestsFromTestCase(TerminalCloseBoundaries);suite.run(result)
    good=result.testsRun==8 and result.wasSuccessful() and not(result.skipped or result.expectedFailures or result.unexpectedSuccesses)
    return {'status':'PASS' if inherited['status']=='PASS' and good else 'FAIL','source_full_inherited_tests':inherited,
        'new_close_test_methods':8,'new_close_tests_run':result.testsRun,
        'failures':[{'test':t.id(),'traceback':error} for t,error in result.failures],
        'errors':[{'test':t.id(),'traceback':error} for t,error in result.errors],
        'skips':[str(row) for row in result.skipped],'expected_failures':[str(row) for row in result.expectedFailures],
        'unexpected_successes':[str(row) for row in result.unexpectedSuccesses],
        'executed_before_scientific_bodies':True,'new_UFF_calls':0,'new_QM_calls':0}


def actual_file(path):
    path=pathlib.Path(path)
    C.need(path.is_absolute() and '..' not in path.parts and not any(p.is_symlink() for p in (path,*path.parents)),
        'LITERAL_NON_SYMLINK_EVIDENCE_PATH_REQUIRED')
    info=path.stat();C.need(stat.S_ISREG(info.st_mode) and info.st_uid==1278,'REGULAR_MAIN_UID1278_EVIDENCE_ONLY')
    C.need(info.st_size<=V.PACKET_CAP,'BOUNDED_ORIGINAL_DURABLE_EVIDENCE_FILE')
    result=ref(path);after=path.stat()
    C.need((info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns,info.st_uid)==(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_uid),
        'EVIDENCE_CHANGED_DURING_FRESH_SHA')
    return result


def observe(path,*,decode=False):
    """Keep malformed/zero-byte evidence visible without making it a valid ref."""
    path=pathlib.Path(path);result={'path':str(path),'exists':path.exists() or path.is_symlink(),'reference':None,'value':None,'error':None}
    if not result['exists']:return result
    try:
        result['reference']=actual_file(path)
        if decode:result['value']=read(result['reference'])
    except Exception as exc:result['error']=repr(exc)
    return result


def claim_owner(observation):
    value=observation['value']
    return str(value.get('job_id','')) if isinstance(value,dict) else ''


def accounts(reference,prepared_job_id,proof=None):
    if proof is not None:authorized(proof,[reference])
    value=read(reference)
    C.need(value.get('endpoint')==C.ENDPOINT and value.get('uid')==1278,'EXPLICIT_MAIN_ENDPOINT_UID_ACCOUNTING_REQUIRED')
    if proof is not None:authorized(proof,[value['raw_sacct_reference']])
    C.need(value.get('schema')=='DATA_V1_PARENT_ACCOUNTING_CLOSURE_V1'
        and value.get('status')=='ACTUAL_PARENT_ACCOUNTING_CLOSED' and value.get('query_returncode')==0,
        'REAL_SUCCESSFUL_PARENT_ACCOUNTING_QUERY_REQUIRED')
    raw=read_text(value['raw_sacct_reference']);rows={}
    for row in csv.DictReader(io.StringIO(raw),delimiter='|'):
        jid=row.get('JobIDRaw',row.get('JobID',''))
        if not jid.isdecimal():continue
        if row.get('UID'):C.need(row['UID']=='1278','FOREIGN_ALPHA_OR_OTHER_UID_PARENT_NOT_MAIN')
        C.need(jid not in rows,'DUPLICATE_RAW_PARENT_ACCOUNTING');rows[jid]=row
    parents={str(row['job_id']):row for row in value['parents']}
    C.need(len(parents)==len(value['parents']) and set(rows)==set(parents),'EXACT_ALL_RAW_AND_DECLARED_PARENT_SET')
    C.require_parents(parents,parents)
    for jid,row in parents.items():
        raw=rows[jid]
        C.need(raw['State'].split()[0]==row['state'] and raw['ExitCode']==row['exit_code']
            and int(raw['AllocCPUS'])==int(row['alloc_cpus']) and int(raw['ElapsedRaw'])==int(row['elapsed_raw_seconds']),
            'DECLARED_PARENT_DIFFERS_FROM_ACTUAL_SACCT')
        C.need(int(row['alloc_cpus'])>=0 and int(row['elapsed_raw_seconds'])>=0,'NONNEGATIVE_ACTUAL_PARENT_COST')
    C.require_parents([str(prepared_job_id)],parents);prepared=parents[str(prepared_job_id)]
    C.need(prepared['state']=='COMPLETED' and prepared['exit_code']=='0:0' and int(prepared['alloc_cpus'])==16,
        'ORIGINAL_FULL_PREPARATION_REQUIRES_ACTUAL_CPU16_C0')
    return value,parents,rows


def read_text(reference):
    source_check(reference);C.need(reference['bytes']<=V.TASK_CAP,'SMALL_TERMINAL_ACCOUNTING_TEXT_ONLY')
    with pathlib.Path(reference['path']).open('rb') as stream:body=stream.read(V.TASK_CAP+1)
    C.need(len(body)==reference['bytes'] and hashlib.sha256(body).hexdigest()==reference['sha256'],'RAW_ACCOUNTING_TEXT_SHA_CHANGED')
    return body.decode()


def request_pin(request,path):
    hits=[r for group in ('source_references','data_references') for r in request.get(group,[]) if r['path']==str(path)]
    C.need(hits and all(r==hits[0] for r in hits),'EXACT_REGISTERED_TRANSITIVE_INPUT_REFERENCE_REQUIRED:'+str(path))
    return hits[0]


def registration(request_reference,submission_reference,prepared_reference,batch_reference,batch_review_reference,pilot_review_reference,prepared,batch,parents):
    request=read(request_reference);submission=read(submission_reference)
    C.need(submission['schema']=='CPU_AUTO_MEMORY_SUBMISSION_V1' and submission['uid']==1278
        and submission['sbatch_returncode']==0 and submission['request']==request and submission['request_reference']==request_reference,
        'ACTUAL_MAIN_REGISTERED_REQUEST_AND_SUCCESSFUL_SUBMISSION_REQUIRED')
    jid=str(submission['job_id']);C.need(jid.isdecimal(),'REAL_NUMERIC_PARENT_ID_REQUIRED');C.require_parents([jid],parents)
    C.need(request['scope_key']==F.SCOPE_KEY and request['scope_parameters']==F.SCOPE and request['kind']=='conformer'
        and request['pilot'] is False and request['cpus']==16 and request['node']==C.NODE
        and request['memory_policy']=='SLURM_DEFAULT_UNSPECIFIED' and request['scope']['mode']=='FULL_SOURCE_AFTER_PROFILE',
        'ONLY_ORIGINAL_REGISTERED_MAIN_FULL_SOURCE_PRODUCER_ACCEPTED')
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.contract import PY
    expected_options=('prepared','prepare-accounting','batch','batch-review','pilot-review','root-preflight','quota-provider-review','ledger-root','output')
    argv=request['execution_argv'];C.need(len(argv)==3+2*len(expected_options) and argv[:3]==[PY,'-B',str(F.V4.parent/'n1_pprime2_source_full_v1/run_batch.py')],
        'EXACT_ACTUAL_ORIGINAL_PRIMARY_PRODUCER_REQUIRED')
    values={}
    for i,name in enumerate(expected_options):
        C.need(argv[3+2*i]=='--'+name,'EXACT_COMPLETE_REGISTERED_PRODUCER_OPTION_ORDER_REQUIRED')
        path=pathlib.Path(argv[4+2*i]);C.need(path.is_absolute() and '..' not in path.parts,'LITERAL_REGISTERED_PRODUCER_LOCATORS_ONLY');values[name]=path
    C.need(str(values['prepared'])==prepared_reference['path'] and str(values['batch'])==batch_reference['path']
        and str(values['batch-review'])==batch_review_reference['path'] and str(values['pilot-review'])==pilot_review_reference['path']
        and values['ledger-root']==V.LEDGER and str(values['root-preflight'])==request['startup_proof_path'],
        'REGISTERED_PREPARED_BATCH_REVIEWS_LEDGER_AND_PROOF_PATH_BINDING_REQUIRED')
    for value in (prepared_reference,batch_reference,batch_review_reference,pilot_review_reference):C.same_sha(request_pin(request,value['path']),value)
    for path in (V.HERE/name for name in V.FILES):C.same_sha(request_pin(request,path),ref(path))
    quota_ref=request_pin(request,values['quota-provider-review'])
    F.finite_batch_review(batch_review_reference,prepared_reference,batch_reference,batch,quota_ref,pilot_review_reference)
    out=values['output'];C.need(V.BASE in out.parents and not any(p.is_symlink() for p in (out,*out.parents)),'EXACT_REGISTERED_SOURCE_OUTPUT_NAMESPACE')
    C.need(batch['source_population_authority']==prepared['source_population_authority'] and batch['source_task_roster']==prepared['source_task_roster'],
        'REGISTERED_BATCH_MUST_BELONG_TO_FROZEN_SOURCE_POPULATION')
    actual=parents[jid]
    if actual.get('node'):C.need(actual['node'].split('.')[0]==C.NODE,'ACTUAL_REGISTERED_PARENT_NODE_MUST_BE_MAIN13')
    return {'request':request,'submission':submission,'job_id':jid,'output_root':out,'request_reference':request_reference,
        'submission_reference':submission_reference,'actual_parent':actual,'producer_final_receipt_required':False}


def identity_claim(claim,key,task,jid,out):
    C.need(claim['schema']=='N1_PPRIME2_ONCE_ATTEMPT_STARTED_V2' and claim['task_key']==key
        and claim['molecule_id']==task['meta']['molecule_id'] and claim['seed']==F.proposed_seed(task['meta']['molecule_id'])
        and claim['uid']==1278 and str(claim['job_id'])==jid and pathlib.Path(claim['output_root'])==out
        and claim['node'].split('.')[0]==C.NODE and claim['automatic_retry'] is False
        and type(claim['pid']) is int and claim['pid']>0 and type(claim['pid_start_ticks']) is int and claim['pid_start_ticks']>0,
        'ACTUAL_MAIN_CANONICAL_CLAIM_KEY_SEED_JOB_AND_PARENT_IDENTITY_REQUIRED')
    C.same_sha(claim['core_reference'],ref(V.HERE/'core.py'))


def identity_dispatch(dispatch,key,task_reference,claim_reference,batch_reference,jid,claim):
    C.need(dispatch['schema']=='N1_SOURCE_FULL_DISPATCH_INTENT_V1' and dispatch['task_key']==key
        and dispatch['task_reference']==task_reference and dispatch['once_claim_reference']==claim_reference
        and dispatch['batch_reference']==batch_reference and str(dispatch['job_id'])==jid and dispatch['pid']==claim['pid']
        and dispatch['automatic_retry'] is False,'ACTUAL_REGISTERED_DISPATCH_CHAIN_REQUIRED')


def identity_start(start,key,task,claim_reference,dispatch_reference,jid,claim):
    runtime=start['runtime']
    C.need(start['schema']=='N1_SOURCE_FULL_WORKER_STARTED_V1' and start['task_key']==key
        and start['molecule_id']==task['meta']['molecule_id'] and start['once_claim_reference']==claim_reference
        and start['dispatch_intent_reference']==dispatch_reference and start['parent_pid']==claim['pid']
        and str(runtime['job_id'])==jid and runtime['uid']==1278 and runtime['node']==C.NODE
        and runtime['boot_id']==claim['boot_id'] and type(runtime['pid']) is int and runtime['pid']>0
        and type(runtime['start_ticks']) is int and runtime['start_ticks']>0
        and runtime['allocated_cpus']==16 and runtime['memory_policy']=='SLURM_DEFAULT_UNSPECIFIED'
        and runtime['memory_requested'] is False and runtime['seed_domain']==F.SEED_DOMAIN
        and runtime['rdkit_version']=='2025.09.5','OBSERVED_REAL_MAIN_WORKER_START_REQUIRED_NO_INFERENCE')


def validate_packet(task,reference,prepared_reference,prepared,jid,start):
    packet=planning.packet_readback(task,reference) # unchanged scientific readback/geometry math
    C.need(packet['schema']=='N1_PPRIME2_PILOT_GENERATION_PACKET_V2' and packet['runtime']==start['runtime']
        and packet['runtime']['uid']==1278 and packet['runtime']['node']==C.NODE and str(packet['runtime']['job_id'])==jid
        and packet['prepared_manifest_reference']==prepared_reference
        and packet['source_population_authority_reference']==prepared['source_population_authority']
        and packet['catalog_reference']==ref(V.HERE/'frozen_sources.json')
        and packet['authority_references']==task['authority_references']
        and packet['summary']['seed']==F.proposed_seed(task['meta']['molecule_id']),
        'EXACT_MAIN_PACKET_SOURCE_PREPARED_BASELINE_AUTHORITY_AND_SEED_REQUIRED')
    if packet['supplement'] is not None:
        C.need(packet['supplement']['seed']==F.proposed_seed(task['meta']['molecule_id'])
            and packet['summary']['Pprime_actual_records']==2,'REAL_SECOND_HAS_ORIGINAL_ACTUAL_SEED_AND_TWO_ROWS')
    return packet


def prepared_inputs(proof,reference,pilot_review_reference):
    value=read(reference);F.source_review(pilot_review_reference)
    C.need(value['schema']=='N1_PPRIME2_SOURCE_FULL_PREPARED_V1'
        and value['status']=='ACTUAL_FULL_SOURCE_TASKS_FROZEN_NO_GENERATION'
        and value['mother_count']==5105 and value['eligible_count']==value['selected_count']==4631
        and value['imported_count']==32 and value['new_attempt_count']==4599 and value['batch_count']==72
        and value['common'] is False and value['pilot_membership'] is False and value['production_membership'] is False
        and value['physical_int64_integration_frozen'] is False and value['catalog']==ref(V.HERE/'frozen_sources.json')
        and value['science_cost_review_reference']==pilot_review_reference and value['once_ledger_root']==str(V.LEDGER),
        'EXACT_FROZEN_SOURCE_PREPARATION_AND_ORIGINAL32_SCIENCE_REVIEW_REQUIRED')
    authorized(proof,[value[k] for k in ('batch_index','source_population_authority','imported32','source_task_roster','mother_inventory','role_status_usable_audit')])
    authority=read(value['source_population_authority'])
    C.need(authority['schema']=='N1_PPRIME2_SOURCE_FULL_POPULATION_AUTHORITY_V1'
        and authority['status']=='ORIGINAL_SOURCE_FULL_POPULATION_CLOSED_NO_FINAL_MEMBERSHIP'
        and authority['mother_count']==authority['expected_mother_count']==5105 and authority['eligible_source_baselines']==4631
        and authority['common'] is False and authority['production_membership'] is False,'NO_FINAL_COMMON_AUTHORITY')
    return value


def frozen_task(row,prepared_reference,prepared):
    """Only preparation-owned exact task/base refs; called after pure fixtures."""
    for name in ('task_reference','baseline_reference'):
        path=pathlib.Path(row[name]['path'])
        C.need(path.parent.parent==pathlib.Path(prepared_reference['path']).parent and '..' not in path.parts,
            'ONLY_EXACT_FROZEN_PREPARATION_TASK_AND_BASELINE_LEAVES')
    task=read(row['task_reference']);base=read(row['baseline_reference']);F.validate_task(task,prepared['source_population_authority'])
    C.need(task['task_key']==row['task_key'] and task['meta']['molecule_id']==row['molecule_id']
        and task['baseline_geometry_id']==row['baseline_geometry_id'] and base['original_row']==task['existing_conformers'][0]
        and base['validation']['status']=='ORIGINAL_SOURCE_AND_BASELINE_VALIDATED_NO_NEW_UFF'
        and base['validation']['atomic_numbers']==task['source_atomic_numbers'],'ORIGINAL_SOURCE_BASELINE_TASK_BYTES_CHANGED')
    return task
