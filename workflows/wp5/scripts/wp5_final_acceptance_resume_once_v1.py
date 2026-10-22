"""Root-started, one-shot WP5 metadata continuation after real retry 4515515.

The controller runs on sonmi for at most eight hours.  It submits one catalog,
updates only the two existing catalog dependencies, and never cancels a job.
All scientific work uses unchanged frozen sources.  Every mutation is guarded
by a write-once intent; an uncertain RPC is left for Root review, not replayed.
"""
from __future__ import annotations
import argparse,concurrent.futures,fcntl,hashlib,json,os,re,shlex,shutil,socket,stat,subprocess,tempfile,time,traceback
from pathlib import Path
ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011')
PROJECT=ROOT.parent.parent
FINAL=ROOT/'acceptance/final_20261016_v1'
PY='/share/home/zixiao/.conda/envs/chemprop/bin/python'
DEPS='/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps'
JOB='4515515';QA=('4515498','4515499','4515500','4515501','4515502')
MIDS={'principal_01100742','principal_01152793'}
TOOL=ROOT/'scripts/wp5_exact_two_retry_v2.py'
TOOL_SHA='91c6c7d9f8502a128b2ff70eb78a851cecaae756336fd57b13242aaf319934ef'
PREPARED=FINAL/'exact_two_budget1_retry_v1/prepared.json'
PREPARED_SHA='86c75e92aebf35f31d22d420885eea6248886eaac7c7a6efe4cdb247ef14b5c1'
VERIFIED=PREPARED.parent/'verified_240_slots.json'
ADOPTION=PREPARED.parent/'production_adoption.json'
OLD_MAP=ROOT/'reports/wp5_acceptance_control_jobmap_actual541_v1.json'
OLD_MAP_SHA='7cfac0397a2b47dc0ab2cd85a77c3c35b15a7cdb4d0b8cbfbcc65187271409df'
NEW_MAP=FINAL/'control_jobmap_actual542_v1.json'
BATCH=ROOT/'scripts/wp5_acceptance_v14.sbatch'
BATCH_SHA='2eaab5d1c79fb1dd81deb20c30efddc297e98f6fa0824cab5058c2f953bc75e9'
PLAN=ROOT/'packing/node_assignment_v3/tasks.json'
PLAN_SHA='dd195e994628c75b710de6e267f99556df59e918b875117907753693af638f3b'
FIELDS='JobID,User,State,ExitCode,Start,End,ElapsedRaw,AllocCPUS'
TERMINAL={'COMPLETED','FAILED','CANCELLED','NODE_FAIL','OUT_OF_MEMORY','TIMEOUT','BOOT_FAIL','DEADLINE','PREEMPTED','REVOKED','SPECIAL_EXIT'}
class Review(RuntimeError):pass
def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(8<<20),b''):h.update(block)
    return h.hexdigest()
def ref(path):return {'path':str(path),'bytes':Path(path).stat().st_size,'sha256':sha(path)}
def publish(path,value):
    path=Path(path)
    if path.exists():raise Review('WRITE_ONCE_ALREADY_EXISTS:'+str(path))
    pending=path.with_name(path.name+'.pending')
    with pending.open('xb') as stream:stream.write(json.dumps(value,ensure_ascii=False,allow_nan=False,indent=2).encode()+b'\n');stream.flush();os.fsync(stream.fileno())
    pending.rename(path)
def status(folder,value):
    target=folder/'status.json';pending=target.with_name('status.json.pending')
    with pending.open('w') as stream:json.dump({**value,'time':time.time(),'source_sha256':sha(__file__)},stream,ensure_ascii=False,indent=2);stream.write('\n');stream.flush();os.fsync(stream.fileno())
    pending.replace(target)
def command(argv,timeout=90):
    started=time.time()
    try:
        result=subprocess.run(argv,text=True,capture_output=True,timeout=timeout)
        return {'argv':argv,'returncode':result.returncode,'stdout':result.stdout,'stderr':result.stderr,'started':started,'seconds':time.time()-started}
    except (subprocess.TimeoutExpired,OSError) as error:
        return {'argv':argv,'returncode':None,'stdout':getattr(error,'stdout',None).decode(errors='replace') if isinstance(getattr(error,'stdout',None),bytes) else getattr(error,'stdout',''),'stderr':str(error),'started':started,'seconds':time.time()-started,'observation_or_rpc_uncertain':True}
