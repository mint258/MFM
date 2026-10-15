"""Root-only bounded Slurm coordination of the three guide-defined S runs."""
from __future__ import annotations
import fcntl,json,os,socket,subprocess,time
from pathlib import Path
from prepare import ROOT,PROJECT,save,sha
from submit import query,fields,mem_mib

TERMINAL={'COMPLETED','FAILED','CANCELLED','TIMEOUT','OUT_OF_MEMORY','NODE_FAIL','PREEMPTED','BOOT_FAIL','DEADLINE','REVOKED'}
NODES=['compute-0-20','compute-0-21','compute-0-22']

def registered():
    rows={}
    for path in (ROOT/'submission').glob('formal_s_*_attempt*.json'):
        value=json.loads(path.read_text())
        if value.get('job_id'):
            condition=next(c for c in ['B1_seed0','B1_seed1','B3_seed0'] if path.stem.startswith('formal_s_'+c+'_'))
            rows[value['job_id']]={'condition':condition,'receipt_path':str(path),'receipt':value}
    return rows

def actual_jobs(rows):
    if not rows:return {}
    raw=query(['sacct','-j',','.join(rows),'-n','-P','--format=JobIDRaw,User,State,ExitCode,ElapsedRaw,AllocCPUS,NodeList'])
    result={}
    for line in raw.splitlines():
        cols=line.split('|')
        if cols[0] not in rows:continue
        assert cols[1]=='zixiao'
        result[cols[0]]={'state':cols[2].split()[0],'exit_code':cols[3],'elapsed_seconds':int(cols[4]),
                        'allocated_cpus':int(cols[5]),'node':cols[6],'user':cols[1]}
    for job in rows:result.setdefault(job,{'state':'ACCOUNTING_NOT_YET_PUBLISHED','user':'zixiao'})
    return result

def resource_ready(node):
    raw=query(['scontrol','show','node',node,'--oneliner']);info=fields(raw)
    observation={'node':node,'raw_metadata':raw,'timestamp':time.time(),'eligible':False}
    if any(s in info['State'] for s in ['DOWN','DRAIN','FAIL']):return observation
    if int(info['CPUTot'])-int(info['CPUAlloc'])<16:return observation
    total=0.;refs=[]
    jobs=query(['squeue','-h','-w',node,'-t','RUNNING,COMPLETING','-o','%i'])
    for job in jobs.split():
        metadata=query(['scontrol','show','job',job,'--oneliner']);value=fields(metadata)
        if 'MinMemoryNode' in value:amount=mem_mib(value['MinMemoryNode'])
        elif 'MinMemoryCPU' in value:amount=mem_mib(value['MinMemoryCPU'])*int(value['NumCPUs'])/int(value['NumNodes'])
        else:raise RuntimeError('Unknown all-user memory declaration')
        if amount==0:amount=int(info['RealMemory'])
        total+=amount;refs.append({'job_id':job,'declared_mib':amount,'metadata':metadata})
    committed=max(total,float(info['AllocMem']))
    observation.update(all_users=refs,committed_mib=committed,
                       eligible=committed+64*1024<=.85*int(info['RealMemory']))
    return observation

def quota_ready():
    raw=query(['quota','-w','-u','zixiao'])
    rows=[line.split() for line in raw.splitlines() if line.strip().startswith('/dev/sda1 ')]
    assert len(rows)==1
    used,soft,hard=[int(v.rstrip('*')) for v in rows[0][1:4]];assert hard>0 and used<=hard
    available=(hard-used)*1024
    # Whole-phase allowance already includes A parts/final, WP5 and retained B evidence.
    reserve=800*(1<<30)
    result={'timestamp':time.time(),'raw_quota':raw,'available_bytes':available,
            'required_peak_and_reserve_bytes':reserve,'eligible':available>=reserve}
    save(ROOT/'formal_s/quota_latest.json',result);return result

