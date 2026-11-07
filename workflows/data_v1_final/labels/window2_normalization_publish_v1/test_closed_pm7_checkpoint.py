"""One new pure-metadata fixture for early, actually closed PM7 parameter stages."""
import copy
import contextlib
import io
import unittest
from unittest.mock import patch
from . import run as publisher


class ClosedPM7CheckpointTests(unittest.TestCase):
    def test_full_closed_parameter_input_preserves_refs_and_pending_MAD_contract(self):
        checkpoint='/metadata/checkpoint.json'
        refs={key:{'path':'/metadata/'+key+'.json','bytes':100} for key in (
            'coverage_reference','common_reference','d5_reference','field_map_reference',
            'element_models_reference','exact_tail_reference','winsorized_statistics_reference',
            'mask_overrides_reference','r73_derived_reference','molecule_field_means_reference')}
        eligibility_ref={'path':'/metadata/eligibility.sqlite','bytes':200}
        cfg={'mode':'full','source_records':100,**{key:refs[key] for key in ('coverage_reference','common_reference','d5_reference','field_map_reference')}}
        cfg['input_release_reference']=copy.deepcopy(cfg['common_reference'])
        eligibility={'eligibility_reference':eligibility_ref,'source_records':100,'fit_records':90,
            'Common_TRAIN_only':True,'D5_excludes_base_and_all_14_source_tasks':True}
        results={key:refs[key] for key in ('element_models_reference','exact_tail_reference','winsorized_statistics_reference',
            'mask_overrides_reference','r73_derived_reference','molecule_field_means_reference')}
        results['query_stage_reference']={'path':'/metadata/active_MAD_query.json','bytes':150}
        state={'inputs':cfg,'eligibility':eligibility,'results':results,'purpose_index':3,'pass_index':17,
            'active_stage':{'path':'/metadata/pass17/stage.json','bytes':120},'groups':{'0':{'path':'/metadata/current_MAD_group.json'}}}
        fields=[{'field_id':41,'field_key':'fixture-energy'}]
        numeric={'fit_role':'TRAIN_ONLY','source_labels_modified':False,'series':[{'key':'41/residual','mean':3.,'std_ddof0':2.}]}
        models={'41':{'basis':[1,6],'intercept':0.8,'coefficients':[-0.1,-9.]}}
        tail={'coverage_reference':cfg['coverage_reference'],'field_map_reference':cfg['field_map_reference'],
            'input_release_reference':cfg['input_release_reference'],'eligibility_reference':eligibility_ref,
            'element_models_reference':refs['element_models_reference']}
        documents={checkpoint:state,refs['field_map_reference']['path']:fields,
            refs['winsorized_statistics_reference']['path']:numeric,refs['element_models_reference']['path']:models,
            refs['exact_tail_reference']['path']:tail}
        reads=[]
        def read(reference):
            key=reference['path'] if isinstance(reference,dict) else str(reference)
            reads.append(key)
            return copy.deepcopy(documents[key])
        common_args=['--schema','schema.json','--physical-policy','policy.json','--disk-plan','guard.json','--output','output']
        args=publisher.argument_parser().parse_args(['--pm7-closed-checkpoint',checkpoint,*common_args])
        self.assertIsNone(args.pm7);self.assertEqual(args.pm7_closed_checkpoint,checkpoint)
        before=copy.deepcopy(documents)
        with patch.object(publisher,'read',side_effect=read):
            actual_fields,actual_numeric,actual_models,actual_refs=publisher.pm7_input(args)
        self.assertEqual(actual_fields,fields);self.assertEqual(actual_numeric,numeric);self.assertEqual(actual_models,models)
        self.assertEqual(actual_refs['statistics'],refs['winsorized_statistics_reference'])
        self.assertEqual(actual_refs['element_models'],refs['element_models_reference'])
        self.assertEqual(actual_refs['exact_tail'],refs['exact_tail_reference'])
        self.assertEqual(actual_refs['fields'],refs['field_map_reference'])
        self.assertEqual(actual_refs['eligibility'],eligibility)
        self.assertEqual(actual_refs['inputs'],cfg)
        self.assertEqual(actual_refs['closed_training_stage_references'],{key:value for key,value in results.items() if key!='query_stage_reference'})
        self.assertNotIn('manifest',actual_refs)
        self.assertNotIn('query_stage_reference',actual_refs['closed_training_stage_references'])
        output_state={'status':'METADATA_ROUTES_WITH_EXPLICIT_TARGET_LOCAL_READINESS'}
        output_state.update(actual_refs['publication_state'])
        self.assertEqual(output_state['status'],'NORMALIZATION_PARAMETERS_READY_D4_PENDING_MAD')
        self.assertFalse(output_state['D4_complete']);self.assertTrue(output_state['PM7_parent_C0_not_claimed'])
        self.assertFalse(output_state['PM7_parent_C0_claimed']);self.assertTrue(output_state['PM7_diagnostics_continue'])
        self.assertEqual(output_state['PM7_diagnostic_status'],'PENDING_MAD')
        self.assertEqual(actual_refs['completed_parameter_purposes'],['element_reference','normalization_quantiles','normalization_moments'])
        self.assertEqual(actual_refs['diagnostic_progress']['pass_index'],17)
        self.assertNotIn(eligibility_ref['path'],reads)
        self.assertNotIn(results['query_stage_reference']['path'],reads)
        self.assertEqual(documents,before)  # No checkpoint/results/ongoing diagnostics mutation.
        cases=[]
        bad=copy.deepcopy(state);bad['purpose_index']=2;cases.append(bad)
        bad=copy.deepcopy(state);bad['results'].pop('winsorized_statistics_reference');cases.append(bad)
        bad=copy.deepcopy(state);bad['inputs']['mode']='pilot';cases.append(bad)
        bad=copy.deepcopy(state);bad['eligibility']['Common_TRAIN_only']=False;cases.append(bad)
        bad=copy.deepcopy(state);bad['eligibility']['D5_excludes_base_and_all_14_source_tasks']=False;cases.append(bad)
        bad=copy.deepcopy(state);bad['eligibility']['source_records']=99;cases.append(bad)
        bad=copy.deepcopy(state);bad['purpose_index']=4;cases.append(bad)
        for bad in cases:
            documents[checkpoint]=bad
            with patch.object(publisher,'read',side_effect=read),self.assertRaisesRegex(ValueError,'PM7_CLOSED_CHECKPOINT:'):
                publisher.pm7_input(args)
        documents[checkpoint]=state
        documents[refs['exact_tail_reference']['path']]=dict(tail,eligibility_reference={'path':'wrong-population.sqlite'})
        with patch.object(publisher,'read',side_effect=read),self.assertRaisesRegex(ValueError,'CLOSED_TAIL_SOURCE_BINDING'):
            publisher.pm7_input(args)
        # Original completed-manifest delegation remains the original code path.
        legacy=publisher.argument_parser().parse_args(['--pm7','producer-complete-manifest.json',*common_args])
        with patch.object(publisher,'dataset_input',return_value=('unchanged',)) as original:
            self.assertEqual(publisher.pm7_input(legacy),('unchanged',))
            original.assert_called_once_with('producer-complete-manifest.json','P_D')
        with contextlib.redirect_stderr(io.StringIO()),self.assertRaises(SystemExit):
            publisher.argument_parser().parse_args(['--pm7','complete.json','--pm7-closed-checkpoint',checkpoint,*common_args])


if __name__=='__main__':unittest.main()