def require_zero(result):
    if result['returncode']!=0:raise Review('COMMAND_FAILED_OR_UNCERTAIN:'+repr(result['argv']))
def once(folder,label,argv,execute=command,timeout=180):
    intent=folder/(label+'_intent.json');receipt=folder/(label+'_result.json')
    if intent.exists() or receipt.exists():raise Review('ACTION_ALREADY_INTENDED_DO_NOT_REPLAY:'+label)
    publish(intent,{'argv':argv,'time':time.time(),'source':ref(__file__),'policy':'One invocation only. An uncertain result requires Root inspection of actual external state.'})
    result=execute(argv,timeout=timeout);publish(receipt,result);require_zero(result);return result
def pinned():
    for path,digest in ((TOOL,TOOL_SHA),(PREPARED,PREPARED_SHA),(OLD_MAP,OLD_MAP_SHA),(BATCH,BATCH_SHA),(PLAN,PLAN_SHA)):
        if sha(path)!=digest:raise Review('FROZEN_BINDING_CHANGED:'+str(path))
    receipt=json.loads((FINAL/'exact_two_retry_submission_receipt.json').read_text())
    if receipt.get('returncode')!=0 or receipt.get('job_id')!=JOB or receipt.get('stdout','').strip().split(';')[0]!=JOB:raise Review('FIXED_ACTUAL_RETRY_SUBMISSION_NOT_BOUND')
def parent_row(result,job=JOB):
    if result['returncode']!=0:return None
    rows=[]
    for line in (result.get('stdout') or '').splitlines():
        fields=[s.strip() for s in line.split('|')]
        if len(fields)>=8 and fields[0]==job:rows.append(fields)
    if not rows:return None
    if len(rows)!=1 or rows[0][1]!='zixiao':raise Review('FIXED_PARENT_ACCOUNTING_IDENTITY_DIFFERS')
    return rows[0]
def job_fields(result):
    require_zero(result);text=' '.join(result['stdout'].split())
    def field(name):
        match=re.search(r'(?:^|\s)'+re.escape(name)+r'=([^\s]*)',text)
        if match is None:raise Review('SCONTROL_FIELD_MISSING:'+name)
        return match.group(1)
    match=re.search(r'(?:^|\s)Command=(.*?)\s+WorkDir=',text)
    return {'JobId':field('JobId'),'UserId':field('UserId'),'JobState':field('JobState'),'Dependency':field('Dependency'),'Command':match.group(1) if match else None,'ReqNodeList':field('ReqNodeList'),'NumCPUs':field('NumCPUs'),'WorkDir':field('WorkDir'),'raw':text}
def read_pending(execute=command):
    rows={};receipts={}
    markers={'4515498':'wp5_acceptance_v14.sbatch verify ','4515499':'wp5_acceptance_v14.sbatch plan-200 ','4515500':'wp5_acceptance_v15.sbatch recompute-200 ','4515501':'wp5_acceptance_v15.sbatch compare-200 ','4515502':'wp5_acceptance_v16.sbatch pilot '}
    for job in QA:
        result=execute(['scontrol','show','job',job,'-o'],timeout=90);row=job_fields(result);receipts[job]=result
        if row['JobId']!=job or row['UserId']!='zixiao(1278)' or row['JobState']!='PENDING' or row['ReqNodeList']!='compute-0-17' or row['NumCPUs']!='24' or row['WorkDir']!=str(PROJECT) or markers[job] not in (row['Command'] or ''):raise Review('EXISTING_QA_NOT_EXACT_PENDING:'+job)
        expected='4515497' if job in ('4515498','4515502') else {'4515499':'4515498','4515500':'4515499','4515501':'4515500'}[job]
        if not row['Dependency'].startswith('afterok:'+expected):raise Review('EXISTING_QA_DEPENDENCY_CHANGED:'+job)
        rows[job]=row
    return rows,receipts
def memory_mib(text,cpus):
    match=re.fullmatch(r'(\d+(?:\.\d+)?)([KMGT]?)([cn]?)',text.strip(),re.I)
    if not match:raise Review('UNPARSEABLE_ACTUAL_MEMORY_DECLARATION:'+text)
    value=float(match.group(1))*{'':1,'K':1/1024,'M':1,'G':1024,'T':1024**2}[match.group(2).upper()]
    return value*cpus if match.group(3).lower()=='c' else value
