"""Recorded-trace boundary: names/messages alone never identify the scaffold site."""
import json
import unittest
from .core import classify


class Source(unittest.TestCase):
    def test_recorded_site_requires_official_frame_and_call_text(self):
        real='Traceback (most recent call last):\n  File "/env/rdkit/Chem/Scaffolds/MurckoScaffold.py", line 44, in MakeScaffoldGeneric\n    res = Chem.RemoveHs(res)\nAtomValenceException: Explicit valence for atom # 4 C, 5'
        misleading='Traceback (most recent call last):\n  File "/work/RemoveHs_helper.py", line 4, in MakeScaffoldGeneric\n    x = unavailable()\nAtomValenceException: RemoveHs C, 5'
        for trace, expected in [(real,True),(misleading,False)]:
            row={'error_evidence_json':json.dumps({'COMPATIBLE_DISPATCHER_EXCEPTION':dict(type='AtomValenceException',message='C, 5',traceback=trace)})}
            value=classify(row)
            self.assertEqual(value['generic_RemoveHs_AtomValence_trace_candidate'],expected)
            self.assertIsNone(value['errors'][0]['recoverable_by_representation_repair'])
            self.assertFalse(value['P5_to_C5_cause_inferred'])
        self.assertTrue(classify({'error_evidence_json':'{}'})['no_recorded_exception'])
