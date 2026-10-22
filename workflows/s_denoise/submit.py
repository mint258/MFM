"""Single Root submission entry; authentic resource snapshots and exact receipts."""
import argparse,fcntl,hashlib,json,os,re,socket,subprocess,time
from pathlib import Path
ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016')
PROJECT=ROOT.parent.parent

def query(argv):
    p=subprocess.run(argv,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=30)
    if p.returncode: raise RuntimeError({'argv':argv,'rc':p.returncode,'stderr':p.stderr})
    return p.stdout

def fields(text): return dict(re.findall(r'(\w+)=([^\s]+)',text))

def mem_mib(v):
    match=re.fullmatch(r'(\d+)([KMGTP]?)',v)
    if not match: raise ValueError('Unknown memory declaration '+v)
    amount=int(match[1]); unit=match[2] or 'M'
    return amount*{'K':1/1024,'M':1,'G':1024,'T':1024**2,'P':1024**3}[unit]

def main():
    ap=argparse.ArgumentParser();ap.add_argument('script');ap.add_argument('--node',required=True);ap.add_argument('--cpus',type=int,required=True);ap.add_argument('--mem-gib',type=int,required=True)
    a=ap.parse_args(); assert os.getuid()==1278 and socket.gethostname().split('.')[0]=='sonmi'
    assert a.cpus>=16
    script=Path(a.script).absolute();assert script.is_relative_to(ROOT)
    raw=script.read_bytes();assert b'\r' not in raw and raw.startswith(b'#!/bin/bash\n')
    name=re.search(rb'#SBATCH --job-name=(\S+)',raw)[1].decode()
    assert name.startswith(('srepair_',))
    receipts=ROOT/'submission';receipts.mkdir(exist_ok=True)
    with (receipts/'root.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        dest=receipts/(script.stem+'.json')
        if dest.exists(): raise FileExistsError('Registered job cannot be submitted again')
        before=query(['squeue','-h','-u','zixiao','-o','%i|%j|%N|%T'])
        if any(line.split('|')[1]==name for line in before.splitlines()): raise ValueError('Duplicate active job')
        sinfo=query(['sinfo','--Node','--nodes='+a.node,'--noheader','--format=%P|%N|%t|%C|%m'])
        node_raw=query(['scontrol','show','node',a.node,'--oneliner']);node=fields(node_raw)
        if int(node['CPUTot'])-int(node['CPUAlloc'])<a.cpus: raise ValueError('Wait for free CPUs')
        jobs=query(['squeue','-h','-w',a.node,'-t','RUNNING,COMPLETING','-o','%i'])
        declared=0.;job_refs=[]
        for jid in jobs.split():
            data=query(['scontrol','show','job',jid,'--oneliner']);info=fields(data)
            if 'MinMemoryNode' in info: amount=mem_mib(info['MinMemoryNode'])
            elif 'MinMemoryCPU' in info: amount=mem_mib(info['MinMemoryCPU'])*int(info['NumCPUs'])/int(info['NumNodes'])
            else: raise ValueError('Existing memory declaration unavailable')
            if amount==0: amount=int(node['RealMemory'])  # Slurm zero means no explicit bound.
            declared+=amount;job_refs.append({'job_id':jid,'metadata':data,'memory_mib_on_node':amount})
        committed=max(float(node['AllocMem']),declared)
        assert committed+a.mem_gib*1024<=int(node['RealMemory'])*.85,'Node declared memory budget unavailable'
        p=subprocess.run(['sbatch','--parsable','--chdir='+str(PROJECT),str(script)],cwd=PROJECT,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=30)
        result={'timestamp':time.time(),'uid':os.getuid(),'script':str(script),'sha256':hashlib.sha256(raw).hexdigest(),'queue_before':before,'node_metadata':node_raw,'sinfo':sinfo,'existing_jobs_all_users':job_refs,'committed_memory_mib':committed,'sbatch_rc':p.returncode,'sbatch_stdout':p.stdout,'sbatch_stderr':p.stderr}
        if p.returncode==0:
            jid=p.stdout.strip().split(';')[0]; assert jid.isdecimal();result['job_id']=jid
            actual=query(['scontrol','show','job',jid,'--oneliner']);result['actual_job_metadata']=actual
            info=fields(actual);assert info['WorkDir']==str(PROJECT) and info['ReqNodeList']==a.node
        dest.write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(result),flush=True)
        if p.returncode: raise RuntimeError('Slurm submission failed')

if __name__=='__main__':main()