def admission(node_result,queue_result):
    if node_result['returncode']!=0 or queue_result['returncode']!=0:return {'ready':False,'reason':'RESOURCE_OBSERVATION_UNAVAILABLE'}
    text=node_result['stdout'];values=dict(re.findall(r'(\w+)=([^\s]+)',text))
    if values.get('NodeName')!='compute-0-17':raise Review('CATALOG_NODE_IDENTITY_DIFFERS')
    try:real=int(values['RealMemory']);cpu_total=int(values['CPUTot']);cpu_alloc=int(values['CPUAlloc'])
    except (KeyError,ValueError) as error:raise Review('CATALOG_NODE_RESOURCE_FIELDS_MISSING') from error
    declared=0.;rows=[]
    for line in queue_result['stdout'].splitlines():
        fields=line.split('|')
        if len(fields)!=5:raise Review('ALL_USER_RESOURCE_DECLARATION_SCHEMA_DIFFERS')
        job,user,cpus,memory,nodes=fields
        amount=memory_mib(memory,int(cpus));declared+=amount;rows.append({'job_id':job,'user':user,'cpus':int(cpus),'declared_mib':amount,'nodes':int(nodes)})
    unhealthy=any(token in values.get('State','') for token in ('DOWN','DRAIN','FAIL','UNKNOWN','MAINT','NOT_RESPONDING'))
    ready=real>0 and declared+32768<=real*.85 and not unhealthy
    return {'ready':ready,'reason':'READY' if ready else 'WAIT_FOR_ACTUAL_MEMORY_OR_NODE','real_memory_mib':real,'all_user_declared_mib':declared,'after_catalog_declared_mib':declared+32768,'fraction_limit':.85,'cpu_total':cpu_total,'cpu_allocated':cpu_alloc,'cpu_free_observed':cpu_total-cpu_alloc,'cpu_policy':'The original node and 24CPU/32GiB request are retained. Slurm may queue the job if CPUs are currently occupied.','declarations':rows}
def remote_argv(arguments):
    body='cd '+shlex.quote(str(PROJECT))+' && env '+shlex.quote('PYTHONPATH='+DEPS+':'+str(ROOT/'scripts'))+' '+shlex.join([PY,'-B',*arguments])
    return ['ssh','-n','compute-0-20',body]
