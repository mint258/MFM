"""Own-process supervision for one frozen S training segment under Slurm."""
from __future__ import annotations
import argparse,csv,json,os,signal,socket,subprocess,time
from pathlib import Path
from prepare import ROOT,PROJECT,save,sha

def process_identity(pid):
    path=Path('/proc')/str(pid);tail=(path/'stat').read_text().rsplit(')',1)[1].split()
    return {'pid':pid,'uid':path.stat().st_uid,'pgid':int(tail[2]),'start_ticks':tail[19],
            'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip()}

def own_rss(pgid):
    total=0;members=[]
    for path in Path('/proc').iterdir():
        if not path.name.isdigit():continue
        try:
            if path.stat().st_uid!=os.getuid():continue
            tail=(path/'stat').read_text().rsplit(')',1)[1].split()
            if int(tail[2])!=pgid:continue
            rss=int(tail[21])*os.sysconf('SC_PAGE_SIZE');total+=rss
            members.append({'pid':int(path.name),'start_ticks':tail[19],'rss_bytes':rss})
        except (FileNotFoundError,ProcessLookupError,PermissionError):continue
    return total,members

def output_bytes(segment,job):
    roots=[segment]+[p for p in Path('/tmp').glob('sconv_runner_'+job+'_*') if p.stat().st_uid==os.getuid()]
    total=0
    for root in roots:
        if not root.exists():continue
        for path in root.rglob('*'):
            try:
                if path.is_file() and not path.is_symlink():total+=path.stat().st_size
            except FileNotFoundError:pass
    return total

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--configuration',required=True);ap.add_argument('--binding',required=True);ap.add_argument('--resume');args=ap.parse_args()
    assert os.getuid()==1278 and int(os.environ['SLURM_CPUS_PER_TASK'])>=16
    assert socket.gethostname().split('.')[0] in ['compute-0-20','compute-0-21','compute-0-22']
    assert len(os.sched_getaffinity(0))>=16
    binding=json.loads(Path(args.binding).read_text())
    assert binding['status']=='ROOT_BOUND_FORMAL_S_CONTROLLER'
    for ref in binding['sources']:assert sha(ref['path'])==ref['sha256']
    cfg=json.loads(Path(args.configuration).read_text());condition=cfg['kind']+'_seed'+str(cfg['seed'])
    ref=next(v for v in binding['configurations'] if v['condition']==condition)
    assert str(Path(args.configuration).absolute())==ref['path'] and sha(args.configuration)==ref['sha256']
    assert cfg['status']=='FORMAL_PROTOCOL_RESOLVED_AND_FROZEN'
    job=os.environ['SLURM_JOB_ID'];segment=ROOT/'s_training'/condition/('segment_'+job)
    controller=ROOT/'formal_s'/('launcher_'+job);controller.mkdir(exist_ok=False)
    argv=[binding['python'],'-B',str(ROOT/'scripts/s_convergence_runner_v8.py'),'--configuration',args.configuration]
    if args.resume:
        assert Path(args.resume).absolute().is_relative_to(ROOT/'s_training'/condition)
        argv+=['--resume',args.resume]
    child=subprocess.Popen(argv,cwd=PROJECT,stdin=subprocess.DEVNULL,start_new_session=True)
    identity=process_identity(child.pid);assert identity['uid']==1278 and identity['pgid']==child.pid
    save(controller/'identity.json',{'job_id':job,'condition':condition,'node':socket.gethostname(),'child':identity,
        'configuration_sha256':ref['sha256'],'launcher_sha256':sha(__file__),'binding_sha256':sha(args.binding)})
    requested=False;signal_sent=False;reason=None;started=time.monotonic();maximum_rss=maximum_output=0
    def request(signum,frame):
        nonlocal requested
        requested=True
    signal.signal(signal.SIGUSR1,request);signal.signal(signal.SIGTERM,request)
    gpu_rows=list(csv.reader(subprocess.run(['nvidia-smi','--query-gpu=uuid,name,memory.total','--format=csv,noheader,nounits'],
        capture_output=True,text=True,check=True,timeout=20).stdout.splitlines()))
    gpu_limits={row[0].strip():(int(row[2])-1024)*(1<<20) for row in gpu_rows}
    try:
        while child.poll() is None:
            rss,members=own_rss(child.pid);used=output_bytes(segment,job)
            maximum_rss=max(maximum_rss,rss);maximum_output=max(maximum_output,used)
            applications=subprocess.run(['nvidia-smi','--query-compute-apps=gpu_uuid,pid,used_memory','--format=csv,noheader,nounits'],
                capture_output=True,text=True,timeout=20)
            assert applications.returncode==0,applications.stderr
            app_rows=list(csv.reader(applications.stdout.splitlines()))
            owned=[r for r in app_rows if r[1].strip().isdigit() and int(r[1])==child.pid]
            if owned:
                assert len(owned)==1 and owned[0][0].strip() in gpu_limits
                if int(owned[0][2])*(1<<20)>gpu_limits[owned[0][0].strip()]:reason=reason or 'OWN_GPU_MEMORY_EXCEEDS_MEASURED_TOTAL_MINUS_1_GIB'
            if rss>56*(1<<30):reason=reason or 'OWN_RSS_EXCEEDS_56_GIB'
            if used>int(1.70*(1<<30)):reason=reason or 'SEGMENT_OUTPUT_SOFT_LIMIT_1P70_GIB'
            if time.monotonic()-started>=3*3600:reason=reason or 'LAUNCHER_SOFT_WALL_3_HOURS'
            if requested:reason=reason or 'OWN_LAUNCHER_SIGNAL'
            if (ROOT/'formal_s/scientific_stop.json').exists():reason=reason or 'GUIDE_COHORT_SCIENTIFIC_STOP'
            if reason and not signal_sent and child.poll() is None:
                assert process_identity(child.pid)==identity
                child.send_signal(signal.SIGUSR1);signal_sent=True
            observation={'status':'SEGMENT_RUNNING' if reason is None else 'OWN_GRACEFUL_STOP_REQUESTED',
                'job_id':job,'condition':condition,'reason':reason,'elapsed_seconds':time.monotonic()-started,
                'own_rss_bytes':rss,'own_output_bytes_including_scratch':used,'owned_processes':members,
                'gpu_apps_actual':app_rows,'own_gpu_memory_limits_bytes':gpu_limits,
                'gpu_protection':'USER_ACCEPTED_SHARED_GPU_RISK','timestamp':time.time()}
            save(controller/'status.json',observation)
            time.sleep(30)
        summary_path=segment/'summary.json';summary=json.loads(summary_path.read_text()) if summary_path.exists() else None
        result={'status':'ACTUAL_CHILD_TERMINAL','job_id':job,'condition':condition,'returncode':child.returncode,
            'reason':reason,'elapsed_seconds':time.monotonic()-started,'peak_own_rss_bytes':maximum_rss,
            'peak_own_output_bytes_including_scratch':maximum_output,'child_identity':identity,
            'actual_summary_path':str(summary_path),'actual_summary_sha256':sha(summary_path) if summary else None,
            'gpu_protection':'USER_ACCEPTED_SHARED_GPU_RISK'}
        save(controller/'summary.json',result)
        assert summary is not None,'Actual training summary is missing'
        if child.returncode:raise SystemExit(child.returncode)
    finally:
        if child.poll() is None:
            assert process_identity(child.pid)==identity
            child.send_signal(signal.SIGUSR1)
            # Slurm retains the outer wall bound; never signal somebody else's process.
            child.wait()

if __name__=='__main__':main()
