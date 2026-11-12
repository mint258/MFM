"""Poll only metadata; submit taskbook step 1 when an isolated GPU is available."""
import json
import os
from pathlib import Path
import re
import subprocess
import time

ROOT = Path('/share/home/zixiao/descriptor_analysis/MFM_model_v3_cpu_perf_20261112')
OUT = ROOT/'results/model_v3_perf_20261112'
NODES = ('compute-0-20', 'compute-0-21', 'compute-0-22', 'compute-0-1', 'compute-0-3', 'compute-0-4', 'compute-0-0', 'compute-0-5', 'compute-0-6', 'compute-0-7')
PYTHON128 = '/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage43_5090_environment/install_4511929/venv/bin/python'
PYTHON118 = '/share/home/zixiao/.venvs/model_v2_cu118_20261105/bin/python'


def command(argv):
    return subprocess.check_output(argv, text=True, stdin=subprocess.DEVNULL, timeout=30).strip()


def publish(value):
    # Metadata only, nevertheless retain actual root and NFS disk protection.
    for path in (Path('/'), OUT):
        stats = os.statvfs(path)
        total, available = stats.f_blocks*stats.f_frsize, stats.f_bavail*stats.f_frsize
        reserve = max(10*1024**3, (total+9)//10) if path == Path('/') else 100_000_000_000
        if available < reserve+1024**2 or stats.f_favail < 10:
            raise OSError('Controller disk headroom unavailable; no new metadata writes')
    value.update(pid=os.getpid(), observed_time=time.time(), host=os.uname().nodename,
                 boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
                 start_ticks=Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19])
    pending=OUT/'adaptive_state.next.json'
    pending.write_text(json.dumps(value,indent=2)+'\n')
    pending.replace(OUT/'adaptive_state.json')
    print(json.dumps(value),flush=True)


def choose():
    # Do not compete with the model line's already running or queued chains.
    reserved=set()
    for row in command(['squeue','-h','-u','zixiao','-o','%i|%T|%r|%j']).splitlines():
        job,state,reason,name=row.split('|',3)
        if name.startswith(('v3-cpu-perf','v3-sdk-')) or reason=='JobHeldUser':
            continue
        info=command(['scontrol','show','job',job,'--oneliner'])
        fields=dict(re.findall(r'(\w+)=([^ ]+)',info))
        for field in ('ReqNodeList','NodeList'):
            value=fields.get(field,'')
            if value and value!='(null)':
                reserved.update(command(['scontrol','show','hostnames',value]).splitlines())
    observations=[]
    for node in NODES:
        if node in reserved:
            observations.append(dict(node=node,status='MODEL_LINE_RESERVED'))
            continue
        text=command(['scontrol','show','node',node,'--oneliner'])
        fields=dict(re.findall(r'(\w+)=([^ ]+)',text))
        free=int(fields['CPUTot'])-int(fields['CPUAlloc'])
        if any(s in fields.get('State','') for s in ('DRAIN','DOWN','FAIL')) or free<4:
            observations.append(dict(node=node,free_cpu=free,status='CPU_UNAVAILABLE'))
            continue
        inventory=command(['ssh','-n','-o','BatchMode=yes','-o','ConnectTimeout=5',node,
            'nvidia-smi --query-gpu=uuid,name --format=csv,noheader; nvidia-smi --query-compute-apps=gpu_uuid,pid --format=csv,noheader'])
        gpus=[];busy=set()
        for line in inventory.splitlines():
            parts=[x.strip() for x in line.split(',')]
            if len(parts)!=2 or not parts[0].startswith('GPU-'):
                continue
            if parts[1].isdigit():
                busy.add(parts[0])
            elif any(x in parts[1] for x in ('5090','4090','3090')):
                gpus.append((parts[0],parts[1]))
        observations.append(dict(node=node,free_cpu=free,gpus=gpus,busy=sorted(busy)))
        for uuid,name in gpus:
            if uuid not in busy:
                cores=min(16,free)
                return dict(node=node,gpu=uuid,name=name,cores=cores,
                            python=PYTHON118 if '3090' in name else PYTHON128),observations
    return None,observations


def main():
    os.chdir(ROOT)
    job=None
    while True:
        try:
            if job:
                state=command(['squeue','-h','-j',job,'-o','%T'])
                if state:
                    publish(dict(status='STEP1_JOB_LIVE',job=job,state=state,plan=plan))
                else:
                    marker=Path('/lfshome/zixiao/model_v3_perf_20261112')/('step1_'+job)/'STEP1_COMPLETE.json'
                    if marker.is_file():
                        publish(dict(status='STEP1_COMPLETE_REVIEW_PROFILING_NEXT',job=job,plan=plan,marker=str(marker)))
                        return
                    # Do not silently repeat a measurement after failure; preserve the failure.
                    terminal=command(['sacct','-n','-X','-j',job,'--format=JobID,State,ExitCode','--parsable2'])
                    publish(dict(status='STEP1_TERMINAL_REQUIRES_INSPECTION',job=job,terminal=terminal,plan=plan))
                    return
            else:
                plan,observations=choose()
                if plan is None:
                    publish(dict(status='WAITING_FOR_IDLE_AUTHORIZED_GPU',observations=observations))
                else:
                    export=','.join(['ALL','MFM_CPU_GPU_UUIDS='+plan['gpu'],'MFM_CPU_PYTHON='+plan['python']])
                    job=command(['sbatch','--parsable','--nodelist='+plan['node'],
                        '--cpus-per-task='+str(plan['cores']),'--export='+export,
                        'tools/model_v3/cpu_bottleneck_step1.sbatch']).split(';')[0]
                    if not job.isdigit():
                        raise RuntimeError('No actual Slurm job ID returned')
                    publish(dict(status='STEP1_SUBMITTED',job=job,plan=plan))
        except (OSError,RuntimeError,KeyError,subprocess.SubprocessError) as error:
            publish(dict(status='OBSERVATION_RETRY',job=job,reason=str(error)))
        time.sleep(60)


if __name__=='__main__':
    main()
