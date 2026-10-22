"""Read-only runtime counters, restricted to this exact owned Slurm job."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import time

ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    assert os.getuid()==1278 and os.environ['SLURM_JOB_ID']=='4515527'
    assert socket.gethostname().split('.')[0]=='compute-0-9'
    assert args.output.is_absolute() and args.output.is_relative_to(ROOT/'reports') and not args.output.exists()
    entries=[]
    for proc in Path('/proc').iterdir():
        if not proc.name.isdecimal():continue
        try:
            if proc.stat().st_uid!=1278:continue
            environment=(proc/'environ').read_bytes().split(b'\0')
            if b'SLURM_JOB_ID=4515527' not in environment:continue
            fields=(proc/'stat').read_text().rsplit(')',1)[1].split()
            command=(proc/'cmdline').read_bytes()
            role='lookup_parent' if b'refit_lookup.py' in command else 'spawn_worker' if b'spawn_main' in command else 'other_owned_job_process'
            io={}
            try:io={k:int(v) for k,v in (line.split(':',1) for line in (proc/'io').read_text().splitlines())}
            except (PermissionError,FileNotFoundError):pass
            entries.append(dict(pid=int(proc.name),ppid=int(fields[1]),role=role,state=fields[0],
                cpu_ticks=int(fields[11])+int(fields[12]),clock_ticks_per_second=os.sysconf('SC_CLK_TCK'),
                RSS_bytes=int(fields[21])*os.sysconf('SC_PAGE_SIZE'),wchan=(proc/'wchan').read_text(),io=io,
                start_ticks=fields[19],user_cpu_ticks=int(fields[11]),system_cpu_ticks=int(fields[12]),minor_faults=int(fields[7]),major_faults=int(fields[9]),
                allowed_CPU_count=len(os.sched_getaffinity(int(proc.name)))))
        except (FileNotFoundError,ProcessLookupError,PermissionError):continue
    memory={}
    for line in Path('/proc/meminfo').read_text().splitlines():
        key,value=line.split(':',1)
        if key in ['MemTotal','MemAvailable','MemFree','SwapTotal','SwapFree','Cached','Dirty','Writeback','Slab']:
            memory[key]=value.strip()
    cgrows=Path('/proc/self/cgroup').read_text().splitlines();cgroups=[]
    for line in cgrows:
        hierarchy,controllers,name=line.split(':',2)
        if 'memory' not in controllers.split(',') and not (hierarchy=='0' and controllers==''):continue
        mount=Path('/sys/fs/cgroup') if hierarchy=='0' else Path('/sys/fs/cgroup/memory')
        parts=Path(name).parts
        for length in range(len(parts),0,-1):
            relative=Path(*parts[1:length]);path=mount/relative
            if '4515527' not in str(path):continue
            fields={}
            for filename in ['memory.current','memory.max','memory.swap.current','memory.events','memory.stat',
                'memory.limit_in_bytes','memory.usage_in_bytes','memory.memsw.usage_in_bytes','memory.failcnt']:
                candidate=path/filename
                if candidate.is_file():fields[filename]=candidate.read_text()[:16000]
            cgroups.append(dict(path=str(path),fields=fields))
    pressure={}
    for item in ['memory','io']:
        path=Path('/proc/pressure')/item
        if path.is_file():pressure[item]=path.read_text()
    report=dict(status='READ_ONLY_EXACT_OWN_JOB_RUNTIME_COUNTERS',timestamp=time.time(),host=socket.gethostname(),
        job_id='4515527',entries=entries,py_spy_path=shutil.which('py-spy'),memory_info=memory,cgroup_memory=cgroups,pressure=pressure,
        source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        no_process_signalled_or_modified=True,no_dataset_or_model_execution=True)
    with args.output.open('x') as stream:json.dump(report,stream,indent=2);stream.write('\n')
    print(json.dumps(dict(status=report['status'],job_id='4515527',entries=len(entries),
        parent=[e for e in entries if e['role']=='lookup_parent'],spawn_workers=sum(e['role']=='spawn_worker' for e in entries),
        worker_cpu_ticks=sum(e['cpu_ticks'] for e in entries if e['role']=='spawn_worker'),memory_info=memory,cgroup_memory=cgroups,pressure=pressure)))


if __name__=='__main__':main()
