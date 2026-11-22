"""New endpoint admission/wiring only; no checkpoint, model or probe rerun."""
from contextlib import contextmanager
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import terminal_readouts_20261122 as terminal
import test_snapshot_boundaries_20261122 as snapshots


class TerminalTests(unittest.TestCase):
    def setUp(self):
        self.scratch=tempfile.TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        self.output=Path(self.scratch.name)
        self.c=dict(run='S_N1_s0_3M',arm='S-N1',seed=0,samples=3000000,
            output=str(self.output),evaluation_samples=[3000000],
            training_closure_record=str(self.output/'closure.json'))
        self.c.update(source='PM7',noise='multiscale',disabled=[],
            population=str(self.output/'population.json'),root=str(self.output/'source'),
            batch_size=32,microbatch_size=32,lr=.0003,betas=[.9,.95],weight_decay=.01,
            clip_calibration={'initial_clip':281.7},distance_bias='C1-0',views='three',
            components=['S-N1'],normalization=str(self.output/'normalization.json'))
        (self.output/'configuration.json').write_text(json.dumps(self.c))
        self.summary('TRAINING_COMPLETE_READOUT_PENDING')
        (self.output/'samples_3000000.pt').write_bytes(b'closed unit fixture, never loaded')
        self.closure(3000000)
        self.guard=SimpleNamespace(stopping=lambda: False,phase='preparing')

    def summary(self,status,samples=3000000):
        (self.output/'summary.json').write_text(json.dumps(dict(status=status,samples=samples,seconds=12)))

    def closure(self,samples):
        (self.output/'closure.json').write_text(json.dumps(dict(run=self.c['run'],
            result=dict(samples=samples),ended_at=1,owned_descendants_exited=True)))

    def test_partial_training_clock_cannot_be_an_endpoint(self):
        self.summary('TRAINING_COMPLETE_READOUT_PENDING',2999968)
        with patch.dict(sys.modules,dispatch=SimpleNamespace(authorized=lambda c: None)):
            with self.assertRaises(ValueError):
                terminal.registered(self.c,3000000)

    def test_saved_handoff_is_not_full_budget_exit(self):
        self.closure(985024)
        with patch.dict(sys.modules,dispatch=SimpleNamespace(authorized=lambda c: None)):
            with self.assertRaises(ValueError):
                terminal.registered(self.c,3000000)
            self.closure(3000000)
            terminal.registered(self.c,3000000)

    def test_producer_condition_cannot_be_relabelled_as_another_arm(self):
        with patch.dict(sys.modules,dispatch=SimpleNamespace(authorized=lambda c: None)):
            with self.assertRaisesRegex(ValueError,'arm'):
                terminal.registered(dict(self.c,arm='S-N2'),3000000)

    def readouts(self,calls):
        return SimpleNamespace(existing_evaluation=lambda: None,
            configuration=lambda c,n:dict(c,layer=6,checkpoint_samples=n),
            gpu=lambda setting:calls.append(('R3',setting['layer'],setting['checkpoint_samples'])))

    def test_only_known_B0_G1_capture_and_all_formal_probes_stay_layer6(self):
        for arm,expected in (('S-N1',[('R3',6,3000000)]),
                             ('S-G1',['capture',('R3',6,3000000)])):
            calls=[]
            self.summary('TRAINING_COMPLETE_READOUT_PENDING')
            c=dict(self.c,arm=arm)
            old=lambda: self.fail('Legacy peer-budget callback must not run')
            endpoint=SimpleNamespace(capacity=old)
            def capture(actual):
                self.assertIs(actual,c)
                endpoint.capacity()
                calls.append('capture')
            endpoint.capture=capture
            with patch.dict(sys.modules,readouts=self.readouts(calls),endpoint_readouts=endpoint):
                with patch.dict('os.environ',SLURM_JOB_ID='4530001'):
                    result=terminal.work(c,3000000,'gpu',self.guard)
            self.assertEqual(calls,expected)
            self.assertIs(endpoint.capacity,old)
            self.assertEqual(result['layer'],6)
            self.assertEqual(json.loads((self.output/'summary.json').read_text())['seconds'],12)

    def test_original_cpu_finalizer_is_called_and_legacy_callback_restored(self):
        self.summary('GPU_READOUT_COMPLETE_WAITING_CPU_STATISTICS')
        directory=self.output/'readout'
        directory.mkdir()
        (directory/'terminal_gpu_status.json').write_text(json.dumps(dict(run=self.c['run'],
            samples=3000000,ended_at=1,owned_descendants_exited=True,
            status='GPU_TERMINAL_COMPLETE_WAITING_CPU')))
        calls=[]
        old=lambda:self.fail('Legacy peer-budget callback must not run')
        statistics=SimpleNamespace(capacity=old)
        def finalize(actual):
            self.assertIs(actual,self.c)
            statistics.capacity()
            calls.append('original finalize')
            return {'status':'COMPLETE'}
        statistics.finalize=finalize
        with patch.dict(sys.modules,readouts=self.readouts([]),s_statistics=statistics):
            result=terminal.work(self.c,3000000,'cpu',self.guard)
        self.assertEqual(result['status'],'COMPLETE')
        self.assertEqual(calls,['original finalize'])
        self.assertIs(statistics.capacity,old)

    def test_complete_result_does_not_refit(self):
        self.summary('COMPLETE')
        calls=[]
        with patch.dict(sys.modules,readouts=self.readouts(calls)):
            result=terminal.work(self.c,3000000,'gpu',self.guard)
        self.assertTrue(result['already_closed'])
        self.assertEqual(calls,[])


def load_tests(loader,tests,pattern):
    tests.addTests(loader.loadTestsFromModule(snapshots))
    return tests


if __name__=='__main__':
    unittest.main()
