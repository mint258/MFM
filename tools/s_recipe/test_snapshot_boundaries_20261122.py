"""Only new interruption boundaries; no model, labels or old readout rerun."""
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import lifecycle_20261122 as life
import snapshot_readouts_20261122 as snapshot


class BoundaryTests(unittest.TestCase):
    def setup_evaluation(self, stopping):
        calls=[]
        class History:
            def log(self, row, *, step, commit):
                calls.append(('logged',row,step,commit))
        e=SimpleNamespace(History=History,
            produce_missing_features=lambda *a,**k: calls.append(('feature',a,k)) or 'original payload',
            ridge_probe=lambda *a,**k: calls.append(('ridge',a,k)) or 'original prediction')
        guard=SimpleNamespace(stopping=lambda: stopping, phase='preparing')
        return snapshot.bind_evaluation(e,guard),guard,calls

    def test_unchanged_arguments_payload_and_committed_metric(self):
        e,guard,calls=self.setup_evaluation(False)
        self.assertEqual(e.produce_missing_features(1, dataset='d'),'original payload')
        self.assertEqual(e.ridge_probe(2, seed=0),'original prediction')
        e.History().log({'loss':3},step=4,commit=True)
        self.assertEqual(calls,[('feature',(1,),{'dataset':'d'}),
            ('ridge',(2,),{'seed':0}),('logged',{'loss':3},4,True)])

    def test_stop_does_not_start_new_feature_or_ridge_unit(self):
        e,guard,calls=self.setup_evaluation(True)
        for function in (e.produce_missing_features,e.ridge_probe):
            with self.assertRaises(life.StopAtBoundary):
                function('not started')
        self.assertEqual(calls,[])

    def test_stop_follows_committed_readout_update_log(self):
        e,guard,calls=self.setup_evaluation(True)
        with self.assertRaises(life.StopAtBoundary):
            e.History().log({'loss':3},step=4,commit=True)
        self.assertEqual(calls,[('logged',{'loss':3},4,True)])

    def test_only_registered_b0_intermediate_cosine_snapshots(self):
        c=dict(arm='S-B0',seed=0,samples=3000000,evaluation_samples=[1000000,2000000,3000000])
        snapshot.registered(c,1000000)
        for changed,samples in ((dict(arm='S-N1'),1000000),({},3000000),({},1500000)):
            with self.assertRaises(ValueError):
                snapshot.registered(dict(c,**changed),samples)

    def test_small_group_retains_the_actual_empty_context_requirement(self):
        with patch.object(snapshot,'require_empty_context') as check:
            for node in ('compute-0-0','compute-0-6','compute-0-7'):
                snapshot.check_gpu_context(node,'actual-uuid')
        self.assertEqual(check.call_count,3)
        check.assert_called_with('actual-uuid')

    def test_native_group_uses_existing_memory_and_uuid_mutex_without_extra_small_group_gate(self):
        with patch.object(snapshot,'require_empty_context') as check:
            for node in ('compute-0-20','compute-0-22'):
                snapshot.check_gpu_context(node,'actual-uuid')
        check.assert_not_called()


if __name__ == '__main__':
    unittest.main()