def submit_segment(condition,node,config):
    prior=list((ROOT/'scripts').glob('formal_s_'+condition+'_node'+node.rsplit('-',1)[1]+'_attempt*.sbatch'))
    attempt=len(prior);stem='formal_s_'+condition+'_node'+node.rsplit('-',1)[1]+'_attempt'+str(attempt).zfill(3)
    path=ROOT/'scripts'/(stem+'.sbatch');assert not path.exists()
    checkpoint=ROOT/'s_training'/condition/'latest_checkpoint.json';resume=''
    if checkpoint.exists():
        ref=json.loads(checkpoint.read_text());assert sha(ref['path'])==ref['sha256']
        assert Path(ref['path']).is_relative_to(ROOT/'s_training'/condition)
        resume=' --resume '+ref['path']
    lines=['#!/bin/bash','#SBATCH --job-name=sconv_'+stem,'#SBATCH --partition=all',
        '#SBATCH --nodelist='+node,'#SBATCH --cpus-per-task=16','#SBATCH --mem=64G','#SBATCH --time=04:00:00',
        '#SBATCH --output='+str(ROOT/'logs'/(stem+'_%j.log')),'set -euo pipefail','cd '+str(PROJECT),
        'export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1',
        'export PYTORCH_ALLOC_CONF=expandable_segments:True',
        'export PYTHONPATH=/share/home/zixiao/PhyChem_MFM_stage59_three_epoch_runtime:'+str(PROJECT/'docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps'),
        'srun --ntasks=1 --cpus-per-task=16 --cpu-bind=cores /share/home/zixiao/.conda/envs/chemprop/bin/python -B '+
        str(ROOT/'scripts/s_convergence_segment_launcher_v1.py')+' --configuration '+config['path']+
        ' --binding '+str(ROOT/'formal_s/controller_binding_v1.json')+resume]
    path.write_text('\n'.join(lines)+'\n')
    run=subprocess.run(['python',str(ROOT/'scripts/submit.py'),str(path),'--node',node,'--cpus','16','--mem-gib','64'],
        cwd=PROJECT,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=120)
    save(ROOT/'formal_s'/('submission_'+stem+'.json'),{'timestamp':time.time(),'returncode':run.returncode,'stdout':run.stdout,'stderr':run.stderr})
    if run.returncode:return None
    return json.loads((ROOT/'submission'/(stem+'.json')).read_text())['job_id']

