"""New identity dispatch only; no real experiment or old test replay."""
import os
import unittest
from unittest.mock import patch
from cpu_execution_20261126 import execution_fields


class ExecutionIdentity(unittest.TestCase):
    def test_real_slurm_identity_is_preserved(self):
        with patch.dict(os.environ, {'SLURM_JOB_ID':'123'}, clear=True):
            self.assertEqual(execution_fields(),dict(job_id=123))

    def test_native_context_never_becomes_a_slurm_id(self):
        with patch.dict(os.environ,{},clear=True), patch('cpu_execution_20261126.native_record',
                return_value=dict(handle='synthetic_native')):
            with patch.dict(os.environ,{'S_NATIVE_CPU_RECORD':'synthetic/record.json'}):
                self.assertEqual(execution_fields(),dict(job_id=None,
                    native_handle='synthetic_native',native_record='synthetic/record.json'))
