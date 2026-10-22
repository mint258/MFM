import copy
import math
import unittest
import json
from pathlib import Path
import tempfile
from stage3_gate_v5 import query_parents, ROOT
from stage3_gate_v5 import judge, denoise_fraction, estimate_cost


def fixture():
    def result(rmse=.03, acc=.9, bond=.99):
        return dict(final=dict(local_rmse_A=rmse, masked_element_accuracy=acc, bond_order_accuracy=bond),
            final_gradient_rows=[dict(optimizer_update=i, diagnostics=dict(norms=dict(element=1., denoise_eps_mse=1., bond_order=1.),
                fractions_of_sum_of_norms=dict(element=.45, denoise_eps_mse=.1, bond_order=.45))) for i in range(3980,4000)])
    return {i:dict(multitask=result(),denoise_only=result(),A0=result(),cost=dict(estimated_GPU_hours=15.)) for i in [0,1]}


class GateTests(unittest.TestCase):
    def test_all_five_require_both_seeds(self):
        seeds=fixture(); self.assertTrue(judge(seeds,.04)['formal_training_authorized_by_gate'])
        seeds[1]['multitask']['final']['local_rmse_A']=.041
        self.assertFalse(judge(seeds,.04)['gates']['denoising'])

    def test_lookup_equality_fails_historical_reference_is_not_gate(self):
        seeds=fixture(); self.assertFalse(judge(seeds,.03)['gates']['denoising'])
        for seed in seeds.values():
            seed['multitask']['final']['local_rmse_A']=.045; seed['denoise_only']['final']['local_rmse_A']=.045
        report=judge(seeds,.05)
        self.assertTrue(report['gates']['denoising']); self.assertFalse(report['measurements'][0]['below_historical_0_042_A'])

    def test_better_or_worse_A5_large_gap_fails(self):
        for rmse in [.02,.04]:
            seeds=fixture(); seeds[0]['denoise_only']['final']['local_rmse_A']=rmse
            self.assertFalse(judge(seeds,.05)['gates']['interference'])

    def test_interference_exact_ten_percent_passes(self):
        seeds=fixture(); seeds[0]['denoise_only']['final']['local_rmse_A']=.033
        self.assertTrue(judge(seeds,.04)['gates']['interference'])

    def test_no_accuracy_tolerance_or_seed_mean_substitution(self):
        seeds=fixture(); seeds[0]['multitask']['final']['masked_element_accuracy']-=1e-8
        seeds[1]['multitask']['final']['masked_element_accuracy']+=.02
        self.assertFalse(judge(seeds,.04)['gates']['other_tasks'])

    def test_gradient_exact_boundary_and_lower(self):
        seeds=fixture(); self.assertTrue(judge(seeds,.04)['gates']['gradient'])
        for row in seeds[1]['multitask']['final_gradient_rows']:
            row['diagnostics']['fractions_of_sum_of_norms'].update(denoise_eps_mse=.099,element=.451)
        self.assertFalse(judge(seeds,.04)['gates']['gradient'])

    def test_cost_exact_boundary_and_larger(self):
        seeds=fixture(); self.assertTrue(judge(seeds,.04)['gates']['cost'])
        seeds[1]['cost']['estimated_GPU_hours']=15.001
        self.assertFalse(judge(seeds,.04)['gates']['cost'])

    def test_missing_or_nan_cannot_pass(self):
        seeds=fixture(); seeds[1]['multitask']['final']['local_rmse_A']=math.nan
        with self.assertRaises(ValueError): judge(seeds,.04)
        seeds=fixture(); seeds[0]['multitask']['final_gradient_rows'].pop()
        with self.assertRaises(ValueError): denoise_fraction(seeds[0]['multitask'])

    def test_estimator_subtracts_all_checkpoint_time(self):
        result=dict(training_records_per_second=100.,training_seconds_including_loader=100.,
            checkpoint_all_save_readback_seconds=90.,checkpoint_save_readback_seconds=10.,
            runtime=dict(gpu_model='fixture'),gpu_peak_allocated_bytes=100,gpu_peak_reserved_bytes=200)
        curve=[dict(optimizer_update=i,evaluation_records=18486,evaluation_wall_seconds=10.) for i in range(0,4001,500)]
        estimator=dict(train_records=10000,FULL_records=18486,routine_records=0,
            FULL_plus_routine_validation_events_per_epoch_upper_reference=1,
            checkpoint_save_readback_events_per_epoch_reference=2,usable_training_segment_seconds=60)
        cost=estimate_cost(result,curve,300.,estimator)
        self.assertEqual(cost['measured_startup_close_seconds'],20.)
        self.assertAlmostEqual(cost['estimated_GPU_hours'],170/3600)
        with self.assertRaises(ValueError): estimate_cost(result,curve,200.,estimator)


