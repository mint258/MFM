"""New native CPU phase accounting; no model or original result is loaded."""
import unittest
from extension_output_budget_20261124 import phase_live


class NativePhaseBudget(unittest.TestCase):
    def test_native_without_slurm_identity_stays_live_until_owned_closure(self):
        row=dict(job_id=None,lifecycle_record='native.json')
        self.assertTrue(phase_live(row,{},lambda _:dict(status='RUNNING')))
        closed=dict(ended_at=1,owned_descendants_exited=True,observer_joined=True,exit_code=0)
        self.assertFalse(phase_live(row,{},lambda _:closed))
        self.assertTrue(phase_live(row,{},lambda _:dict(closed,observer_joined=False)))

    def test_missing_native_observation_keeps_its_future(self):
        def missing(_):raise FileNotFoundError('not yet published')
        self.assertTrue(phase_live(dict(job_id=None,native_record='native.json'),{},missing))
        self.assertTrue(phase_live(dict(job_id=None),{},missing))
