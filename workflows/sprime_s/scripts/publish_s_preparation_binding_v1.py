"""Publish actual preparation evidence; deliberately no B training acceptance."""
import json,time
from prepare import ROOT,save,sha

def main():
    paths=['training_inputs_v1/manifest.json','training_inputs_v1/native_read_checks.json',
        'training_inputs_v1/shard_snapshot_v1.json','reports/s_denoising_metric_reference_v1.json',
        'reports/s_native_adapter_check_v1.json','reports/cross_node_native_identity_v1.json',
        'reports/s_model_memory_equivalence_v1.json','reports/candidate_s_model_profile_4515067.json',
        'scripts/prepare_s_training_inputs_v1.py','scripts/s_native_adapter_v1.py','scripts/s_native_adapter_v2.py',
        'scripts/s_model_memory_v1.py','configs/s_memory_validation_tolerances_v1.json',
        'scripts/check_s_model_memory_v1.py','scripts/profile_candidate_s_model_v4.py']
    references=[{'path':str(ROOT/p),'bytes':(ROOT/p).stat().st_size,'sha256':sha(ROOT/p)} for p in paths]
    proof=json.loads((ROOT/'reports/s_model_memory_equivalence_v1.json').read_text())
    capacity=json.loads((ROOT/'reports/candidate_s_model_profile_4515067.json').read_text())
    assert proof['status']=='CANDIDATE_MEMORY_IMPLEMENTATION_NUMERICAL_GRADIENT_RNG_RESUME_PASS'
    assert capacity['status']=='BOUNDED_CANDIDATE_S_MODEL_PATH_PASS' and capacity['optimizer_updates']==3
    assert proof['implementation_sha256']==sha(ROOT/'scripts/s_model_memory_v1.py')
    assert capacity['numerical_gradient_rng_resume_proof']['sha256']==sha(ROOT/'reports/s_model_memory_equivalence_v1.json')
    save(ROOT/'reports/s_preparation_binding_v1.json',{'status':'PREPARATION_BOUND_AWAITING_REQUIRED_FROZEN_CONFIG_REFERENCE',
        'timestamp':time.time(),'references':references,'actual_successful_jobs':[4515058,4515061,4515063,4515066,4515067],
        'actual_failed_preparation_jobs_preserved':[4515062,4515064,4515065],
        'formal_B1_B3_started':False,'formal_B_training_accepted':False,'full_epoch_duration_measured':False,
        'candidate_architecture_accepted_by_user':False,'original_lmdb_written':False,'new_lmdb_created':False,
        'resolved_denoising_metric':'geometry_local_pair_A; clean target distance < 2 A; geometry view only',
        'allowed_scientific_scope':'Original PM7 and S labels; B1 two seeds one epoch horizon; B3 one seed three epoch horizon; frozen H0 linear probes. No S-prime training.',
        'remaining_required_input':'Identify the intended frozen_protocol.json, or confirm that the historical stage59 immutable scientific protocol supplies this round model/training/downstream parameters.'})
    print('S_PREPARATION_BOUND_NO_B_TRAINING_ACCEPTANCE',flush=True)

if __name__=='__main__':main()
