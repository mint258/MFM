"""Figure transport keeps exact Git bytes and refuses accidental binary DATA export."""
import base64,hashlib,json,pathlib,tempfile,unittest
from .publish_payload import blob_entry

PNG=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=')
def oid(raw):return hashlib.sha1(('blob '+str(len(raw))+'\0').encode()+raw).hexdigest()

class FigurePublication(unittest.TestCase):
    def test_utf8_sources_keep_original_inline_transport(self):
        raw='原始统计与图表\n'.encode()
        with tempfile.TemporaryDirectory()as folder:
            blobs=[];entry=blob_entry('docs/expansion/report.md','100644',oid(raw),raw,folder,blobs)
            self.assertEqual(entry['content'].encode(),raw);self.assertEqual(blobs,[])
            self.assertEqual(list(pathlib.Path(folder).iterdir()),[])

    def check_binary(self,name,raw):
        with tempfile.TemporaryDirectory()as folder:
            blobs=[];entry=blob_entry(name,'100755',oid(raw),raw,folder,blobs,True)
            self.assertEqual(entry,dict(path=name,mode='100755',type='blob',sha=oid(raw)))
            self.assertEqual(len(blobs),1);transport=pathlib.Path(blobs[0]['path']).read_bytes()
            self.assertEqual(blobs[0]['bytes'],len(transport))
            self.assertEqual(blobs[0]['sha256'],hashlib.sha256(transport).hexdigest())
            value=json.loads(transport);decoded=base64.b64decode(value['content'],validate=True)
            self.assertEqual(decoded,raw);self.assertEqual(value['git_blob_sha'],oid(decoded))
            self.assertEqual(value['original_sha256'],hashlib.sha256(decoded).hexdigest())
            self.assertEqual(value['original_bytes'],len(decoded));self.assertEqual(value['encoding'],'base64')

    def test_png_binary_exact_transport(self):self.check_binary('docs/expansion/batch1_figures/a.png',PNG)
    def test_pdf_binary_exact_transport(self):self.check_binary('docs/expansion/batch1_figures/a.pdf',b'%PDF-1.4\n%\xff\x00\x81\n%%EOF\n')

    def test_flag_scope_and_actual_file_signature_required(self):
        with tempfile.TemporaryDirectory()as folder:
            for name,raw,enabled in(
                ('docs/expansion/a.png',PNG,False),
                ('workflows/expansion/a.png',PNG,True),
                ('docs/data_v1/a.png',PNG,True),
                ('docs/expansion/a.png',b'%PDF-1.4',True),
                ('docs/expansion/a.pdf',PNG,True),
            ):
                with self.subTest(name=name,enabled=enabled),self.assertRaises(RuntimeError):
                    blob_entry(name,'100644',oid(raw),raw,folder,[],enabled)
            self.assertEqual(list(pathlib.Path(folder).iterdir()),[])

    def test_changed_git_bytes_oversize_and_nonregular_modes_rejected(self):
        with tempfile.TemporaryDirectory()as folder:
            large=PNG+b'x'*(2<<20)
            for mode,digest,raw in(('100644','0'*40,PNG),('120000',oid(PNG),PNG),('100644',oid(large),large)):
                with self.subTest(mode=mode,size=len(raw)),self.assertRaises(RuntimeError):
                    blob_entry('docs/expansion/a.png',mode,digest,raw,folder,[],True)
            self.assertEqual(list(pathlib.Path(folder).iterdir()),[])

    def test_figure_flag_does_not_allow_binary_scientific_formats(self):
        with tempfile.TemporaryDirectory()as folder:
            for suffix in('parquet','npy','zip','sqlite','bin'):
                with self.subTest(suffix=suffix),self.assertRaises(RuntimeError):
                    blob_entry('docs/expansion/data.'+suffix,'100644',oid(PNG),PNG,folder,[],True)
            self.assertEqual(list(pathlib.Path(folder).iterdir()),[])

if __name__=='__main__':unittest.main()
