"""Metadata-only pick of an eligible CPU partition node, unique immutable script/receipt."""
import hashlib,json,os,socket,subprocess,time
from pathlib import Path
R=Path('/share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016')
assert os.getuid()==1278 and socket.gethostname().split('.')[0]=='sonmi'
qptr=json.loads((R/'control/live_quota_v1/current.json').read_text());q=json.loads(Path(qptr['latest_path']).read_text())
assert q['complete'] and q['returncode']==0 and q['owner_uid']==1278 and 0<=time.time()-q['sampled_unix_seconds']<90
assert q['limit_kib']-q['used_kib']>=4*1024**2
v=os.statvfs(R);assert v.f_bavail*v.f_frsize>=4*1024**3 and v.f_favail>=10000
assert not list((R/'submission').glob('formal_cpu_pool_tests_v1_n*.json')),'REGISTERED_TASK_ALREADY_EXISTS'
raw=subprocess.check_output(['sinfo','--Node','--partition=cpu','--noheader','--format=%N|%t|%C|%m'],text=True,stdin=subprocess.DEVNULL,timeout=30)
candidates=[]
for line in raw.splitlines():
    node,state,cpus,memory=line.split('|')
    if node in ['compute-0-'+str(n) for n in [2,8,9,10,11,12,13,14,15,16,17,18,19]] and state in ['idle','mix'] and int(cpus.split('/')[1])>=16:candidates.append((state!='idle',-int(cpus.split('/')[1]),node))
assert candidates,'WAIT_FOR_AVAILABLE_CPU_NODE'
for _,_,node in sorted(candidates):
    name='formal_cpu_pool_tests_v1_n'+node.rsplit('-',1)[1]
    script=R/'scripts'/(name+'.sbatch');receipt=R/'submission'/(name+'.json')
    assert not receipt.exists(),'REGISTERED_JOB_ALREADY_EXISTS'
    template=(R/'scripts/message_source_gate_tests_v3.sbatch').read_text()
    lines=template.splitlines()
    lines=[('#SBATCH --job-name=srepair_'+name if l.startswith('#SBATCH --job-name=') else
        '#SBATCH --nodelist='+node if l.startswith('#SBATCH --nodelist=') else
        '#SBATCH --output='+str(R/'logs')+'/'+name+'_%j.log' if l.startswith('#SBATCH --output=') else l) for l in lines]
    lines[-1]=lines[-1].replace('/analysis/run_message_source_gate_tests_v1.py','/analysis/run_formal_cpu_pool_tests_v1.py')
    text='\n'.join(lines)+'\n'
    if script.exists():assert script.read_text()==text
    else:
        with script.open('x') as f:f.write(text)
    assert b'\r' not in script.read_bytes()
    subprocess.run(['bash','-n',str(script)],stdin=subprocess.DEVNULL,check=True)
    run=subprocess.run(['python','-B',str(R/'source_v3/workflows/s_denoise/submit.py'),str(script),'--node',node,'--cpus','16','--mem-gib','32'],stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=180)
    out=R/'reports'/(name+'_submission_attempt_'+str(time.time_ns())+'.json')
    with out.open('x') as f:json.dump(dict(node=node,sinfo=raw,returncode=run.returncode,stdout=run.stdout,stderr=run.stderr),f,indent=2)
    if run.returncode:
        if receipt.exists():raise RuntimeError('Actual sbatch attempt failed; review receipt')
        continue
    actual=json.loads(receipt.read_text())
    print(json.dumps(dict(status='FORMAL_CPU_POOL_TESTS_SUBMITTED',job_id=actual['job_id'],node=node,receipt=str(receipt))),flush=True)
    break
else:raise RuntimeError('WAIT_FOR_CPU_RESOURCES_MEMORY')
