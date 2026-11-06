"""New reference membership logic only; no nearest-neighbor computation."""
import json
from pathlib import Path
import tempfile
import unittest

from .nn_after import pack


class MemberPackingTest(unittest.TestCase):
    def test_whole_original_prefix_then_positive_3d_members_in_source_order(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); inputs=root/'inputs'; out=root/'out'
            inputs.mkdir(); out.mkdir()
            base=b'A'*256+b'B'*256
            base_keys=b'A'*27+b'\n'+b'B'*27+b'\n'
            (inputs/'before_fingerprints.bin').write_bytes(base)
            (inputs/'before_keys.ascii').write_bytes(base_keys)
            rows=[dict(molecule_id=str(i),full_key=str(i)*27,ecfp4_2048_hex=(bytes([i])*256).hex())
                  for i in range(1,5)]
            (inputs/'addition_projection.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
            members=root/'members.jsonl'
            members.write_text(json.dumps(dict(molecule_id='4'))+'\n'+json.dumps(dict(molecule_id='2'))+'\n')
            result=pack(inputs,out,base_count=2,added_count=2,members_path=str(members))
            self.assertEqual(Path(result['fingerprints']).read_bytes(),base+bytes([2])*256+bytes([4])*256)
            self.assertEqual(Path(result['keys']).read_bytes(),base_keys+b'2'*27+b'\n'+b'4'*27+b'\n')
            self.assertEqual(result['original_prefix'],2)
            self.assertEqual(result['molecules'],4)
            self.assertEqual(pack(inputs,out,2,2,str(members)),result)

    def test_missing_member_fails_before_any_nn_call(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); inputs=root/'inputs'; out=root/'out'
            inputs.mkdir(); out.mkdir()
            (inputs/'before_fingerprints.bin').write_bytes(b'A'*256)
            (inputs/'before_keys.ascii').write_bytes(b'A'*27+b'\n')
            (inputs/'addition_projection.jsonl').write_text('')
            members=root/'members.jsonl'; members.write_text(json.dumps(dict(molecule_id='missing'))+'\n')
            with self.assertRaisesRegex(ValueError,'3D_MEMBER_MISSING'):
                pack(inputs,out,1,1,str(members))


if __name__ == '__main__':
    unittest.main()
