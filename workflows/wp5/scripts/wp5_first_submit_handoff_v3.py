"""Root-only handoff for the already approved R13 first 72+6 phase. Default: no action."""
import argparse, ast, fcntl, getpass, hashlib, json, math, os, shlex, socket, subprocess, sys, time
from pathlib import Path
ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011')
PYTHON='/share/home/zixiao/.conda/envs/chemprop/bin/python'
DIRECTORY=ROOT/'submission/recovery_attempt_v13'
PREPARED=DIRECTORY/'prepared_plan_v13.json'
DECISION=ROOT/'submission/recovery_attempt_v12/user_approved_drain_and_one_phase_v1.json'
CONTINUE=ROOT/'submission/recovery_attempt_v12/user_continue_all_calculations_20261012_v1.json'
CALL='call_e92f4936799142f49105fe45329daf89'
STOP=ROOT/'STOP_NEW_MOLECULES.json'
STOP_SHA='77e20f22e3084db81c676d81f866d0c736a791bdee6bdf41c68880ac7db71748'
EXPECTED={
 'scripts/wp5_submit_formal_v13.py':'500852e29a6ba7b1ef1130643268b0e5333c12f3e51f3266f0e9c82345eb1c3a',
 'scripts/submit_wp5_job_v2.py':'7bf29cbe2fa76169609fc97f615695ed2a498386595f14b6755787cd5baa7e12',
 'scripts/wp5_queue_reconcile_apply_v5.sbatch':'5965d24153648613bf99fa2957d7ff4b88601b2a396bdb2a71fb5e816fc17102',
 'scripts/wp5_production_bootstrap_v13.sbatch':'890160fa374c8916af1b655834069971155f4baa5a0faa8ec5cd89878c17ccc0',
 'scripts/wp5_materialized_permanent_v2.sbatch':'89187b5f4f0208bdbaa8691ca5ae6756d7e4d26c0637e247bb8ad045893638e5',
 'scripts/wp5_assemble_g0_r13_v1.py':'6d5a597112162a6b2de49ec5712b1b71aa804cb53a8c5a7ee0c5f06d05866199',
 'scripts/wp5_switch_watch_v6_v1.py':'38ed5ee99bd6ffad537ab1400d21486f39c22b5dc3b29eb81a4a09b2f68d2915',
 'scripts/wp5_recovery_hourly_watch_v4.py':'43a055e5e51152f74dcb3f762a04cd4e75c09c20e82ae3af3c29446345fb3ca9'}
TERMINAL={'COMPLETED','FAILED','CANCELLED','NODE_FAIL','PREEMPTED','BOOT_FAIL','OUT_OF_MEMORY','TIMEOUT','DEADLINE','REVOKED'}

def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def ref(path):return {'path':str(path),'sha256':sha(path)}
def checked(r):
    if sha(r['path'])!=r['sha256']:raise ValueError('ACTUAL_REFERENCE_DIFFERS: '+r['path'])
    return read(r['path'])
