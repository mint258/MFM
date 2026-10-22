"""No real Slurm calls: test message fallback admission with terminal parents."""
import argparse
from contextlib import ExitStack
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import d3_message_root_v1 as root


class StopFixture(BaseException):pass


class MessageCoordinatorTests(unittest.TestCase):
    def exercise(self,values,failed_parent=False,expect_A5=False):
        with tempfile.TemporaryDirectory(prefix='owned_message_root_fixture_') as temporary:
            task=Path(temporary);source=task/'source'
            for path in [task/'configs',task/'scripts',source/'workflows/s_denoise/configs']:
                path.mkdir(parents=True,exist_ok=True)
            binding=task/'configs/D3_source_binding_v4.json';binding.write_text(json.dumps(dict(files=[])))
            lookup=task/'lookup.json';lookup.write_text(json.dumps(dict(
                status='NEW_TRAIN_LOOKUP_REFIT_AND_FULL_EVALUATION_COMPLETE',TRAIN_records=11104772,
                validation_values_used_for_fit=False,metrics=dict(D3_FULL2000=dict(lookup_rmse_A=.04)))))
            plan=task/'plan.json';plan.write_text(json.dumps(dict(phase='fixture',conditions=['M1'],scan_groups=['M1'],
                A5_name='A5_M1',message_layers=1,new_lookup_reference=dict(path=str(lookup),sha256=root.sha(lookup)))))
            control=task/'control/fixture';control.mkdir(parents=True)
            jobs={f'M1_seed{s}':dict(job_id=str(100+s)) for s in [0,1]}
            (control/'jobs.json').write_text(json.dumps(jobs))
            for seed in [0,1]:
                (source/f'workflows/s_denoise/configs/M1_seed{seed}_v3.json').write_text(json.dumps(dict(
                    condition='M1',seed=seed,loss_policy=dict(task_weights=dict(denoise_eps_mse=1.)))))
            def completed(condition,seed):
                if condition!='M1':return None
                return dict(status='D3_CONDITION_COMPLETE',optimizer_updates=4000,final=dict(local_rmse_A=values[seed]))
            def query(argv):
                if argv[0]=='squeue':return ''
                if argv[0]=='sacct':return argv[2]+('|FAILED|1:0\n' if failed_parent and argv[2]=='101' else '|COMPLETED|0:0\n')
                if argv[0]=='quota':return '/dev/fixture 0 100000000 100000000\n'
                if argv[0]=='du':return '1 fixture\n'
                raise AssertionError('Unexpected real metadata command '+repr(argv))
            with ExitStack() as stack:
                for name,value in [('ROOT',task),('SOURCE',source)]:stack.enter_context(patch.object(root,name,value))
                stack.enter_context(patch.object(root.socket,'gethostname',return_value='sonmi'))
                stack.enter_context(patch.object(root.os,'getuid',return_value=1278))
                stack.enter_context(patch.object(root,'completed_result',side_effect=completed))
                stack.enter_context(patch.object(root,'query',side_effect=query))
                stack.enter_context(patch.object(root.argparse.ArgumentParser,'parse_args',return_value=argparse.Namespace(plan=str(plan))))
                submitted=stack.enter_context(patch.object(root.subprocess,'run',return_value=argparse.Namespace(returncode=1,stderr='fixture resource wait')))
                stack.enter_context(patch.object(root.time,'sleep',side_effect=StopFixture))
                if expect_A5:
                    with self.assertRaises(StopFixture):root.main()
                else:root.main()
                if not expect_A5:submitted.assert_not_called()
            status=json.loads((control/'status.json').read_text())
            if expect_A5:
                tasks=json.loads((control/'tasks.json').read_text());self.assertEqual(len(tasks),4)
                for seed in [0,1]:
                    cfg=json.loads((source/f'workflows/s_denoise/configs/A5_M1_seed{seed}_v3.json').read_text())
                    self.assertEqual(cfg['loss_policy']['structural_tasks'],['denoise_eps_mse'])
                    self.assertAlmostEqual(cfg['total_loss_scale'],1/3)
                self.assertEqual(json.loads((control/'LR_selection.json').read_text())['selected'],'M1')
            else:
                self.assertFalse(any((source/'workflows/s_denoise/configs').glob('A5*')))
            return status

    def test_both_pass_creates_two_matching_A5_configs(self):
        self.exercise([.03,.035],expect_A5=True)

    def test_either_seed_failure_prevents_A5(self):
        status=self.exercise([.03,.05]);self.assertEqual(status['status'],'D3_MESSAGE_LAYER_CAPABILITY_FAILED')

    def test_lookup_equality_does_not_pass(self):
        status=self.exercise([.03,.04]);self.assertEqual(status['status'],'D3_MESSAGE_LAYER_CAPABILITY_FAILED')

    def test_failed_actual_parent_prevents_promotion_even_with_results(self):
        status=self.exercise([.03,.035],failed_parent=True)
        self.assertEqual(status['status'],'ORDINARY_FAILURE_NEEDS_ROOT_REVIEW')


if __name__=='__main__':unittest.main()
