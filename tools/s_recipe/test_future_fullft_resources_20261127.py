"""New integration boundaries for future resources and unchanged old Guard."""
from copy import deepcopy
import unittest
from unittest.mock import patch
from storage_20261122 import CONTROL as C
from fullft_ram_envelope_20261127 import read,PROOF,GiB


class FutureResourceIntegration(unittest.TestCase):
    def test_only_proven_future_sixteen_and_legacy_sixtyfour_are_admitted(self):
        from finetune_extension_20261124 import validate
        source=next(row for row in read(C/'execution.json')['statistics'].values()
            if row.get('point')=='S_B0_3M' and row.get('resource_closed')
            and row.get('mode') in ('finetune','finetune_native'))
        old=read(source['configuration'])
        self.assertEqual(old['peak_ram_bytes'],64*GiB)
        self.assertIs(validate(old),old)
        future=deepcopy(old)
        future.update(peak_ram_bytes=16*GiB,host_ram_envelope_source=str(PROOF))
        self.assertIs(validate(future),future)
        bad=deepcopy(future);bad['host_ram_envelope_source']='/unproven'
        with self.assertRaises(ValueError):validate(bad)
        self.assertEqual(old['peak_ram_bytes'],64*GiB)

    def test_future_clock_copy_is_accepted_by_unchanged_native_training_guard(self):
        from extension_spawn_clock_20261127 import node_clock_task
        from native_training_20261123 import NativeGuard
        configuration=dict(run='S_subset_T5_s0_9M',node='compute-0-20')
        original=dict(configuration=configuration,contract=dict(schema='S_FINITE_NATIVE_V1',
            uid=1278,run=configuration['run'],node=configuration['node'],created_at=100.5,
            duration_seconds=48*3600))
        with patch('native_clock_anchor_20261127.time.time',return_value=100):
            bound=node_clock_task(original)
        guard=NativeGuard(bound['contract'],configuration,now=lambda:100.1)
        self.assertEqual(guard.end_epoch,100+48*3600)
        self.assertLessEqual(guard.end_epoch,original['contract']['created_at']+48*3600)
        self.assertEqual(original['contract']['created_at'],100.5)


if __name__=='__main__':unittest.main()
