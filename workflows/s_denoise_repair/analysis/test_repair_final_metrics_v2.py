import copy,math,unittest
from repair_final_metrics_v2 import (N,MOLECULES,CONDITIONS,ENDPOINTS,CELLS,TASKS,PRIMARY_EXCLUSIONS,
    final_training,aggregate_map,compare_full,old_new_comparisons)

def training_fixture():
    values=dict(records=127082,missing=0,duplicates=0,noise_mse_normalized=.5,local_rmse_A=.03,
                masked_element_nll=.1,bond_order_accuracy=.98)
    training={}
    for condition in CONDITIONS:
        epochs=1 if condition.startswith('B1_') else 3
        training[condition]={'status':'TRAINING_EXPOSURES_COMPLETE_AWAITING_H0_PROBES','condition':condition,
           'epoch_accepted':True,'development_only':False,'scientific_stop':False,'consumed_records':epochs*N,
           'completed_epochs':[{'epoch':e,'records':N,'molecules':MOLECULES} for e in range(1,epochs+1)],
           'validation_history':[{'consumed_records':e*N,'optimizer_updates':e*100,
                'values':{'full':copy.deepcopy(values),'routine':{**values,'records':11322}}} for e in range(1,epochs+1)]}
    return training

def probe_fixture():
    cells=[dict(dataset=d,fold=f,encoder_trained=False,test_targets_used_for_model_or_endpoint_selection=False) for d,f in sorted(CELLS)]
    rows=[]
    for dataset,tasks in TASKS.items():
        for task in tasks:
            atom=dataset in ['cyp_isoform','az_exactsom'];value=.8 if atom else 1.
            rows.append(dict(dataset=dataset,task=task,metric_name='molecule_hit_at_1' if atom else 'MAE',
               primary_metric=value,fold_metrics=[value]*(1 if dataset=='expansionrx' else 10),
               included_in_primary_judgment=dataset+'.'+task not in PRIMARY_EXCLUSIONS))
    return {p:dict(endpoint=p,status='ALL_FORTY_ONE_FROZEN_LINEAR_PROBE_CELLS_CLOSED',primary_tasks=32,
        all_reported_tasks=35,expansion_official_test_rows_used_for_training=False,cells=copy.deepcopy(cells),aggregate=copy.deepcopy(rows)) for p in ENDPOINTS}

def set_metric(probes,point,key,value):
    row=next(r for r in probes[point]['aggregate'] if r['dataset']+'.'+r['task']==key)
    row['primary_metric']=value;row['fold_metrics']=[value]*len(row['fold_metrics'])

