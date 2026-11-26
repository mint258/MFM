"""New safe-continuation identity cases only; no model state is read."""
import unittest
from fullft_resume_20261126 import require_resume


class FullFTResume(unittest.TestCase):
    def fixture(self):
        configuration={key:key for key in ('run','output','task','seed','pretraining_seed',
            'internal_split_seed','bootstrap_seed','source_binding','store','providers_sha256',
            'authority','invoking_authority','kind','mode')}
        previous=dict(resource_closed=True,status='PAUSED_SAFE_CONTINUATION',run='run')
        closure=dict(status='CONTINUATION_REQUIRED',exit_code=75,ended_at=1,
            owned_descendants_exited=True,observer_joined=True)
        return previous,closure,configuration

    def test_resume_keeps_the_original_scientific_identity(self):
        previous,closure,c=self.fixture()
        require_resume(previous,closure,dict(c,node='old'),dict(c,node='new'))
        with self.assertRaises(ValueError):require_resume(previous,closure,c,dict(c,seed='another'))
        with self.assertRaises(ValueError):require_resume(previous,closure,c,dict(c,source_binding='another'))

    def test_complete_or_unclosed_execution_cannot_be_replayed_as_resume(self):
        previous,closure,c=self.fixture()
        with self.assertRaises(ValueError):require_resume(dict(previous,resource_closed=False),closure,c,c)
        with self.assertRaises(ValueError):require_resume(previous,dict(closure,status='COMPLETE',exit_code=0),c,c)
