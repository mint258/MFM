"""Prepare a bounded development configuration; never select a formal protocol."""
import json
from pathlib import Path
from prepare import ROOT,PROJECT,save,sha

def main():
    protocol_path=PROJECT/'docs/phase1/evidence/stage59_three_epoch_protocol_v1/actual_scientific_freeze_v1/phase1_three_epoch_scientific_protocol.json'
    protocol=json.loads(protocol_path.read_text())
    assert sha(protocol_path)=='cde2ca717934955f340a5f160a3390ff1dd6eda12c9ffbab93fc54fce0c8a2a4'
    runtime=Path('/share/home/zixiao/PhyChem_MFM_stage59_three_epoch_runtime')
    sources=sorted((runtime/'phychem_mfm').rglob('*.py'))
    sources.extend(ROOT/'scripts'/name for name in ['s_convergence_runner_v2.py','s_model_memory_v1.py','s_native_adapter_v1.py','s_native_adapter_v2.py','s_training_components_v1.py','s_training_components_v2.py','prepare.py'])
    sources.append(Path(protocol['draft_provenance']['runner_artifacts']['native_transport']['path']))
    configuration={'status':'DRAFT_CANDIDATE_INTERFACE_ONLY','kind':'B1','variant':'S','seed':0,'epochs':1,
        'dynamic_balancer_enabled':False,'train_records':11104772,'train_molecules':1206608,
        'frozen_reference_resolution':{'resolved':False,'reason':'User clarification for the intended frozen_protocol.json is pending; this is a bounded development test only.'},
        'frozen_protocol_reference':{'path':str(protocol_path),'sha256':sha(protocol_path)},
        'model':protocol['model'],'views':protocol['views'],'sampler':protocol['sampler'],'loader':protocol['loader'],
        'training':protocol['training'],'validation_seed':protocol['validation_seed'],'tracking':protocol['tracking'],
        'input_manifest_sha256':sha(ROOT/'training_inputs_v1/manifest.json'),
        'memory_implementation_sha256':sha(ROOT/'scripts/s_model_memory_v1.py'),
        'source_references':[{'path':str(path),'sha256':sha(path),'bytes':path.stat().st_size} for path in sources],
        'effective_loss_weights':{'element':1/3,'distance':1/3,'bond_order':1/3},
        'all_checkpoint_event_positions_apply_to_all_conditions':True,
        'original_lmdb_readonly':True,'new_lmdb_created':False,'formal_B_training_permitted':False}
    target=ROOT/'configs/s_runner_development_v2.json';assert not target.exists()
    save(target,configuration);print('DEVELOPMENT_CONFIGURATION_ONLY',flush=True)

if __name__=='__main__':main()