def main():
    assert os.getuid()==1278 and socket.gethostname().split('.')[0]=='sonmi'
    lock=(ROOT/'formal_s/root_coordinator_v1.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    binding_path=ROOT/'formal_s/controller_binding_v1.json';binding=json.loads(binding_path.read_text())
    assert binding['status']=='ROOT_BOUND_FORMAL_S_CONTROLLER'
    for ref in binding['sources']+binding['configurations']:assert sha(ref['path'])==ref['sha256']
    assert binding['run_plan_sha256']==sha(ROOT/'formal_s/run_plan_v2.json')
    configs={row['condition']:row for row in binding['configurations']}
    identity={'pid':os.getpid(),'uid':os.getuid(),'hostname':socket.gethostname(),'started_epoch':time.time(),
        'proc_start_ticks':Path('/proc/self/stat').read_text().split()[21],
        'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
        'source_sha256':sha(__file__),'binding_sha256':sha(binding_path),'poll_interval_seconds':60,'max_hours':21*24}
    save(ROOT/'formal_s/root_coordinator_v1_identity.json',identity)
    deadline=time.monotonic()+21*86400
    while time.monotonic()<deadline:
        try:
            for ref in binding['sources']+binding['configurations']:assert sha(ref['path'])==ref['sha256']
            records=registered();actual=actual_jobs(records);conditions={};global_stop=(ROOT/'formal_s/scientific_stop.json').exists()
            for condition,config in configs.items():
                jobs=[j for j,r in records.items() if r['condition']==condition]
                latest=max(jobs,key=lambda j:records[j]['receipt']['timestamp']) if jobs else None
                state={'state':'PENDING','consumed_records':0,'latest_job_id':latest,'configuration':config}
                if latest:
                    info=actual[latest];state['actual_job']=info
                    if info['state'] not in TERMINAL:state['state']='ACTIVE'
                    else:
                        summary_path=ROOT/'s_training'/condition/('segment_'+latest)/'summary.json'
                        if not summary_path.exists():state['state']='ROOT_REPAIR_REQUIRED_MISSING_SUMMARY'
                        else:
                            summary=json.loads(summary_path.read_text())
                            assert summary['job_id']==latest and summary['config_sha256']==config['sha256'] and not summary['development_only']
                            state.update(consumed_records=summary.get('consumed_records',0),summary_path=str(summary_path),summary_sha256=sha(summary_path))
                            if summary.get('scientific_stop') or any(k in summary.get('error','') for k in ['SCIENTIFIC_STOP','ACTUAL_RECORD_MANIFEST_MISMATCH','NONFINITE_VALIDATION_LOSS','VALIDATION_RECORD_COVERAGE_MISMATCH','ACTUAL_CONSUMED_RECORD_DUPLICATE','EPOCH_RECORD_COVERAGE_MISMATCH','EPOCH_FOLDED_MOLECULE_COUNT_MISMATCH']):
                                state['state']='GUIDE_SCIENTIFIC_STOP';global_stop=True
                                stop={'status':'GUIDE_COHORT_SCIENTIFIC_STOP','timestamp':time.time(),'condition':condition,
                                    'job_id':latest,'actual_accounting':info,'summary_path':str(summary_path),'summary_sha256':sha(summary_path),'summary':summary}
                                if not (ROOT/'formal_s/scientific_stop.json').exists():save(ROOT/'formal_s/scientific_stop.json',stop)
                            elif info['state']=='COMPLETED' and info['exit_code']=='0:0' and summary['status']=='TRAINING_EXPOSURES_COMPLETE_AWAITING_H0_PROBES':
                                assert summary['epoch_accepted'] and len(summary['completed_epochs'])==config['epochs']
                                assert summary['consumed_records']==11104772*config['epochs']
                                assert all(e['records']==11104772 and e['molecules']==1206608 for e in summary['completed_epochs'])
                                state['state']='TRAINING_COMPLETE_AWAITING_H0_PROBES'
                            elif info['state']=='COMPLETED' and info['exit_code']=='0:0' and summary['status']=='PARTIAL_CHECKPOINT_REQUIRES_CONTINUATION':pass
                            elif summary['status']=='RUNNER_FAILED_RETRYABLE_LOADER_TIMEOUT':
                                failures=sum(actual[j]['state']=='FAILED' for j in jobs)
                                if failures>3:state['state']='ROOT_REPAIR_REQUIRED_REPEATED_LOADER_TIMEOUT'
                            else:state['state']='ROOT_REPAIR_REQUIRED_'+summary['status']
                conditions[condition]=state
            repair=any(v['state'].startswith('ROOT_REPAIR_REQUIRED') for v in conditions.values())
            state={'timestamp':time.time(),'status':'GUIDE_SCIENTIFIC_STOP' if global_stop else 'ROOT_REPAIR_REQUIRED' if repair else 'COORDINATING_FORMAL_S',
                'conditions':conditions,'actual_jobs':actual,'binding_sha256':sha(binding_path),
                'formal_training_epochs_complete':False,'all_required_probes_complete':False}
            save(ROOT/'formal_s/root_coordinator_v1_status.json',state)
            accounting={'timestamp':time.time(),'actual_registered_jobs':actual,
                'allocated_core_hours':sum(v.get('elapsed_seconds',0)*v.get('allocated_cpus',0)/3600 for v in actual.values()),
                'actual_job_count':len(actual),'training_records_not_added_across_resumed_segments':True}
            save(ROOT/'formal_s/accounting_latest.json',accounting)
            if global_stop:
                if not any(v['state']=='ACTIVE' for v in conditions.values()):return
            elif not repair:
                if all(v['state']=='TRAINING_COMPLETE_AWAITING_H0_PROBES' for v in conditions.values()):
                    state['status']='ALL_THREE_TRAINING_RUNS_COMPLETE_AWAITING_H0_PROBES';state['formal_training_epochs_complete']=True
                    save(ROOT/'formal_s/root_coordinator_v1_status.json',state);return
                available=[resource_ready(n) for n in NODES];save(ROOT/'formal_s/resources_latest.json',{'timestamp':time.time(),'nodes':available})
                ready=sorted([c for c in configs if conditions[c]['state']=='PENDING'],key=lambda c:(conditions[c]['consumed_records'],c))
                if ready and any(v['eligible'] for v in available):
                    quota=quota_ready()
                    if quota['eligible']:
                        for observation in available:
                            if not ready:break
                            if not observation['eligible']:continue
                            condition=ready.pop(0);job=submit_segment(condition,observation['node'],configs[condition])
                            if job:print(json.dumps({'event':'FORMAL_S_SUBMITTED','condition':condition,'job_id':job,'node':observation['node']}),flush=True)
            print(json.dumps({'status':state['status'],'conditions':{k:v['state'] for k,v in conditions.items()}}),flush=True)
        except Exception as exc:
            save(ROOT/'formal_s/root_coordinator_v1_error.json',{'timestamp':time.time(),'error':repr(exc)})
            print('ROOT_S_METADATA_ERROR '+repr(exc),flush=True)
        time.sleep(60)
    save(ROOT/'formal_s/root_coordinator_v1_status.json',{'status':'BOUNDED_COORDINATOR_EXPIRED','timestamp':time.time()})

if __name__=='__main__':main()
