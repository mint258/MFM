"""Metadata-only CPU dispatch of a final guide-STOP diagnostic packet."""
import argparse,json,os,re,shlex,socket,subprocess,time
from pathlib import Path
from dispatch_stage3_gate_v1 import R,P,PYTHON,query,sha

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--tag',required=True);ap.add_argument('--gate-tag',required=True)
    ap.add_argument('--phases',nargs='+',required=True);ap.add_argument('--profiles',type=Path,nargs='+',required=True);ap.add_argument('--performance-reference',type=Path);a=ap.parse_args()
    assert os.getuid()==1278 and socket.gethostname().split('.')[0]=='sonmi'
    assert all(re.fullmatch(r'[A-Za-z0-9_]+',s) for s in [a.tag,a.gate_tag]+a.phases)
    task='diagnostic_stop_packet_'+a.tag
    stop=json.loads((R/'GUIDE_STOP.json').read_text());assert stop['reason'] in ['D3_MESSAGE_LAYER_CAPABILITY_FAILED','STAGE3_GATES_NOT_ALL_PASSED']
    assert not list((R/'submission').glob(task+'_n*.json')),'RENDER_JOB_ALREADY_REGISTERED'
    gate_receipts=list((R/'submission').glob('stage3_gate_eval_'+a.gate_tag+'_n*.json'));assert len(gate_receipts)==1
    gate_receipt=json.loads(gate_receipts[0].read_text());jid=gate_receipt['job_id']
    raw=query(['sacct','-j',jid,'-n','-X','-P','-o','JobIDRaw,State,ExitCode,ElapsedRaw,AllocCPUS'])
    rows=[line.split('|') for line in raw.splitlines() if line.strip()]
    assert len(rows)==1 and rows[0][0]==jid and rows[0][1:3]==['COMPLETED','0:0'],'ACTUAL_GATE_CPU_PARENT_NOT_CLOSED_C0'
    gate=R/'reports'/('Stage3_gate_'+a.gate_tag+'.json');g=json.loads(gate.read_text())
    assert g['phase'] in a.phases and g['status'] in ['ALL_STAGE3_GATES_PASS','STAGE3_GATES_NOT_ALL_PASSED']
    snapshot=R/'control/accounting_snapshots'/('stage3_gate_eval_'+a.gate_tag+'_v1.json')
    assert any(row['path']==str(snapshot) and row['sha256']==sha(snapshot) for row in g['scientific_inputs'])
    if a.performance_reference:
        assert a.performance_reference.is_absolute() and a.performance_reference.is_relative_to(R/'reports')
        assert a.performance_reference.is_file()
    gate_snapshot=snapshot
    identifiers=set()
    for phase in a.phases:
        control=R/'control'/phase;st=json.loads((control/'status.json').read_text())
        assert st['status'] in ['D3_PHASE_COMPLETE_AWAITING_SCIENTIFIC_GATE','D3_MESSAGE_LAYER_CAPABILITY_FAILED']
        for key,job in json.loads((control/'jobs.json').read_text()).items():
            p=json.loads((R/'reports'/(key+'_latest.json')).read_text());assert sha(p['path'])==p['sha256']
            result=json.loads(Path(p['path']).read_text());assert result['status']=='D3_CONDITION_COMPLETE' and result['optimizer_updates']==4000 and result['runtime']['job_id']==job['job_id']
            assert result['configuration_sha256']==job['configuration_sha256']==sha(job['configuration']);identifiers.add(job['job_id'])
    closed_raw=query(['sacct','-j',','.join(sorted(identifiers)),'-n','-X','-P','-o','JobIDRaw,State,ExitCode,ElapsedRaw,AllocCPUS'])
    closed_rows={r[0]:r[1:] for r in (line.split('|') for line in closed_raw.splitlines() if line.strip())}
    assert set(closed_rows)==identifiers and all(row[:2]==['COMPLETED','0:0'] for row in closed_rows.values())
    snapshot=R/'control/accounting_snapshots'/(task+'_v1.json')
    if not snapshot.exists():
        subprocess.run(['python','-B',str(R/'analysis/capture_actual_parents_v1.py'),'--phases']+a.phases+['completed_lookup_reference_v1','--include-tests','--output',str(snapshot)],stdin=subprocess.DEVNULL,check=True)
    snap=json.loads(snapshot.read_text());assert all(snap['rows'][jid]==row for jid,row in closed_rows.items())
    for profile in a.profiles:assert profile.is_absolute() and profile.is_relative_to(R/'reports') and profile.is_file()
    output=R/'reports'/('final_diagnostic_stop_'+a.tag);assert not output.exists()
    qp=json.loads((R/'control/live_quota_v1/current.json').read_text());q=json.loads(Path(qp['latest_path']).read_text())
    assert q['complete'] and q['returncode']==0 and q['owner_uid']==1278 and 0<=time.time()-q['sampled_unix_seconds']<90
    assert q['limit_kib']-q['used_kib']>=4*1024**2
    v=os.statvfs(R);assert v.f_bavail*v.f_frsize>=4*1024**3 and v.f_favail>=10000
    source_check=json.loads((R/'reports/source_v3_repository_check_v26.json').read_text());assert source_check['status']=='PASS'
    node_snapshot=query(['sinfo','--Node','--partition=cpu','--noheader','--format=%N|%t|%C|%m']);nodes=[]
    for line in node_snapshot.splitlines():
        node,state,cpus,_=line.split('|')
        if node in ['compute-0-'+str(n) for n in [2,8,9,10,11,12,13,14,15,16,17,18,19]] and state in ['idle','mix'] and int(cpus.split('/')[1])>=16:
            nodes.append((state!='idle',-int(cpus.split('/')[1]),node))
    assert nodes,'WAIT_FOR_CPU_RESOURCES'
    argv=[PYTHON,'-B',str(R/'analysis/render_stop_packet_v3.py'),'--phases']+a.phases+['--parent-snapshot',str(snapshot),'--gate',str(gate),'--output-dir',str(output)]
    argv+=['--profiles']+[str(p) for p in a.profiles]
    if a.performance_reference:argv+=['--performance-reference',str(a.performance_reference)]
    for _,_,node in sorted(nodes):
        name=task+'_n'+node.rsplit('-',1)[1];script=R/'scripts'/(name+'.sbatch')
        text='\n'.join(['#!/bin/bash','#SBATCH --job-name=srepair_'+name,'#SBATCH --partition=cpu','#SBATCH --nodelist='+node,
            '#SBATCH --cpus-per-task=16','#SBATCH --mem=32G','#SBATCH --time=00:10:00','#SBATCH --output='+str(R/'logs')+'/'+name+'_%j.log',
            'set -euo pipefail','cd '+str(R/'source_v3'),'export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1',
            'srun --input=none --ntasks=1 --cpus-per-task=16 --cpu-bind=cores '+shlex.join(argv)])+'\n'
        if script.exists():assert script.read_text()==text
        else:
            with script.open('x') as f:f.write(text)
        subprocess.run(['bash','-n',str(script)],stdin=subprocess.DEVNULL,check=True)
        run=subprocess.run(['python','-B',str(R/'source_v3/workflows/s_denoise/submit.py'),str(script),'--node',node,'--cpus','16','--mem-gib','32'],stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=180)
        with (R/'reports'/(name+'_attempt_'+str(time.time_ns())+'.json')).open('x') as f:
            json.dump(dict(node=node,returncode=run.returncode,stdout=run.stdout,stderr=run.stderr,sinfo=node_snapshot,gate_job_id=jid,gate_actual_parent=rows[0],gate_sha256=sha(gate)),f,indent=2)
        receipt=R/'submission'/(name+'.json')
        if run.returncode:
            assert not receipt.exists(),'ACTUAL_SBATCH_ATTEMPT_FAILED_REVIEW_RECEIPT'
            continue
        actual=json.loads(receipt.read_text());print(json.dumps(dict(status='FINAL_GUIDE_STOP_PACKET_CPU_SUBMITTED',job_id=actual['job_id'],node=node,output=str(output))),flush=True);return
    raise RuntimeError('WAIT_FOR_CPU_MEMORY_RESOURCES')
if __name__=='__main__':main()
