"""Five pure HTTP seams; fake responses only, no requests import or network."""
import io,tempfile,unittest,zipfile
from pathlib import Path
from . import http as H

class Raw:
    def __init__(self,body,fail=False):self.body=body;self.pos=0;self.fail=fail
    def read(self,n,decode_content=False):
        if self.fail and self.pos:raise OSError('synthetic secret URL must never be persisted')
        result=self.body[self.pos:self.pos+n];self.pos+=len(result);return result
class Response:
    def __init__(self,body,status=200,headers=None):self.raw=Raw(body);self.status_code=status;self.headers=headers or {};self.closed=False
    def close(self):self.closed=True
class Cookies:
    def clear(self):pass
class Session:
    def __init__(self,responses):self.responses=list(responses);self.calls=[];self.cookies=Cookies()
    def get(self,url,**kwargs):self.calls.append((url,kwargs));return self.responses.pop(0)
def spec(cap=1024,range_=False):return {'source_id':'marcel_drugs_zip_landing' if range_ else 'tdc_admet_group_zip',
    'url':'https://official.example/file','cap_bytes':cap,'range_first_MiB':range_}

class HTTPBoundaries(unittest.TestCase):
    def test_complete_zip_requires_eof_correct_length_magic_all_CRC(self):
        blob=io.BytesIO()
        with zipfile.ZipFile(blob,'w',compression=zipfile.ZIP_DEFLATED) as archive:archive.writestr('endpoint/train_val.csv',b'pure synthetic fixture bytes')
        payload=blob.getvalue();response=Response(payload,headers={'Content-Length':str(len(payload)),'Content-Type':'application/zip'})
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'response';result=H.fetch(spec(len(payload)+16),Session([response]),path,lambda:False)
            self.assertTrue(result['archive_complete']);self.assertEqual(result['archive_whole_sha256'],H.hashlib.sha256(payload).hexdigest())
            self.assertEqual(result['ZIP_inventory']['status'],'COMPLETE_ZIP_ALL_ENTRIES_EOF_CRC_PASS');self.assertFalse(result['ZIP_inventory']['CSV_or_identity_decoded'])
        self.assertTrue(response.closed)

    def test_declared_length_mismatch_and_false_magic_cannot_be_whole_archive(self):
        with tempfile.TemporaryDirectory() as d:
            response=Response(b'PK\x03\x04broken',headers={'Content-Length':'99'})
            result=H.fetch(spec(),Session([response]),Path(d)/'body',lambda:False)
            self.assertTrue(result['actual_eof_observed']);self.assertFalse(result['response_entity_complete']);self.assertIsNone(result['archive_whole_sha256'])
            self.assertIsNotNone(result['partial_entity_sha256']);self.assertTrue(result['zip_magic'])
            html=b'<html>ordinary200 is not ZIP</html>'
            result=H.fetch(spec(),Session([Response(html,headers={'Content-Length':str(len(html))})]),Path(d)/'HTML200',lambda:False)
            self.assertTrue(result['response_entity_complete']);self.assertFalse(result['zip_magic']);self.assertFalse(result['archive_complete'])
            result=H.fetch(spec(),Session([Response(b'PK\x03\x04broken')]),Path(d)/'badCRC',lambda:False)
            self.assertTrue(result['response_entity_complete']);self.assertFalse(result['archive_complete']);self.assertEqual(result['ZIP_inventory']['status'],'ZIP_NOT_ACCEPTED')

    def test_ignored_Range_and_exact_cap_close_without_one_extra_byte_or_full_claim(self):
        response=Response(b'x'*40,headers={'Content-Length':'40'});session=Session([response])
        with tempfile.TemporaryDirectory() as d:
            result=H.fetch(spec(16,True),session,Path(d)/'body',lambda:False)
            self.assertEqual(response.raw.pos,16);self.assertEqual(result['bytes_saved'],16);self.assertFalse(result['actual_eof_observed'])
            self.assertFalse(result['Range_honored']);self.assertFalse(result['archive_complete']);self.assertEqual(session.calls[0][1]['headers'],{'Range':'bytes=0-1048575'})
        self.assertTrue(response.closed)

    def test_full_403_HTML_and_midstream_failure_preserve_distinct_complete_partial_hashes(self):
        with tempfile.TemporaryDirectory() as d:
            payload=b'<html>403 forbidden</html>';response=Response(payload,403,{'Content-Length':str(len(payload)),'Set-Cookie':'never logged','Authorization':'never logged'})
            result=H.fetch(spec(),Session([response]),Path(d)/'403',lambda:False)
            self.assertTrue(result['response_entity_complete']);self.assertEqual(result['status_code'],403);self.assertFalse(result['archive_complete'])
            self.assertNotIn('Set-Cookie',repr(result));self.assertNotIn('Authorization',repr(result));self.assertEqual((Path(d)/'403').read_bytes(),payload)
            broken=Response(b'x'*(70<<10));broken.raw.fail=True
            observed=H.fetch(spec(128<<10),Session([broken]),Path(d)/'partial',lambda:False)
            self.assertEqual(observed['read_error_type'],'OSError');self.assertFalse(observed['actual_eof_observed']);self.assertIsNotNone(observed['partial_entity_sha256'])

    def test_normal_https_redirect_host_only_206_total_and_no_follow_after_stop(self):
        redirect=Response(b'not downloaded',302,{'Location':'https://download.example/file?private=must_not_log'})
        final=Response(b'prefix',206,{'Content-Length':'6','Content-Range':'bytes 0-5/9999'});session=Session([redirect,final])
        with tempfile.TemporaryDirectory() as d:
            result=H.fetch(spec(32,True),session,Path(d)/'body',lambda:False)
            self.assertEqual(result['content_range']['total'],9999);self.assertTrue(result['Range_honored']);self.assertFalse(result['archive_complete'])
            self.assertEqual(result['redirect_hops'][0]['to_host'],'download.example');self.assertNotIn('private=',repr(result));self.assertEqual(redirect.raw.pos,0)
            stopped=Session([]);result=H.fetch(spec(),stopped,Path(d)/'notstarted',lambda:True);self.assertEqual(stopped.calls,[])
            self.assertEqual(result['status'],'NOT_STARTED_OR_STOPPED_BEFORE_NEXT_HTTP_HOP')
        self.assertTrue(redirect.closed and final.closed)

if __name__=='__main__':unittest.main()
