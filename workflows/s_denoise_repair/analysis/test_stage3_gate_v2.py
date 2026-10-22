import copy
import math
import unittest
import json
from pathlib import Path
import tempfile
from stage3_gate_v2 import query_parents, ROOT
from stage3_gate_v2 import judge, denoise_fraction, estimate_cost


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


if __name__=='__main__': unittest.main()
