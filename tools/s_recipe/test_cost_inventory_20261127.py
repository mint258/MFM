import unittest
import json
from pathlib import Path
import tempfile
from cost_inventory_20261127 import cpu_proof,gpu_proof,inventory


class CostInventory(unittest.TestCase):
    def test_closed_proofs_are_cached_without_reopening_original_files(self):
        # This shared target is covered by the real CPU stage's disk/quota guard.
        parent=Path('/share/home/zixiao/descriptor_analysis/runs/s_recipe_20261120')
        with tempfile.TemporaryDirectory(prefix='cost_inventory_unit_',dir=parent) as directory:
            root=Path(directory)
            (root/'execution.json').write_text(json.dumps(dict(runs={},statistics={})))
            gpu=root/'example_native_record.json'
            value=dict(node='compute-0-20',gpu_uuid='GPU-example',
                producer=dict(pid=1,uid=1278,start_ticks=10),started_at=1,ended_at=2,
                exit_code=75,owned_descendants_exited=True,observer_joined=True)
            gpu.write_text(json.dumps(value))
            spawn=root/'example_native_spawn.json'
            spawn.write_text(json.dumps(dict(value,ended_at=None)))
            legacy=root/'cost_accounting_snapshot_20261123.json'
            legacy.write_text(json.dumps(dict(native_closed_phases=[])))
            first=inventory(root)
            self.assertEqual(first['new_GPU_proofs'],1)
            self.assertEqual(first['open_execution_sources'],[])
            self.assertEqual(len(first['superseded_open_descriptors']),1)
            (root/'cost_inventory_20261127.json').write_text(json.dumps(first))
            gpu.write_text('Do not reread a closed proof')
            spawn.write_text('Do not reread a startup alias with an exact closed identity')
            legacy.write_text('Do not reread a consumed legacy snapshot')
            second=inventory(root)
            self.assertEqual(second['new_GPU_proofs'],0)
            self.assertEqual(second['closed_GPU_proofs'],first['closed_GPU_proofs'])

    def test_gpu_actual_pause_unknown_legacy_and_pending_not_completed(self):
        value=dict(node='compute-0-20',gpu_uuid='GPU-example',
            producer=dict(pid=1,uid=1278,start_ticks=10),started_at=10,ended_at=20,
            exit_code=75,status='CONTINUATION_REQUIRED',owned_descendants_exited=True,observer_joined=True)
        kind,row=gpu_proof(value,'actual_native')
        self.assertEqual(kind,'CLOSED');self.assertEqual(row['exit_code'],75)
        self.assertTrue(row['closure_verified'])
        kind,row=gpu_proof(dict(value,ended_at=None),'active')
        self.assertEqual(kind,'OPEN')
        self.assertEqual(gpu_proof(dict(job_id=2,state='CANCELLED',elapsed_seconds=0),'unused_standby')[0],'NOT_GPU_PROOF')
        legacy={k:v for k,v in value.items() if k not in ('producer','owned_descendants_exited','observer_joined','exit_code')}
        legacy.update(pid=1,uid=1278,start_ticks=10)
        kind,row=gpu_proof(legacy,'legacy')
        self.assertEqual(kind,'CLOSED');self.assertIsNone(row['exit_code'])
        self.assertFalse(row['closure_verified'])
        with self.assertRaises(ValueError):gpu_proof(value,'conflict',dict(gpu_uuid='GPU-other'))

    def test_native_cpu_failed_closed_and_open_sources(self):
        value=dict(execution='native_cpu',node='compute-0-11',handle='S_failed',stage='check',
            producer=dict(pid=3,uid=1278,start_ticks=30),started_at=1,ended_at=3,
            exit_code=1,cpu_user_seconds=0.4,cpu_system_seconds=0.1,
            owned_descendants_exited=True,observer_joined=True)
        kind,row=cpu_proof(value,'actual',dict(exit_code=1))
        self.assertEqual(kind,'CLOSED');self.assertEqual(row['exit_code'],1)
        self.assertEqual(row['command_exit_code'],1)
        self.assertEqual(cpu_proof(dict(value,observer_joined=False),'still_closing')[0],'OPEN')
        self.assertEqual(cpu_proof(dict(value,execution='not_native_cpu'),'not_a_producer')[0],'NOT_CPU_PROOF')


if __name__=='__main__':unittest.main()
