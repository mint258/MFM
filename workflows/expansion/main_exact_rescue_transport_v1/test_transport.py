"""Real newline, whole-SHA, source-domain and mutation tests; no scientific data."""
import json,os,tempfile,unittest
from pathlib import Path
from .transport import Transport,ALPHA,MAIN
from ..exact_nn_inverted_cpp_v1.artifacts import reference
class ExternalCatalog(unittest.TestCase):
    def test_complete_large_catalog_and_mutation(self):
        with tempfile.TemporaryDirectory()as temp:
            root=Path(temp);replica=root/'replica';replica.write_bytes(b'exact bytes')
            ref=reference(replica);rows=[dict(origin=dict(ref,path='/origin/'+str(i)),replica=ref)for i in range(12000)]
            catalog=root/'files.jsonl';catalog.write_bytes(b''.join(json.dumps(row).encode()+b'\n'for row in rows))
            self.assertGreater(catalog.stat().st_size,2<<20)
            desc=root/'transport.json'
            desc.write_text(json.dumps(dict(schema='EXACT_RESCUE_TRANSPORT_V1',source_endpoint=MAIN,source_uid=1278,
                destination_endpoint=ALPHA,destination_uid=os.getuid(),files_catalog_reference=reference(catalog),file_count=12000)))
            t=Transport(reference(desc),MAIN,ALPHA,os.getuid())
            self.assertEqual(t.resolve(rows[0]['origin']),ref);self.assertEqual(t.resolve(rows[-1]['origin']),ref);t.finish()
            with catalog.open('ab')as f:f.write(b'\n')
            with self.assertRaises(ValueError):t.finish()
    def test_newline_count_duplicates_and_hash(self):
        with tempfile.TemporaryDirectory()as temp:
            root=Path(temp);replica=root/'replica';replica.write_bytes(b'x');ref=reference(replica)
            row=dict(origin=dict(ref,path='/origin'),replica=ref);catalog=root/'files.jsonl';desc=root/'transport.json'
            def check(raw,count):
                catalog.write_bytes(raw)
                desc.write_text(json.dumps(dict(schema='EXACT_RESCUE_TRANSPORT_V1',source_endpoint=MAIN,source_uid=1278,
                    destination_endpoint=ALPHA,destination_uid=os.getuid(),files_catalog_reference=reference(catalog),file_count=count)))
                return Transport(reference(desc),MAIN,ALPHA,os.getuid())
            encoded=json.dumps(row).encode()
            with self.assertRaises(ValueError):check(encoded,1)
            with self.assertRaises(ValueError):check(encoded+b'\n',2)
            with self.assertRaises(ValueError):check((encoded+b'\n')*2,2)
            broken=dict(origin=dict(row['origin'],sha256='0'*64),replica=ref)
            with self.assertRaises(ValueError):check(json.dumps(broken).encode()+b'\n',1)
            t=check(encoded+b'\n',1);t.resolve(row['origin']);replica.write_bytes(b'y')
            with self.assertRaises(ValueError):t.finish()
    def test_inline_compatibility_and_exclusive_representation(self):
        with tempfile.TemporaryDirectory()as temp:
            root=Path(temp);file=root/'replica';file.write_bytes(b'x');ref=reference(file);desc=root/'transport.json'
            value=dict(schema='EXACT_RESCUE_TRANSPORT_V1',source_endpoint=MAIN,source_uid=1278,destination_endpoint=ALPHA,
                destination_uid=os.getuid(),files=[dict(origin=dict(ref,path='/origin'),replica=ref)])
            desc.write_text(json.dumps(value));t=Transport(reference(desc),MAIN,ALPHA,os.getuid());t.resolve(value['files'][0]['origin']);t.finish()
            value['files_catalog_reference']=ref;desc.write_text(json.dumps(value))
            with self.assertRaises(ValueError):Transport(reference(desc),MAIN,ALPHA,os.getuid())
if __name__=='__main__':unittest.main()
