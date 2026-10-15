"""Single bounded Root orchestrator through full-population scientific acceptance."""
import fcntl,json,os,socket,sqlite3,subprocess,time,hashlib,re
from pathlib import Path
from prepare import ROOT,PROJECT,save,sha

TERMINAL={'COMPLETED','FAILED','CANCELLED','TIMEOUT','OUT_OF_MEMORY','NODE_FAIL','PREEMPTED','BOOT_FAIL','DEADLINE','REVOKED'}
NODES={2:32,8:64,9:64,10:64,11:64}

def registered():
    rows={}
    for p in (ROOT/'submission').glob('*.json'):
        d=json.loads(p.read_text())
        if d.get('job_id') and (p.stem.startswith(('full_worker_v7_','recover_full_v7','finalize_full_v7','reproduce100_full_v7','report_full_v7'))):
            rows[d['job_id']]={'stem':p.stem,'receipt':d}
    return rows

def actual_jobs(records):
    if not records:return {}
    p=subprocess.run(['sacct','-j',','.join(records),'-n','-P','--format=JobIDRaw,User,State,ExitCode,NodeList,JobName'],stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=30)
    assert p.returncode==0,(p.returncode,p.stderr)
    actual={}
    for line in p.stdout.splitlines():
        cols=line.split('|')
        if cols[0] in records:
            assert cols[1]=='zixiao' and cols[5].startswith('sprime_')
            actual[cols[0]]={'user':cols[1],'state':cols[2].split()[0],'exit_code':cols[3],'node':cols[4],'job_name':cols[5]}
    # Newly submitted jobs can precede sacct publication. Missing rows are unknown, never success.
    for jid in records:
        if jid not in actual:actual[jid]={'state':'ACCOUNTING_NOT_YET_PUBLISHED','user':'zixiao'}
    return actual

def queue_state():
    db=sqlite3.connect('file:'+str(ROOT/'full/work.sqlite')+'?mode=ro',uri=True,timeout=120)
    rows=db.execute('SELECT id,state,molecules,owner,job_id,receipt FROM chunks').fetchall();db.close()
    counts={};closed_m=0;closed_c=0
    for cid,state,n,owner,jid,receipt in rows:
        counts[state]=counts.get(state,0)+1
        if receipt:
            r=json.loads(receipt);closed_m+=r['molecules'];closed_c+=r['conformers']
    return rows,{'states':counts,'closed_new_molecules':closed_m,'closed_new_conformers':closed_c,'molecules_including_pilot':closed_m+10000,'expected_new_molecules':1210466}

def submit(template,node,cpus,mem,attempt=None):
    source=ROOT/'scripts'/template
    script=source
    if attempt is not None:
        script=source.with_name(source.stem+f'_attempt{attempt:02d}'+source.suffix)
        assert not script.exists()
        text=source.read_text();text=re.sub(r'(#SBATCH --job-name=\S+)',lambda m:m.group(1)+f'_a{attempt:02d}',text)
        script.write_text(text)
    p=subprocess.run(['python',str(ROOT/'scripts/submit.py'),str(script),'--node',node,'--cpus',str(cpus),'--mem-gib',str(mem)],cwd=PROJECT,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=120)
    save(ROOT/'reports'/('submission_attempt_'+script.stem+'.json'),{'timestamp':time.time(),'returncode':p.returncode,'stdout':p.stdout,'stderr':p.stderr})
    if p.returncode:
        if attempt is not None and not (ROOT/'submission'/(script.stem+'.json')).exists():
            # Keep failed candidate text, retry with a new unique name at the next resource check.
            pass
        return None
    receipt=json.loads((ROOT/'submission'/(script.stem+'.json')).read_text());return receipt['job_id']

def next_attempt(stem):
    existing=[p.name for p in (ROOT/'scripts').glob(stem+'_attempt*.sbatch')]
    return max([int(re.search(r'_attempt(\d+)\.sbatch$',n)[1]) for n in existing]+[0])+1

def stage_job(stem,records,actual):
    matches=[(jid,d) for jid,d in records.items() if d['stem'].startswith(stem)]
    if not matches:return None,None
    jid,d=max(matches,key=lambda v:v[1]['receipt']['timestamp'])
    return jid,actual[jid]

