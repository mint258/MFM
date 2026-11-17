"""One read-only Slurm/CPU/GPU observation; no trainer is signaled or modified."""
import argparse,csv,json,os,pathlib,re,socket,subprocess,time
from h_resources import REPO,guard,save

def environment(pid):
    entries=(pathlib.Path('/proc')/str(pid)/'environ').read_bytes().split(b'\0')
    wanted={'SLURM_JOB_ID','SLURM_CPUS_PER_TASK','CUDA_VISIBLE_DEVICES'}
    return {key.decode():value.decode() for entry in entries if b'=' in entry for key,value in [entry.split(b'=',1)] if key.decode(errors='replace') in wanted}

def identity(pid):
    directory=pathlib.Path('/proc')/str(pid)
    if directory.stat().st_uid!=os.getuid():raise PermissionError('Not an owned process')
    fields=(directory/'stat').read_text().rsplit(')',1)[1].split()
    return dict(pid=pid,uid=os.getuid(),pgid=os.getpgid(pid),ppid=int(fields[1]),start_ticks=int(fields[19]),cpu_mask=sorted(os.sched_getaffinity(pid)))

def main():
    p=argparse.ArgumentParser();p.add_argument('--job',type=int,required=True);p.add_argument('--arm',choices=['T2','T3','T4','T5'],required=True);p.add_argument('--gpu',required=True);a=p.parse_args()
    guard(force=True)
    target=REPO/'results/p_heads/T'/(a.arm+'_resources_'+str(a.job)+'.json')
    if target.exists():
        print('RESOURCE_OBSERVATION_ALREADY_RECORDED',str(target),flush=True);return
    configuration=json.loads((REPO/'configs/p_heads/T'/(a.arm+'_seed0.json')).read_text())
    output=pathlib.Path(configuration['output'])
    with (output/'losses.csv').open() as stream:first=next(csv.DictReader(stream))
    if int(first['samples'])!=32 or not (output/'samples_32.pt').is_file():raise RuntimeError('First32 producer checkpoint not yet published')
    candidates=[]
    for directory in pathlib.Path('/proc').iterdir():
        if not directory.name.isdigit():continue
        try:
            if directory.stat().st_uid!=os.getuid():continue
            env=environment(int(directory.name))
            command=(directory/'cmdline').read_bytes()
            if env.get('SLURM_JOB_ID')==str(a.job) and b't_train.py' in command and b'--configuration' in command:candidates.append((int(directory.name),env))
        except (FileNotFoundError,ProcessLookupError,PermissionError):continue
    if len(candidates)!=1:raise RuntimeError('Expected one owned trainer for this real job')
    pid,env=candidates[0];parent=identity(pid);records=[];todo=[pid];seen={pid}
    while todo:
        current=todo.pop()
        children=set()
        try:tasks=list((pathlib.Path('/proc')/str(current)/'task').iterdir())
        except FileNotFoundError:continue
        for task in tasks:
            try:children.update((task/'children').read_text().split())
            except FileNotFoundError:continue
        for child in children:
            child=int(child)
            if child in seen:continue
            seen.add(child);todo.append(child)
            try:
                row=identity(child);command=(pathlib.Path('/proc')/str(child)/'cmdline').read_bytes()
                row['reader']=b'multiprocessing.spawn' in command and b'spawn_main' in command
                records.append(row)
            except (FileNotFoundError,ProcessLookupError):continue
    readers=[row for row in records if row['reader']]
    observations=dict(parent_mask_has15=len(parent['cpu_mask'])==15,
        slurm_declares15=env.get('SLURM_CPUS_PER_TASK')=='15',
        configured_reader_maximum=configuration['workers'],actual_reader_count=len(readers),
        descendants_within_parent_mask=all(set(row['cpu_mask'])<=set(parent['cpu_mask']) for row in records),
        visible_gpu_matches=env.get('CUDA_VISIBLE_DEVICES','').split(',')[0]==a.gpu)
    contexts=list(csv.reader(subprocess.check_output(['nvidia-smi','--query-compute-apps=gpu_uuid,pid','--format=csv,noheader,nounits'],text=True).splitlines()))
    observations['actual_gpu_context_matches']=any(len(row)==2 and row[0].strip()==a.gpu and row[1].strip()==str(pid) for row in contexts)
    control=subprocess.check_output(['scontrol','show','job','-d',str(a.job)],text=True)
    facts=dict(re.findall(r'(JobId|JobState|NodeList|NumCPUs|CPUs/Task|CPU_IDs)=([^\s]+)',control))
    save(target,dict(status='OBSERVED',observed_time_unix=time.time(),job_id=a.job,arm=a.arm,node=socket.gethostname().split('.')[0],gpu_uuid=a.gpu,parent=parent,readers=readers,other_descendants=[row for row in records if not row['reader']],slurm=facts,checkpoint_32=str(output/'samples_32.pt'),checkpoint_present=True,checkpoint_contents_reread=False,configuration_workers=configuration['workers'],observations=observations,scientific_benchmark=False))
    print('RESOURCE_OBSERVATION_COMPLETE',a.arm,a.job,pid,len(readers),parent['cpu_mask'],flush=True)
if __name__=='__main__':main()
