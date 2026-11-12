"""Wait for one isolated old/new 200-step acceptance; never auto-replay a capture."""
import json,os,subprocess,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).absolute().parent))
from cpu_perf_wait import choose,command,ROOT,OUT


def publish(value):
    for path in (Path('/'),OUT):
        stat=os.statvfs(path);total=stat.f_blocks*stat.f_frsize
        reserve=max(10*1024**3,(total+9)//10) if path==Path('/') else 100_000_000_000
        if stat.f_bavail*stat.f_frsize<reserve+1024**2 or stat.f_favail<10:
            raise OSError('Actual metadata filesystem headroom unavailable')
    value.update(pid=os.getpid(),observed_time=time.time(),host=os.uname().nodename,
        boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
        start_ticks=Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19])
    pending=OUT/'equivalence_wait.next.json';pending.write_text(json.dumps(value,indent=2)+'\n')
    pending.replace(OUT/'equivalence_wait.json');print(json.dumps(value),flush=True)


def main():
    os.chdir(ROOT);job=None
    while True:
        try:
            if job:
                state=command(['squeue','-h','-j',job,'-o','%T'])
                if state:publish(dict(status='ACCEPTANCE_JOB_LIVE',job=job,state=state,plan=plan))
                else:
                    result=Path('/lfshome/zixiao/model_v3_perf_20261112')/('equivalence_'+job)/'acceptance.json'
                    terminal=command(['sacct','-n','-X','-j',job,'--format=JobID,State,ExitCode','--parsable2'])
                    publish(dict(status='ACCEPTANCE_TERMINAL_REVIEW_REQUIRED',job=job,plan=plan,
                                 terminal=terminal,result=str(result) if result.is_file() else None))
                    return
            else:
                captured=list(Path('/lfshome/zixiao/model_v3_perf_20261112').glob('equivalence_*/*/trace_200.json'))
                if captured:
                    publish(dict(status='EXISTING_CAPTURE_REVIEW_REQUIRED',paths=list(map(str,captured))));return
                plan,observations=choose()
                if plan is None:publish(dict(status='WAITING_FOR_IDLE_ACCEPTANCE_GPU',observations=observations))
                else:
                    export=','.join(['ALL','MFM_CPU_GPU_UUIDS='+plan['gpu'],'MFM_CPU_PYTHON='+plan['python']])
                    job=command(['sbatch','--parsable','--nodelist='+plan['node'],'--cpus-per-task='+str(plan['cores']),
                        '--export='+export,'tools/model_v3/cpu_perf_equivalence.sbatch']).split(';')[0]
                    if not job.isdigit():raise RuntimeError('No actual acceptance job returned')
                    publish(dict(status='ACCEPTANCE_SUBMITTED',job=job,plan=plan))
        except (OSError,RuntimeError,KeyError,subprocess.SubprocessError) as error:
            publish(dict(status='OBSERVATION_RETRY',job=job,reason=str(error)))
        time.sleep(60)


if __name__=='__main__':main()
