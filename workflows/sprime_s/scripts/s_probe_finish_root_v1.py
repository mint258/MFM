"""Coordinate common-input acceptance, overlap, seven real H0 endpoints and probes."""
import fcntl,json,os,socket,subprocess,time
from pathlib import Path
from prepare import ROOT,PROJECT,save,sha
from submit import query
from s_convergence_root_v1 import resource_ready,TERMINAL

POINTS={'B1_seed0_e1':('B1_seed0','epoch_1'),'B1_seed1_e1':('B1_seed1','epoch_1'),
    'B3_seed0_e0p25':('B3_seed0','epoch_0p25'),'B3_seed0_e0p5':('B3_seed0','epoch_0p5'),
    'B3_seed0_e1':('B3_seed0','epoch_1'),'B3_seed0_e2':('B3_seed0','epoch_2'),'B3_seed0_e3':('B3_seed0','epoch_3')}
CPUS=['compute-0-8','compute-0-9','compute-0-10','compute-0-11','compute-0-12','compute-0-2']

def state_of(job):
    raw=query(['sacct','-j',job,'-n','-P','--format=JobIDRaw,User,State,ExitCode'])
    rows=[r.split('|') for r in raw.splitlines() if r.split('|')[0]==job]
    if not rows:return {'state':'ACCOUNTING_NOT_YET_PUBLISHED'}
    assert len(rows)==1 and rows[0][1]=='zixiao'
    return {'state':rows[0][2].split()[0],'exit_code':rows[0][3]}

def receipt_job(stem):
    path=ROOT/'submission'/(stem+'.json')
    return json.loads(path.read_text()).get('job_id') if path.exists() else None

def submit_script(stem,node,cpus,memory,hours,command,gpu=False):
    path=ROOT/'scripts'/(stem+'.sbatch')
    if not path.exists():
        lines=['#!/bin/bash','#SBATCH --job-name=sconv_'+stem,'#SBATCH --partition='+('all' if gpu else 'cpu'),
            '#SBATCH --nodelist='+node,'#SBATCH --cpus-per-task='+str(cpus),'#SBATCH --mem='+str(memory)+'G',
            '#SBATCH --time='+str(hours).zfill(2)+':00:00','#SBATCH --output='+str(ROOT/'logs'/(stem+'_%j.log')),
            'set -euo pipefail','cd '+str(PROJECT),
            'export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1',
            'export PYTORCH_ALLOC_CONF=expandable_segments:True',
            'export PYTHONPATH=/share/home/zixiao/PhyChem_MFM_stage59_three_epoch_runtime:'+str(PROJECT/'docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps')]
        if not gpu:lines.append("export CUDA_VISIBLE_DEVICES=''")
        lines.append(command);path.write_text('\n'.join(lines)+'\n')
    run=subprocess.run(['python',str(ROOT/'scripts/submit.py'),str(path),'--node',node,'--cpus',str(cpus),'--mem-gib',str(memory)],
        cwd=PROJECT,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=120)
    save(ROOT/'probe_preparation_control'/('attempt_'+stem+'.json'),{'timestamp':time.time(),'returncode':run.returncode,'stdout':run.stdout,'stderr':run.stderr})
    return receipt_job(stem) if run.returncode==0 else None

def cpu_node():
    return next((node for node in CPUS if resource_ready(node)['eligible']),None)

