"""Root-only phase16 continuation: frozen R14 metadata/runtime with inherited R13 science, explicit PROJECT cwd, actual463 guards."""
import argparse,ast,copy,fcntl,getpass,hashlib,json,os,re,socket,subprocess,time
from pathlib import Path
PROJECT=Path('/share/home/zixiao/descriptor_analysis');ROOT=PROJECT/'runs/phase1_wp5_20261011'
PY='/share/home/zixiao/.conda/envs/chemprop/bin/python';DIRECTORY=ROOT/'submission/recovery_attempt_v16'
MANIFESTS=[ROOT/'submission/submitted_jobs.json',ROOT/'submission/recovery_attempt_v11/submitted_jobs.json',
           ROOT/'submission/startup_replacement_v1/submitted_jobs.json',ROOT/'submission/recovery_attempt_v13/submitted_jobs.json',
           ROOT/'submission/recovery_attempt_v14/submitted_jobs.json',ROOT/'submission/recovery_attempt_v15/submitted_jobs.json']
COUNTS=[(72,6),(72,6),(69,4),(72,6),(72,6),(72,6)]
STOP=ROOT/'STOP_NEW_MOLECULES.json'
def read(path):return json.loads(Path(path).read_text())
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def ref(path):return {'path':str(path),'sha256':sha(path)}
def identity(reference):return {key:reference[key] for key in ('path','sha256')}
def checked(reference):
    if sha(reference['path'])!=reference['sha256']:raise ValueError('Actual reference changed: '+reference['path'])
    return read(reference['path'])
