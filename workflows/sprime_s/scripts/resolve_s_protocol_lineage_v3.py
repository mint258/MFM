"""Read-only protocol lineage review, then save a new resolution receipt."""
import json,os,time
from prepare import ROOT,PROJECT,save,sha

def main():
    assert os.getuid()==1278
    baseline=PROJECT/'docs/phase1/evidence/stage59_three_epoch_protocol_v1/actual_scientific_freeze_v1/phase1_three_epoch_scientific_protocol.json'
    expected='cde2ca717934955f340a5f160a3390ff1dd6eda12c9ffbab93fc54fce0c8a2a4'
    assert sha(baseline)==expected and json.loads(baseline.read_text())['state']=='frozen'
    paths=sorted(PROJECT.glob('docs/phase1/evidence/stage60*/*/protocol.json'));assert len(paths)==6
    refs=[]
    for path in paths:
        assert sha(path)==expected and json.loads(path.read_text())['state']=='frozen'
        refs.append({'path':str(path),'sha256':expected,'bytes':path.stat().st_size})
    target=ROOT/'formal_s/protocol_resolution_v3.json';assert not target.exists()
    value={'status':'ROOT_RESOLVED_FROM_ACTIVE_FROZEN_PROJECT_LINEAGE','resolved':True,'timestamp':time.time(),
        'guide_generic_reference':'frozen_protocol.json','guide_sha256':sha(ROOT/'configs/user_guide.md'),
        'actual_protocol':{'path':str(baseline),'sha256':expected,'bytes':baseline.stat().st_size},
        'basis':'Stage59 sealed frozen protocol is byte-identical to all six later Stage60 runtime/statistics references',
        'subsequent_frozen_references':refs,'user_selected_this_exact_filename':False,
        'prior_filename_question':'Resolved using newly verified primary project evidence; no reply or approval inferred',
        'explicit_guide_overrides':['formal WP5 population','S-only fixed losses, balancer off','B1 two seeds one epoch; B3 one seed three epochs',
            'N/3N scheduler horizons and named checkpoints','guide raw losses and denoising stop/assessment rules',
            'H0 linear downstream probes, ETKDG+UFF and scaffold rules','authorized compute-node selection'],
        'pool_review':{'unsubmitted_proposal':'s_convergence_pool_v1.py','decision':'REJECTED_BEFORE_SUBMISSION',
            'reason':'Each formal training task requires64GiB; two such tasks exceed85% of node21 RealMemory120000MiB',
            'actual_pool_jobs_submitted':0,'chosen_policy':'one64GiB task per eligible node; add parallel conditions only after live resources pass'}}
    save(target,value);print(json.dumps({'status':value['status'],'resolution_path':str(target),'sha256':sha(target)}),flush=True)

if __name__=='__main__':main()