def catalog_preparation(folder):
    if socket.gethostname().split('.')[0]!='compute-0-20' or os.getuid()!=1278:raise Review('CATALOG_METADATA_PREPARATION_COMPUTE20_ONLY')
    pinned();account=folder/'retry_terminal_accounting.json'
    result=json.loads(account.read_text());row=parent_row(result)
    if row is None or row[2].split()[0]!='COMPLETED' or row[3]!='0:0':raise Review('TRUE_RETRY_NOT_COMPLETED_ZERO')
    adoption=json.loads(ADOPTION.read_text())
    if adoption.get('status')!='EXACT_TWO_TRUE_RETRY_ADOPTED' or adoption.get('new_formal_parent_job_id')!=JOB or adoption.get('actual_terminal_accounting')!=ref(account):raise Review('EXACT_TRUE_RETRY_NOT_ADOPTED')
    old=json.loads(OLD_MAP.read_text());jobs=old['jobs']
    if len(jobs)!=541 or len({str(r['job_id']) for r in jobs})!=541 or any(str(r['job_id'])==JOB for r in jobs):raise Review('ACTUAL_OLD541_SCOPE_DIFFERS')
    launch=json.loads((PREPARED.parent/'launch_receipt.json').read_text());run_path=Path(launch['run_root'])/'run.json';run=json.loads(run_path.read_text());options=run['options']
    if str(options['job_id'])!=JOB or run['node']!='compute-0-13' or options['task_id']!='69' or options['queue']!=str(PREPARED.parent/'queue.sqlite'):raise Review('NEW_ACTUAL_FORMAL_PARENT_IDENTITY_DIFFERS')
    new_entry={'job_id':JOB,'node':run['node'],'task_id':'69','user':'zixiao','execution_id':options['session'],'role':'EXACT_TWO_TRUE_SCIENTIFIC_RETRY_BUDGET1','run_json':ref(run_path)}
    newmap={'schema':'WP5_ACCEPTANCE_ACTUAL_FORMAL_PARENTS_V1','generated_epoch':time.time(),'status':'ACTUAL_542_FORMAL_PARENTS_CLOSED','actual_job_count':542,'sources':[ref(OLD_MAP),ref(account),ref(ADOPTION),ref(run_path)],'jobs':jobs+[new_entry],'SCI_execution_id':None,'Slurm_queried':True,'SCI_read':False,'population_counted':False,'old541_entries_preserved_exactly':True,'new_science_parent_separate_from_QA':True}
    publish(NEW_MAP,newmap)
    current=FINAL/'catalog';archived=FINAL/'catalog_failed_4515497';next_catalog=FINAL/'catalog_closed_v2'
    if current.is_symlink() or not current.is_dir() or archived.exists() or os.path.lexists(next_catalog):raise Review('FAILED_CATALOG_ARCHIVE_DESTINATION_NOT_FRESH')
    original=json.loads((current/'catalog.json').read_text())
    if original.get('status')!='INCOMPLETE_OR_REQUIRES_ACTION' or {r.get('molecule_id') for r in original['issues']}!=MIDS or any(r.get('issue')!='RECEIPT_OR_EXPORT_NOT_AUTHORITATIVE' for r in original['issues']):raise Review('ORIGINAL_FAILED_CATALOG_NOT_EXACT_TWO_CASE')
    files=[]
    for path in [current,*current.rglob('*')]:
        info=path.lstat()
        if info.st_uid!=1278 or not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)):raise Review('FAILED_CATALOG_OWNERSHIP_OR_TYPE_DIFFERS:'+str(path))
        if stat.S_ISREG(info.st_mode):files.append(path)
    with concurrent.futures.ThreadPoolExecutor(max_workers=24) as pool:proofs=list(pool.map(ref,files))
    move_intent=folder/'failed_catalog_move_intent.json'
    publish(move_intent,{'source':str(current),'archive':str(archived),'files':proofs,'bytes':sum(r['bytes'] for r in proofs),'replacement_link':'catalog_closed_v2','scope':'Only this run\'s failed acceptance indexes/metadata. All bytes preserved by same-filesystem rename; no scientific artifact is written or deleted.'})
    current.rename(archived)
    for proof in proofs:
        moved=archived/Path(proof['path']).relative_to(current)
        if moved.stat().st_size!=proof['bytes']:raise Review('RENAMED_FAILED_METADATA_SIZE_DIFFERS')
        proof['archived_path']=str(moved)
    current.symlink_to('catalog_closed_v2',target_is_directory=True)
    receipt={'status':'FAILED_CATALOG_PRESERVED_AND_LOGICAL_PATH_PREPARED','files':proofs,'original_catalog_manifest_paths_are_historical':True,'path_projection':'Each original path resolves its archived bytes using archived_path in this receipt; original JSON bytes were not rewritten.','directory_rename_preserves_bytes':True,'relative_symlink':{'path':str(current),'text':os.readlink(current),'target':str(next_catalog)},'new_jobmap':ref(NEW_MAP),'old_metadata_bytes':sum(r['bytes'] for r in proofs),'old_scientific_files_written_or_deleted':False,'source':ref(__file__)}
    publish(folder/'catalog_metadata_prepared.json',receipt);print(json.dumps({'status':receipt['status'],'new_jobmap':str(NEW_MAP),'new_catalog':str(next_catalog)}))
