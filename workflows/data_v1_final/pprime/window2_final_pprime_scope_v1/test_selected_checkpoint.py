"""A closed selected phase survives a later failure and never replays source."""
import tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from .binding import BindingStore
from . import prepare as P

class SelectedCheckpoint(unittest.TestCase):
    def test_complete_phase_atomic_commit_frozen_resume_and_later_rollback(self):
        with tempfile.TemporaryDirectory() as temporary:
            filename=Path(temporary)/'physical_bindings.sqlite'
            frozen={'first2':'frozen_first2.json','common':'frozen_common.json'}
            row={'molecule_id':'M','sprime_conf_idx':7,'geometry_id':'actual:G','source_path':'opaque-source','source_row_index':0,'source_format':'parquet'}
            raw={'source_record_id':'native:exact','atomic_numbers':[6,1],'coordinates':[[1.0000000000000002,0.,0.],[2.,0.,0.]],'sprime_conf_idx':7,'status':'SUCCESS','converged':True}
            first=BindingStore(filename);first.freeze_inputs(frozen)
            with patch.object(P,'geometry',return_value=raw) as source:
                self.assertTrue(P.selected_bindings(first,{('M',7):row}));source.assert_called_once_with(row)
            # Simulate an exception after the selected phase: later uncommitted
            # metadata is rolled back, while the phase's atomic marker survives.
            first.candidate(dict(row,molecule_id='later',geometry_id='uncommitted:G'))
            first.db.close()
            second=BindingStore(filename)
            try:
                second.freeze_inputs(frozen)
                with patch.object(P,'geometry',side_effect=AssertionError('CLOSED_SOURCE_REPLAY_FORBIDDEN')):
                    self.assertFalse(P.selected_bindings(second,{('M',7):row}))
                self.assertEqual(second.raw(('M',7)),raw)
                self.assertIsNone(second.db.execute('SELECT 1 FROM candidates WHERE gid=?',('uncommitted:G',)).fetchone())
                with self.assertRaisesRegex(ValueError,'SAME_FROZEN_BINDING_INPUTS_REQUIRED'):
                    second.freeze_inputs(dict(frozen,first2='different_first2.json'))
            finally:second.close()
