"""One pure-mock comparison-input regression; no arrays, files or computation."""
import copy,io,unittest
from contextlib import nullcontext
from unittest.mock import Mock,patch
from . import compare as C
from ..window2_normalization_publish_v1 import run as P

class ClosedCheckpointCompare(unittest.TestCase):
    def test_old_mode_closed_bindings_missing_means_and_exclusive_arguments(self):
        def ref(path):return {'path':path,'bytes':100}
        cfg={'mode':'full','source_records':10,**{key:ref('/closed/'+key) for key in ('coverage_reference','common_reference','d5_reference','field_map_reference')}}
        cfg['input_release_reference']=copy.deepcopy(cfg['common_reference'])
        results={key:ref('/closed/'+key) for key in ('element_models_reference','exact_tail_reference','winsorized_statistics_reference','molecule_field_means_reference')}
        eligibility={'Common_TRAIN_only':True,'D5_excludes_base_and_all_14_source_tasks':True,'source_records':10,'fit_records':8,'eligibility_reference':ref('/closed/eligibility')}
        state={'inputs':cfg,'results':results,'eligibility':eligibility,'purpose_index':3,'pass_index':16,'active_stage':ref('/closed/running-diagnostics')}
        tail={key:cfg[key] for key in ('coverage_reference','field_map_reference','input_release_reference')}
        tail.update(eligibility_reference=eligibility['eligibility_reference'],element_models_reference=results['element_models_reference'])
        documents={'/closed/checkpoint.json':state,results['exact_tail_reference']['path']:tail,results['winsorized_statistics_reference']['path']:{'fit_role':'TRAIN_ONLY','source_labels_modified':False},results['element_models_reference']['path']:{},cfg['field_map_reference']['path']:[]}
        means={'fit_role':'TRAIN','geometry_source':'pm7','files':[ref('/closed/pm7-means.parquet')]}
        pp_means=ref('/pprime/means.json');legacy={'fit_role':'TRAIN','statistics':results}
        pprime={'fit_role':'TRAIN','statistics':{'molecule_field_means_reference':pp_means}}
        def read(value):return copy.deepcopy(documents[value['path'] if isinstance(value,dict) else str(value)])
        def load(path):return copy.deepcopy(legacy if str(path)=='/legacy/manifest.json' else pprime)
        def load_data(value):
            return copy.deepcopy(means if value==results['molecule_field_means_reference'] else {'files':[ref('/pprime/means.parquet')]})
        db=Mock();db.execute.return_value=db;db.fetch_arrow_table.return_value.to_pylist.return_value=[]
        runtime=Mock();runtime.duckdb.side_effect=lambda connection:nullcontext(connection)
        with patch.object(P,'read',side_effect=read) as closed_read,patch.object(C.I,'load',side_effect=load),patch.object(C.I,'load_data',side_effect=load_data),patch.object(C.Temp,'activate',return_value=runtime),patch.object(C.Path,'mkdir'),patch.object(C.I,'save',side_effect=lambda path,value:ref(str(path))),patch.object(C.I,'ref',side_effect=lambda path:ref(str(path))),patch.object(C,'distributions',return_value=[]),patch('duckdb.connect',return_value=db),patch('pyarrow.Table',new=Mock()),patch('pyarrow.parquet.write_table'):
            old=C.compare('/legacy/manifest.json','/pprime/manifest.json','/mock/old',{'mock_runtime':True})
            self.assertNotIn('pm7_input_source',old);closed_read.assert_not_called()
            old_sql=[call.args[0] for call in db.execute.call_args_list];db.reset_mock()
            current=C.compare(None,'/pprime/manifest.json','/mock/new',{'mock_runtime':True},pm7_closed_checkpoint='/closed/checkpoint.json')
            self.assertEqual([call.args[0] for call in db.execute.call_args_list],old_sql)
            source=current['pm7_input_source']
            self.assertEqual(source['source_kind'],'PM7_CLOSED_PARAMETER_CHECKPOINT')
            self.assertEqual(source['inputs']['common_reference'],cfg['common_reference']);self.assertEqual(source['inputs']['d5_reference'],cfg['d5_reference'])
            self.assertEqual(source['closed_training_stage_references'],results)
            self.assertEqual(source['exact_tail'],results['exact_tail_reference'])
            self.assertFalse(current['PM7_D4_complete']);self.assertFalse(current['PM7_parent_C0_claimed'])
            self.assertEqual(source['publication_state']['PM7_diagnostic_status'],'PENDING_MAD')
            self.assertEqual(db.read_parquet.call_args_list[0].args[0],['/closed/pm7-means.parquet'])
            view,_,_=C.pm7_comparison_input(closed_checkpoint='/closed/checkpoint.json');self.assertNotIn('status',view)
            del results['molecule_field_means_reference']
            with self.assertRaisesRegex(ValueError,'MEANS_REFERENCE_REQUIRED'):C.pm7_comparison_input(closed_checkpoint='/closed/checkpoint.json')
            results['molecule_field_means_reference']=ref('/closed/molecule_field_means_reference')
            means['fit_role']='VAL'
            with self.assertRaisesRegex(ValueError,'TRAIN_MEANS_REQUIRED'):C.pm7_comparison_input(closed_checkpoint='/closed/checkpoint.json')
            with self.assertRaisesRegex(ValueError,'EXACTLY_ONE_PM7'):C.pm7_comparison_input('/legacy/manifest.json','/closed/checkpoint.json')
        args=C.argument_parser().parse_args(['--pm7','legacy','--pprime','pp','--output','out'])
        self.assertEqual(args.pm7,'legacy');self.assertIsNone(args.pm7_closed_checkpoint)
        args=C.argument_parser().parse_args(['--pm7-closed-checkpoint','closed','--pprime','pp','--output','out'])
        self.assertEqual(args.pm7_closed_checkpoint,'closed');self.assertIsNone(args.pm7)
        with patch('sys.stderr',io.StringIO()):
            with self.assertRaises(SystemExit):C.argument_parser().parse_args(['--pm7','legacy','--pm7-closed-checkpoint','closed','--pprime','pp','--output','out'])