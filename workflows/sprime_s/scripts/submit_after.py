"""Queue one reviewed recovery behind its exact owned predecessor, without overlap."""
import argparse,fcntl,hashlib,json,os,re,socket,subprocess,time
from pathlib import Path
from submit import ROOT,PROJECT,query,fields,mem_mib

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--group',type=int,required=True);ap.add_argument('--revision',choices=['recover','pilot_v4','pilot_v5','pilot_v6'],default='recover');a=ap.parse_args()
    placement={1:(2,32),2:(8,64),3:(9,64),4:(10,64),5:(11,64)}
    nodeid,cpus=placement[a.group];node='compute-0-'+str(nodeid)
    assert os.getuid()==1278 and socket.gethostname().split('.')[0]=='sonmi'
    predecessor=({'pilot_v5':'pilot_v4_group','pilot_v6':'pilot_v5_group'}.get(a.revision,'pilot_group'))+str(a.group)
    previous=json.loads((ROOT/f'submission/{predecessor}.json').read_text());jid=previous['job_id']
    stem=f'{a.revision}_group{a.group}'
    script=ROOT/f'scripts/{stem}.sbatch';raw=script.read_bytes()
    assert raw.startswith(b'#!/bin/bash\n') and b'\r' not in raw
    dest=ROOT/f'submission/{stem}.json'
    with (ROOT/'submission/root.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if dest.exists():raise FileExistsError('Recovery already registered')
        queue=query(['squeue','-h','-u','zixiao','-o','%i|%j|%N|%T'])
        name={'recover':'sprime_recover_group','pilot_v4':'sprime_v4_group','pilot_v5':'sprime_v5_group','pilot_v6':'sprime_v6_group'}[a.revision]+str(a.group)
        assert not any(line.split('|')[1]==name for line in queue.splitlines())
        old_query=subprocess.run(['scontrol','show','job',jid,'--oneliner'],stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=30)
        active=False;old_memory=0.;old_cpus=0
        if old_query.returncode==0:
            old=fields(old_query.stdout)
            assert old['UserId']=='zixiao(1278)' and old['WorkDir']==str(PROJECT) and old['ReqNodeList']==node
            active=old['JobState'] in {'RUNNING','COMPLETING','PENDING'}
            if old['JobState'] in {'RUNNING','COMPLETING'}:
                old_memory=mem_mib(old['MinMemoryNode']);old_cpus=int(old['NumCPUs'])
        else:
            terminal=query(['sacct','-j',jid,'--noheader','--parsable2','--format=JobIDRaw,User,State,ExitCode'])
            rows=[line.split('|') for line in terminal.splitlines() if line.split('|')[0]==jid]
            assert len(rows)==1 and rows[0][1]=='zixiao' and rows[0][2] in {'COMPLETED','FAILED','TIMEOUT','CANCELLED','OUT_OF_MEMORY'}
        nraw=query(['scontrol','show','node',node,'--oneliner']);n=fields(nraw)
        assert int(n['CPUTot'])-int(n['CPUAlloc'])+old_cpus>=cpus
        declared=0.;job_refs=[]
        for other in query(['squeue','-h','-w',node,'-t','RUNNING,COMPLETING','-o','%i']).split():
            data=query(['scontrol','show','job',other,'--oneliner']);info=fields(data)
            amount=mem_mib(info['MinMemoryNode']) if 'MinMemoryNode' in info else mem_mib(info['MinMemoryCPU'])*int(info['NumCPUs'])/int(info['NumNodes'])
            if not amount:amount=int(n['RealMemory'])
            declared+=amount;job_refs.append({'job_id':other,'metadata':data,'memory_mib':amount})
        future=max(float(n['AllocMem']),declared)-old_memory
        assert max(future,0)+65536<=int(n['RealMemory'])*.85
        argv=['sbatch','--parsable','--chdir='+str(PROJECT)]
        if active:argv.append('--dependency=afterany:'+jid)
        argv.append(str(script))
        p=subprocess.run(argv,cwd=PROJECT,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=30)
        assert p.returncode==0,(p.returncode,p.stderr)
        actual_id=p.stdout.strip().split(';')[0];assert actual_id.isdecimal()
        actual=query(['scontrol','show','job',actual_id,'--oneliner']);actual_fields=fields(actual)
        assert actual_fields['WorkDir']==str(PROJECT) and actual_fields['ReqNodeList']==node
        result={'job_id':actual_id,'predecessor_job_id':jid,'predecessor_active':active,'predecessor_metadata':old_query.stdout,'predecessor_query_rc':old_query.returncode,'script':str(script),'sha256':hashlib.sha256(raw).hexdigest(),'queue_before':queue,'node_metadata':nraw,'existing_jobs_all_users':job_refs,'future_committed_memory_mib':max(future,0),'argv':argv,'sbatch_rc':p.returncode,'sbatch_stdout':p.stdout,'sbatch_stderr':p.stderr,'actual_job_metadata':actual,'timestamp':time.time()}
        dest.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'job_id':actual_id,'group':a.group,'dependency':jid if active else 'predecessor_terminal'}),flush=True)

if __name__=='__main__':main()
