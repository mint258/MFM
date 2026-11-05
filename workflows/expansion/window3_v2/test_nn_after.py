import json
import multiprocessing
import os
from pathlib import Path
import tempfile
import unittest
from concurrent.futures import ProcessPoolExecutor
from . import nn_after as N


class Tests(unittest.TestCase):
    def test_reference_keeps_original_prefix_and_addition_order(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); source=root/'inputs'; source.mkdir(); out=root/'out'; out.mkdir()
            raw1=b'\1'+bytes(255); raw2=b'\2'+bytes(255)
            (source/'before_fingerprints.bin').write_bytes(raw1)
            (source/'before_keys.ascii').write_bytes(b'A'*27+b'\n')
            (source/'addition_projection.jsonl').write_text(json.dumps({'full_key':'B'*27,'ecfp4_2048_hex':raw2.hex()})+'\n')
            value=N.pack(source,out,base_count=1,added_count=1)
            self.assertEqual(Path(value['fingerprints']).read_bytes(),raw1+raw2)
            self.assertEqual(Path(value['keys']).read_bytes(),b'A'*27+b'\n'+b'B'*27+b'\n')

    def test_query_uses_frozen_before_identity_and_deduplicates_only_fps(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); raw=b'\1'+bytes(255)
            queries=[{'cid':i+1,'full_key':str(i),'ecfp4_2048_hex':raw.hex()} for i in range(2)]
            before=[{'sample_ordinal':i,'cid':i+1,'full_key':str(i),'nearest_reference_tanimoto':.5} for i in range(2)]
            (root/'sample_query.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in queries))
            (root/'before_coverage.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in before))
            rows,unique=N.queries(root,expected=2)
            self.assertEqual(len(rows),2);self.assertEqual(unique,[raw]);self.assertEqual([r[2] for r in rows],[0,0])
            before[1]['cid']=999
            (root/'before_coverage.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in before))
            with self.assertRaisesRegex(ValueError,'ID_ALIGNMENT'):N.queries(root,expected=2)

    def test_existing_native_kernel_after_fork_empty_tie_and_ratios(self):
        binary=os.environ['PUBCHEM_EXISTING_NN_BINARY']
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'refs.bin'; p.write_bytes(bytes(256)+b'\1'+bytes(255)+b'\3'+bytes(255)+b'\1'+bytes(255))
            N.load_native(binary,p,4)
            task=(0,[(0,bytes(256)),(1,b'\1'+bytes(255)),(2,b'\2'+bytes(255))])
            with ProcessPoolExecutor(max_workers=2,mp_context=multiprocessing.get_context('fork')) as pool:
                _,values=pool.submit(N.batch,task).result()
            expected=[(0.,0),(1.,1),(.5,2)]
            for (_,n,d,ordinal),(score,winner) in zip(values,expected):
                self.assertLessEqual(abs(n/d-score),1e-12+1e-12*abs(score));self.assertEqual(ordinal,winner)


if __name__=='__main__':unittest.main()
