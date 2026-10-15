"""Resolve the guide's generic protocol reference from the active frozen lineage."""
import copy,glob,json,os,subprocess,time
from pathlib import Path
from prepare import ROOT,PROJECT,save,sha

def main():
    assert os.getuid()==1278
    baseline=PROJECT/'docs/phase1/evidence/stage59_three_epoch_protocol_v1/actual_scientific_freeze_v1/phase1_three_epoch_scientific_protocol.json'
    expected='cde2ca717934955f340a5f160a3390ff1dd6eda12c9ffbab93fc54fce0c8a2a4'
    assert sha(baseline)==expected
    source=json.loads(baseline.read_text());assert source['state']=='frozen'
    paths=sorted(PROJECT.glob('docs/phase1/evidence/stage60*/*/protocol.json'))
    assert len(paths)==7
    refs=[]
    for path in paths:
        assert sha(path)==expected and json.loads(path.read_text())['state']=='frozen'
        refs.append({'path':str(path),'sha256':expected,'bytes':path.stat().st_size})
    evidence=json.loads((ROOT/'reports/s_runner_uninterrupted_resume_v2.json').read_text())
    assert evidence['status']=='ACTUAL_UNINTERRUPTED_VS_RESUMED_RUNNER_PASS'
    assert evidence['runner_sha256']==sha(ROOT/'scripts/s_convergence_runner_v7.py')
    actual=subprocess.run(['sacct','-j',evidence['job_id'],'-n','-P','--format=JobIDRaw,User,State,ExitCode'],capture_output=True,text=True,check=True,timeout=30)
    parent=[r.split('|') for r in actual.stdout.splitlines() if r.split('|')[0]==evidence['job_id']]
    assert len(parent)==1 and parent[0][1:]==['zixiao','COMPLETED','0:0']
    resolution={'status':'ROOT_RESOLVED_FROM_ACTIVE_FROZEN_PROJECT_LINEAGE','resolved':True,
        'timestamp':time.time(),'guide_generic_reference':'frozen_protocol.json',
        'actual_protocol':{'path':str(baseline),'sha256':expected,'bytes':baseline.stat().st_size},
        'basis':'Stage59 sealed frozen protocol is byte-identical to all seven subsequent Stage60 runtime/statistics references',
        'subsequent_frozen_references':refs,'user_selected_this_exact_filename':False,
        'prior_filename_question':'Reference ambiguity resolved by new primary project evidence; no user response inferred',
        'explicit_guide_overrides':['WP5 formal population and TRAIN/FULL/ROUTINE membership','only three S tasks',
            'dynamic balancer disabled; fixed S leaf weights 1/3 each','B1 seeds0,1 one epoch; B3 seed0 three epochs',
            'scheduler total exposures N or 3N','B3 checkpoints0.25,0.5,1,2,3',
            'raw FULL losses and guide denoising reference/stop rule','frozen H0 linear downstream probes with ETKDG+UFF',
            'GPU nodes20/21/22; other CPU nodes except reserved14-19'],
        'authorization':{'path':str(ROOT/'reports/full_run_user_decision.json'),'sha256':sha(ROOT/'reports/full_run_user_decision.json')},
        'development_resume_proof':{'path':str(ROOT/'reports/s_runner_uninterrupted_resume_v2.json'),'sha256':sha(ROOT/'reports/s_runner_uninterrupted_resume_v2.json')}}
    target=ROOT/'formal_s';target.mkdir(exist_ok=True)
    assert not (target/'protocol_resolution_v1.json').exists()
    save(target/'protocol_resolution_v1.json',resolution)
    template=json.loads((ROOT/'configs/s_runner_development_v7.json').read_text())
    assert template['status']=='DRAFT_CANDIDATE_INTERFACE_ONLY'
    for ref in template['source_references']:assert sha(ref['path'])==ref['sha256']
    rows=[]
    for kind,seed,epochs in [('B1',0,1),('B1',1,1),('B3',0,3)]:
        cfg=copy.deepcopy(template);cfg.update(status='FORMAL_PROTOCOL_RESOLVED_AND_FROZEN',kind=kind,seed=seed,epochs=epochs)
        cfg['frozen_reference_resolution']=resolution
        cfg['formal_trial_definition']={'training_epochs':epochs,'total_committed_base_exposures':11104772*epochs,
            'one_epoch':'all 11104772 formal TRAIN records exactly once, 1206608 folded molecules',
            'effective_S_weights':{'element':1/3,'distance':1/3,'bond_order':1/3},
            'scheduler_horizon_epochs':epochs,'guide_sha256':sha(ROOT/'configs/user_guide.md'),
            'runtime_changes':'Verified tiled distance MLP; bounded same-cursor loader recovery; RNG-preserving checkpoint continuation',
            'downstream_tasks_reference':'actual frozen protocol dataset_definitions; guide overrides readout/geometry/split rules'}
        cfg['development_resume_proof']=resolution['development_resume_proof']
        condition=kind+'_seed'+str(seed);path=target/(condition+'.json');assert not path.exists()
        save(path,cfg);rows.append({'condition':condition,'path':str(path),'sha256':sha(path),'epochs':epochs})
    plan={'status':'FORMAL_S_CONFIGURATIONS_FROZEN_NOT_YET_EXECUTED','timestamp':time.time(),
        'configurations':rows,'resolution_sha256':sha(target/'protocol_resolution_v1.json'),
        'train_records':11104772,'train_molecules':1206608,'seeds':[0,1],
        'pending':['actual B1/B3 training and exact epoch closure','all required H0 linear probes','convergence judgment/report']}
    save(target/'run_plan_v1.json',plan);print(json.dumps(plan),flush=True)

if __name__=='__main__':main()
