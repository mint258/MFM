"""Root-only phase14 continuation: frozen R13 science, explicit PROJECT cwd, actual307 guards."""
import argparse,ast,copy,fcntl,getpass,hashlib,json,os,re,socket,subprocess,time
from pathlib import Path
PROJECT=Path('/share/home/zixiao/descriptor_analysis');ROOT=PROJECT/'runs/phase1_wp5_20261011'
PY='/share/home/zixiao/.conda/envs/chemprop/bin/python';DIRECTORY=ROOT/'submission/recovery_attempt_v14'
MANIFESTS=[ROOT/'submission/submitted_jobs.json',ROOT/'submission/recovery_attempt_v11/submitted_jobs.json',
           ROOT/'submission/startup_replacement_v1/submitted_jobs.json',ROOT/'submission/recovery_attempt_v13/submitted_jobs.json']
COUNTS=[(72,6),(72,6),(69,4),(72,6)]
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
    if len(ids)!=307 or len(set(ids))!=307:raise ValueError('Exact unique prior307 required')
    return references,sorted(ids,key=int)
def prepare():
    from wp5_submit_formal_v13 import validate_current_contract,validate_authority
    old=read(MANIFESTS[-1])['prepared_plan']
    contract=validate_current_contract(ROOT/'configs/production_contract_v6.json',ROOT/'gates/wp5_node_replacement_user_approved.json')
    refs,ids=registry();plan=copy.deepcopy(old)
    if old['version']!=13 or identity(old['production_contract'])!=ref(ROOT/'configs/production_contract_v6.json'):
        raise ValueError('Actual R13 recipe/contract differs')
    plan.update(version=14,status='PREPARED_NOT_SUBMITTED',prior_submissions=refs,prior_job_ids=ids,prior_unique_jobs=307,
                submission_cwd=str(PROJECT),runtime_version=13,coordination_only_version=14)
    for role in ('main','cleanup'):
        for row in plan[role]:
            row['name']=row['name'].replace('wp5_recovery13_','wp5_recovery14_')
            if role=='cleanup':row['afterany_main_names']=[value.replace('wp5_recovery13_','wp5_recovery14_') for value in row['afterany_main_names']]
    if len(plan['main'])!=72 or len(plan['cleanup'])!=6 or Path(plan['script']).name!='wp5_main_v13.sbatch':
        raise ValueError('Unchanged72+6/main13 required')
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
    raw=command(['sacct','-X','-n','-P','-j',','.join(plan['prior_job_ids']),'--format=JobID,User,State,ExitCode'],directory,'fresh307_sacct',60)
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
        raise ValueError('Actual full307 are not yet terminal')
    if any(value in {'OUT_OF_MEMORY','TIMEOUT'} for value in states.values()):
        raise ValueError('Original guide SLURM OOM/TIMEOUT stop must be handled by Root')
    proof={'status':'ACTUAL_FULL307_TERMINAL','registered_jobs_count':307,'states':states,'time':time.time(),
           'source_command':ref(directory/'fresh307_sacct.command.json')}
    atomic(directory/'fresh307_terminal.json',proof);return proof
def verify_evidence(a,plan,contract):
    references,_=registry();proof=read(a.reconciliation_report)
    if proof.get('schema')!='WP5_TERMINAL_SUBSET_RECONCILIATION_APPLY_V3' or proof.get('status')!='APPLIED_AND_VERIFIED':
        raise ValueError('Actual full307 reconciliation apply required')
    for key in ('all_registered_jobs_terminal','plan_was_all307_terminal','full307_terminal_scope_verified','all_applied_rows_verified'):
        if proof.get(key) is not True:raise ValueError('Actual307 reconciliation not closed: '+key)
    if proof.get('registered_jobs_count')!=307 or proof.get('prior_submissions')!=references or proof.get('plan_skipped_count')!=0 or proof.get('protected_jobs')!={} or proof.get('protected_tasks')!=[]:
        raise ValueError('Actual307 reconciliation counts/protected scope differ')
    reconcile_plan=checked(proof['plan'])
    if reconcile_plan.get('protected_jobs')!={} or reconcile_plan.get('protected_tasks')!=[] or reconcile_plan.get('registered_jobs_count')!=307:
        raise ValueError('Actual307 plan still has protected/incomplete scope')
    exports=checked(reconcile_plan['export_roots'])
    from wp5_collect_materialized_permanent_v2 import read_closure
    missing=[entry['run_root'] for entry in exports if not (Path(entry['run_root'])/'export_completion.json').is_file() or read_closure(Path(entry['run_root'])/'export_completion.json')['issues']]
    if missing:raise ValueError('Actual pure export roots still need closure: '+json.dumps(missing))
    smoke=read(a.smoke_report)
    if smoke.get('status')!='CWD_COMPLETE_CHAIN_SMOKE_PASS' or smoke.get('actual_cwd')!=str(PROJECT) or smoke.get('runtime_subprocess_cwd')!=str(PROJECT) or smoke.get('effective_worker_count')!=24 or smoke.get('completed_molecules')!=1 or smoke.get('issues')!=[]:
        raise ValueError('Actual PROJECT-cwd whole-molecule smoke not passed')
    runtime=next(value for name,value in contract['current_runtime'].items() if name=='wp5_runner_v13.py')
    if identity(smoke['runner'])!=identity(runtime) or identity(smoke['production_contract'])!=plan['production_contract'] or identity(smoke['reproduction_package'])!=identity(plan['reproduction_package']):
        raise ValueError('Actual cwd smoke used a different science chain')
    g0=read(a.g0)
    if g0.get('status')!='READY_FOR_ONE_PHASE_FORMAL_SUBMISSION' or identity(g0.get('production_contract',{}))!=plan['production_contract']:
        raise ValueError('Current contract6 G0 required')
    for name in ('G1','G2','G3','G4','G6','REPRO50'):
        if g0['gates'][name]['status']!='PASS':raise ValueError('Actual science/runtime/storage gate not passed: '+name)
    if g0['gates']['G5']['status'] not in ('PASS','PASS_FULL_FIELD_EXTRACTION'):raise ValueError('Current G5 not passed')
    for reference in g0['bindings']:
        if sha(reference['path'])!=reference['sha256']:raise ValueError('Current G0 binding changed: '+reference['path'])
    if g0.get('raw_policy')!=plan['raw_policy'] or plan['raw_policy']!='FAILURES_PLUS_STRATIFIED_RECORD_AUDIT_NO_INPUT':
        raise ValueError('Original no-input audit policy changed')
    directive=ROOT/'submission/recovery_attempt_v12/user_continue_all_calculations_20261012_v1.json'
    decision=read(directive)
    if decision.get('status')!='USER_DIRECTED_CONTINUE' or decision.get('resolve_routine_execution_errors_autonomously') is not True or decision.get('scientific_scope_change_authorized') is not False or decision.get('final200_required') is not True:
        raise ValueError('Actual continuous directive is not bound')
    return {'latest_user_continuous_directive':ref(directive),'queue_reconciliation_report':ref(a.reconciliation_report),
            'cwd_complete_chain_smoke':ref(a.smoke_report),'current_G0':ref(a.g0)}