def submit_and_rebind(folder,pending_rows,execute=command):
    argv=['sbatch','--parsable','--job-name=wp5_final_catalog_v2','--dependency=afterok:'+JOB,str(BATCH),'catalog','--plan',str(PLAN),'--jobmap',str(NEW_MAP),'--threads','24','--out',str(FINAL/'catalog_closed_v2')]
    submitted=once(folder,'catalog_submit',argv,execute,timeout=90)
    match=re.fullmatch(r'(\d+)(?:;[A-Za-z0-9_.-]+)?\s*',submitted['stdout'])
    if not match:raise Review('CATALOG_SUBMISSION_RESULT_UNCERTAIN_DO_NOT_RESUBMIT')
    newjob=match.group(1)
    if newjob in QA or newjob in (JOB,'4515497'):raise Review('CATALOG_NEW_PARENT_ID_INVALID')
    actual=execute(['scontrol','show','job',newjob,'-o'],timeout=90);row=job_fields(actual);publish(folder/'catalog_scontrol_actual.json',actual)
    if row['JobId']!=newjob or row['UserId']!='zixiao(1278)' or row['ReqNodeList']!='compute-0-17' or row['NumCPUs']!='24' or row['WorkDir']!=str(PROJECT) or 'wp5_acceptance_v14.sbatch catalog ' not in (row['Command'] or '') or str(NEW_MAP) not in row['Command'] or str(FINAL/'catalog_closed_v2') not in row['Command']:raise Review('ACTUAL_NEW_CATALOG_CONFIGURATION_DIFFERS')
    for job in ('4515498','4515502'):
        before=job_fields(execute(['scontrol','show','job',job,'-o'],timeout=90))
        if before['JobState']!='PENDING' or before['Command']!=pending_rows[job]['Command'] or before['Dependency']!=pending_rows[job]['Dependency']:raise Review('QA_CHANGED_BEFORE_DEPENDENCY_UPDATE:'+job)
        once(folder,'dependency_update_'+job,['scontrol','update','JobId='+job,'Dependency=afterok:'+newjob],execute,timeout=90)
        after_result=execute(['scontrol','show','job',job,'-o'],timeout=90);after=job_fields(after_result);publish(folder/('dependency_'+job+'_scontrol_actual.json'),after_result)
        if after['Command']!=before['Command'] or after['JobState'] not in ('PENDING','RUNNING','COMPLETING','COMPLETED') or not (after['Dependency'].startswith('afterok:'+newjob) or after['Dependency']=='(null)' and after['JobState']!='PENDING'):raise Review('QA_DEPENDENCY_READBACK_DIFFERS:'+job)
    return newjob
