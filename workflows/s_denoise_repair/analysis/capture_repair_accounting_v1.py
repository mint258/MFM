"""Sonmi metadata capture of every actual registered parent in this task.

CPU core-hours count actual AllocCPUS times actual parent ElapsedRaw once.
GPU-node allocation hours include setup/evaluation/waiting; these are not GPU
utilization hours or exclusive GPU reservations. Failed parents are retained.
"""
from __future__ import annotations
import argparse,hashlib,json,os,socket,subprocess,time
from pathlib import Path
ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016')
TERMINAL={'COMPLETED','FAILED','CANCELLED','TIMEOUT','OUT_OF_MEMORY','NODE_FAIL','PREEMPTED','BOOT_FAIL','DEADLINE','REVOKED'}
COLUMNS=['JobIDRaw','User','State','ExitCode','ElapsedRaw','AllocCPUS','NodeList','Start','End']
def ref(path):
    raw=Path(path).read_bytes();return {'path':str(path),'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)}
def query(argv):
    p=subprocess.run(argv,stdin=subprocess.DEVNULL,text=True,capture_output=True,timeout=60)
    if p.returncode:raise RuntimeError({'argv':argv,'returncode':p.returncode,'stderr':p.stderr})
    return p.stdout
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True);ap.add_argument('--allow-active',action='store_true');a=ap.parse_args()
    assert os.getuid()==1278 and socket.gethostname().split('.')[0]=='sonmi'
    assert a.output.is_absolute() and a.output.is_relative_to(ROOT/'control/repair_accounting_snapshots') and not a.output.exists()
    receipts={};unsubmitted=[]
    for path in sorted((ROOT/'submission').glob('*.json')):
        d=json.loads(path.read_text());job=d.get('job_id')
        if job is None:
            assert d.get('sbatch_rc',1)!=0,'Ambiguous successful submission without actual job ID'
            unsubmitted.append({'reference':ref(path),'reason':'NO_REGISTERED_JOB_ID'});continue
        job=str(job);assert job.isdecimal()
        script=Path(d['script']);assert script.is_absolute() and script.is_relative_to(ROOT)
        sr=ref(script);assert sr['sha256']==d['sha256']
        row={'reference':ref(path),'script_reference':sr,'script_name':script.stem}
        receipts.setdefault(job,[]).append(row)
    assert receipts
    raw=query(['sacct','-X','-j',','.join(sorted(receipts)),'-n','-P','--format='+','.join(COLUMNS)])
    rows={};core_seconds=gpu_node_seconds=0;active=[]
    for line in raw.splitlines():
        cols=line.split('|')
        if cols[0] not in receipts:continue
        assert len(cols)==len(COLUMNS) and cols[1]=='zixiao'
        assert cols[0] not in rows and cols[4].isdecimal() and cols[5].isdecimal()
        row=dict(zip(COLUMNS,cols));state=row['State'].split()[0]
        row['terminal']=state in TERMINAL
        row['elapsed_seconds']=int(row['ElapsedRaw']);row['allocated_cpus']=int(row['AllocCPUS'])
        row['allocated_CPU_core_seconds']=row['elapsed_seconds']*row['allocated_cpus']
        gpu_node=row['NodeList'] in ['compute-0-20','compute-0-21','compute-0-22']
        row['GPU_node_allocation_seconds']=row['elapsed_seconds'] if gpu_node else 0
        row['submission_references']=receipts[cols[0]];rows[cols[0]]=row
        core_seconds+=row['allocated_CPU_core_seconds'];gpu_node_seconds+=row['GPU_node_allocation_seconds']
        if not row['terminal']:active.append(cols[0])
    assert set(rows)==set(receipts),'Missing actual registered parent accounting'
    queue=query(['squeue','-h','-u','zixiao','-o','%i|%j|%N|%T'])
    unknown=[line for line in queue.splitlines() if line and line.split('|')[1].startswith('srepair_') and line.split('|')[0] not in rows]
    assert not unknown,'Unregistered live S-repair task needs audit'
    if not a.allow_active:assert not active,'Final costs require all actual parents terminal'
    document={'status':'ACTUAL_ALL_REGISTERED_REPAIR_PARENTS_TERMINAL' if not active else 'INTERIM_ACTUAL_REPAIR_ACCOUNTING_ACTIVE_JOBS_REMAIN',
       'timestamp_unix':time.time(),'host':socket.gethostname(),'uid':os.getuid(),'columns':COLUMNS,'raw_sacct':raw,
       'raw_own_queue':queue,'rows':rows,'active_parent_ids':active,'unsubmitted_receipts':unsubmitted,
       'unique_registered_parent_count':len(rows),'allocated_CPU_core_hours':core_seconds/3600,
       'GPU_node_allocation_hours':gpu_node_seconds/3600,'failed_and_cancelled_parents_included':True,
       'batch_extern_or_step_rows_added_to_parent_cost':False,'metadata_services_have_no_Slurm_allocation':True,
       'GPU_timing_definition':'Single GPU-node job wall allocation including setup, evaluation and waits; not utilization or exclusivity',
       'source_reference':ref(Path(__file__))}
    a.output.parent.mkdir(parents=True,exist_ok=True)
    with a.output.open('x') as f:json.dump(document,f,indent=2,allow_nan=False);f.write('\n')
    print(json.dumps({k:document[k] for k in ['status','unique_registered_parent_count','allocated_CPU_core_hours','GPU_node_allocation_hours','active_parent_ids']}),flush=True)
if __name__=='__main__':main()
