"""Root live scheduler admission; worker fallback is explicit, never accounting DB."""
from __future__ import annotations
from decimal import Decimal
from pathlib import Path
import re
import shlex
from common import *

NODE_QUERY=['scontrol','show','node',NODE]
QUEUE_QUERY=['squeue','-h','-w',NODE,'-o','%i|%u|%t|%m|%C']

def unavailable(row):
    if row['returncode']==0:return False
    return row.get('exception') in ('FileNotFoundError','TimeoutExpired') or any(
        x in row['stderr'].lower() for x in ('connection refused','unable to contact slurm',
        'persist_conn_open','slurm_persist_conn_open','accounting storage','problem talking to the database'))

def memory_mib(value,cpus):
    m=re.fullmatch(r'(\d+(?:\.\d+)?)([KMGT]?)([cn]?)',value)
    require(m and cpus>0,'Unknown all-user memory request')
    scale={'':Decimal(1),'K':Decimal(1)/1024,'M':Decimal(1),'G':Decimal(1024),'T':Decimal(1024**2)}
    return Decimal(m[1])*scale[m[2]]*(cpus if m[3]=='c' else 1)

def memory(node,queue,*,allocated):
    values=dict(re.findall(r'(CPUAlloc|CPUTot|RealMemory|AllocMem)=(\d+)',node))
    require(set(values)=={'CPUAlloc','CPUTot','RealMemory','AllocMem'} and
        not any(x in node for x in ('DOWN','DRAIN','UNKNOWN','NOT_RESPONDING')),'Unknown/unavailable Slurm node')
    requested=Decimal(0)
    for line in queue.splitlines():
        if not line.strip():continue
        fields=line.split('|');require(len(fields)==5,'Unknown all-user queue shape')
        if fields[2] in ('R','CG','CF'):requested+=memory_mib(fields[3],int(fields[4]))
    committed=max(requested,Decimal(values['AllocMem'])); total=Decimal(values['RealMemory'])
    after=committed+(0 if allocated else 32768)
    require(after<Decimal('.85')*total,'Node requested/allocated memory would reach85%')
    require(allocated or int(values['CPUTot'])-int(values['CPUAlloc'])>=16,'16 actual CPUs unavailable')
    return dict(total_MiB=str(total),queue_MiB=str(requested),AllocMem_MiB=values['AllocMem'],
        with_this_job_MiB=str(after),already_allocated=allocated)

def selected_gpu(gpus,apps):
    selected=[line.split(',') for line in gpus.splitlines() if line and normalized_uuid(line.split(',')[0])==GPU]
    require(len(selected)==1 and '5090' in selected[0][1] and selected[0][2].strip()=='590.44.01',
        'Exact physical5090/driver590.44.01 required')
    require(not any(normalized_uuid(line.split(',')[0])==GPU for line in apps.splitlines() if line.strip()),
        'Selected UUID has a foreign GPU compute process')
    return [x.strip() for x in selected[0]]

def observe(*,worker=False,root_frame=None):
    rows=[]
    def run(argv,*,local=False,check=True):
        command=argv
        if not worker and local:
            command=['ssh','-n','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes',
                '-o','UserKnownHostsFile='+str(OLD/'compute21_known_hosts_v1'),NODE,shlex.join(map(str,argv))]
        row=actual(command,check=check);rows.append(row);return row
    node=run(NODE_QUERY,check=not worker);queue=run(QUEUE_QUERY,check=not worker)
    fallback=worker and (node['returncode']!=0 or queue['returncode']!=0)
    if fallback:
        require(all(x['returncode']==0 or unavailable(x) for x in (node,queue)),
            'Unexpected scheduler failure cannot use fallback')
        require(root_frame is not None,'Missing sealed Root preallocation frame')
        old=root_frame['resource_observations']
        parent=[r for r in old['raw'] if r['argv'] in (NODE_QUERY,QUEUE_QUERY)]
        require(len(parent)==2,'Missing exact fresh Root controller observations')
        for row in parent:fresh(row)
        node=next(r for r in parent if r['argv']==NODE_QUERY)
        queue=next(r for r in parent if r['argv']==QUEUE_QUERY)
        require(node['returncode']==queue['returncode']==0,'Sealed Root scheduler call failed')
    mem=memory(node['stdout'],queue['stdout'],allocated=worker and not fallback)
    host=run(['hostname','-s'],local=True)['stdout'].strip();require(host==NODE,'Wrong actual node')
    available_raw=run(['cat','/proc/meminfo'],local=True)['stdout']
    matches=re.findall(r'^MemAvailable:\s*(\d+) kB$',available_raw,re.M)
    require(len(matches)==1,'Actual MemAvailable unknown')
    available=Decimal(matches[0])/1024
    require(available-32768>=Decimal('.15')*Decimal(mem['total_MiB']),
        'Actual MemAvailable cannot retain15% after job working set')
    gpus=run(['nvidia-smi','--query-gpu=uuid,name,driver_version,memory.total,memory.free',
        '--format=csv,noheader,nounits'],local=True)['stdout']
    apps=run(['nvidia-smi','--query-compute-apps=gpu_uuid,pid,process_name,used_gpu_memory',
        '--format=csv,noheader,nounits'],local=True)['stdout']
    gpu=selected_gpu(gpus,apps)
    run(['flock','-n',str(LOCK),'/bin/true'],local=True)
    return dict(raw=rows,memory=mem,gpu_row=gpu,MemAvailable_MiB=str(available),foreign_compute_processes=[],
        scheduler_scope='sealed_fresh_Root_preallocation_frame_not_worker_live' if fallback else 'actual_live_controller',
        GPU_scope='actual_worker_NVML' if worker else 'actual_node_NVML_via_login_SSH',
        lock_probe_only=True)

def process_allocation(job):
    require(str(job)==os.environ.get('SLURM_JOB_ID') and os.environ.get('SLURM_CPUS_PER_TASK')=='16'
        and os.environ.get('SLURM_MEM_PER_NODE')=='32768' and socket.gethostname()==NODE
        and os.getuid()==1278 and os.environ.get('CUDA_VISIBLE_DEVICES')==GPU,'Actual GPU allocation/environment differs')
    cgroup=Path('/proc/self/cgroup').read_text()
    require(re.search(r'(?:job[_/-])'+re.escape(str(job))+r'(?:[/\n]|$)',cgroup),
        'Actual Slurm job cgroup missing')
    return dict(job_id=str(job),uid=os.getuid(),hostname=socket.gethostname(),
        cgroup=cgroup,boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
        CPU_request=16,memory_request_MiB=32768,proof='actual_Slurm_environment_plus_kernel_job_cgroup',
        allocated_memory_source='Root_sbatch_request_and_actual_environment_not_fabricated_AllocTRES')