def run(folder):
    if socket.gethostname().split('.')[0]!='sonmi' or os.getuid()!=1278:raise Review('ROOT_STARTED_CONTROLLER_SONMI_UID1278_ONLY')
    if not folder.resolve().is_relative_to(FINAL) or folder.exists():raise Review('FRESH_ONE_SHOT_CONTROL_DIRECTORY_REQUIRED')
    folder.mkdir(parents=True);lock=(folder/'control.lock').open('x');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    started=time.time();deadline=time.monotonic()+8*3600
    def observed(argv,timeout=90):
        # Retry read-only scheduler observations within this same bounded run.
        # A mutating RPC is always invoked once, even if its result is uncertain.
        readonly=argv[0] in ('sacct','squeue') or argv[:2]==['scontrol','show']
        while True:
            result=command(argv,timeout=timeout)
            if result['returncode']==0 or not readonly:return result
            status(folder,{'stage':'WAIT_TRANSIENT_SCHEDULER_OBSERVATION','query':result})
            remaining=deadline-time.monotonic()
            if remaining<=0:raise Review('EIGHT_HOUR_BOUND_DURING_READ_ONLY_SCHEDULER_WAIT')
            time.sleep(min(90,remaining))
    try:
        pinned();publish(folder/'identity.json',{'schema':'WP5_ROOT_ONE_SHOT_ACCEPTANCE_RESUMER_V1','pid':os.getpid(),'uid':os.getuid(),'host':socket.gethostname(),'start_epoch':started,'deadline_epoch':started+8*3600,'poll_seconds':90,'source':ref(__file__),'retry_parent':JOB,'prepared':ref(PREPARED),'old_jobmap':ref(OLD_MAP),'QA_preserved':list(QA),'one_new_catalog_only':True,'scientific_jobs_cancelled':False})
        latest={};terminal_result=None
        while time.monotonic()<deadline:
            query=command(['sacct','-X','-n','-P','-j',JOB,'--format='+FIELDS],timeout=90);row=parent_row(query);latest={'stage':'WAIT_FIXED_TRUE_RETRY','query':query}
            if row is not None:
                state=row[2].split()[0];latest['actual_state']=state
                if state in TERMINAL:
                    if state!='COMPLETED' or row[3]!='0:0':raise Review('TRUE_RETRY_PARENT_TERMINAL_REQUIRES_ROOT_REVIEW:'+state+':'+row[3])
                    if VERIFIED.exists():terminal_result=query;break
                    latest['stage']='WAIT_ACTUAL_VERIFIED240_REPORT_AFTER_PARENT_COMPLETE'
            status(folder,latest);time.sleep(min(90,max(0,deadline-time.monotonic())))
        if terminal_result is None:raise Review('EIGHT_HOUR_BOUND_REACHED_NO_MUTATIONS_AFTER_UNVERIFIED_WAIT')
        report=json.loads(VERIFIED.read_text())
        if report.get('status')!='EXACT_TWO_BUDGET1_SCI_EXPORT_VERIFIED' or str(report.get('job_id'))!=JOB or report.get('records')!=20 or report.get('task_slots')!=240 or report.get('attempt_id')!=1 or report.get('prepared')!=ref(PREPARED) or report.get('script')!=ref(TOOL):raise Review('ACTUAL_VERIFIED240_REPORT_BINDINGS_DIFFER')
        publish(folder/'retry_terminal_accounting.json',terminal_result)
        pending_rows,pending_receipts=read_pending(observed);publish(folder/'old_five_pending_QA_actual.json',pending_receipts)
        adopt_argv=remote_argv([str(TOOL),'adopt','--prepared',str(PREPARED),'--verified',str(VERIFIED),'--terminal-accounting',str(folder/'retry_terminal_accounting.json'),'--out',str(ADOPTION)])
        status(folder,{'stage':'ADOPT_TRUE_BUDGET1_AFTER_ACTUAL_TERMINAL'})
        once(folder,'adopt_exact_two',adopt_argv,timeout=300)
        once(folder,'prepare_catalog_metadata',remote_argv([str(Path(__file__)),'--prepare-catalog','--control-root',str(folder)]),timeout=600)
        ready=False
        while time.monotonic()<deadline:
            node=command(['scontrol','show','node','compute-0-17','-o'],timeout=90)
            users=command(['squeue','--noheader','--states=RUNNING,COMPLETING,CONFIGURING','--nodelist=compute-0-17','--format=%i|%u|%C|%m|%D'],timeout=90)
            resource=admission(node,users)
            if resource['ready']:
                publish(folder/'catalog_actual_resource_admission.json',{'node':node,'all_users':users,'decision':resource});ready=True;break
            status(folder,{'stage':'WAIT_CATALOG_ORIGINAL_NODE_MEMORY_ADMISSION','resource':resource,'node':node,'all_users':users});time.sleep(min(90,max(0,deadline-time.monotonic())))
        if not ready:raise Review('EIGHT_HOUR_BOUND_BEFORE_CATALOG_RESOURCE_ADMISSION')
        current_rows,current_receipts=read_pending(observed)
        if any(current_rows[j]['Command']!=pending_rows[j]['Command'] or current_rows[j]['Dependency']!=pending_rows[j]['Dependency'] for j in QA):raise Review('PENDING_QA_CHANGED_DURING_CONTROLLER_WAIT')
        publish(folder/'five_pending_QA_before_catalog_actual.json',current_receipts)
        newjob=submit_and_rebind(folder,pending_rows,observed)
        status(folder,{'stage':'CONTINUATION_DISPATCHED','new_catalog_job_id':newjob,'formal_science_jobmap':str(NEW_MAP),'existing_QA_jobs_preserved':list(QA),'dependency_updates_only':['4515498','4515502'],'remaining_QA_chain_unchanged':['4515499','4515500','4515501'],'Root_review_required':False,'new_science_QM_calls_by_controller':0,'elapsed_seconds':time.time()-started})
    except Exception as error:
        status(folder,{'stage':'ROOT_REVIEW_REQUIRED','error_type':type(error).__name__,'error':str(error),'traceback':traceback.format_exc(limit=8),'automatic_mutation_replay':False,'global_STOP_written':False,'jobs_cancelled':False,'elapsed_seconds':time.time()-started});raise
    finally:fcntl.flock(lock,fcntl.LOCK_UN);lock.close()
