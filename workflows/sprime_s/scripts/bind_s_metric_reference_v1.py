"""Bind historical denoising reference evidence without selecting a model recipe."""
import json,time
from prepare import ROOT,PROJECT,save,sha

def main():
    path=PROJECT/'docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/checks/pipeline_D5_v7_actual_result.json'
    value=json.loads(path.read_text())
    assert value['status']=='COMPLETE_VISITATION' and value['train_fit_only'] is True
    assert value['validation_values_used_for_table_fit'] is False and value['local_cutoff_A']==2.0
    assert value['TRAIN_scanned_records']==15709889 and value['routine_evaluated_records']==16000
    save(ROOT/'reports/s_denoising_metric_reference_v1.json',{
        'status':'HISTORICAL_METRIC_DEFINITION_BOUND','timestamp':time.time(),
        'evidence':{'path':str(path),'sha256':sha(path),'bytes':path.stat().st_size},
        'primary_metric':'geometry_local_pair_A','local_target_distance_cutoff_A':2.0,
        'pair_policy':'Each unordered valid native atom pair once; target clean distance < 2 A; includes H and nonbonded pairs; geometry view only.',
        'historical_noisy_rmse_A':value['identity_noisy_baseline_rmse_A'],
        'historical_lookup_rmse_A':value['lookup_rmse_A'],
        'guide_noisy_stop_threshold_A':0.141,'guide_lookup_comparison_threshold_A':0.042,
        'historical_train_records':value['TRAIN_scanned_records'],'historical_routine_records':value['routine_evaluated_records'],
        'historical_local_unordered_pairs':value['local_unordered_atom_pairs'],
        'new_population_train_records':11104772,'new_population_full_records':127082,'new_population_routine_records':11322,
        'new_population_lookup_refit_or_inference_claimed':False,
        'interpretation':'Use the guide thresholds with the same local pair metric. The historical lookup numbers come from the former population; never claim the table was fitted only on the new TRAIN or evaluated on the new FULL.',
        'also_report_geometry_all_pair_A':True,'model_training_started':False})
    print('HISTORICAL_METRIC_DEFINITION_BOUND',flush=True)

if __name__=='__main__':main()