def atomic(path,obj):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_name(path.name+'.'+str(os.getpid())+'.pending')
    with tmp.open('w') as f:json.dump(obj,f,indent=2,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
    os.replace(tmp,path)
def once(path,obj):
    if Path(path).exists():
        if read(path)!=obj:raise ValueError('Preserve existing evidence: '+str(path))
    else:atomic(path,obj)
def registry():
    references=[];ids=[]
    for path,(m,c) in zip(MANIFESTS,COUNTS):
        obj=read(path);entries=obj['main']+obj['cleanup']
        if (len(obj['main']),len(obj['cleanup']))!=(m,c) or obj.get('error') is not None:raise ValueError('Actual previous phase incomplete: '+str(path))
        current=[str(row['job_id']) for row in entries]
        if not all(job.isdigit() for job in current):raise ValueError('Actual integer JobIDs required')
        ids+=current;references.append({**ref(path),'main':m,'cleanup':c,'status':obj['status']})
    if len(ids)!=463 or len(set(ids))!=463:raise ValueError('Exact unique prior463 required')
    return references,sorted(ids,key=int)
def prepare():
    from wp5_submit_formal_v14 import prepare as runtime_prepare
    plan=runtime_prepare(ROOT/'gates/wp5_node_replacement_user_approved.json',ROOT/'configs/production_contract_v7.json')
    contract=checked(plan['production_contract']);refs,ids=registry()
    if plan['version']!=14 or plan['prior_submissions']!=refs or plan['prior_job_ids']!=ids or plan['prior_unique_jobs']!=463:
        raise ValueError('Actual runtime14 freeze and full463 receipt registry differ')
    plan.update(version=16,status='PREPARED_NOT_SUBMITTED',submission_cwd=str(PROJECT),runtime_version=14,coordination_only_version=16)
    for role in ('main','cleanup'):
        for row in plan[role]:
            row['name']=row['name'].replace('wp5_runtime14_','wp5_recovery16_')
            if role=='cleanup':row['afterany_main_names']=[v.replace('wp5_runtime14_','wp5_recovery16_') for v in row['afterany_main_names']]
    if len(plan['main'])!=72 or len(plan['cleanup'])!=6 or Path(plan['script']).name!='wp5_main_v14.sbatch':raise ValueError('Exact72+6/main14 required')
    return plan,contract
def command(argv,directory,name,timeout=600,env=None):
    out=directory/(name+'.stdout');err=directory/(name+'.stderr');started=time.time()
    with out.open('w') as fo,err.open('w') as fe:
        result=subprocess.run(list(map(str,argv)),cwd=str(PROJECT),env=env,stdin=subprocess.DEVNULL,
                              stdout=fo,stderr=fe,timeout=timeout)
    evidence={'argv':list(map(str,argv)),'cwd':str(PROJECT),'returncode':result.returncode,
              'started_epoch':started,'finished_epoch':time.time(),'stdout':str(out),'stderr':str(err)}
    atomic(directory/(name+'.command.json'),evidence)
    if result.returncode:raise RuntimeError('Actual command failed: '+name+' '+str(err))
    return out.read_text()
def terminal(plan,directory):
    raw=command(['sacct','-X','-n','-P','-j',','.join(plan['prior_job_ids']),'--format=JobID,User,State,ExitCode'],directory,'fresh463_sacct',60)
    states={}
    for line in raw.splitlines():
        cells=[v.strip() for v in line.split('|')]
        if len(cells)<4 or cells[0] not in set(plan['prior_job_ids']):continue
        if cells[1]!='zixiao':raise ValueError('Actual previous JobID user differs')
        state=cells[2].split()[0].rstrip('+')
        if cells[0] in states and states[cells[0]]!=state:raise ValueError('Conflicting actual accounting rows')
        states[cells[0]]=state
    terminal_states={'COMPLETED','FAILED','CANCELLED','NODE_FAIL','PREEMPTED','BOOT_FAIL','OUT_OF_MEMORY','TIMEOUT','DEADLINE','REVOKED'}
    if set(states)!=set(plan['prior_job_ids']) or any(value not in terminal_states for value in states.values()):
        raise ValueError('Actual full463 are not yet terminal')
    if any(value in {'OUT_OF_MEMORY','TIMEOUT'} for value in states.values()):
        raise ValueError('Original guide SLURM OOM/TIMEOUT stop must be handled by Root')
    proof={'status':'ACTUAL_FULL463_TERMINAL','registered_jobs_count':463,'states':states,'time':time.time(),
           'source_command':ref(directory/'fresh463_sacct.command.json')}
    atomic(directory/'fresh463_terminal.json',proof);return proof
def required_reference(path,expected):
    if path is None or not Path(path).is_absolute() or not expected or len(expected)!=64:
        raise ValueError('Explicit absolute evidence path and SHA256 required')
    result=ref(path)
    if result['sha256']!=expected:raise ValueError('Explicit actual evidence SHA differs: '+str(path))
    return result

def reconciliation_evidence(plan_path,plan_sha,apply_path,apply_sha):
    plan_ref=required_reference(plan_path,plan_sha);apply_ref=required_reference(apply_path,apply_sha)
    recovery=checked(plan_ref);applied=checked(apply_ref);references,_=registry()
    if applied.get('schema')!='WP5_TERMINAL_SUBSET_RECONCILIATION_APPLY_V3' or applied.get('status')!='APPLIED_AND_VERIFIED' or applied.get('implementation_version')!=10:
        raise ValueError('Actual R10 APPLIED_AND_VERIFIED required')
    for key in ('all_registered_jobs_terminal','plan_was_all463_terminal','full463_terminal_scope_verified','all_applied_rows_verified'):
        if applied.get(key) is not True:raise ValueError('Actual463 R10 apply not closed: '+key)
    if applied.get('registered_jobs_count')!=463 or applied.get('prior_submissions')!=references or applied.get('plan_skipped_count')!=0 or applied.get('protected_jobs')!={} or applied.get('protected_tasks')!=[] or identity(applied['plan'])!=plan_ref:
        raise ValueError('Actual full463 R10 apply scope/readback differs')
    if (recovery.get('schema')!='WP5_TERMINAL_SUBSET_RECONCILIATION_PLAN_V3' or recovery.get('implementation_version')!=10 or recovery.get('registered_jobs_count')!=463 or recovery.get('manifests')!=references or recovery.get('all_registered_jobs_terminal') is not True or recovery.get('plan_was_all463_terminal') is not True or recovery.get('protected_jobs')!={} or recovery.get('protected_tasks')!=[]):
        raise ValueError('Actual full463 R10 plan differs')
    exports=checked(recovery['export_roots'])
    if not isinstance(exports,list) or len({row['run_root'] for row in exports})!=len(exports) or any(row.get('scan_complete') is not True for row in exports):
        raise ValueError('Actual R10 complete unique export-root scope required')
    return applied,recovery,exports

def verify_evidence(a,plan,contract):
    reconciliation_evidence(a.reconciliation_plan,a.reconciliation_plan_sha256,a.reconciliation_report,a.reconciliation_report_sha256)
    declared={'queue_reconciliation_report':required_reference(a.reconciliation_report,a.reconciliation_report_sha256),
        'reconciliation_plan':required_reference(a.reconciliation_plan,a.reconciliation_plan_sha256),
        'pure_export_report':required_reference(a.export_report,a.export_report_sha256),
        'remaining_storage_gate':required_reference(a.g3,a.g3_sha256),'runtime_freeze_gate':required_reference(a.g4,a.g4_sha256)}
    g0=read(a.g0)
    if (g0.get('status')!='READY_FOR_ONE_PHASE_FORMAL_SUBMISSION' or g0.get('coordination_version')!=16 or g0.get('runtime_version')!=14 or g0.get('actual_prior_formal_job_count')!=463 or identity(g0['production_contract'])!=plan['production_contract'] or identity(g0['prepared_plan'])!=ref(DIRECTORY/'prepared_plan_v16.json')):
        raise ValueError('Current contract7/phase16 actual G0 required')
    if any(identity(g0.get(key,{}))!=value for key,value in declared.items()):raise ValueError('Actual R10/E8/G3/G4 explicit evidence differs from closed G0')
    for name in ('G1','G2','G3','G4','G6','REPRO50'):
        if g0['gates'][name]['status']!='PASS':raise ValueError('Actual gate not passed: '+name)
    if g0['gates']['G5']['status'] not in ('PASS','PASS_FULL_FIELD_EXTRACTION'):raise ValueError('Current full-field G5 not passed')
    for reference in g0['bindings']:
        if sha(reference['path'])!=reference['sha256']:raise ValueError('Current G0 binding changed: '+reference['path'])
    if g0.get('raw_policy')!=plan['raw_policy'] or plan['raw_policy']!='FAILURES_PLUS_STRATIFIED_RECORD_AUDIT_NO_INPUT':raise ValueError('Original no-input audit policy changed')
    transfer=g0['scientific_evidence_transfer']
    if transfer.get('new_QM_calls')!=0 or transfer.get('R13_science_sources_SHA_identical') is not True or transfer.get('R14_own_finalize_AST_identical') is not True:
        raise ValueError('Actual R13-to-R14 metadata-only science evidence transfer required')
    directive=ROOT/'submission/recovery_attempt_v12/user_continue_all_calculations_20261012_v1.json';decision=read(directive)
    if decision.get('status')!='USER_DIRECTED_CONTINUE' or decision.get('resolve_routine_execution_errors_autonomously') is not True or decision.get('scientific_scope_change_authorized') is not False or decision.get('final200_required') is not True:raise ValueError('Actual continuous directive not bound')
    return {'latest_user_continuous_directive':ref(directive),**declared,'inherited_cwd_complete_chain_smoke':g0['cwd_complete_chain_smoke'],'current_G0':ref(a.g0)}
def startup_probe(a):
    if os.getuid()!=1278 or socket.gethostname().split('.')[0]!='compute-0-20':raise ValueError('Read-only metadata startup probe belongs on actual compute20')
    obj=read(a.phase_receipt);jobs=[str(row['job_id']) for role in ('main','cleanup') for row in obj[role]]
    if obj.get('status')!='ALL_MAIN_AND_SIX_CLEANUP_SUBMITTED' or len(set(jobs))!=78:raise ValueError('Actual phase78 receipt required')
    import wp5_runner_v14 as runtime
    db=runtime.connection(ROOT/'queue/pending.sqlite',deadline=time.monotonic()+120)
    try:
        marks=','.join('?' for _ in jobs)
        claims=db.execute('SELECT coalesce(sum(claims),0) FROM sessions WHERE job_id IN ('+marks+')',jobs).fetchone()[0]
        science=db.execute("SELECT count(*),coalesce(sum(record_count),0) FROM molecules WHERE owner IN (SELECT session_id FROM sessions WHERE job_id IN ("+marks+")) AND state IN ('COMPLETE','RETRY_PENDING') AND receipt_json IS NOT NULL AND cast(json_extract(receipt_json,'$.context.job_id') AS TEXT) IN ("+marks+") AND json_extract(receipt_json,'$.context.attempt_id')=attempt",jobs+jobs).fetchone()
    finally:db.close()
    print(json.dumps({'status':'NEW_DURABLE_SCI_VERIFIED' if science[0]>0 else ('CLAIMS_STARTED_NO_DURABLE_SCI_YET' if claims>0 else 'NO_NEW_CLAIMS_OR_SCI_YET'),
          'new_phase_claims':claims,'new_durable_molecules':science[0],'new_durable_records':science[1],
          'actual_node':socket.gethostname(),'time':time.time(),'production_queue_written':False}))
def submit(a,plan,contract):
    DIRECTORY.mkdir(parents=True,exist_ok=True)
    result_path=DIRECTORY/'submitted_jobs.json'
    if result_path.exists():raise ValueError('Phase16 already has an actual receipt; do not reissue. Inspect its IDs.')
    prepared=DIRECTORY/'prepared_plan_v16.json'
    if read(prepared)!=plan:raise ValueError('Actual prepared14 differs')
    dependencies=verify_evidence(a,plan,contract)
    if STOP.exists() or (ROOT/'control/STOP.json').exists():raise ValueError('Actual guide STOP remains; driver never clears it')
    terminal_evidence=terminal(plan,DIRECTORY)
    authority={'schema':'WP5_ACTUAL_CONTINUOUS_DIRECTIVE_PHASE16_V1','status':'USER_DIRECTED_ONE_PHASE_CONTINUATION',
               'authorization_basis':'ACTUAL_LATEST_USER_CONTINUOUS_DIRECTIVE_UNCHANGED_SCIENCE_TERMINAL_RECOVERY',
               'prepared_plan':ref(prepared),'production_contract':plan['production_contract'],
               'prior_submissions':plan['prior_submissions'],**dependencies,'main_jobs':72,'cleanup_jobs':6,
               'submission_cwd':str(PROJECT),'runtime_version':14,'scientific_scope_changed':False,'final200_required':True}
    once(DIRECTORY/'actual_continuation_authority_v16.json',authority)
    result={'status':'ONE_PHASE_SUBMISSION_IN_PROGRESS','prepared_plan':plan,'start':time.time(),'main':[],'cleanup':[],
        'prior_terminal_snapshot':terminal_evidence,'current_authority':ref(DIRECTORY/'actual_continuation_authority_v16.json'),
        'original_submission_sha256':sha(MANIFESTS[0]),'submission_cwd':str(PROJECT),
        'runtime_version':14,'coordination_version':16,'actual_WorkDir_proof':[],'error':None}
    atomic(result_path,result)
    g0=read(a.g0);environment=dict(os.environ)
    environment.update(WP5_DICTIONARIES=g0['dictionary_manifest'],WP5_BASELINE=str(ROOT/'configs/pilot_success_baseline.json'),
        WP5_POLICY=plan['raw_policy'],WP5_NODE_AUTHORITY=plan['node_authority'],WP5_AUDIT_MEMBERSHIP=plan['audit_manifest']['path'],
        WP5_REPRODUCTION_PACKAGE=plan['reproduction_package']['path'],WP5_PRODUCTION_CONTRACT=plan['production_contract']['path'])
    try:
        for role in ('main','cleanup'):
            for row in plan[role]:
                if STOP.exists() or (ROOT/'control/STOP.json').exists():raise ValueError('Actual guide STOP appeared during submission')
                environment.update(WP5_TASK_ID=row['task_id'],WP5_MODE=row['mode'])
                argv=[PY,'-B',str(ROOT/'scripts/submit_wp5_job_v2.py'),'--script',plan['script'],'--name',row['name'],
                      '--node',row['node'],'--cpus','24','--memory-gb','32','--time','48:00:00','--kind','quantum','--allow-pending']
                if role=='cleanup':argv+=['--dependency','afterany:'+':'.join(item['job_id'] for item in result['main'] if item['node']==row['node'])]
                text=command(argv,DIRECTORY,row['name']+'_submit',600,environment)
                receipt=json.loads(text.strip().splitlines()[-1]);actual={**row,**receipt}
                result[role].append(actual);atomic(result_path,result)
                raw=command(['scontrol','show','job','-o',receipt['job_id']],DIRECTORY,row['name']+'_workdir',60)
                fields=dict(re.findall(r'(\w+)=([^\s]+)',raw))
                if fields.get('WorkDir')!=str(PROJECT) or fields.get('UserId')!='zixiao(1278)':
                    raise ValueError('Actual Slurm WorkDir/UID differs: '+receipt['job_id'])
                result['actual_WorkDir_proof'].append({'job_id':receipt['job_id'],'WorkDir':fields['WorkDir'],'UserId':fields['UserId'],
                     'command':ref(DIRECTORY/(row['name']+'_workdir.command.json'))})
                atomic(result_path,result);print(json.dumps({'role':role,'job_id':receipt['job_id'],'node':row['node'],'actual_WorkDir':fields['WorkDir']}),flush=True)
        result.update(status='ALL_MAIN_AND_SIX_CLEANUP_SUBMITTED',end=time.time());atomic(result_path,result)
    except BaseException as error:
        result.update(status='PARTIAL_ONE_PHASE_SUBMISSION_REQUIRES_ROOT_RECONCILIATION',error=repr(error))
        atomic(result_path,result);raise
    print(json.dumps({'status':result['status'],'receipt':ref(result_path),'new_jobs':78,'actual_unique_formal_cost_jobs':541,
        'scientific_completion_claimed':False,'next_step':'Root phase16 hourly watch plus startup-probe; COMPLETED0 alone is not science evidence'}))
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--check',action='store_true')
    p.add_argument('--prepare',action='store_true');p.add_argument('--submit',action='store_true')
    p.add_argument('--startup-probe',action='store_true');p.add_argument('--phase-receipt',type=Path,default=DIRECTORY/'submitted_jobs.json')
    for name in ('reconciliation-plan','reconciliation-report','export-report','g3','g4'):
        p.add_argument('--'+name,type=Path);p.add_argument('--'+name+'-sha256')
    p.add_argument('--g0',type=Path,default=ROOT/'gates/g0_ready_for_recovery_v16.json')
    a=p.parse_args()
    if a.check:ast.parse(Path(__file__).read_text());print('CONTINUE16_AST_PASS_NOT_STARTED_NO_SUBMISSION');return
    if a.startup_probe:startup_probe(a);return
    if os.getuid()!=1278 or getpass.getuser()!='zixiao' or socket.gethostname().split('.')[0]!='sonmi':raise ValueError('Actual Root zixiao UID1278 on sonmi only')
    os.chdir(PROJECT)
    DIRECTORY.mkdir(parents=True,exist_ok=True)
    with (DIRECTORY/'driver16.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        plan,contract=prepare()
        if a.prepare:
            once(DIRECTORY/'prepared_plan_v16.json',plan);print(json.dumps({'prepared':ref(DIRECTORY/'prepared_plan_v16.json'),'version':16,'runtime_version':14,'main':72,'cleanup':6,'prior_unique_jobs':463,'submission_cwd':str(PROJECT)}));return
        if not a.submit or any(getattr(a,name.replace('-','_')) is None or getattr(a,name.replace('-','_')+'_sha256') is None for name in ('reconciliation-plan','reconciliation-report','export-report','g3','g4')):p.error('--prepare or --submit with actual explicit evidence paths and SHA256s required')
        submit(a,plan,contract)
if __name__=='__main__':main()