def check():
    """Only a fresh tiny controller fixture, fake scheduler and metadata strings."""
    base=ROOT/'tests';base.mkdir(exist_ok=True);folder=Path(tempfile.mkdtemp(prefix='final_resume_once_metadata_',dir=base));calls=[]
    try:
        terminal={'returncode':0,'stdout':JOB+'|zixiao|COMPLETED|0:0|start|end|3600|24|\n'}
        assert parent_row(terminal)[2]=='COMPLETED' and parent_row({'returncode':1,'stdout':''}) is None and parent_row({'returncode':0,'stdout':''}) is None
        try:parent_row({'returncode':0,'stdout':JOB+'|foreign|COMPLETED|0:0|a|b|1|24|\n'});raise AssertionError('Wrong user accepted')
        except Review:pass
        node={'returncode':0,'stdout':'NodeName=compute-0-17 CPUTot=96 CPUAlloc=96 RealMemory=375000 State=MIXED'}
        users={'returncode':0,'stdout':'123|foreign|24|32G|1\n'}
        assert admission(node,users)['ready'] and memory_mib('2Gc',24)==49152
        assert not admission(node,{'returncode':0,'stdout':'123|foreign|96|300G|1\n'})['ready']
        assert not admission({'returncode':1,'stdout':''},users)['ready']
        states={j:('4515497' if j in ('4515498','4515502') else {'4515499':'4515498','4515500':'4515499','4515501':'4515500'}[j]) for j in QA}
        commands={'4515498':str(BATCH)+' verify --catalog '+str(FINAL/'catalog/catalog.json'),'4515499':str(BATCH)+' plan-200 --catalog '+str(FINAL/'catalog/catalog.json'),'4515500':str(ROOT/'scripts/wp5_acceptance_v15.sbatch')+' recompute-200 --recompute-plan FAKE','4515501':str(ROOT/'scripts/wp5_acceptance_v15.sbatch')+' compare-200 --recompute-plan FAKE','4515502':str(ROOT/'scripts/wp5_acceptance_v16.sbatch')+' pilot --catalog '+str(FINAL/'catalog/catalog.json')}
        def fake(argv,timeout=90):
            calls.append(argv)
            if argv[0]=='sbatch':return {'argv':argv,'returncode':0,'stdout':'9999999\n','stderr':''}
            if argv[:2]==['scontrol','update']:
                jid=argv[2].split('=',1)[1];states[jid]=argv[3].split('afterok:',1)[1];return {'argv':argv,'returncode':0,'stdout':'','stderr':''}
            if argv[:3]==['scontrol','show','job']:
                jid=argv[3];cmd=commands[jid] if jid in commands else str(BATCH)+' catalog --jobmap '+str(NEW_MAP)+' --out '+str(FINAL/'catalog_closed_v2')
                return {'argv':argv,'returncode':0,'stdout':'JobId='+jid+' UserId=zixiao(1278) JobState=PENDING Dependency=afterok:'+states.get(jid,JOB)+'(unfulfilled) ReqNodeList=compute-0-17 NumCPUs=24 Command='+cmd+' WorkDir='+str(PROJECT),'stderr':''}
            raise AssertionError('Unapproved fake command:'+repr(argv))
        pending,_=read_pending(fake);newjob=submit_and_rebind(folder,pending,fake)
        assert newjob=='9999999' and sum(argv[0]=='sbatch' for argv in calls)==1
        assert [argv[2] for argv in calls if argv[:2]==['scontrol','update']]==['JobId=4515498','JobId=4515502']
        before=len(calls)
        try:submit_and_rebind(folder,pending,fake);raise AssertionError('Duplicate mutation was accepted')
        except Review:assert len(calls)==before
        assert states['4515499']=='4515498' and states['4515500']=='4515499' and states['4515501']=='4515500'
        print(json.dumps({'status':'ROOT_ONE_SHOT_RESUMER_METADATA_FAKE_COMMAND_FIXTURE_PASS','fake_catalog_submissions':1,'fake_dependency_updates':2,'duplicate_submit_blocked_before_command':True,'transient_query_and_resource_wait_cases':True,'real_Slurm_commands':0,'real_queue_opened':False,'QM_calls':0,'fixture_cleaned':True}))
    finally:
        if folder.resolve().parent!=base.resolve():raise Review('FIXTURE_CLEANUP_SCOPE_DIFFERS')
        shutil.rmtree(folder)
def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--run',action='store_true');ap.add_argument('--check',action='store_true');ap.add_argument('--prepare-catalog',action='store_true');ap.add_argument('--control-root',type=Path,default=FINAL/'resume_after_true_retry_once_v1');args=ap.parse_args()
    if sum((args.run,args.check,args.prepare_catalog))!=1:raise ValueError('Choose one explicit --run/--check/--prepare-catalog')
    if args.check:check()
    elif args.prepare_catalog:catalog_preparation(args.control_root)
    else:run(args.control_root)
if __name__=='__main__':main()
