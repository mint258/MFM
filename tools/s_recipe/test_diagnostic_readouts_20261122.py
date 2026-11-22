"""Guard wiring tests only; no model, bootstrap or existing-result re-evaluation."""
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import diagnostic_readouts_20261122 as diagnostic


class DiagnosticTests(unittest.TestCase):
    def setUp(self):
        scratch=tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.output=Path(scratch.name)
        self.c=dict(run='S_B0_s0_3M',samples=3000000,output=str(self.output))
        self.guard=SimpleNamespace(phase='preparing',stopping=lambda:False)

    def test_diagnostics_wait_for_formal_statistics_and_registered_scope(self):
        calls=[]
        representation=SimpleNamespace(registered=lambda c:calls.append('registered'))
        with patch.object(diagnostic.terminal,'registered') as formal, patch.dict(sys.modules,representations=representation):
            (self.output/'summary.json').write_text(json.dumps({'status':'GPU_READOUT_COMPLETE_WAITING_CPU_STATISTICS'}))
            with self.assertRaisesRegex(ValueError,'formal layer6'):
                diagnostic.registered(self.c,3000000)
            (self.output/'summary.json').write_text(json.dumps({'status':'COMPLETE'}))
            diagnostic.registered(self.c,3000000)
        self.assertEqual(formal.call_count,2)
        self.assertEqual(calls,['registered','registered'])

    def modules(self,calls):
        def forbidden():
            self.fail('Legacy capacity polling must be replaced after admission')
        statistics=SimpleNamespace(capacity=forbidden)
        def operation(label,module):
            def call(c):
                self.assertIs(c,self.c)
                module.capacity()
                if label in ('cpu','calculate'):
                    statistics.capacity()
                calls.append(label)
                return {'status':'original result'}
            return call
        geometry=SimpleNamespace(capacity=forbidden)
        geometry.extract=operation('extract',geometry)
        geometry.calculate=operation('calculate',geometry)
        curve=SimpleNamespace(capacity=forbidden)
        curve.gpu=operation('gpu',curve)
        curve.cpu=operation('cpu',curve)
        return dict(representations=geometry,endpoint_readouts=curve,
                    s_statistics=statistics,
                    readouts=SimpleNamespace(existing_evaluation=lambda:None)),forbidden

    def proof(self,prefix,status='GPU_DIAGNOSTIC_COMPLETE_WAITING_CPU',closed=True):
        path=self.output/'diagnostic_readouts'
        path.mkdir(exist_ok=True)
        (path/(prefix+'_gpu_status.json')).write_text(json.dumps(dict(run=self.c['run'],
            samples=3000000,ended_at=1,owned_descendants_exited=closed,status=status)))

    def test_each_stage_calls_only_its_original_numerical_entry(self):
        for stage,expected in (('curve_gpu','gpu'),('curve_cpu','cpu'),
                               ('geometry_gpu','extract'),('geometry_cpu','calculate')):
            calls=[]
            modules,old=self.modules(calls)
            self.proof(stage.split('_')[0])
            with patch.dict(sys.modules,modules):
                result=diagnostic.work(self.c,3000000,stage,self.guard)
            self.assertEqual(calls,[expected])
            self.assertIs(modules['representations'].capacity,old)
            self.assertIs(modules['endpoint_readouts'].capacity,old)
            self.assertIs(modules['s_statistics'].capacity,old)
            self.assertTrue(result['descriptive_only'])
            self.assertEqual(result['formal_decision_layer'],6)

    def test_cpu_cannot_consume_an_unclosed_gpu_phase(self):
        calls=[]
        modules,_=self.modules(calls)
        self.proof('curve',closed=False)
        with patch.dict(sys.modules,modules),self.assertRaises(ValueError):
            diagnostic.work(self.c,3000000,'curve_cpu',self.guard)
        self.assertEqual(calls,[])

    def test_boundary_restores_legacy_callback_after_stopping(self):
        old=lambda:None
        module=SimpleNamespace(capacity=old)
        self.guard.stopping=lambda:True
        with self.assertRaises(diagnostic.worker.life.StopAtBoundary):
            with diagnostic.boundaries(module,self.guard):
                module.capacity()
        self.assertIs(module.capacity,old)


if __name__=='__main__':
    unittest.main()
