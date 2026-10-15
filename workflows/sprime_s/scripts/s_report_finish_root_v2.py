"""Root-only metadata watcher; refresh evidence and close the real final report."""
import fcntl,json,os,socket,subprocess,time
from pathlib import Path
from prepare import ROOT,PROJECT,save,sha
from submit import query,fields

TERMINAL={'COMPLETED','FAILED','CANCELLED','TIMEOUT','OUT_OF_MEMORY','NODE_FAIL','PREEMPTED','BOOT_FAIL','DEADLINE','REVOKED'}

def state_of(job):
    rows=[line.split('|') for line in query(['sacct','-j',job,'-n','-P','--format=JobIDRaw,User,State,ExitCode']).splitlines() if line.split('|')[0]==job]
    if not rows:return {'state':'ACCOUNTING_NOT_YET_PUBLISHED'}
    assert len(rows)==1 and rows[0][1]=='zixiao'
    return {'state':rows[0][2].split()[0],'exit_code':rows[0][3]}

def main():
    assert os.getuid()==1278 and socket.gethostname().split('.')[0]=='sonmi'
    control=ROOT/'report_control';control.mkdir(exist_ok=True)
    lock=(control/'root_v2.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    binding_path=control/'binding_v2.json';binding=json.loads(binding_path.read_text())
    assert binding['status']=='ROOT_BOUND_REVIEWED_REPORT_FINISH_FLOW'
    for source in binding['sources']:assert sha(source['path'])==source['sha256']
    identity={'pid':os.getpid(),'uid':os.getuid(),'proc_start_ticks':Path('/proc/self/stat').read_text().split()[21],
        'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'source_sha256':sha(__file__),
        'binding_sha256':sha(binding_path),'interval_seconds':120,'max_hours':504}
    save(control/'identity_v2.json',identity)
    deadline=time.monotonic()+21*86400;next_refresh=0.;last_signature=None;active=None
    python='/share/home/zixiao/.conda/envs/chemprop/bin/python'
    while time.monotonic()<deadline:
        try:
            for source in binding['sources']:assert sha(source['path'])==source['sha256']
            b=json.loads((ROOT/'formal_s/root_coordinator_v1_status.json').read_text())
            probe=json.loads((ROOT/'probe_preparation_control/finish_root_v2_status.json').read_text())
            complete=b['status']=='ALL_THREE_TRAINING_RUNS_COMPLETE_AWAITING_H0_PROBES' and probe['status']=='ALL_SEVEN_ENDPOINTS_AND_OVERLAP_CLOSED'
            signature=(b['status'],tuple((k,v.get('state'),v.get('latest_job_id')) for k,v in b.get('conditions',{}).items()),tuple((k,v.get('probe_closed',False)) for k,v in probe.get('endpoints',{}).items()))
            state={'timestamp':time.time(),'status':'WAITING_FOR_FULL_EXPERIMENT','training_status':b['status'],'probe_status':probe['status'],'final_inputs_complete':complete}
            if active:
                actual=state_of(active);state['report_job']={'job_id':active,**actual}
                if actual['state'] in TERMINAL:
                    if actual['state']!='COMPLETED' or actual['exit_code']!='0:0':
                        state['status']='ROOT_REPAIR_REQUIRED_REPORT_JOB';save(control/'status_v2.json',state);time.sleep(120);continue
                    validation=json.loads((ROOT/'reports/current_experiment/artifact_validation.json').read_text())
                    assert validation['job_id']==active
                    archive=control/('report_job_'+active+'.json')
                    if not archive.exists():save(archive,{'actual_accounting':actual,'artifact_validation':validation,'summary_sha256':sha(ROOT/'reports/current_experiment/summary.json')})
                    if validation['complete_experiment']:
                        state['status']='FINAL_REPORT_AND_ARTIFACT_CLOSURE_COMPLETE_AWAITING_VISUAL_REVIEW'
                        save(control/'status_v2.json',state);return
                    active=None
            if not active and (complete or signature!=last_signature or time.monotonic()>=next_refresh):
                accounting=json.loads((ROOT/'formal_s/report_accounting_latest.json').read_text())
                registered={json.loads(p.read_text())['job_id'] for p in (ROOT/'submission').glob('formal_s_*.json') if json.loads(p.read_text()).get('job_id')}
                if not registered<=set(accounting['parents']) or time.time()-accounting['timestamp']>900:
                    state['status']='WAITING_FOR_FRESH_ACTUAL_SONMI_ACCOUNTING'
                else:
                    nodes=['compute-0-8','compute-0-9','compute-0-10','compute-0-11','compute-0-12','compute-0-2']
                    for node in nodes:
                        metadata=fields(query(['scontrol','show','node',node,'--oneliner']))
                        if int(metadata['CPUTot'])-int(metadata['CPUAlloc'])<16:continue
                        attempt=len(list((ROOT/'scripts').glob('s_report_refresh_v2_*.sbatch')))
                        stem='s_report_refresh_v2_'+str(attempt).zfill(4)
                        template=(ROOT/'scripts/s_current_report_v5.sbatch').read_text()
                        template=template.replace('sconv_current_report_v5','sconv_'+stem).replace('s_current_report_v5_%j',stem+'_%j').replace('compute-0-8',node)
                        path=ROOT/'scripts'/(stem+'.sbatch');assert not path.exists();path.write_text(template)
                        result=subprocess.run(['python',str(ROOT/'scripts/submit.py'),str(path),'--node',node,'--cpus','16','--mem-gib','32'],cwd=PROJECT,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=120)
                        save(control/('attempt_'+stem+'.json'),{'timestamp':time.time(),'returncode':result.returncode,'stdout':result.stdout,'stderr':result.stderr})
                        if result.returncode==0:
                            active=json.loads((ROOT/'submission'/(stem+'.json')).read_text())['job_id']
                            state['status']='ACTUAL_REPORT_JOB_SUBMITTED';state['report_job']={'job_id':active}
                            next_refresh=time.monotonic()+3600;last_signature=signature;break
            save(control/'status_v2.json',state)
            print(json.dumps({'status':state['status'],'report_job':state.get('report_job'),'final_inputs_complete':complete}),flush=True)
        except Exception as exc:
            save(control/'error_v2.json',{'timestamp':time.time(),'error':repr(exc)});print('REPORT_ROOT_METADATA_ERROR '+repr(exc),flush=True)
        time.sleep(120)
    save(control/'status_v2.json',{'status':'BOUNDED_REPORT_COORDINATOR_EXPIRED','timestamp':time.time()})

if __name__=='__main__':main()
