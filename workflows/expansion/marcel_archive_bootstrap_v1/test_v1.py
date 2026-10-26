"""Three synthetic bounded archive checks, before any official opaque bytes."""
import io,struct,unittest,zipfile
from types import SimpleNamespace
from . import archive as A


class Boundaries(unittest.TestCase):
    def test_normal_archive_and_pickle_bytes_are_only_streamed(self):
        data=io.BytesIO();payload=b"cbuiltins\nexec\n(S'raise AssertionError(\"NO_PICKLE_EXECUTION\")'\ntR."
        with zipfile.ZipFile(data,'w',compression=zipfile.ZIP_DEFLATED) as z:z.writestr('Kraken.pickle',payload)
        pre=A.preflight(data,len(data.getvalue()))
        with zipfile.ZipFile(data) as z:
            infos,total=A.directory(z,pre,1<<20);out=A.member(z,infos[0],lambda:None,total)
        self.assertEqual(out['decoded_bytes'],len(payload));self.assertTrue(out['EOF_CRC_passed']);self.assertIn('NO_LOAD',out['format_hint'])
    def test_bad_CRC_unsafe_duplicate_and_directory_bound(self):
        data=io.BytesIO()
        with zipfile.ZipFile(data,'w') as z:z.writestr('x',b'opaque')
        raw=bytearray(data.getvalue());raw[raw.index(b'opaque')]^=1
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            with self.assertRaises(zipfile.BadZipFile):A.member(z,z.infolist()[0],lambda:None,100)
        with zipfile.ZipFile(io.BytesIO(data.getvalue())) as z:
            info=z.infolist()[0]
            with self.assertRaises(ValueError):A.directory(SimpleNamespace(infolist=lambda:[info,info]),{'entries_declared':2},100)
        data=io.BytesIO()
        with zipfile.ZipFile(data,'w') as z:z.writestr('../x',b'a')
        pre=A.preflight(data,len(data.getvalue()))
        with zipfile.ZipFile(data) as z:
            with self.assertRaises(ValueError):A.directory(z,pre,100)
        raw=bytearray(data.getvalue());off=raw.rfind(b'PK\x05\x06');struct.pack_into('<HH',raw,off+8,4097,4097)
        with self.assertRaises(ValueError):A.preflight(io.BytesIO(raw),len(raw))
    def test_ZIP64_bounded_empty_directory_and_truncation(self):
        raw=struct.pack('<4sQ2H2L4Q',b'PK\x06\x06',44,45,45,0,0,0,0,0,0)
        raw+=struct.pack('<4sLQL',b'PK\x06\x07',0,0,1)
        raw+=struct.pack('<4s4H2LH',b'PK\x05\x06',0,0,65535,65535,0xffffffff,0xffffffff,0)
        self.assertTrue(A.preflight(io.BytesIO(raw),len(raw))['ZIP64'])
        with self.assertRaises(ValueError):A.preflight(io.BytesIO(raw[:-1]),len(raw)-1)
