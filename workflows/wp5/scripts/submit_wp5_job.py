"""Single-coordinator Slurm submission with current node CPU/memory checks."""
import argparse, hashlib, json, os, re, subprocess, time
from pathlib import Path
ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011')

def run(argv):
    p=subprocess.run(argv,capture_output=True,text=True,stdin=subprocess.DEVNULL,timeout=45)
    if p.returncode:raise RuntimeError(str(argv)+': '+p.stderr)
    return p.stdout

def memory_mib(value):
    m=re.fullmatch(r'(\d+(?:\.\d+)?)([KMGT]?)',value)
    if not m:raise ValueError('Unsupported memory value '+value)
    return float(m[1])*{'K':1/1024,'':1,'M':1,'G':1024,'T':1024**2}[m[2]]

def main():
    p=argparse.ArgumentParser();p.add_argument('--script',required=True)
    p.add_argument('--name',required=True);p.add_argument('--node',required=True)
    p.add_argument('--cpus',type=int,default=16);p.add_argument('--memory-gb',type=int,default=32)
    p.add_argument('--time',default='02:00:00');p.add_argument('--kind',choices=['audit','quantum','resource'],required=True)
    p.add_argument('--allow-pending',action='store_true',help='Permit queueing a node-specific job while CPUs are currently busy')
    p.add_argument('--dependency',help='Root-owned afterok job dependency')
    args,extra=p.parse_known_args();script=Path(args.script).absolute();assert args.node in [f'compute-0-{i}' for i in range(14,20)], 'WP5 nodes 14..19 only'
    if args.dependency and not re.fullmatch(r'after(?:ok|any):\d+(?::\d+)*',args.dependency):
        raise ValueError('Only explicit afterok/afterany job IDs are supported')
    if not script.is_relative_to(ROOT) or not script.is_file():raise ValueError('Expected current-task script')
    data=script.read_bytes()
    if b'\r' in data:raise ValueError('Slurm script must use LF')
    if args.cpus<16:raise ValueError('At least 16 CPUs required')
    run(['bash','-n',str(script)])
    queue=run(['squeue','-u','zixiao','-h','-o','%i|%j|%T|%N'])
    if any(line.split('|')[1]==args.name for line in queue.splitlines()):raise RuntimeError('Task name already queued')
    node=run(['scontrol','show','node',args.node]);exact=run(['sinfo','--Node','--nodes='+args.node,'-h','-o','%N|%P|%t|%C'])
    fields=dict(re.findall(r'(\w+)=([^\s]+)',node))
    idle=int(fields['CPUTot'])-int(fields['CPUAlloc'])
    node_jobs=run(['squeue','-w',args.node,'-h','-o','%i'])
    details=[];memory=0.0
    for jid in node_jobs.split():
        text=run(['scontrol','show','job','-o',jid]);f=dict(re.findall(r'(\w+)=([^\s]+)',text))
        if f.get('JobState') not in ['RUNNING','COMPLETING']:continue
        declared=0.0
        if 'MinMemoryNode' in f:declared=memory_mib(f['MinMemoryNode'])
        elif 'MinMemoryCPU' in f:declared=memory_mib(f['MinMemoryCPU'])*int(f['NumCPUs'])
        memory+=declared;details.append({'job':jid,'declared_mib':declared,'raw':text})
    if idle<args.cpus and not args.allow_pending:raise RuntimeError(f'Insufficient current idle CPUs on {args.node}: {idle}')
    committed=max(memory,float(fields.get('AllocMem',0)))
    if committed+args.memory_gb*1024 > float(fields['RealMemory'])*.85:
        raise RuntimeError('Declared memory plus new request exceeds 85% RealMemory')
    partition='cpu' if 'cpu' in fields.get('Partitions','').split(',') else 'all'
    stamp=time.strftime('%Y%m%d_%H%M%S');receipt=ROOT/'logs'/f'{args.name}_{stamp}_submission.json'
    argv=['sbatch','--parsable','--job-name='+args.name,'--partition='+partition,
        '--nodelist='+args.node,'--nodes=1','--ntasks=1','--cpus-per-task='+str(args.cpus),
        '--mem='+str(args.memory_gb)+'G','--time='+args.time,
        '--output='+str(ROOT/'logs'/(args.name+'_%j.out')),
        '--error='+str(ROOT/'logs'/(args.name+'_%j.err'))]
    if args.dependency:argv.append('--dependency='+args.dependency)
    argv += [str(script)]+extra
    record={'time':time.time(),'kind':args.kind,'script':str(script),
        'script_sha256':hashlib.sha256(data).hexdigest(),'node':args.node,'node_raw':node,
        'node_exact':exact,'all_node_jobs':details,'memory_committed_mib':committed,
        'memory_request_mib':args.memory_gb*1024,'own_queue_before':queue,'argv':argv,
        'queued_while_cpus_busy':idle<args.cpus,'allow_pending':args.allow_pending}
    result=run(argv).strip();record['job_id']=result.split(';')[0];record['sbatch_stdout']=result
    receipt.write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps({'job_id':record['job_id'],'receipt':str(receipt),'name':args.name,'node':args.node}))

if __name__=='__main__':main()

