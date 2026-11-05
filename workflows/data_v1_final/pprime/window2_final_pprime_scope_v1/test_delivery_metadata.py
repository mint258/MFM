"""Final delivery metadata only: C0, exact partition and preserved old history."""
import copy,unittest
from .publish_delivery import assemble

class DeliveryMetadata(unittest.TestCase):
    def test_metadata_closure_preserves_history_and_reports_scientific_failures(self):
        scope={'schema':'PPRIME_FINAL_PHYSICAL_FIRST2_CONTINUATION_SCOPE_V1','needed_records':2,
            'reused_closed_records':8,'actual_first2_records':10,'actual_chosen_MIDs':6,'unknown_native_intents':0,
            'no_Pprime_rank_ge_2':True,'no_new_N1_generation':True,'no_padding_or_duplication':True,
            'record_level_state_table':{'path':'/frozen/states.parquet','bytes':11},'shortfall_counts':{'ACTUAL_SHORTFALL':2}}
        producer={'schema':'PPRIME_FINAL_PHYSICAL_FIRST2_PRODUCER_V1','status':'COMPLETED_ALL_MISSING_PHYSICAL_RECORDS',
            'actual_job_id':'1234','scope':'/scope/v3/manifest.json','records_completed':2,'records_assigned':2,
            'prior_scope_unknown_native_intents':0,'claim_status_counts':{'CLOSED_TWELVE_OUTCOMES':2},
            'original_native_recipe_900s_unchanged':True,'no_Pprime_rank_ge_2':True,'no_new_N1_generation':True,
            'no_automatic_native_retry':True,'all12_success':1,'batches':[{'completed':2,'all12_success':1,
                'raw_outputs':{'path':'/new/raw.sqlite','bytes':20},'files':[{'family':'base_geometry','path':'/new/base.parquet','bytes':10,'rows':2}]}]}
        initial={'manifest':'/old_initial/manifest.json','missing_molecule_ids':'/original/missing_mids.parquet',
            'missing_reason':'Original exact 80740 minus 12 already ready = 80728, unchanged.',
            'molecules':80728,'first2_records_completed':161456,'all12_success':161044,
            'records_with_scientific_task_failures':412,'status':'INITIAL_SCOPE_COMPLETE_FINAL_POPULATION_DELTA_PENDING'}
        refs={'scope':{'path':'/scope/v3/manifest.json','bytes':100},'producer':{'path':'/new/manifest.json','bytes':200},
            'initial_delivery':{'path':'/repo/initial.json','bytes':30},'initial_manifest':{'path':'/old_initial/manifest.json','bytes':40},
            'original_ready':{'path':'/old_ready/completion.json','bytes':50}}
        closure={'job_id':'1234','state':'COMPLETED','exit_code':'0:0'};saved=copy.deepcopy(initial)
        result=assemble(scope,producer,initial,refs,closure)
        self.assertEqual(result['actual_first2_records'],result['existing_closed_geometry_records_reused']+result['new_geometry_records_completed'])
        self.assertEqual(result['new_records_with_scientific_task_failures'],1);self.assertIsNone(result['reused_subset_all12_success'])
        self.assertEqual(result['historical_initial_fill']['missing_reason'],initial['missing_reason'])
        self.assertEqual(result['historical_initial_fill']['raw_output_root'],'/old_initial');self.assertEqual(initial,saved)
        with self.assertRaisesRegex(ValueError,'ACTUAL_NATIVE_C0_REQUIRED'):
            assemble(scope,producer,initial,refs,dict(closure,state='RUNNING'))
        with self.assertRaisesRegex(ValueError,'CLOSED_FINAL_NATIVE_PRODUCER_REQUIRED'):
            assemble(scope,dict(producer,status='CLOSED_WITH_EXPLICIT_UNRESOLVED'),initial,refs,closure)