class ParentSnapshotTests(unittest.TestCase):
    def run_snapshot(self,mutation=None):
        folder=ROOT/'control/accounting_snapshots'
        with tempfile.TemporaryDirectory(prefix='gate_unit_fixture_',dir=folder) as temporary:
            path=Path(temporary)/'fixture.json'
            doc=dict(status='ACTUAL_SONMI_SACCT_SNAPSHOT',host='sonmi',uid=1278,
                columns=['State','ExitCode','ElapsedRaw','AllocCPUS'],
                rows={'123':['COMPLETED','0:0','10','16']},raw_stdout='123|COMPLETED|0:0|10|16\n')
            if mutation:mutation(doc)
            path.write_text(json.dumps(doc))
            return query_parents({'123'},path)

    def test_parent_snapshot_accepts_matching_terminal_raw_row(self):
        self.assertEqual(self.run_snapshot()['123'][2:3],['10'])

    def test_parent_snapshot_rejects_row_raw_disagreement(self):
        with self.assertRaises(ValueError):self.run_snapshot(lambda d:d['rows']['123'].__setitem__(0,'RUNNING'))

    def test_parent_snapshot_rejects_failed_or_missing_parent(self):
        def failed(d):
            d['rows']['123'][0]='FAILED';d['raw_stdout']='123|FAILED|0:0|10|16\n'
        with self.assertRaises(ValueError):self.run_snapshot(failed)
        with self.assertRaises(ValueError):self.run_snapshot(lambda d:d['rows'].clear())

    def test_parent_snapshot_rejects_wrong_origin(self):
        with self.assertRaises(ValueError):self.run_snapshot(lambda d:d.update(host='compute-0-8'))


class GateCLITests(unittest.TestCase):
    def test_default_baseline_phase_is_original_d3(self):
        from stage3_gate_v5 import parse_args
        args=parse_args(['--phase','message_fixture','--parent-snapshot','snapshot.json','--output','gate.json'])
        self.assertEqual(args.baseline_phase,'d3_local_blocks_v1')

    def test_explicit_baseline_phase_is_preserved(self):
        from stage3_gate_v5 import parse_args
        args=parse_args(['--phase','message_fixture','--baseline-phase','original_fixture',
                         '--parent-snapshot','snapshot.json','--output','gate.json'])
        self.assertEqual(args.baseline_phase,'original_fixture')

    def test_missing_required_arguments_are_rejected(self):
        from stage3_gate_v5 import parse_args
        import contextlib,io
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as caught:parse_args(['--phase','fixture'])
        self.assertEqual(caught.exception.code,2)

    def test_completed_phase_cli_reaches_lookup_without_missing_attribute(self):
        import stage3_gate_v5 as gate
        from unittest.mock import patch
        with tempfile.TemporaryDirectory(prefix='stage3_cli_entry_fixture_') as temporary:
            root=Path(temporary)
            phase=root/'control'/'fixture';phase.mkdir(parents=True)
            baseline=root/'control'/'d3_local_blocks_v1';baseline.mkdir()
            (phase/'status.json').write_text(json.dumps({'status':'D3_PHASE_COMPLETE_AWAITING_SCIENTIFIC_GATE'}))
            (phase/'LR_selection.json').write_text(json.dumps({'selected':'A2','scores':{'A2':.03,'A3':.04,'A4':.05}}))
            (phase/'jobs.json').write_text('{}')
            (baseline/'jobs.json').write_text(json.dumps({'A0_seed0':{'job_id':'fixture0'},'A0_seed1':{'job_id':'fixture1'}}))
            (phase/'tasks.json').write_text(json.dumps([['A2',0],['A2',1],['A5',0],['A5',1]]))
            with patch.object(gate,'ROOT',root),patch.object(gate,'sha',return_value=gate.GUIDE_SHA),patch.object(gate,'read_ref',side_effect=ValueError('FIXTURE_LOOKUP_BOUNDARY')) as reader,patch('sys.argv',['gate','--phase','fixture','--parent-snapshot',str(root/'snapshot.json'),'--output',str(root/'gate.json')]):
                with self.assertRaisesRegex(ValueError,'FIXTURE_LOOKUP_BOUNDARY'):gate.main()
                reader.assert_called_once_with(root/'reports/lookup_latest.json',[])
            self.assertFalse((root/'gate.json').exists())


