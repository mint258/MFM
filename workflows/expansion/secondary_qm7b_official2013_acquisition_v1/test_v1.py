"""Three new pure methods; no real network, archive DATA, chemistry or old tests."""
import io,unittest,zipfile
from . import contracts as C,archive as A


class Boundaries(unittest.TestCase):
    def test_exact_author_URL_and_HTTP_HEAD_mismatch_remains_HOLD(self):
        self.assertEqual(C.exact_url('https://www.mrupp.info/Data/2013dsgdb7njp.zip'),C.URL)
        for url in ('http://www.mrupp.info/Data/2013dsgdb7njp.zip','https://qmml.org/Datasets/gdb7-13.zip',C.URL+'?download=1','https://example.com/x.zip'):
            with self.assertRaises(ValueError):C.exact_url(url)
        self.assertIsNone(A.NoRedirect().redirect_request(None,None,302,'',{},'https://example.com/alternate'))
        headers={'Content-Length':'3','Content-Type':'application/zip','Content-Encoding':None};body={'actual_body_EOF':True,'observed_body_bytes':3,'bounded_prefix_only':False}
        self.assertTrue(A.response_acceptable(200,headers,body,3))
        for status,h,b in ((403,headers,body),(429,headers,body),(302,headers,body),(200,{**headers,'Content-Length':'4'},body),
            (200,{**headers,'Content-Length':None},body),(200,{**headers,'Content-Type':None},body),(200,headers,{**body,'observed_body_bytes':2})):
            self.assertFalse(A.response_acceptable(status,h,b,3))
        self.assertEqual(len(C.PRIMARY_PIN[1]),64);self.assertEqual(len(C.HEAD_PIN[1]),64)
        self.assertFalse(C.PARAMETERS['coordinates_SMILES_bonds_or_MAT_row_mapping_parsed_or_inferred']);self.assertEqual(C.PARAMETERS['new_graph_parse_key_UFF_QM_calls'],0)

    def test_bounded_response_prefix_full_EOF_and_no_overread(self):
        class Stream(io.BytesIO):
            def __init__(self,raw):super().__init__(raw);self.requests=[]
            def read(self,n=-1):self.requests.append(n);return super().read(n)
        f=Stream(b'abc');out=io.BytesIO();v=A.copy_response(f,out,lambda n=0:None,7,3)
        self.assertEqual(out.getvalue(),b'abc');self.assertTrue(v['actual_body_EOF']);self.assertFalse(v['bounded_prefix_only'])
        f=Stream(b'abcdef');out=io.BytesIO();v=A.copy_response(f,out,lambda n=0:None,2,3)
        self.assertEqual(out.getvalue(),b'ab');self.assertEqual(f.tell(),2);self.assertFalse(v['actual_body_EOF']);self.assertTrue(v['bounded_prefix_only']);self.assertFalse(v['body_length_matches_original_HEAD'])
        f=Stream(b'ab');out=io.BytesIO();v=A.copy_response(f,out,lambda n=0:None,7,3)
        self.assertTrue(v['actual_body_EOF']);self.assertFalse(v['body_length_matches_original_HEAD'])
        self.assertFalse(A.response_acceptable(200,{'Content-Length':'3','Content-Type':'application/zip'},v,3))

    def test_all_original_member_bytes_CRC_and_declared_mass_bounds(self):
        original=io.BytesIO()
        with zipfile.ZipFile(original,'w',compression=zipfile.ZIP_STORED) as z:z.writestr('README.txt',b'alpha');z.writestr('empty/',b'')
        payload=original.getvalue();raw=io.BytesIO();rows=[]
        result=A.inventory(io.BytesIO(payload),raw,rows.append,lambda n=0:None,10,2)
        self.assertEqual(result['physical_members'],2);self.assertEqual(result['total_uncompressed_bytes'],5);self.assertEqual(raw.getvalue(),b'alpha')
        self.assertEqual(rows[0]['original_uncompressed_blob_segment']['offset'],0);self.assertTrue(rows[0]['whole_member_EOF_CRC_verified'])
        self.assertFalse(rows[0]['coordinates_identity_SMILES_graph_or_rowmap_parsed']);self.assertEqual(result['original_graph_SMILES_MAT_row_mapping'],'UNKNOWN')
        for maximum,members in ((4,2),(10,1)):
            output=io.BytesIO()
            with self.assertRaises(ValueError):A.inventory(io.BytesIO(payload),output,lambda x:None,lambda n=0:None,maximum,members)
            self.assertEqual(output.tell(),0)
        corrupted=payload.replace(b'alpha',b'Alpha',1)
        with self.assertRaises(zipfile.BadZipFile):A.inventory(io.BytesIO(corrupted),io.BytesIO(),lambda x:None,lambda n=0:None,10,2)