def main():
    assert os.getuid()==1278 and socket.gethostname().split('.')[0]=='sonmi'
    lock=(ROOT/'submission/full_coordinator_v7.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    prepared=json.loads((ROOT/'full/prepared.json').read_text())
    assert prepared['worker_sha256']==sha(ROOT/'scripts/full_dataset_v7.py') and prepared['source_sha256']==sha(ROOT/'scripts/sprime_v6.py')
    pinned={str(ROOT/'scripts'/name):sha(ROOT/'scripts'/name) for name in ['full_dataset_v7.py','sprime_v6.py','recover_full_v7.py','finalize_full_v7.py','reproduce100_full_v7.py','report_full_v7.py']}
    identity={'pid':os.getpid(),'uid':os.getuid(),'hostname':socket.gethostname(),'started_epoch':time.time(),'proc_start_ticks':Path('/proc/self/stat').read_text().split()[21],'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'source_sha256':sha(__file__),'pinned_sources':pinned,'poll_interval_seconds':600,'max_hours':24*21,'authorization_sha256':sha(ROOT/'reports/full_run_user_decision.json')}
    save(ROOT/'reports/full_coordinator_v7_identity.json',identity)
    deadline=time.monotonic()+21*86400
    while time.monotonic()<deadline:
        try:
            assert all(sha(p)==h for p,h in pinned.items()),'Frozen coordinator inputs changed'
            records=registered();actual=actual_jobs(records);rows,summary=queue_state()
            state={'timestamp':time.time(),'status':'GENERATING','queue':summary,'actual_jobs':actual}
            save(ROOT/'reports/full_coordinator_v7_status.json',state)
            stale=[r for r in rows if r[1]=='RUNNING' and r[4] in actual and actual[r[4]]['state'] in TERMINAL]
            recovery_id,recovery=stage_job('recover_full_v7',records,actual)
            recovery_active=recovery is not None and recovery['state'] not in TERMINAL
            if stale and not recovery_active:
                terminal={r[4]:actual[r[4]] for r in stale}
                save(ROOT/'reports/full_recovery_plan.json',{'timestamp':time.time(),'terminal_registered_jobs':terminal,'source_sha256':prepared['source_sha256']})
                stem='recover_full_v7';attempt=next_attempt(stem);submit(stem+'.sbatch','compute-0-2',16,32,attempt)
                state['status']='RECOVERY_SUBMITTED_OR_WAITING_FOR_RESOURCES'
            elif not stale and not recovery_active:
                if summary['states'].get('PENDING',0):
                    for node,cpus in NODES.items():
                        stem=f'full_worker_v7_node{node}';matches=[jid for jid,d in records.items() if d['stem'].startswith(stem)]
                        if any(actual[j]['state'] not in TERMINAL for j in matches):continue
                        submit(stem+'.sbatch',f'compute-0-{node}',cpus,64,next_attempt(stem))
                elif summary['states']=={'DONE':244}:
                    assert summary['closed_new_molecules']==1210466
                    stages=['finalize_full_v7','reproduce100_full_v7','report_full_v7']
                    for stem in stages:
                        jid,job=stage_job(stem,records,actual)
                        if job is None:
                            # Large final stages use the same 16 CPU resource floor.
                            subprocess.run(['python',str(ROOT/'scripts/collect_accounting.py'),'--stage','pilot_v6'],cwd=PROJECT,stdin=subprocess.DEVNULL,check=True,timeout=60)
                            submit(stem+'.sbatch','compute-0-2',16,32)
                            state['status']='SUBMITTED_'+stem.upper();break
                        if job['state'] not in TERMINAL:state['status']='WAITING_'+stem.upper();break
                        if job['state']!='COMPLETED' or job['exit_code']!='0:0':
                            state['status']='ROOT_REPAIR_REQUIRED_'+stem.upper();break
                        if stem=='report_full_v7':
                            accepted=json.loads((ROOT/'dataset/acceptance.json').read_text());assert accepted['status']=='FULL_DATASET_ACCEPTED'
                            state['status']='A_FULL_DATASET_AND_REPORT_ACCEPTED';state['acceptance']=accepted
                            save(ROOT/'reports/full_coordinator_v7_status.json',state);print(json.dumps(state),flush=True);return
            save(ROOT/'reports/full_coordinator_v7_status.json',state);print(json.dumps({'status':state['status'],'queue':summary}),flush=True)
        except Exception as exc:
            save(ROOT/'reports/full_coordinator_v7_error.json',{'timestamp':time.time(),'error':repr(exc)})
            print('ROOT_METADATA_ERROR '+repr(exc),flush=True)
        time.sleep(600)
    save(ROOT/'reports/full_coordinator_v7_status.json',{'status':'BOUNDED_COORDINATOR_EXPIRED','timestamp':time.time()})

if __name__=='__main__':main()
