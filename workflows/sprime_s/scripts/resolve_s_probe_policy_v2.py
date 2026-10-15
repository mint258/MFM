"""Small Root metadata binding of the unchanged Stage59 downstream boundaries."""
import csv,json,os,socket,time
from pathlib import Path
from prepare import ROOT,save,sha

def main():
    assert os.getuid()==1278 and socket.gethostname().split('.')[0]=='sonmi'
    resolved=json.loads((ROOT/'formal_s/protocol_resolution_v3.json').read_text())
    ref=resolved['actual_protocol'];assert sha(ref['path'])==ref['sha256']
    frozen=json.loads(Path(ref['path']).read_text());assert frozen['state']=='frozen'
    d=frozen['downstream'];official=d['scope_clarification']['expansionrx']
    assert d['metric_policy']['primary_family_exclusions']==['qm9.A','qm9.B','qm9.C']
    assert d['metric_policy']['primary_inference_endpoints']==32
    source_receipt=json.loads((ROOT/'probe_data_v3/expansionrx_receipt.json').read_text())
    prepared={r['path']:r for r in source_receipt['sources']};sources=[]
    for key,role in [('training_path','train'),('official_test_path','test')]:
        path=Path(official[key]);assert str(path) in prepared and sha(path)==prepared[str(path)]['sha256']
        with path.open(newline='') as stream:count=sum(1 for _ in csv.DictReader(stream))
        sources.append({'path':str(path),'role':role,'rows':count,'sha256':sha(path)})
    assert sum(r['rows'] for r in sources)==source_receipt['processed_members']
    decision={'status':'STAGE59_DOWNSTREAM_PARTITIONS_AND_PRIMARY_FAMILY_PRESERVED','timestamp':time.time(),
        'frozen_protocol':ref,'user_confirmation_sha256':sha(ROOT/'formal_s/user_frozen_reference_confirmation_20261014_v2.json'),
        'guide_interpretation':'Scaffold fallback applies when downstream datasets are unspecified; these five datasets are specified by Stage59, whose original official and scaffold boundaries remain fixed',
        'scaffold_datasets':d['scope_clarification']['scaffold_rotation']['datasets'],
        'scaffold_rotation':d['scope_clarification']['scaffold_rotation'],
        'expansion_official_sources':sources,'expansion_inner_validation':None,
        'expansion_derived_scaffold_annotations_in_prepared_v3_are_unused':True,
        'readout':'raw H0 linear, frozen encoder; explicit guide override of nonlinear readout',
        'geometry':'ETKDGv3 plus UFF; explicit guide override of previous original/MMFF geometry',
        'optimization_policy':d['optimization_policy'],'readout_seed':0,
        'primary_family_exclusions':d['metric_policy']['primary_family_exclusions'],
        'primary_inference_tasks':32,'all_reported_tasks':35,'cells_per_checkpoint':41,'checkpoints':7,'total_cells':287,
        'original_sources_modified':False,'pretraining_overlap_deleted':False,
        'formal_probe_results_observed_before_this_correction':False,
        'superseded_plan':'Unexecuted LP v1 reassigned Expansion official-test rows into scaffold training and applied the new criterion to auxiliary QM9 A/B/C',
        'resolver_source_sha256':sha(__file__)}
    path=ROOT/'configs/s_probe_protocol_v2.json';assert not path.exists();save(path,decision)
    print(json.dumps({'status':decision['status'],'official_source_rows':sources,'total_cells':287}),flush=True)

if __name__=='__main__':main()
