"""Only new native identity/deadline and handoff-binding logic; no model run."""
import json
import os
from pathlib import Path
import tempfile
import unittest

import lifecycle_20261122 as life
from native_training_20261123 import NativeGuard, verify_closure, resume_from_closure


class NativeTests(unittest.TestCase):
    def setUp(self):
        self.c = dict(run='S_R2_s0_3M', node='compute-0-22', gpu_uuid='GPU-test', samples=3000000)
        self.contract = dict(schema='S_FINITE_NATIVE_V1', uid=os.getuid(), run=self.c['run'],
                             node=self.c['node'], created_at=1000, duration_seconds=172800)

    def test_native_deadline_without_slurm_identity(self):
        guard = NativeGuard(self.contract, self.c, now=lambda: 1001)
        self.assertEqual(guard.end_epoch, 173800)
        self.assertIsNone(guard.handoff(self.c)['job_id'])
        with self.assertRaises(ValueError):
            NativeGuard(self.contract, self.c, now=lambda: 1061)
        with self.assertRaises(ValueError):
            NativeGuard(self.contract, dict(self.c, node='compute-0-21'), now=lambda: 1001)

    def test_closure_alone_cannot_prove_pid_exit(self):
        identity = life.Identity(123, os.getuid(), 456, 12, 'R')
        task = dict(configuration=self.c, producer=vars(identity))
        value = dict(run=self.c['run'], node=self.c['node'], gpu_uuid='GPU-test',
            producer=vars(identity), owned_descendants_exited=True, ended_at=1002)
        self.assertFalse(verify_closure(task, value, identity))
        self.assertTrue(verify_closure(task, value, None))
        self.assertTrue(verify_closure(task, dict(value,
            producer=dict(vars(identity), ppid=1, state='S')), None))
        with self.assertRaises(ValueError):
            verify_closure(task, dict(value, producer=dict(vars(identity), start_ticks=999)), None)

    def test_published_full_state_binding_and_finished_noop(self):
        task = dict(configuration=self.c)
        value = dict(result=dict(status='TRAINING_COMPLETE_READOUT_PENDING', samples=3000000))
        self.assertIsNone(resume_from_closure(task, value))
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            checkpoint = output/'samples_32.pt'
            checkpoint.write_bytes(b'producer fixture')
            ack = dict(request_id='request', run=self.c['run'], job_id=123,
                       checkpoint=str(checkpoint), clock=dict(samples_consumed=32))
            path = output/'ack.json'
            path.write_text(json.dumps(ack))
            task['configuration'] = dict(self.c, output=str(output), handoff_ack=str(path))
            value = dict(result=dict(ack, status='HANDOFF_SAVED'))
            self.assertEqual(resume_from_closure(task, value)['resume'], str(checkpoint))
            path.write_text(json.dumps(dict(ack, request_id='wrong')))
            with self.assertRaises(ValueError):
                resume_from_closure(task, value)


if __name__ == '__main__':
    unittest.main()