def startup_probe(a):
    if os.getuid()!=1278 or socket.gethostname().split('.')[0]!='compute-0-20':raise ValueError('Read-only metadata startup probe belongs on actual compute20')
    obj=read(a.phase_receipt);jobs=[str(row['job_id']) for role in ('main','cleanup') for row in obj[role]]
    if obj.get('status')!='ALL_MAIN_AND_SIX_CLEANUP_SUBMITTED' or len(set(jobs))!=78:raise ValueError('Actual phase78 receipt required')
    import wp5_runner_v13 as runtime
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
    if result_path.exists():raise ValueError('Phase14 already has an actual receipt; do not reissue. Inspect its IDs.')
    prepared=DIRECTORY/'prepared_plan_v14.json'
    if read(prepared)!=plan:raise ValueError('Actual prepared14 differs')
    dependencies=verify_evidence(a,plan,contract)
    if STOP.exists() or (ROOT/'control/STOP.json').exists():raise ValueError('Actual guide STOP remains; driver never clears it')
    terminal_evidence=terminal(plan,DIRECTORY)
    authority={'schema':'WP5_ACTUAL_CONTINUOUS_DIRECTIVE_PHASE14_V1','status':'USER_DIRECTED_ONE_PHASE_CONTINUATION',
               'authorization_basis':'ACTUAL_LATEST_USER_CONTINUOUS_DIRECTIVE_UNCHANGED_SCIENCE_CWD_REPAIR',
               'prepared_plan':ref(prepared),'production_contract':plan['production_contract'],
               'prior_submissions':plan['prior_submissions'],**dependencies,'main_jobs':72,'cleanup_jobs':6,
               'submission_cwd':str(PROJECT),'runtime_version':13,'scientific_scope_changed':False,'final200_required':True}
    once(DIRECTORY/'actual_continuation_authority_v14.json',authority)
    result={'status':'ONE_PHASE_SUBMISSION_IN_PROGRESS','prepared_plan':plan,'start':time.time(),'main':[],'cleanup':[],
        'prior_terminal_snapshot':terminal_evidence,'current_authority':ref(DIRECTORY/'actual_continuation_authority_v14.json'),
        'original_submission_sha256':sha(MANIFESTS[0]),'submission_cwd':str(PROJECT),
        'runtime_version':13,'coordination_version':14,'actual_WorkDir_proof':[],'error':None}
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
    print(json.dumps({'status':result['status'],'receipt':ref(result_path),'new_jobs':78,'actual_unique_formal_cost_jobs':385,
        'scientific_completion_claimed':False,'next_step':'Root watch7 plus startup-probe; COMPLETED0 alone is not science evidence'}))
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--check',action='store_true')
    p.add_argument('--prepare',action='store_true');p.add_argument('--submit',action='store_true')
    p.add_argument('--startup-probe',action='store_true');p.add_argument('--phase-receipt',type=Path,default=DIRECTORY/'submitted_jobs.json')
    p.add_argument('--reconciliation-report',type=Path);p.add_argument('--smoke-report',type=Path)
    p.add_argument('--g0',type=Path,default=ROOT/'gates/g0_ready_for_recovery_v14.json')
    a=p.parse_args()
    if a.check:ast.parse(Path(__file__).read_text());print('CONTINUE14_AST_PASS_NOT_STARTED_NO_SUBMISSION');return
    if a.startup_probe:startup_probe(a);return
    if os.getuid()!=1278 or getpass.getuser()!='zixiao' or socket.gethostname().split('.')[0]!='sonmi':raise ValueError('Actual Root zixiao UID1278 on sonmi only')
    os.chdir(PROJECT)
    DIRECTORY.mkdir(parents=True,exist_ok=True)
    with (DIRECTORY/'driver14.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        plan,contract=prepare()
        if a.prepare:
            once(DIRECTORY/'prepared_plan_v14.json',plan);print(json.dumps({'prepared':ref(DIRECTORY/'prepared_plan_v14.json'),'version':14,'runtime_version':13,'main':72,'cleanup':6,'prior_unique_jobs':307,'submission_cwd':str(PROJECT)}));return
        if not a.submit or not a.reconciliation_report or not a.smoke_report:p.error('--prepare or --submit with actual --reconciliation-report --smoke-report required')
        submit(a,plan,contract)
if __name__=='__main__':main()
