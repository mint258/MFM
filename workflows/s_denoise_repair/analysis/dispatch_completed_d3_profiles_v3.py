"""Metadata-only dispatch of existing frozen D3 profile math after actual two-seed closure."""
import argparse,hashlib,json,os,re,socket,subprocess,time
from pathlib import Path
R=Path('/share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016')
P=R.parent.parent
PYTHON=str(P/'docs/phase1/evidence/stage43_5090_environment/install_4511929/venv/bin/python')

def query(args):return subprocess.check_output(args,stdin=subprocess.DEVNULL,text=True,timeout=30)
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--phase',default='d3_local_blocks_v1');ap.add_argument('--conditions',nargs='+',required=True);ap.add_argument('--tag',required=True);a=ap.parse_args()
    assert os.getuid()==1278 and socket.gethostname().split('.')[0]=='sonmi'
    assert all(re.fullmatch(r'[A-Za-z0-9_]+',v) for v in [a.phase,a.tag]+a.conditions)
    task='completed_d3_profiles_'+a.tag
    assert not list((R/'submission').glob(task+'_n*.json')),'PROFILE_JOB_ALREADY_REGISTERED'
    jobs=json.loads((R/'control'/a.phase/'jobs.json').read_text());selected={}
    for condition in a.conditions:
        for seed in [0,1]:
            key=condition+'_seed'+str(seed);job=jobs[key]
            ptr=json.loads((R/'reports'/(key+'_latest.json')).read_text());assert sha(ptr['path'])==ptr['sha256']
            result=json.loads(Path(ptr['path']).read_text())
            assert result['status']=='D3_CONDITION_COMPLETE' and result['optimizer_updates']==4000 and result['runtime']['job_id']==job['job_id']
            assert result['configuration_sha256']==job['configuration_sha256']==sha(job['configuration'])
            selected[job['job_id']]=key
    raw=query(['sacct','-j',','.join(selected),'-n','-X','-P','-o','JobIDRaw,State,ExitCode,ElapsedRaw,AllocCPUS'])
    parents={row[0]:row[1:] for row in (line.strip().split('|') for line in raw.splitlines() if line.strip())}
    assert set(parents)==set(selected) and all(row[:2]==['COMPLETED','0:0'] for row in parents.values()),'SELECTED_PARENTS_NOT_CLOSED_C0'
    snapshot=R/'control/accounting_snapshots'/(task+'_v1.json')
    if not snapshot.exists():
        phases=[a.phase]+([] if a.phase=='d3_local_blocks_v1' else ['d3_local_blocks_v1'])+['completed_lookup_reference_v1']
        subprocess.run(['python','-B',str(R/'analysis/capture_actual_parents_v1.py'),'--phases']+phases+['--include-tests','--output',str(snapshot)],stdin=subprocess.DEVNULL,check=True)
    snap=json.loads(snapshot.read_text());assert snap['status']=='ACTUAL_SONMI_SACCT_SNAPSHOT' and snap['host']=='sonmi' and snap['uid']==1278
    assert all(snap['rows'][jid]==row for jid,row in parents.items())
    qptr=json.loads((R/'control/live_quota_v1/current.json').read_text());quota=json.loads(Path(qptr['latest_path']).read_text())
    assert quota['complete'] and quota['returncode']==0 and quota['owner_uid']==1278 and 0<=time.time()-quota['sampled_unix_seconds']<90
    assert quota['limit_kib']-quota['used_kib']>=4*1024**2
    v=os.statvfs(R);assert v.f_bavail*v.f_frsize>=4*1024**3 and v.f_favail>=10000
    node_snapshot=query(['sinfo','--Node','--partition=cpu','--noheader','--format=%N|%t|%C|%m']);nodes=[]
    for line in node_snapshot.splitlines():
        node,state,cpus,_=line.split('|')
        if node in ['compute-0-'+str(n) for n in [2,8,9,10,11,12,13,14,15,16,17,18,19]] and state in ['idle','mix'] and int(cpus.split('/')[1])>=16:nodes.append((state!='idle',-int(cpus.split('/')[1]),node))
    assert nodes,'WAIT_FOR_CPU_RESOURCES'
    output=R/'reports'/('completed_D3_profiles_'+a.tag);assert not output.exists(),'PROFILE_OUTPUT_ALREADY_EXISTS'
    for _,_,node in sorted(nodes):
        name=task+'_n'+node.rsplit('-',1)[1];script=R/'scripts'/(name+'.sbatch')
        args=['--phase',a.phase,'--conditions']+a.conditions+['--parent-snapshot',str(snapshot),'--output',str(output)]
        text='\n'.join(['#!/bin/bash','#SBATCH --job-name=srepair_'+name,'#SBATCH --partition=cpu','#SBATCH --nodelist='+node,
            '#SBATCH --cpus-per-task=16','#SBATCH --mem=32G','#SBATCH --time=00:05:00','#SBATCH --output='+str(R/'logs')+'/'+name+'_%j.log',
            'set -euo pipefail','cd '+str(R/'source_v3'),'export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1',
            'export PYTHONPATH='+str(R/'analysis')+':'+str(R/'source_v3/workflows/s_denoise'),
            'srun --input=none --ntasks=1 --cpus-per-task=16 --cpu-bind=cores '+PYTHON+' -B '+str(R/'analysis/profile_completed_d3_conditions_v3.py')+' '+' '.join(args)])+'\n'
        if script.exists():assert script.read_text()==text
        else:
            with script.open('x') as stream:stream.write(text)
        assert b'\r' not in script.read_bytes();subprocess.run(['bash','-n',str(script)],stdin=subprocess.DEVNULL,check=True)
        run=subprocess.run(['python','-B',str(R/'source_v3/workflows/s_denoise/submit.py'),str(script),'--node',node,'--cpus','16','--mem-gib','32'],stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=180)
        with (R/'reports'/(name+'_attempt_'+str(time.time_ns())+'.json')).open('x') as stream:json.dump(dict(node=node,returncode=run.returncode,stdout=run.stdout,stderr=run.stderr,sinfo=node_snapshot),stream,indent=2)
        receipt=R/'submission'/(name+'.json')
        if run.returncode:
            assert not receipt.exists(),'ACTUAL_SBATCH_ATTEMPT_FAILED_REVIEW_RECEIPT'
            continue
        actual=json.loads(receipt.read_text());print(json.dumps(dict(status='FROZEN_PROFILE_MATH_SUBMITTED',job_id=actual['job_id'],node=node,conditions=a.conditions,output=str(output))),flush=True);return
    raise RuntimeError('WAIT_FOR_CPU_MEMORY_RESOURCES')

if __name__=='__main__':main()