class LookupProvenanceTests(unittest.TestCase):
    def execute(self,mutate=None):
        import stage3_gate_v5 as gate
        from unittest.mock import patch
        with tempfile.TemporaryDirectory(prefix='lookup_parent_provenance_fixture_') as temporary:
            root=Path(temporary);config=root/'configs';config.mkdir()
            folder=root/'control/accounting_snapshots';folder.mkdir(parents=True)
            snapshot=folder/'snapshot.json';output=root/'result.json'
            lookup={'metrics':{'full':{'records':127082},'D3_FULL2000':{'records':18486}}}
            output.write_text(json.dumps(lookup))
            accounting=dict(status='ACTUAL_SONMI_SACCT_SNAPSHOT',host='sonmi',uid=1278,
                columns=['State','ExitCode','ElapsedRaw','AllocCPUS'],
                rows={'123':['COMPLETED','0:0','10','16']},raw_stdout='123|COMPLETED|0:0|10|16\n')
            closure={'status':'ACTUAL_FULL_TRAIN_LOOKUP_REFIT_CLOSED','job_id':'123','guide_sha256':gate.GUIDE_SHA,
                'TRAIN_records':11104772,'metrics':lookup['metrics'],'actual_parent':['COMPLETED','0:0','10','16'],
                'result_reference':{'path':str(output),'sha256':gate.sha(output)},
                'canonical_recipe_sources':[],'output_references':[]}
            if mutate:mutate(accounting,closure,output)
            snapshot.write_text(json.dumps(accounting))
            closure['actual_parent_snapshot']={'path':str(snapshot),'sha256':gate.sha(snapshot)}
            path=config/'closure.json';path.write_text(json.dumps(closure))
            with patch.object(gate,'ROOT',root):return gate.lookup_provenance(path,lookup,output)

    def test_actual_completed_lookup_and_same_result_accepted(self):
        job,refs=self.execute();self.assertEqual(job,'123');self.assertEqual(len(refs),2)

    def test_timeout_with_exit_zero_never_accepted(self):
        def mutate(accounting,closure,output):
            accounting['rows']['123'][0]='TIMEOUT';accounting['raw_stdout']='123|TIMEOUT|0:0|10|16\n'
            closure['actual_parent'][0]='TIMEOUT'
        with self.assertRaises(ValueError):self.execute(mutate)

    def test_same_measurements_cannot_substitute_other_result_hash(self):
        with self.assertRaises(ValueError):self.execute(lambda a,c,p:c['result_reference'].update(sha256='0'*64))

    def test_actual_parent_projection_cannot_be_fabricated(self):
        with self.assertRaises(ValueError):self.execute(lambda a,c,p:c['actual_parent'].__setitem__(2,'11'))

    def test_changed_recipe_or_table_rejected(self):
        def mutate(accounting,closure,output):closure['output_references']=[{'path':str(output),'sha256':'0'*64}]
        with self.assertRaises(ValueError):self.execute(mutate)


class SourceBindingCLITests(unittest.TestCase):
    def test_old_source_binding_default_preserved(self):
        from stage3_gate_v5 import parse_args
        args=parse_args(['--phase','fixture','--parent-snapshot','snap','--output','result'])
        self.assertEqual(args.source_binding,ROOT/'configs/D3_source_binding_v4.json')

    def test_new_immutable_binding_argument_preserved(self):
        from stage3_gate_v5 import parse_args
        value=str(ROOT/'configs/D3_source_binding_v5.json')
        args=parse_args(['--phase','fixture','--parent-snapshot','snap','--output','result','--source-binding',value])
        self.assertEqual(str(args.source_binding),value)

    def test_scientific_and_accounting_functions_unchanged(self):
        import ast,inspect,stage3_gate_v4 as old,stage3_gate_v5 as new
        original=ast.parse(inspect.getsource(old));current=ast.parse(inspect.getsource(new))
        for item in original.body:
            if isinstance(item,ast.FunctionDef) and item.name not in ['main','parse_args']:
                counterpart=next(x for x in current.body if isinstance(x,ast.FunctionDef) and x.name==item.name)
                self.assertEqual(ast.dump(item),ast.dump(counterpart),item.name)


if __name__=='__main__': unittest.main()
