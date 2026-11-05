"""Tests for the new taskbook's N-consecutive-no-new termination rule."""
import unittest
from .fill import select_stream


class FillTests(unittest.TestCase):
    def test_success_resets_consecutive_count_and_exhaustion_keeps_shortfall(self):
        existing=[{'x':0.0}]
        candidates=[{'x':0.1},{'x':0.2},{'x':1.0},{'x':0.9},{'x':1.1},{'x':1.2},{'x':2.0}]
        selected,stale,consumed=select_stream(existing,candidates,3,lambda a,b:abs(a['x']-b['x']))
        self.assertEqual([row['x'] for row in selected],[0.0,1.0])
        self.assertEqual(stale,3)
        self.assertEqual(consumed,6)

    def test_exact_half_angstrom_is_accepted_and_existing_is_preserved(self):
        existing=[{'x':0.0,'source_id':9}]
        selected,stale,consumed=select_stream(existing,[{'x':0.5},{'x':2.0}],2,lambda a,b:abs(a['x']-b['x']))
        self.assertIs(selected[0],existing[0])
        self.assertEqual(selected[1]['x'],0.5)
        self.assertEqual(consumed,1)
        self.assertEqual(stale,0)

    def test_failed_candidates_count_without_becoming_fake_geometry(self):
        selected,stale,consumed=select_stream([], [None,{'valid':False},None,{'x':1.0}],3,lambda a,b:0.0)
        self.assertEqual(selected,[])
        self.assertEqual((stale,consumed),(3,3))


if __name__=='__main__':unittest.main()