def atomic(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    pending=path.with_name(path.name+'.'+str(os.getpid())+'.pending')
    with pending.open('w',encoding='utf-8') as f:
        json.dump(data,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
    os.replace(pending,path)
def once(path,data):
    path=Path(path)
    if path.exists():
        if read(path)!=data:raise ValueError('PRESERVE_EXISTING_ACTUAL_EVIDENCE: '+str(path))
    else:atomic(path,data)

class Coordinator:
    def __init__(self,a):
        self.a=a;self.directory=DIRECTORY/'first_submit_handoff_v3'
        self.directory.mkdir(parents=True,exist_ok=True)
        self.state_path=self.directory/'state.json'
        self.state=read(self.state_path) if self.state_path.exists() else {
            'schema':'WP5_R13_FIRST_SUBMIT_HANDOFF_V1','status':'ROOT_HANDOFF_STARTED','started_epoch':time.time(),
            'deadline_epoch':time.time()+a.deadline_hours*3600,'plan':str(a.plan),'plan_job_id':str(a.plan_job_id),
            'source':ref(Path(__file__).resolve()),'steps':{},'scientific_configuration_changed':False,
            'authorized_phase_main':72,'authorized_phase_cleanup':6,'final200_required':True}
        if self.state['plan']!=str(a.plan) or self.state['plan_job_id']!=str(a.plan_job_id) or self.state['source']!=ref(Path(__file__).resolve()):
            raise ValueError('EXISTING_HANDOFF_SCOPE_OR_SOURCE_DIFFERS')
        self.save()
    def save(self):atomic(self.state_path,self.state)
    def log(self,message,**data):
        event={'time':time.time(),'event':message,**data}
        with (self.directory/'events.jsonl').open('a',encoding='utf-8') as f:
            f.write(json.dumps(event,ensure_ascii=False)+'\n');f.flush();os.fsync(f.fileno())
        print(json.dumps(event,ensure_ascii=False),flush=True)
    def remaining(self):
        remaining=self.state['deadline_epoch']-time.time()
        if remaining<=0:raise TimeoutError('HANDOFF_DEADLINE_REACHED_NO_NEW_SUBMISSION')
        return remaining
    def command(self,name,argv,timeout=600,repeat=False):
        steps=self.state['steps'];old=steps.get(name)
        if old and old['status']=='COMMAND_COMPLETE' and not repeat:
            if old['returncode']!=0:raise RuntimeError('PRIOR_COMMAND_FAILED_ROOT_REVIEW_REQUIRED: '+name)
            return Path(old['stdout']).read_text(encoding='utf-8')
        if old and old['status']=='COMMAND_STARTED':
            raise RuntimeError('COMMAND_ACCEPTANCE_UNKNOWN_NO_AUTOMATIC_REISSUE: '+name)
        index=int(old.get('invocations',0))+1 if old else 1
        out=self.directory/(name+'.'+str(index)+'.stdout');err=self.directory/(name+'.'+str(index)+'.stderr')
        row={'status':'COMMAND_STARTED','argv':list(map(str,argv)),'started_epoch':time.time(),
             'stdout':str(out),'stderr':str(err),'invocations':index}
        steps[name]=row;self.save()
        env=dict(os.environ);env['PYTHONPATH']=str(ROOT/'scripts')+':/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps'+(':'+env['PYTHONPATH'] if env.get('PYTHONPATH') else '')
        try:
            with out.open('w',encoding='utf-8') as fo,err.open('w',encoding='utf-8') as fe:
                result=subprocess.run(row['argv'],stdin=subprocess.DEVNULL,stdout=fo,stderr=fe,env=env,
                                      cwd=str(ROOT),timeout=min(timeout,self.remaining()))
            row.update(status='COMMAND_COMPLETE',returncode=result.returncode,finished_epoch=time.time())
            self.save();self.log('COMMAND_COMPLETED',step=name,returncode=result.returncode,stdout=str(out),stderr=str(err))
            if result.returncode!=0:raise RuntimeError('COMMAND_FAILED_ROOT_REVIEW_REQUIRED: '+name)
            return out.read_text(encoding='utf-8')
        except BaseException:
            self.save();raise
    def probe_job(self,jid):
        text=self.command('sacct_'+str(jid),['sacct','-X','-n','-P','-j',str(jid),'--format=JobID,User,State,ExitCode'],60,True)
        rows=[list(map(str.strip,line.split('|'))) for line in text.splitlines()]
        exact=[r for r in rows if len(r)>=4 and r[0]==str(jid)]
        if not exact:return None
        signatures={(r[1],r[2].split()[0].rstrip('+'),r[3]) for r in exact}
        if len(signatures)!=1:raise ValueError('SACCT_EXACT_JOB_ROWS_DIFFER: '+str(jid))
        user,state,code=signatures.pop()
        if user!='zixiao':raise ValueError('ACTUAL_JOB_USER_DIFFERS: '+str(jid))
        return {'job_id':str(jid),'user':user,'state':state,'exit_code':code}
    def wait_job(self,jid):
        while True:
            proof=self.probe_job(jid)
            if proof and proof['state'] in TERMINAL:
                if proof['state']!='COMPLETED' or proof['exit_code']!='0:0':
                    raise RuntimeError('ACTUAL_JOB_NOT_COMPLETED_ZERO: '+json.dumps(proof))
                self.state.setdefault('terminal_jobs',{})[str(jid)]=proof;self.save();return proof
            self.log('WAITING_ACTUAL_JOB',job_id=str(jid),observed=proof)
            time.sleep(min(60,self.remaining()))
    def submit_metadata(self,key,script,node,cpus,memory,args):
        step=self.state['steps'].get('submit_'+key,{})
        if step.get('job_id'):return step['job_id']
        # A completed helper receipt is the authority on resume, not an invented job ID.
        if step.get('status')=='COMMAND_STARTED':
            receipts=[]
            for p in (ROOT/'logs').glob('wp5_r13_handoff_'+key+'_v1_*_submission.json'):
                obj=read(p)
                if obj.get('time',0)>=step['started_epoch'] and obj.get('script')==str(script) and obj.get('uid')==1278:
                    receipts.append((p,obj))
            if len(receipts)!=1:raise RuntimeError('METADATA_SUBMISSION_ACCEPTANCE_UNKNOWN: '+key)
            path,obj=receipts[0];step.update(status='COMMAND_COMPLETE',returncode=0,job_id=str(obj['job_id']),receipt=ref(path))
            self.save();return step['job_id']
        argv=[PYTHON,'-B',str(ROOT/'scripts/submit_wp5_job_v2.py'),'--script',str(script),
              '--name','wp5_r13_handoff_'+key+'_v1','--node',node,'--cpus',str(cpus),'--memory-gb',str(memory),
              '--time','48:00:00','--kind','audit','--allow-pending']+list(map(str,args))
        output=self.command('submit_'+key,argv,600)
        actual=json.loads(output.strip().splitlines()[-1]);receipt=read(actual['receipt'])
        if receipt.get('uid')!=1278 or receipt.get('script')!=str(script) or receipt.get('script_sha256')!=sha(script) or str(receipt.get('job_id'))!=str(actual['job_id']):
            raise ValueError('ACTUAL_METADATA_SUBMISSION_RECEIPT_DIFFERS')
        step=self.state['steps']['submit_'+key];step.update(job_id=str(actual['job_id']),receipt=ref(actual['receipt']))
        self.save();return str(actual['job_id'])

def continuous_authority_fields(plan):
    approved_prepared=ROOT/'submission/recovery_attempt_v12/prepared_plan_v12.json'
    approved_plan=read(approved_prepared)
    contract=checked(plan['production_contract'])
    return {
        'actual_user_approval':ref(DECISION),'prior_approved_plan':ref(approved_prepared),
        'prior_approved_contract':approved_plan['production_contract'],
        'latest_user_continuous_directive':ref(CONTINUE),
        'metadata_only_AST_bridge':contract['metadata_only_AST_bridge'],
        'cleanup_scope_validation':contract['cleanup_scope_validation'],
        'authorization_basis':'LATEST_USER_DIRECTIVE_AUTONOMOUS_METADATA_REPAIR_WITH_UNCHANGED_SCIENCE'}
def approval(plan):
    import wp5_submit_formal_v13 as submitter
    values=continuous_authority_fields(plan)
    submitter.validate_continuous_authority(values,plan)
    approved_plan=read(values['prior_approved_plan']['path'])
    contract=checked(plan['production_contract'])
    if {k:contract.get('previous_contract',{}).get(k) for k in ('path','sha256')}!={k:approved_plan['production_contract'].get(k) for k in ('path','sha256')}:
        raise ValueError('METADATA_REPAIR_PARENT_IS_NOT_ACTUAL_APPROVED_CONTRACT5')
    return checked(values['actual_user_approval'])


def fresh_storage(c,permanent):
    baseline=read(ROOT/'gates/g3_remaining_r12_v1.json');snapshot=read(permanent)
    if snapshot.get('status')!='MATERIALIZED_PERMANENT_SNAPSHOT_CLOSED' or snapshot.get('issues'):
        raise ValueError('ACTUAL_PERMANENT_COLLECTOR_NOT_CLOSED')
    raw=c.command('fresh_quota',['quota','-v','-u','zixiao'],60,True)
    lines=[line.split() for line in raw.splitlines() if line.strip().startswith('/dev/sda1 ')]
    if len(lines)!=1:raise ValueError('ACTUAL_QUOTA_FILESYSTEM_OR_FIELDS_NOT_CLOSED')
    fields=lines[0];used=int(fields[1].rstrip('*'))*1024;limit=int(fields[3].rstrip('*'))*1024
    if limit<=used:raise ValueError('ACTUAL_QUOTA_NO_REMAINING_CAPACITY')
    materialized=int(snapshot['permanent_bytes']);peak=float(baseline['original_full_scope_peak_bytes'])
    remaining=peak-materialized;free=limit-used;headroom=free-remaining
    report={**baseline,'created_epoch':time.time(),'production_contract':read(PREPARED)['production_contract'],
            'materialized_permanent_snapshot':ref(permanent),'confirmed_materialized_permanent_bytes':materialized,
            'remaining_writeback_peak_bytes':remaining,'headroom_bytes':headroom,
            'quota':{'argv':['quota','-v','-u','zixiao'],'returncode':0,'stdout':raw,'stderr':'',
                     'unit_bytes':1024,'used_bytes':used,'limit_bytes':limit,'remaining_bytes':free},
            'status':'PASS' if headroom>=baseline['required_headroom_bytes'] else 'NOT_PASS'}
    if remaining<0:raise ValueError('FROZEN_FORECAST_PERMANENT_SCOPE_NOT_CLOSED')
    path=ROOT/'gates/g3_remaining_r13_handoff_v1.json'
    if path.exists():
        prior=read(path)
        # Never silently reuse a stale capacity measurement.
        if c.state.get('g3')!=ref(path):raise ValueError('EXISTING_G3_NOT_OWNED_BY_THIS_HANDOFF')
        path=c.directory/('g3_remaining_'+str(time.time_ns())+'.json')
    once(path,report);c.state['g3']=ref(path);c.save()
    if report['status']!='PASS':raise ValueError('CURRENT_REMAINING_STORAGE_HEADROOM_BELOW200GB')
    return path

def stop_check(c):
    hour=c.a.observer_hour or int(time.time())
    command='cd /share/home/zixiao/descriptor_analysis && PYTHONPATH='+str(ROOT/'scripts')+' '+PYTHON+' -B '+str(ROOT/'scripts/wp5_hourly_observe_v3.py')+' --hour '+str(hour)+' --write-latest'
    output=c.command('guide_observer',['ssh','-n','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','compute-0-20',command],600,True)
    summary=json.loads(output.strip().splitlines()[-1]);stdout=Path(c.state['steps']['guide_observer']['stdout'])
    observation=ROOT/'reports'/('formal_hour'+str(hour)+'_root_observation_v3.json')
    snapshot=ROOT/'reports'/('formal_hour'+str(hour)+'_queue_snapshot_v3.json')
    import wp5_recovery_hourly_watch_v4 as watch
    from wp5_hourly_observe_v3 import effective_jobs
    obs,snap,publisher=read(observation),read(snapshot),read(ROOT/'reports/observation_latest.json')
    paired=watch.paired_observer_proof(obs,snap,summary,stdout.stat().st_mtime)
    check=watch.evaluate_stop_conditions(publisher,obs,snap,effective_jobs(),paired['valid'])
    if not check.get('eligible') or check.get('conditions') or not summary.get('population_closed') or not summary.get('task_denominators_closed'):
        raise ValueError('ORIGINAL_GUIDE_STOP_OR_UNKNOWN_OBSERVER_PROOF: '+json.dumps(check))
    cache=read(ROOT/'queue/pending.sqlite.first5_health_v1.json')
    baseline_path=ROOT/'configs/pilot_success_baseline.json';baseline=read(baseline_path)['success_rates']
    if cache.get('status')!='READY' or cache.get('bindings',{}).get('baseline_sha256')!=sha(baseline_path) or set(cache.get('counts',{}))!=set(baseline):
        raise ValueError('FIRST5_ORIGINAL_HEALTH_CACHE_BINDINGS_NOT_CLOSED')
    failures=[]
    for calc,rate in baseline.items():
        counts=cache['counts'][calc]
        if counts['total']!=cache['prefix_records']:raise ValueError('FIRST5_TWELVE_DENOMINATORS_NOT_CLOSED')
        if counts['total'] and counts['success']/counts['total']<rate-.02:failures.append(calc)
    if failures:raise ValueError('EARLY_TASK_SUCCESS_DROP_GT2PP: '+','.join(failures))
    proof={'status':'NO_ORIGINAL_GUIDE_STOP_TRIGGERED','time':time.time(),'original_watcher_evaluation':check,
           'observer_pair':paired,'observer':ref(observation),'queue_snapshot':ref(snapshot),
           'first5_cache':ref(ROOT/'queue/pending.sqlite.first5_health_v1.json'),
           'first5_baseline':ref(baseline_path),'first5_threshold_unchanged':-.02,
           'deadline_p99_admission_owned_by_unchanged_runtime':True}
    path=c.directory/('stop_check_'+str(time.time_ns())+'.json');once(path,proof)
    c.state['stop_check']=ref(path);c.save()

def execute(c):
    import wp5_submit_formal_v13 as submitter
    for relative,expected in EXPECTED.items():
        if sha(ROOT/relative)!=expected:raise ValueError('FROZEN_HANDOFF_DEPENDENCY_DIFFERS: '+relative)
    plan=read(PREPARED);approval(plan)
    if plan.get('version')!=13 or len(plan.get('main',[]))!=72 or len(plan.get('cleanup',[]))!=6:
        raise ValueError('EXACT_EXISTING_PREPARED12_REQUIRED')
    actual_result=DIRECTORY/'submitted_jobs.json'
    if actual_result.exists():
        result=read(actual_result)
        if result.get('status')!='ALL_MAIN_AND_SIX_CLEANUP_SUBMITTED' or result.get('prepared_plan')!=plan:
            raise ValueError('EXISTING_PARTIAL_FORMAL_SUBMISSION_ROOT_RECONCILIATION_REQUIRED')
        c.log('EXISTING_ACTUAL_FULL_R13_SUBMISSION_NO_REISSUE',main=len(result['main']),cleanup=len(result['cleanup']))
    else:
        c.wait_job(c.a.plan_job_id)
        reviewed=read(c.a.plan)
        refs,ids,_=submitter.prior_submission_bindings()
        if reviewed.get('status')!='REVIEWABLE_TERMINAL_SUBSET_DRY_RUN' or reviewed.get('conflicts')!=[] or reviewed.get('protected_jobs')!={} or reviewed.get('protected_tasks')!=[] or reviewed.get('manifests')!=refs or set(reviewed.get('registered_jobs',{}))!=set(ids) or reviewed.get('skipped',{}).get('count')!=0 or reviewed.get('all_selected_root_scans_complete') is not True or reviewed.get('accounting',{}).get('all_terminal') is not True:
            raise ValueError('ACTUAL_CONFLICT_FREE_ALL229_DRYRUN_NOT_CLOSED')
        submitter.fresh_all_prior_terminal(plan)
        apply_job=c.submit_metadata('apply',ROOT/'scripts/wp5_queue_reconcile_apply_v5.sbatch','compute-0-12',16,32,[c.a.plan,sha(c.a.plan)])
        c.wait_job(apply_job);apply_path=ROOT/'reports'/('full229_apply_v5_job_'+apply_job)/'report.json'
        applied=read(apply_path)
        if applied.get('status')!='APPLIED_AND_VERIFIED' or applied.get('full229_terminal_scope_verified') is not True or applied.get('plan')!=ref(c.a.plan):
            raise ValueError('ACTUAL_APPLY_FULL229_NOT_VERIFIED')
        exports=checked(reviewed['export_roots'])
        from wp5_collect_materialized_permanent_v2 import read_closure
        unclosed=[]
        for item in exports:
            closure=Path(item['run_root'])/'export_completion.json'
            if not closure.is_file() or read_closure(closure)['issues']:unclosed.append(item['run_root'])
        if unclosed:
            c.state['export_roots_requiring_root_pure_export']=unclosed;c.save()
            raise ValueError('ROOT_PURE_EXPORT_REQUIRED_NO_FAKE_CLOSURE: '+json.dumps(unclosed))
        bootstrap_job=c.submit_metadata('bootstrap',ROOT/'scripts/wp5_production_bootstrap_v13.sbatch','compute-0-17',24,32,
            ['--contract-sha256',plan['production_contract']['sha256'],'--prepared-sha256',sha(PREPARED),
             '--reconciliation-report',apply_path,'--reconciliation-sha256',sha(apply_path)])
        c.wait_job(bootstrap_job);bootstrap=ROOT/'gates/R13_production_bootstrap'/('job_'+bootstrap_job)/'report.json'
        permanent_job=c.submit_metadata('permanent',ROOT/'scripts/wp5_materialized_permanent_v2.sbatch','compute-0-17',16,4,[])
        c.wait_job(permanent_job);permanent=ROOT/'reports'/('formal_materialized_permanent_bytes_v2_job_'+permanent_job+'.json')
        g3=fresh_storage(c,permanent)
        authority_path=DIRECTORY/'user_approved_recovery_bound_v1.json'
        authority={
            'schema':'WP5_ACTUAL_USER_CONTINUOUS_METADATA_RECOVERY_V13','status':'USER_APPROVED_ONE_PHASE_RECOVERY',
            'production_contract':plan['production_contract'],'prepared_plan':ref(PREPARED),
            'original_submission_sha256':sha(ROOT/'submission/submitted_jobs.json'),'prior_submissions':refs,
            'queue_reconciliation_report':ref(apply_path),'queue_bootstrap_report':ref(bootstrap),
            **continuous_authority_fields(plan),'question_item_id':['request_user_input_async',CALL,0],
            'user_reply_call_id':CALL,'latest_user_continuous_directive':ref(CONTINUE),
            'authorized_main_jobs':72,'authorized_cleanup_jobs':6,'single_phase':True,
            'scientific_configuration_changed':False,'final200_required':True}
        once(authority_path,authority)
        submitter.validate_recovery_evidence(authority,plan,PREPARED,authority_path)
        c.state['authority']=ref(authority_path);c.save()
        c.command('G0_assemble',[PYTHON,'-B',str(ROOT/'scripts/wp5_assemble_g0_r13_v1.py'),
                   '--recovery-authority',str(authority_path),'--g3',str(g3),
                   '--extra-binding',str(CONTINUE)],600)
        # Re-evaluate guide conditions immediately before retiring only this user-drain flag.
        stop_check(c);submitter.fresh_all_prior_terminal(plan)
        archive=c.directory/'USER_APPROVED_NORMAL_DRAIN_STOP.original.json'
        if STOP.exists():
            value=read(STOP)
            if sha(STOP)!=STOP_SHA or value.get('reason')!='USER_APPROVED_R12_SOFTWARE_RECOVERY_NORMAL_DRAIN' or value.get('details',{}).get('user_decision')!=ref(DECISION):
                raise ValueError('STOP_IS_NOT_MATCHING_USER_NORMAL_DRAIN_FLAG_LEAVE_UNCHANGED')
            if archive.exists():raise ValueError('DRAIN_ARCHIVE_ALREADY_EXISTS_ROOT_REVIEW_REQUIRED')
            os.rename(STOP,archive)
            if sha(archive)!=STOP_SHA:raise ValueError('ARCHIVED_DRAIN_SHA_DIFFERS')
            c.state['archived_stop']=ref(archive);c.save()
        elif not archive.exists() or sha(archive)!=STOP_SHA:
            raise ValueError('MATCHING_DRAIN_STOP_ARCHIVE_NOT_FOUND_NO_SUBMISSION')
        c.command('formal_submit',[PYTHON,'-B',str(ROOT/'scripts/wp5_submit_formal_v13.py'),'--submit',
            '--node-authority',plan['node_authority'],'--production-contract',plan['production_contract']['path'],
            '--recovery-authority',str(authority_path)],min(c.remaining(),18*3600))
        result=read(actual_result)
        if result.get('status')!='ALL_MAIN_AND_SIX_CLEANUP_SUBMITTED' or len(result.get('main',[]))!=72 or len(result.get('cleanup',[]))!=6:
            raise ValueError('ACTUAL72_PLUS6_SUBMISSION_NOT_CLOSED_ROOT_RECONCILIATION_REQUIRED')
    from wp5_hourly_observe_v4 import effective_jobs
    selected=effective_jobs()
    if not selected['ready']:raise ValueError('ACTUAL_R13_NODE_TASK_IDS_NOT_CLOSED')
    while True:
        pub=read(ROOT/'reports/observation_latest.json')
        registered={str(r['job_id']) for r in pub.get('registered',[])}
        if time.time()-pub.get('time',0)<=180 and set(selected['actual_cost_job_ids'])<=registered and pub.get('sacct',{}).get('returncode')==0:break
        c.log('WAITING_EXISTING_PUBLISHER_TO_REGISTER_ACTUAL307',registered=len(registered))
        time.sleep(min(60,c.remaining()))
    c.command('watch6_switch',[PYTHON,'-B',str(ROOT/'scripts/wp5_switch_watch_v6_v1.py'),'--switch',
               '--first-hour','1','--hours-limit','192'],120)
    c.state.update(status='ACTUAL_R13_ONE_PHASE_SUBMITTED_AND_WATCH6_ACTIVE',
                   actual_submission=ref(actual_result),finished_epoch=time.time(),
                   actual_unique_cost_jobs=len(selected['actual_cost_job_ids']),actual_logical_jobs=len(selected['effective_job_ids']))
    c.save();c.log(c.state['status'],state=str(c.state_path),actual_main=72,actual_cleanup=6)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--check',action='store_true')
    p.add_argument('--run',action='store_true');p.add_argument('--plan',type=Path);p.add_argument('--plan-job-id')
    p.add_argument('--deadline-hours',type=float,default=48);p.add_argument('--observer-hour',type=int)
    a=p.parse_args()
    if a.check:ast.parse(Path(__file__).read_text());print('R13_HANDOFF_AST_PASS_NOT_STARTED_NO_SUBMISSION');return
    if not a.run:
        print(json.dumps({'status':'PREPARED_NOT_STARTED','flow':['actual229plan','apply_v5','zero_export_roots','bootstrap12',
            'actual_permanent_quota_G3','new_actual_authority','G0','same77e20drainSTOP_archive','submit12_once72+6','watch6_switch'],
            'existing119_sources_modified':False,'scientific_configuration_changed':False,'final200_required':True}));return
    if not a.plan or not a.plan_job_id or not str(a.plan_job_id).isdigit():p.error('--plan and --plan-job-id actual dryrun job required')
    if os.getuid()!=1278 or getpass.getuser()!='zixiao' or socket.gethostname().split('.')[0]!='sonmi':
        raise ValueError('ONLY_ACTUAL_ROOT_COORDINATOR_ZIXIAO_UID1278_ON_SONMI')
    DIRECTORY.mkdir(parents=True,exist_ok=True)
    with (DIRECTORY/'first_submit_handoff_v3.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        c=Coordinator(a)
        if c.state.get('status')=='ACTUAL_R13_ONE_PHASE_SUBMITTED_AND_WATCH6_ACTIVE':
            print(json.dumps({'status':c.state['status'],'no_action':True}));return
        try:execute(c)
        except BaseException as error:
            c.state.update(status='ROOT_HANDOFF_NEEDS_CONCRETE_REPAIR',error=repr(error),last_error_epoch=time.time())
            c.save();c.log('ROOT_REPAIR_REQUIRED_NO_REPEAT_USER_PERMISSION',error=repr(error),state=str(c.state_path))
            raise
if __name__=='__main__':main()