class FinalMetricsTests(unittest.TestCase):
    def test_all_four_runs_twelve_endpoints_counts_close(self):
        result=compare_full(training_fixture(),probe_fixture())
        self.assertEqual(result['closed_probe_cells'],492);self.assertEqual(result['closed_report_task_rows'],420)
        self.assertEqual(result['total_base_training_exposures'],88838176)
        self.assertEqual(result['judgment']['status'],'ONE_EPOCH_SUFFICIENT_UNDER_V3_DIRECTIONAL_RULE')
        self.assertFalse(result['required_epoch_count_extrapolated']);self.assertFalse(result['later_than_three_epochs_convergence_claimed'])

    def test_partial_development_wrong_exposure_or_population_rejected(self):
        mutations=[lambda x:x.update(development_only=True),lambda x:x.update(epoch_accepted=False),
          lambda x:x.update(consumed_records=3*N-1),lambda x:x.update(status='PARTIAL_CHECKPOINT_REQUIRES_CONTINUATION'),
          lambda x:x['completed_epochs'][-1].update(molecules=MOLECULES-1)]
        for mutation in mutations:
            x=training_fixture()['B3_seed0'];mutation(x)
            with self.subTest(summary=x),self.assertRaises(ValueError):final_training(x,'B3_seed0')

    def test_exact_epoch_full_and_routine_coverage_required(self):
        for mutation in [lambda x:x['validation_history'][-1].update(consumed_records=3*N-1),
          lambda x:x['validation_history'][-1]['values']['full'].update(duplicates=1),
          lambda x:x['validation_history'][-1]['values']['routine'].update(records=11321)]:
            x=training_fixture()['B3_seed0'];mutation(x)
            with self.assertRaises(ValueError):final_training(x,'B3_seed0')

    def test_missing_any_endpoint_rejected(self):
        probes=probe_fixture();probes.pop('B3_seed1_e0p25')
        with self.assertRaises(ValueError):compare_full(training_fixture(),probes)

    def test_missing_primary_value_remains_missing(self):
        probes=probe_fixture();set_metric(probes,'B1_seed1_e1','qm9.homo',None)
        result=compare_full(training_fixture(),probes)
        self.assertEqual(result['judgment']['status'],'NOT_YET_EVALUABLE')
        self.assertTrue(result['judgment']['missing_metrics_present'])

    def test_b3_worse_is_not_unconverged(self):
        probes=probe_fixture()
        for s in [0,1]:set_metric(probes,'B3_seed'+str(s)+'_e3','qm9.homo',2.)
        result=compare_full(training_fixture(),probes)
        row=next(r for r in result['probe_comparisons'] if r['id']=='qm9.homo')
        self.assertFalse(row['unconverged']);self.assertLess(row['B3_improvement_original_units'],0)

    def test_b3_better_must_exceed_both_seed_spreads(self):
        probes=probe_fixture()
        for point,value in [('B1_seed0_e1',1.),('B1_seed1_e1',2.),('B3_seed0_e3',1.2),('B3_seed1_e3',1.3)]:
            set_metric(probes,point,'qm9.homo',value)
        result=compare_full(training_fixture(),probes)
        self.assertFalse(next(r for r in result['probe_comparisons'] if r['id']=='qm9.homo')['unconverged'])
        for point,value in [('B1_seed1_e1',1.1),('B3_seed0_e3',.5),('B3_seed1_e3',.6)]:set_metric(probes,point,'qm9.homo',value)
        result=compare_full(training_fixture(),probes)
        self.assertEqual(result['judgment']['primary_probes_with_material_B3_improvement'],['qm9.homo'])
        self.assertEqual(result['unconverged_primary_probe_categories']['qm9'],1)

    def test_expansion_official_regression_uses_lower_MAE(self):
        probes=probe_fixture()
        for s in [0,1]:set_metric(probes,'B3_seed'+str(s)+'_e3','expansionrx.LogD',.5)
        result=compare_full(training_fixture(),probes)
        row=next(r for r in result['probe_comparisons'] if r['id']=='expansionrx.LogD')
        self.assertFalse(row['higher_is_better']);self.assertTrue(row['unconverged'])

    def test_old_b3_has_one_seed_and_unknown_spread(self):
        probes=probe_fixture();rows=old_new_comparisons(probes,probes)
        self.assertEqual(len(rows),70)
        b3=[r for r in rows if r['kind']=='B3'];self.assertEqual(len(b3),35)
        self.assertTrue(all(r['old_seed_count']==1 and r['old_seed_spread'] is None and r['new_seed_count']==2 for r in b3))

    def test_missing_fold_not_replaced_by_partial_mean(self):
        p=probe_fixture()['B1_seed0_e1'];p['aggregate'][0]['fold_metrics'][0]=None
        with self.assertRaises(ValueError):aggregate_map(p,'B1_seed0_e1')

    def test_nonfinite_or_impossible_metrics_rejected(self):
        for value in [math.nan,math.inf,-1.]:
            p=probe_fixture();set_metric(p,'B1_seed0_e1','qm9.homo',value)
            with self.assertRaises(ValueError):aggregate_map(p['B1_seed0_e1'],'B1_seed0_e1')
        p=probe_fixture();set_metric(p,'B1_seed0_e1','az_exactsom.exact_som',1.1)
        with self.assertRaises(ValueError):aggregate_map(p['B1_seed0_e1'],'B1_seed0_e1')

    def test_fixed_task_family_and_primary_exclusions_required(self):
        for mutation in [lambda x:x['aggregate'][0].update(task='invented'),
          lambda x:x['aggregate'][0].update(included_in_primary_judgment=False),
          lambda x:x['aggregate'][0].update(metric_name='molecule_hit_at_1')]:
            p=probe_fixture()['B1_seed0_e1'];mutation(p)
            with self.assertRaises(ValueError):aggregate_map(p,'B1_seed0_e1')

    def test_duplicate_or_wrong_scaffold_cells_rejected(self):
        p=probe_fixture()['B1_seed0_e1'];p['cells'][-1]=p['cells'][0]
        with self.assertRaises(ValueError):aggregate_map(p,'B1_seed0_e1')

    def test_encoder_or_test_target_training_rejected(self):
        for field in ['encoder_trained','test_targets_used_for_model_or_endpoint_selection']:
            p=probe_fixture()['B1_seed0_e1'];p['cells'][0][field]=True
            with self.assertRaises(ValueError):aggregate_map(p,'B1_seed0_e1')

if __name__=='__main__':unittest.main()
