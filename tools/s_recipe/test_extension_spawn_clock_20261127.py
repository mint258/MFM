"""Only future task-copy/clock invariants; no actual native process or GPU."""
import unittest
from copy import deepcopy
from unittest.mock import patch
from extension_spawn_clock_20261127 import node_clock_task


def task(created):
    return dict(configuration=dict(run='S_subset_T5_s0_9M',node='compute-0-20',samples=9000000,
        seed=0,gpu_uuid='GPU-existing',workers=14),standby_job_id=123,
        contract=dict(schema='S_FINITE_NATIVE_V1',uid=1278,run='S_subset_T5_s0_9M',
            node='compute-0-20',created_at=created,duration_seconds=48*3600))


class ExtensionSpawnClock(unittest.TestCase):
    def test_node_copy_preserves_original_and_science_without_extending_deadline(self):
        original=task(100.5);before=deepcopy(original)
        with patch('native_clock_anchor_20261127.time.time',return_value=100):
            result=node_clock_task(original)
        self.assertEqual(original,before)
        self.assertEqual(result['configuration'],before['configuration'])
        self.assertEqual(result['standby_job_id'],123)
        self.assertEqual(result['contract']['created_at'],100)
        self.assertEqual(result['contract']['duration_seconds'],48*3600)
        self.assertLessEqual(result['node_clock_binding_20261127']['effective_deadline'],
            result['node_clock_binding_20261127']['original_contract_deadline'])

    def test_out_of_bounds_original_clock_or_misbound_identity_is_rejected(self):
        with patch('native_clock_anchor_20261127.time.time',return_value=100):
            for created in (105.001,39.999):
                with self.assertRaises(ValueError):node_clock_task(task(created))
            value=task(100);value['contract']['run']='another_run'
            with self.assertRaises(ValueError):node_clock_task(value)


if __name__=='__main__':unittest.main()
