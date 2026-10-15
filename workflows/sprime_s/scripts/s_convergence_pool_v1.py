"""Two independent S conditions, each 16 bound CPUs and its own GPU UUID lock."""
from __future__ import annotations
import argparse,csv,fcntl,json,os,signal,socket,subprocess,time
from pathlib import Path
from prepare import ROOT,PROJECT,save,sha

def own_group_usage(groups):
    total=0;members=[]
    for path in Path('/proc').iterdir():
        if not path.name.isdigit():continue
        try:
            if path.stat().st_uid!=os.getuid():continue
            tail=(path/'stat').read_text().rsplit(')',1)[1].split()
            if int(tail[2]) not in groups:continue
            pages=int(tail[21]);rss=pages*os.sysconf('SC_PAGE_SIZE')
            total+=rss;members.append({'pid':int(path.name),'pgid':int(tail[2]),'start_ticks':tail[19],'rss_bytes':rss})
        except (FileNotFoundError,ProcessLookupError,PermissionError):continue
    return total,members

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--binding',required=True);args=ap.parse_args()
    assert os.getuid()==1278 and socket.gethostname().split('.')[0]=='compute-0-21'
    assert int(os.environ['SLURM_CPUS_PER_TASK'])>=33
    binding=json.loads(Path(args.binding).read_text())
    assert binding['status']=='ROOT_BOUND_FORMAL_S_POOL'
    for ref in binding['sources']+binding['configurations']:assert sha(ref['path'])==ref['sha256']
    assert sha(ROOT/'formal_s/run_plan_v1.json')==binding['run_plan_sha256']
    lock=(ROOT/'formal_s/pool_v1.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    available=sorted(os.sched_getaffinity(0));assert len(available)>=33
    slots=[available[:16],available[16:32]];os.sched_setaffinity(0,{available[32]})
    gpu_query=subprocess.run(['nvidia-smi','--query-gpu=uuid,name,memory.total,memory.free','--format=csv,noheader,nounits'],capture_output=True,text=True,check=True,timeout=20)
    gpu_rows=list(csv.reader(gpu_query.stdout.splitlines()))
    assert sum(int(row[3])>=.95*int(row[2]) for row in gpu_rows)>=2,'Two currently idle GPUs required for the two-slot pool'
    job=os.environ['SLURM_JOB_ID'];folder=ROOT/'formal_s'/('pool_'+job);folder.mkdir(exist_ok=False)
    journal=(folder/'events.jsonl').open('a');started=time.monotonic();requested_stop=False
    def request_stop(signum,frame):
        nonlocal requested_stop
        requested_stop=True
    signal.signal(signal.SIGUSR1,request_stop);signal.signal(signal.SIGTERM,request_stop)
    states={row['condition']:{'configuration':row,'state':'PENDING','segments':[],'io_failures':0} for row in binding['configurations']}
    active={};stop_reason=None;signal_sent=set();last_observation=0.;sequence=0
    def record(value):
        value={'timestamp':time.time(),'job_id':job,**value}
        journal.write(json.dumps(value,allow_nan=False)+'\n');journal.flush();os.fsync(journal.fileno())
        print(json.dumps(value),flush=True)
    record({'event':'POOL_STARTED','slot_cpu_affinities':slots,'supervisor_cpu':[available[32]],
            'slurm_cpus':int(os.environ['SLURM_CPUS_PER_TASK']),'gpus_at_start':gpu_rows,
            'gpu_protection':'USER_ACCEPTED_SHARED_GPU_RISK','binding_sha256':sha(args.binding)})
    try:
        while True:
            # Poll completions before launching the next bounded segment.
            for slot,child in list(active.items()):
                code=child['process'].poll()
                if code is None:continue
                child['log'].close();state=states[child['condition']]
                summary_path=ROOT/'s_training'/child['condition']/child['segment_name']/'summary.json'
                summary=json.loads(summary_path.read_text()) if summary_path.exists() else {'status':'MISSING_ACTUAL_CHILD_SUMMARY'}
                receipt={'segment_name':child['segment_name'],'child_pid':child['process'].pid,'returncode':code,
                    'summary_path':str(summary_path),'summary_sha256':sha(summary_path) if summary_path.exists() else None,
                    'status':summary['status'],'consumed_records':summary.get('consumed_records'),
                    'optimizer_updates':summary.get('optimizer_updates'),'gpu_uuid':summary.get('gpu_uuid'),
                    'elapsed_seconds':summary.get('elapsed_seconds')}
                state['segments'].append(receipt);del active[slot]
                if summary_path.exists():
                    assert summary['job_id']==job and summary['config_sha256']==state['configuration']['sha256']
                    assert summary['development_only'] is False
                if summary.get('scientific_stop') or 'SCIENTIFIC_STOP' in summary.get('error','') or 'ACTUAL_RECORD_MANIFEST_MISMATCH' in summary.get('error',''):
                    state['state']='SCIENTIFIC_STOP';stop_reason='GUIDE_SCIENTIFIC_STOP_'+child['condition']
                    save(ROOT/'formal_s/scientific_stop.json',{'status':stop_reason,'receipt':receipt,'summary':summary,'timestamp':time.time()})
                elif code==0 and summary['status']=='TRAINING_EXPOSURES_COMPLETE_AWAITING_H0_PROBES':
                    assert summary['epoch_accepted'] and len(summary['completed_epochs'])==state['configuration']['epochs']
                    state['state']='TRAINING_COMPLETE_AWAITING_PROBES'
                elif code==0 and summary['status']=='PARTIAL_CHECKPOINT_REQUIRES_CONTINUATION':
                    state['state']='PENDING'
                elif summary['status']=='RUNNER_FAILED_RETRYABLE_LOADER_TIMEOUT' and state['io_failures']<3:
                    state['io_failures']+=1;state['state']='PENDING'
                else:
                    state['state']='ROOT_REPAIR_REQUIRED';stop_reason='ROOT_REPAIR_REQUIRED_'+child['condition']
                record({'event':'SEGMENT_TERMINAL','condition':child['condition'],'receipt':receipt,'condition_state':state['state']})
            if requested_stop or time.monotonic()-started>=44*3600:
                stop_reason=stop_reason or 'POOL_BOUNDED_WALL_OR_REQUESTED_STOP'
            if time.monotonic()-last_observation>=30:
                rss,members=own_group_usage({v['process'].pid for v in active.values()})
                if rss>56*(1<<30):stop_reason=stop_reason or 'OWN_AGGREGATE_RSS_EXCEEDS_56_GIB'
                observations={'timestamp':time.time(),'status':'RUNNING' if not stop_reason else stop_reason,
                    'job_id':job,'active':[{k:v[k] for k in ['condition','segment_name']}|{'pid':v['process'].pid} for v in active.values()],
                    'owned_aggregate_rss_bytes':rss,'owned_processes':members,'conditions':states,
                    'elapsed_seconds':time.monotonic()-started,'formal_training_complete':False}
                save(folder/'status.json',observations);save(ROOT/'formal_s/latest_pool_status.json',observations)
                last_observation=time.monotonic()
            if stop_reason:
                for child in active.values():
                    pid=child['process'].pid
                    if pid not in signal_sent and child['process'].poll() is None:
                        # Signal only the recorded direct child, preserving its checkpoint path.
                        assert child['process'].pid==pid and os.getpgid(pid)==pid
                        child['process'].send_signal(signal.SIGUSR1);signal_sent.add(pid)
                if not active:break
            else:
                for slot in range(2):
                    if slot in active:continue
                    order=['B3_seed0','B1_seed0','B1_seed1']
                    ready=next((name for name in order if states[name]['state']=='PENDING'),None)
                    if ready is None:continue
                    state=states[ready];ref=state['configuration'];assert sha(ref['path'])==ref['sha256']
                    tag='pool_'+str(sequence).zfill(4);sequence+=1;segment_name='segment_'+job+'_'+tag
                    argv=[binding['python'],'-B',str(ROOT/'scripts/s_convergence_runner_v7.py'),
                        '--configuration',ref['path'],'--segment-tag',tag]
                    latest=ROOT/'s_training'/ready/'latest_checkpoint.json'
                    if latest.exists():
                        checkpoint=json.loads(latest.read_text());assert sha(checkpoint['path'])==checkpoint['sha256']
                        assert Path(checkpoint['path']).is_relative_to(ROOT/'s_training'/ready)
                        argv+=['--resume',checkpoint['path']]
                    cpus=set(slots[slot]);stream=(folder/(ready+'_'+tag+'.log')).open('wb')
                    process=subprocess.Popen(argv,cwd=PROJECT,stdin=subprocess.DEVNULL,stdout=stream,stderr=subprocess.STDOUT,
                        start_new_session=True,preexec_fn=lambda chosen=cpus:os.sched_setaffinity(0,chosen))
                    state['state']='RUNNING';active[slot]={'condition':ready,'segment_name':segment_name,'process':process,'log':stream}
                    record({'event':'SEGMENT_STARTED','condition':ready,'segment_name':segment_name,'pid':process.pid,
                        'slot':slot,'cpu_affinity':sorted(cpus),'resume_checkpoint':checkpoint if latest.exists() else None})
                if not active and all(s['state']=='TRAINING_COMPLETE_AWAITING_PROBES' for s in states.values()):break
            time.sleep(5)
        result={'status':stop_reason or 'ALL_THREE_S_RUNS_TRAINING_COMPLETE_AWAITING_H0_PROBES','job_id':job,
            'conditions':states,'elapsed_seconds':time.monotonic()-started,'binding_sha256':sha(args.binding),
            'scientific_convergence_judgment_complete':False,'all_required_probes_complete':False}
        save(folder/'summary.json',result);save(ROOT/'formal_s/latest_pool_summary.json',result);record({'event':'POOL_TERMINAL','status':result['status']})
        if stop_reason and stop_reason.startswith('ROOT_REPAIR_REQUIRED'):raise RuntimeError(stop_reason)
    finally:
        journal.close();lock.close()

if __name__=='__main__':main()
