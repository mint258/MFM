"""Seal three guide-defined runs after the actual runner resume proof passes."""
import copy,json,os,socket,subprocess,time
from pathlib import Path
from prepare import ROOT,PROJECT,save,sha

def main():
    assert os.getuid()==1278 and socket.gethostname().split('.')[0]=='sonmi'
    target=ROOT/'formal_s';assert target.is_dir() and not (target/'run_plan_v2.json').exists()
    resolution_path=target/'protocol_resolution_v3.json';resolution=json.loads(resolution_path.read_text())
    assert resolution['resolved'] and resolution['status']=='ROOT_RESOLVED_FROM_ACTIVE_FROZEN_PROJECT_LINEAGE'
    for ref in [resolution['actual_protocol']]+resolution['subsequent_frozen_references']:
        assert sha(ref['path'])==ref['sha256']
    proof_path=ROOT/'reports/s_runner_uninterrupted_resume_v3.json';proof=json.loads(proof_path.read_text())
    assert proof['status']=='ACTUAL_UNINTERRUPTED_VS_RESUMED_RUNNER_PASS'
    assert proof['runner_sha256']==sha(ROOT/'scripts/s_convergence_runner_v8.py')
    raw=subprocess.run(['sacct','-j',proof['job_id'],'-n','-P','--format=JobIDRaw,User,State,ExitCode'],capture_output=True,text=True,check=True,timeout=30).stdout
    parent=[r.split('|') for r in raw.splitlines() if r.split('|')[0]==proof['job_id']]
    assert len(parent)==1 and parent[0][1:]==['zixiao','COMPLETED','0:0']
    template=json.loads((ROOT/'configs/s_runner_development_v8.json').read_text())
    assert template['status']=='DRAFT_CANDIDATE_INTERFACE_ONLY' and template['loader']['worker_timeout_seconds']==600.
    for ref in template['source_references']:assert sha(ref['path'])==ref['sha256']
    protocol=json.loads(Path(resolution['actual_protocol']['path']).read_text())
    definitions=protocol['downstream']['dataset_definitions']
    downstream=[{'dataset_id':v['dataset_id'],'output_level':v['output_level'],
                 'tasks':v.get('tasks'),'endpoint_ids':v.get('endpoint_ids')} for v in definitions]
    trials=[]
    for kind,seed,epochs in [('B1',0,1),('B1',1,1),('B3',0,3)]:
        cfg=copy.deepcopy(template);cfg.update(status='FORMAL_PROTOCOL_RESOLVED_AND_FROZEN',kind=kind,seed=seed,epochs=epochs)
        cfg['frozen_reference_resolution']=resolution
        cfg['formal_trial_definition']={'training_epochs':epochs,'total_committed_base_exposures':11104772*epochs,
            'one_epoch':'all11104772 formal TRAIN records exactly once;1206608 folded molecules',
            'effective_S_weights':{'element':1/3,'distance':1/3,'bond_order':1/3},
            'guide_sha256':sha(ROOT/'configs/user_guide.md'),'scheduler_horizon_epochs':epochs,
            'checkpoint_epochs':[.25,.5,1.,2.,3.] if kind=='B3' else [1.],
            'runtime_changes':'Verified tiled distance MLP; same-cursor loader retries; declared600s IPC guard; RNG-preserving continuation'}
        cfg['development_resume_proof']={'path':str(proof_path),'sha256':sha(proof_path)}
        condition=kind+'_seed'+str(seed);path=target/(condition+'_v2.json');assert not path.exists()
        save(path,cfg);trials.append({'condition':condition,'path':str(path),'sha256':sha(path),'epochs':epochs,'seed':seed})
    plan={'status':'FORMAL_S_CONFIGURATIONS_FROZEN_NOT_YET_EXECUTED','timestamp':time.time(),'configurations':trials,
        'resolution_sha256':sha(resolution_path),'runner_sha256':sha(ROOT/'scripts/s_convergence_runner_v8.py'),
        'train_records':11104772,'train_molecules':1206608,'total_requested_epochs':5,
        'resources_per_training_task':{'cpus':16,'memory_gib':64,'slurm_wall_hours':4,'frozen_segment_wall_seconds':7200},
        'allowed_gpu_nodes':['compute-0-20','compute-0-21','compute-0-22'],
        'downstream_frozen_dataset_definitions':downstream,'downstream_explicit_guide_overrides':{
            'encoder':'frozen backbone H0','readout':'linear; no hidden activation',
            'geometry':'RDKit ETKDG+UFF','split':'scaffold','pretraining_overlap':'report scaffold InChIKey14 overlap without deleting'},
        'predeclared_convergence':{'losses':'each raw FULL S loss; both B1 seeds relative absolute gap vs B3 epoch3 <0.02',
            'probes':'each endpoint absolute difference between B1 two-seed mean and B3 epoch3 < B1 two-seed absolute spread',
            'denoising':'separate comparison with0.042A lookup reference; guide stop after0.1epoch if FULL local RMSE>=0.141A'},
        'pending':['actual B1/B3 training and exact epoch closure','all required frozen H0 linear probes','convergence judgment and combined report']}
    save(target/'run_plan_v2.json',plan)
    names=['s_convergence_runner_v8.py','s_convergence_segment_launcher_v1.py','s_convergence_root_v1.py',
           's_loader_recovery_v1.py','s_loader_recovery_v2.py','s_model_memory_v1.py','s_native_adapter_v1.py',
           's_native_adapter_v2.py','s_training_components_v1.py','s_training_components_v2.py','submit.py']
    sources=[{'path':str(ROOT/'scripts'/n),'sha256':sha(ROOT/'scripts'/n),'bytes':(ROOT/'scripts'/n).stat().st_size} for n in names]
    binding={'status':'ROOT_BOUND_FORMAL_S_CONTROLLER','timestamp':time.time(),'sources':sources,'configurations':trials,
        'python':str(PROJECT/'docs/phase1/evidence/stage43_5090_environment/install_4511929/venv/bin/python'),
        'run_plan_sha256':sha(target/'run_plan_v2.json'),'original_lmdb_written':False,'new_lmdb_created':False,
        'gpu_protection':'USER_ACCEPTED_SHARED_GPU_RISK'}
    save(target/'controller_binding_v1.json',binding);print(json.dumps(plan),flush=True)

if __name__=='__main__':main()
