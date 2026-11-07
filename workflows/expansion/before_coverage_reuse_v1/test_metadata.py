"""Real closed-journal and exact stored-result boundaries; stdlib/no NN calls."""
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import tempfile
import unittest
from . import catalog as C


class Source(unittest.TestCase):
    def test_only_closed_unique_parts_and_original_fp_fraction_bits_are_adopted(self):
        with tempfile.TemporaryDirectory()as folder:
            base=Path(folder);root=base/'original';scores=root/'scores'/'0';scores.mkdir(parents=True)
            part=scores/'part.parquet';part.write_bytes(b'closed fixture bytes, not scientific Parquet')
            ref=dict(path=str(part),bytes=part.stat().st_size,sha256=hashlib.sha256(part.read_bytes()).hexdigest(),rows=2,fp_bucket='0')
            raw=C.canonical(ref)+b'\n'
            journal=root/'closed_files_1.jsonl';journal.write_bytes(raw+raw+b'{"incomplete":')
            (root/'closed_files_2.jsonl').write_bytes(raw)
            out=base/'catalog.jsonl';result=C.collect(root,os.getuid(),out)
            self.assertEqual((result['parts'],result['rows'],result['incomplete_journal_tails']),(1,2,1))
            observed=[json.loads(line)for line in out.read_bytes().splitlines()]
            self.assertEqual(observed[0]['reference'],ref)
            self.assertEqual(tuple(observed[0]['current_frame']),C.actual_frame(part,os.getuid()))
            journal.write_bytes(raw+C.canonical(dict(ref,sha256='0'*64))+b'\n')
            with self.assertRaisesRegex(ValueError,'Conflicting duplicate'):C.collect(root,os.getuid(),base/'conflict.jsonl')
            outside=base/'outside.parquet';outside.write_bytes(b'outside')
            journal.write_bytes(C.canonical(dict(ref,path=str(outside)))+b'\n')
            with self.assertRaisesRegex(ValueError,'outside original root'):C.collect(root,os.getuid(),base/'outside.jsonl')
        row=dict(ecfp4_2048_hex='00'*256,nearest_v1_key='A'*14+'-'+'B'*10+'-N',nearest_v1_tanimoto=2/6,
            reference_ordinal=3,score_numerator=2,score_denominator=6,evaluated_references=9,
            strictly_bound_pruned_references=C.N-9,reference_molecules=C.N)
        before=copy.deepcopy(row);result=C.result_value(row)
        self.assertEqual(row,before);self.assertEqual((result['score_numerator'],result['score_denominator']),(2,6))
        # A fingerprint result has no query CID/full-key: both identities can
        # reuse it, while every final sample identity/order remains separately bound.
        self.assertNotIn('cid',result);self.assertNotIn('searched_popcount_groups',result)
        with self.assertRaisesRegex(ValueError,'binary64'):C.result_value(dict(row,nearest_v1_tanimoto=math.nextafter(2/6,1.)))
        with self.assertRaisesRegex(ValueError,'nine|production score'):C.result_value(dict(row,searched_popcount_groups=[1]))
        with self.assertRaisesRegex(ValueError,'accounting'):C.result_value(dict(row,reference_molecules=C.N-1))


if __name__=='__main__':unittest.main()