def main():
    assert os.getuid()==1278 and socket.gethostname().split('.')[0]=='sonmi'
    control=ROOT/'probe_preparation_control';lock=(control/'finish_root_v1.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    binding_path=control/'finish_binding_v1.json';binding=json.loads(binding_path.read_text())
    assert binding['status']=='ROOT_BOUND_REVIEWED_PROBE_FINISH_FLOW'
    for ref in binding['sources']:assert sha(ref['path'])==ref['sha256']
    identity={'pid':os.getpid(),'uid':os.getuid(),'started':time.time(),'proc_start_ticks':Path('/proc/self/stat').read_text().split()[21],
        'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'binding_sha256':sha(binding_path),'max_hours':21*24}
    save(control/'finish_root_v1_identity.json',identity);deadline=time.monotonic()+21*86400
    python='/share/home/zixiao/.conda/envs/chemprop/bin/python';gpu_python=str(PROJECT/'docs/phase1/evidence/stage43_5090_environment/install_4511929/venv/bin/python')
    while time.monotonic()<deadline:
        try:
            for ref in binding['sources']:assert sha(ref['path'])==ref['sha256']
            gen=json.loads((control/'production_binding_v1.json').read_text());generation=[]
            for item in gen['scripts']:
                job=receipt_job(Path(item['path']).stem);assert job
                actual=state_of(job);generation.append({'dataset':item['dataset'],'job_id':job,**actual})
            status={'timestamp':time.time(),'status':'WAITING_FOR_COMMON_PROBE_INPUTS','generation':generation,'endpoints':{}}
            if any(row['state'] in TERMINAL and (row['state']!='COMPLETED' or row['exit_code']!='0:0') for row in generation):
                status['status']='ROOT_REPAIR_REQUIRED_PROBE_GENERATION'
            elif all(row['state']=='COMPLETED' and row['exit_code']=='0:0' for row in generation):
                validation=receipt_job('s_probe_validate_inputs_v1')
                if not validation:
                    node=cpu_node()
                    if node:validation=submit_script('s_probe_validate_inputs_v1',node,16,32,2,python+' -B '+str(ROOT/'scripts/validate_s_probe_inputs_v1.py'))
                if validation:
                    actual=state_of(validation);status['input_validation']={'job_id':validation,**actual}
                    if actual['state'] in TERMINAL and (actual['state']!='COMPLETED' or actual['exit_code']!='0:0'):status['status']='ROOT_REPAIR_REQUIRED_PROBE_INPUT_VALIDATION'
                    elif actual['state']=='COMPLETED' and actual['exit_code']=='0:0':
                        accepted=json.loads((ROOT/'probe_data_v3/acceptance.json').read_text());assert accepted['status']=='ALL_FIVE_COMMON_PROBE_INPUT_DATASETS_ACCEPTED'
                        status['status']='WAITING_FOR_REAL_CHECKPOINTS_OR_PROBES'
                        overlap=receipt_job('s_probe_overlap_v1')
                        if not overlap:
                            node=cpu_node()
                            if node:overlap=submit_script('s_probe_overlap_v1',node,16,32,2,python+' -B '+str(ROOT/'scripts/s_probe_overlap_v1.py'))
                        if overlap:
                            value=state_of(overlap);status['overlap']={'job_id':overlap,**value}
                            if value['state'] in TERMINAL and (value['state']!='COMPLETED' or value['exit_code']!='0:0'):status['status']='ROOT_REPAIR_REQUIRED_OVERLAP'
                        gpu_active=False
                        for point,(condition,label) in POINTS.items():
                            references=list((ROOT/'s_training'/condition).glob('segment_*/'+label+'.json'))
                            h0=receipt_job('s_probe_h0_'+point+'_v2');probe=receipt_job('s_probe_linear_'+point+'_v1')
                            record={'checkpoint_available':bool(references),'h0_job_id':h0,'linear_job_id':probe}
                            if h0:
                                actual=state_of(h0);record['h0_actual']=actual
                                if actual['state'] not in TERMINAL:gpu_active=True
                                elif actual['state']!='COMPLETED' or actual['exit_code']!='0:0':status['status']='ROOT_REPAIR_REQUIRED_H0_'+point
                                else:
                                    proof=json.loads((ROOT/'probe_h0_v1'/point/'receipt.json').read_text())
                                    assert proof['status']=='ALL_FIVE_FROZEN_H0_DATASETS_CLOSED' and proof['encoder_parameters_and_buffers_unchanged']
                                    if not probe:
                                        node=cpu_node()
                                        if node:probe=submit_script('s_probe_linear_'+point+'_v1',node,17,64,24,python+' -B '+str(ROOT/'scripts/run_s_linear_probes_v1.py')+' --endpoint '+point)
                                        record['linear_job_id']=probe
                            if probe:
                                actual=state_of(probe);record['linear_actual']=actual
                                if actual['state'] in TERMINAL:
                                    if actual['state']!='COMPLETED' or actual['exit_code']!='0:0':status['status']='ROOT_REPAIR_REQUIRED_LINEAR_'+point
                                    else:
                                        value=json.loads((ROOT/'probe_results_v1'/point/'receipt.json').read_text())
                                        assert value['status']=='ALL_FIFTY_LINEAR_PROBE_CELLS_CLOSED';record['probe_closed']=True
                            if references and not h0 and not gpu_active and not status['status'].startswith('ROOT_REPAIR_REQUIRED'):
                                reference=references[0];ref=json.loads(reference.read_text())
                                assert ref['consumed_records']=={'epoch_0p25':2776193,'epoch_0p5':5552386,'epoch_1':11104772,'epoch_2':22209544,'epoch_3':33314316}[label]
                                if resource_ready('compute-0-21')['raw_metadata']:
                                    # An inference task requests32GiB; Root submit performs the exact fresh all-user check.
                                    node_fields=dict(__import__('submit').fields(query(['scontrol','show','node','compute-0-21','--oneliner'])))
                                    free=int(node_fields['CPUTot'])-int(node_fields['CPUAlloc'])
                                    if free>=16:
                                        command='srun --ntasks=1 --cpus-per-task=16 --cpu-bind=cores '+gpu_python+' -B '+str(ROOT/'scripts/extract_s_probe_h0_v2.py')+' --checkpoint-reference '+str(reference)+' --endpoint '+point
                                        h0=submit_script('s_probe_h0_'+point+'_v2','compute-0-21',16,32,4,command,True)
                                        record['h0_job_id']=h0;gpu_active=h0 is not None
                            status['endpoints'][point]=record
                        stop=(ROOT/'formal_s/scientific_stop.json').exists()
                        complete=len(status['endpoints'])==7 and all(r.get('probe_closed') for r in status['endpoints'].values())
                        if complete and overlap:
                            info=state_of(overlap)
                            if info['state']=='COMPLETED' and info['exit_code']=='0:0':status['status']='ALL_SEVEN_ENDPOINTS_AND_OVERLAP_CLOSED'
                        if stop:status['status']='GUIDE_TRAINING_STOP_RECORDED_NO_FAKE_ENDPOINTS'
            save(control/'finish_root_v1_status.json',status)
            print(json.dumps({'status':status['status'],'endpoints':status['endpoints']}),flush=True)
            if status['status']=='ALL_SEVEN_ENDPOINTS_AND_OVERLAP_CLOSED':return
        except Exception as exc:
            save(control/'finish_root_v1_error.json',{'timestamp':time.time(),'error':repr(exc)});print('PROBE_ROOT_METADATA_ERROR '+repr(exc),flush=True)
        time.sleep(120)
    save(control/'finish_root_v1_status.json',{'status':'BOUNDED_PROBE_COORDINATOR_EXPIRED','timestamp':time.time()})

if __name__=='__main__':main()
