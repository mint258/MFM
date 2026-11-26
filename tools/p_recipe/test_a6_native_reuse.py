"""Regressions for byte-preserving closed TRAIN reuse, without redoing native math."""
import hashlib
from pathlib import Path
import struct
import tempfile
import unittest
from types import SimpleNamespace
from a6_native_reuse import read_bound_frame,materialization_one


class NativeReuseTests(unittest.TestCase):
    def fixture(self,root):
        # Keep two distinct stored FP64/FP32 representations literally intact.
        raw=struct.pack("<4I",1,1,1,1)+struct.pack("<H",5)+struct.pack("<3d",1.000000000000004,2.,3.)+struct.pack("<3f",1.,2.,3.)+struct.pack("<f",7.)+bytes([1,1])
        path=Path(root)/"records.bin";path.write_bytes(b"P1DS1\0\0\0"+raw)
        row=dict(offset=8,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),native_n_atoms=1,target_rows=1,tasks=["qm9.homo"],geometry_ready=True)
        return path,row,raw

    def test_closed_FP64_and_FP32_bytes_preserved(self):
        with tempfile.TemporaryDirectory() as root:
            path,row,raw=self.fixture(root)
            self.assertEqual(read_bound_frame(path,row),raw)
            self.assertNotEqual(struct.unpack_from("<d",raw,18)[0],struct.unpack_from("<f",raw,42)[0])

    def test_changed_closed_frame_refused(self):
        with tempfile.TemporaryDirectory() as root:
            path,row,raw=self.fixture(root);path.write_bytes(b"P1DS1\0\0\0"+raw[:-1]+bytes([0]))
            with self.assertRaisesRegex(ValueError,"binding"):
                read_bound_frame(path,row)

    def test_only_new_source_reaches_original_decoder(self):
        calls=[]
        reuse=SimpleNamespace(get=lambda dataset,row:{"reused_frame":b"closed"} if row["member_index"]==1 else None)
        def decode(dataset,index,role):
            calls.append((dataset,index,role));return {"new":True}
        a=materialization_one(("qm9",{"member_index":1,"selected_role":"train"}),reuse,decode)
        b=materialization_one(("qm9",{"member_index":2,"selected_role":"train"}),reuse,decode)
        self.assertEqual(a[2]["reused_frame"],b"closed")
        self.assertTrue(b[2]["new"])
        self.assertEqual(calls,[("qm9",2,"train")])


if __name__=="__main__":
    unittest.main()
