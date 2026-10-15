"""Root-only user-approved replacement of startup failures; science stays frozen."""
import argparse, ast, getpass, hashlib, json, os, re, socket, subprocess, time
from pathlib import Path
import wp5_submit_formal_v11 as formal
ROOT=formal.ROOT
PYTHON=formal.PYTHON
PLAN=ROOT/'reports/recovery_startup_replacement_plan_v1.json'
DIRECTORY=ROOT/'submission/startup_replacement_v1'
EXPECTED_PLAN='a40ab78ee6cf0ca8fe7e0dd83306a9f74d6db0fb83edb521bfa55ba74026145f'
TERMINAL={'COMPLETED','FAILED','CANCELLED','NODE_FAIL','PREEMPTED','BOOT_FAIL'}

def read(path):return json.loads(Path(path).read_text())
def run(argv,env=None,check=True):
    p=subprocess.run(argv,env=env,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=600)
    row={'argv':argv,'returncode':p.returncode,'stdout':p.stdout,'stderr':p.stderr,'time':time.time()}
    if check and p.returncode:raise RuntimeError(json.dumps(row))
    return row

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--check',action='store_true');ap.add_argument('--submit',action='store_true')
    args=ap.parse_args()
    if args.check:ast.parse(Path(__file__).read_text());print('AST_PASS_NO_SUBMISSION');return
    if not args.submit:ap.error('--submit required')
    assert os.getuid()==1278 and getpass.getuser()=='zixiao' and socket.gethostname().split('.')[0]=='sonmi'
    assert formal.digest(PLAN)==EXPECTED_PLAN
    plan=read(PLAN)
    assert len(plan['replacement_main'])==69 and len(plan['replacement_cleanup'])==4 and len(plan['existing_cleanup_dependency_updates'])==2
    for ref in [plan['source_submission'],plan['scope'],plan['production_contract'],plan['zero_claim_terminal_metadata_repair']]+plan['startup_probe_actual_6_nodes_144_workers']:
        assert formal.digest(ref['path'])==ref['sha256'],ref['path']
    contract=formal.validate_current_contract(Path(plan['production_contract']['path']),Path(read(plan['production_contract']['path'])['node_authority']['path']))
    assert formal.digest(plan['script'])==plan['script_sha256']
    assert not (ROOT/'STOP_NEW_MOLECULES.json').exists()
    obs=read(ROOT/'reports/observation_latest.json')
    assert time.time()-obs['time']<180 and obs['uid']==1278 and obs['hostname']=='sonmi'
    for item in plan['replacement_main']+plan['replacement_cleanup']:
        assert obs['registered_job_states'].get(item['old_job_id']) in TERMINAL,item['old_job_id']
    g3=read(ROOT/'gates/g3_current_scope_closed_v12.json')
    materialized=read(ROOT/'reports/formal_materialized_permanent_bytes_v1.json')['permanent_bytes']
    future=g3['writeback_peak_bytes']-materialized
    free=obs['quota_parsed']['remaining_bytes']
    assert free-future>=g3['required_headroom_bytes'],(free,future,free-future)
    assert free>=g3['runtime_stop_remaining_bytes']
    authority=read(DIRECTORY/'user_authority_20261012_v1.json')
    assert authority['status']=='USER_APPROVED_STARTUP_REPLACEMENT_AND_DEPENDENCY_UPDATE'
    assert authority['plan']=={'path':str(PLAN),'sha256':EXPECTED_PLAN}
    assert authority['production_contract']==plan['production_contract']
    destination=DIRECTORY/'submitted_jobs.json'
    assert not destination.exists(),'Actual receipt already exists; reconcile rather than duplicate submission'
    fd=os.open(DIRECTORY/'root_submit.lock',os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    os.write(fd,json.dumps({'pid':os.getpid(),'uid':os.getuid(),'time':time.time()}).encode());os.close(fd)
    result={'schema':'WP5_STARTUP_REPLACEMENT_ACTUAL_SUBMISSION_V1','status':'SUBMISSION_IN_PROGRESS','start':time.time(),
        'plan':authority['plan'],'user_authority':{'path':str(DIRECTORY/'user_authority_20261012_v1.json'),'sha256':formal.digest(DIRECTORY/'user_authority_20261012_v1.json')},
        'production_contract':plan['production_contract'],'resources':plan['resources'],'main':[],'cleanup':[],
        'existing_cleanup_dependency_updates':[],'scheduler_operations':[],
        'successful_original_main_jobs_preserved':plan['successful_original_main_jobs_preserved'],
        'capacity_preflight':{'quota_remaining_bytes':free,'already_materialized_permanent_bytes':materialized,'future_peak_bytes':future,'headroom_bytes':free-future},'error':None}
    formal.atomic(destination,result)
    def operation(argv):
        row=run(argv,check=False);result['scheduler_operations'].append(row);formal.atomic(destination,result)
        if row['returncode']:raise RuntimeError(json.dumps(row))
        return row
    def submit(item,role,dependency=None):
        env=dict(environment,WP5_TASK_ID=item['task_id'],WP5_MODE=item['mode'])
        command=[PYTHON,'-B',str(ROOT/'scripts/submit_wp5_job_v2.py'),'--script',plan['script'],'--name',item['name'],
            '--node',item['node'],'--cpus','24','--memory-gb','32','--time','48:00:00','--kind','quantum','--allow-pending']
        if dependency:command+=['--dependency',dependency]
        process=run(command,env=env,check=False)
        if process['returncode']:raise RuntimeError(json.dumps(process))
        receipt=json.loads(process['stdout'])
        clean={k:v for k,v in item.items() if k not in ('job_id','receipt','afterany_main_names')}
        result[role].append({**clean,**receipt,'dependency':dependency})
        formal.atomic(destination,result)
        print(json.dumps({'role':role,'task_id':item['task_id'],'job_id':receipt['job_id'],'node':item['node']}),flush=True)
    def dependency(item):
        ids=[];satisfied=[]
        mapping={r['name']:r['job_id'] for r in result['main']}
        for ref in item['afterany_main']:
            if 'replacement_name' in ref:ids.append(mapping[ref['replacement_name']]);continue
            jid=ref['existing_job_id'];current=run(['scontrol','show','job','-o',jid],check=False)
            if current['returncode']==0:ids.append(jid)
            else:
                state=obs['registered_job_states'].get(jid)
                if state not in TERMINAL:raise RuntimeError('Unverified missing existing dependency '+jid)
                satisfied.append({'job_id':jid,'terminal_state':state,'reason':'Already terminal and purged from controller; afterany satisfied','controller_query':current})
        assert ids
        return 'afterany:'+':'.join(ids),satisfied
    try:
        for item in plan['existing_cleanup_dependency_updates']:
            raw=run(['scontrol','show','job','-o',item['existing_job_id']])
            assert 'UserId=zixiao(1278)' in raw['stdout'] and 'JobState=PENDING' in raw['stdout']
            result['scheduler_operations'].append(raw);formal.atomic(destination,result)
            operation(['scontrol','hold',item['existing_job_id']])
        environment=dict(os.environ,WP5_DICTIONARIES=read(ROOT/'gates/g0_ready_for_recovery_v11.json')['dictionary_manifest'],
            WP5_BASELINE=str(ROOT/'configs/pilot_success_baseline.json'),WP5_POLICY=formal.POLICY,
            WP5_NODE_AUTHORITY=contract['node_authority']['path'],WP5_AUDIT_MEMBERSHIP=contract['audit_manifest']['path'],
            WP5_REPRODUCTION_PACKAGE=contract['reproduction_package']['path'],WP5_PRODUCTION_CONTRACT=plan['production_contract']['path'])
        for item in plan['replacement_main']:submit(item,'main')
        for item in plan['existing_cleanup_dependency_updates']:
            dep,satisfied=dependency(item)
            operation(['scontrol','update','JobId='+item['existing_job_id'],'Dependency='+dep])
            result['existing_cleanup_dependency_updates'].append({**item,'job_id':item['existing_job_id'],'dependency':dep,'already_satisfied_terminal_dependencies':satisfied})
            formal.atomic(destination,result)
        for item in plan['replacement_cleanup']:
            dep,satisfied=dependency(item);submit(item,'cleanup',dep)
            result['cleanup'][-1]['already_satisfied_terminal_dependencies']=satisfied;formal.atomic(destination,result)
        for item in plan['existing_cleanup_dependency_updates']:operation(['scontrol','release',item['existing_job_id']])
        result['status']='ALL_69_MAIN_4_CLEANUP_AND_2_DEPENDENCY_UPDATES_COMPLETE'
        result['end']=time.time();formal.atomic(destination,result)
        print(json.dumps({'status':result['status'],'main':69,'new_cleanup':4,'updated_cleanup':2,'receipt':str(destination)}),flush=True)
    except BaseException as exc:
        result['status']='PARTIAL_SUBMISSION_REQUIRES_ROOT_RECONCILIATION';result['error']=repr(exc);formal.atomic(destination,result);raise
    finally:(DIRECTORY/'root_submit.lock').unlink(missing_ok=True)
if __name__=='__main__':main()
