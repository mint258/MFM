"""One official sider path profile, then ten new GETs and eleven-source inventory.

Only Root can materialize/review this draft's actual Alpha plan and queue stage.
No normalization, target decoding, archive extraction or pool acceptance.
"""
import argparse,concurrent.futures as cf,gzip,hashlib,io,json,os,stat,tarfile,threading,time,unittest
from pathlib import Path
from urllib import error,parse,request
from . import contracts as c
from .runtime import Budget

class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None

class StrictTarInfo(tarfile.TarInfo):
    """Preserve zero-block traversal; damaged headers may never be skipped."""
    @classmethod
    def frombuf(cls,buf,encoding,errors):
        try:return super().frombuf(buf,encoding,errors)
        except (tarfile.InvalidHeaderError,tarfile.TruncatedHeaderError) as exc:
            raise tarfile.ReadError('INVALID_TAR_HEADER_STOP_UNKNOWN') from exc

def safe_headers(headers):
    out={k:headers.get(k) for k in ('Content-Length','ETag','Last-Modified','Content-Type','Content-Encoding')}
    c.need(sum(len(x or '') for x in out.values())<=8192,'BOUNDED_WHITELIST_HEADERS_REQUIRED')
    if headers.get('Location'):
        value=headers['Location'];u=parse.urlsplit(value)
        out['Location_redacted']=parse.urlunsplit((u.scheme,u.hostname or '',u.path,'REDACTED' if u.query else '','REDACTED' if u.fragment else ''))
        out['Location_original_SHA256']=hashlib.sha256(value.encode()).hexdigest()
    return out

def source_hash(path,check):
    c.need(c.ROOT/'artifacts' in path.parents and not any(p.is_symlink() for p in (path,*path.parents)),'OWNED_NONSYMLINK_PAYLOAD_ONLY')
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        before=os.fstat(stream.fileno());c.need(stat.S_ISREG(before.st_mode) and before.st_uid==c.UID,'CURRENT_OWNED_REGULAR_PAYLOAD')
        for block in iter(lambda:stream.read(1024**2),b''):check();digest.update(block)
        after=os.fstat(stream.fileno())
    c.need(c.frame(before)==c.frame(after)==c.frame(path.stat()),'PAYLOAD_FRAME_CHANGED_DURING_FULL_SHA')
    return {'path':str(path),'bytes':before.st_size,'sha256':digest.hexdigest()},c.frame(after)

class Expanded:
    def __init__(self,stream,check,maximum):self.stream=stream;self.check=check;self.maximum=maximum;self.n=0;self.sha=hashlib.sha256();self.prefix=b''
    def read(self,size=-1):
        self.check();c.need(type(size) is int and 0<=size<=1024**2,'FINITE_CONTAINER_READ_REQUIRED')
        data=self.stream.read(size);self.n+=len(data);self.sha.update(data)
        if len(self.prefix)<128:self.prefix=(self.prefix+data)[:128]
        c.need(self.n<=self.maximum,'EXPANDED_CONTAINER_BYTE_CEILING_UNKNOWN_STOP')
        return data

def inspect_container(path,kind,inventory_path,check,maximum):
    """Read-only, complete gzip stream/CRC; tar bodies hashed, never extracted."""
    start=time.monotonic();cpu=time.thread_time();members=0;member_bytes=0
    record_sha=hashlib.sha256();inventory_bytes=0
    with inventory_path.open('xb') as output:
        def record(value):
            nonlocal members,inventory_bytes
            raw=(json.dumps(value,ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n').encode()
            c.need(len(raw)<=4096,'TAR_METADATA_RECORD_EXCEEDS_BOUND_NO_TRUNCATION')
            check();output.write(raw);record_sha.update(raw);inventory_bytes+=len(raw);members+=1
        if kind=='TAR_GZIP':
            with path.open('rb') as payload,gzip.GzipFile(fileobj=payload,mode='rb') as gz:
                expanded=Expanded(gz,check,maximum)
                with tarfile.open(fileobj=expanded,mode='r|',ignore_zeros=True,tarinfo=StrictTarInfo,bufsize=10240) as archive:
                    for member in archive:
                        check();digest=None;observed=0
                        if member.isfile():
                            h=hashlib.sha256();body=archive.extractfile(member)
                            c.need(body is not None,'REGULAR_TAR_MEMBER_BODY_REQUIRED')
                            with body:
                                while True:
                                    check();block=body.read(1024**2)
                                    if not block:break
                                    observed+=len(block);h.update(block)
                            c.need(observed==member.size,'COMPLETE_TAR_MEMBER_BYTES_REQUIRED');digest=h.hexdigest();member_bytes+=observed
                        record({'ordinal':members,'name':member.name,'type_hex':member.type.hex(),'declared_bytes':member.size,
                          'regular_member_bytes_read':observed,'regular_member_sha256':digest,'linkname':member.linkname if member.issym() or member.islnk() else None,
                          'extracted':False,'identity_or_target_rows_decoded':False})
                while expanded.read(1024**2):pass
                expanded_n=expanded.n;expanded_sha=expanded.sha.hexdigest()
            info={'container':'TAR_GZIP','gzip_EOF_CRC_verified':True,'decoded_stream_bytes':expanded_n,'decoded_stream_sha256':expanded_sha,
              'tar_members':members,'regular_member_total_bytes':member_bytes,'member_values_extracted':False}
        elif kind=='GZIP_CSV_BYTES':
            with path.open('rb') as payload,gzip.GzipFile(fileobj=payload,mode='rb') as gz:
                expanded=Expanded(gz,check,maximum)
                while expanded.read(1024**2):pass
                info={'container':kind,'gzip_EOF_CRC_verified':True,'decoded_stream_bytes':expanded.n,'decoded_stream_sha256':expanded.sha.hexdigest(),
                  'CSV_records_counted':False,'CSV_values_decoded':False}
            record({'container':kind,'stream_EOF_CRC_verified':True,'decoded_bytes':info['decoded_stream_bytes']})
        elif kind=='MAT':
            with path.open('rb') as payload:prefix=payload.read(128)
            recognized='MATLAB5_HEADER' if prefix.startswith(b'MATLAB 5.0 MAT-file') else 'MATLAB73_HEADER' if prefix.startswith(b'MATLAB 7.3 MAT-file') else 'HDF5_SIGNATURE' if prefix.startswith(b'\x89HDF\r\n\x1a\n') else 'UNKNOWN_MAGIC'
            info={'container':'MAT','header_kind':recognized,'header_prefix_bytes':len(prefix),'header_prefix_sha256':hashlib.sha256(prefix).hexdigest(),
              'first_16_bytes_hex':prefix[:16].hex(),'variables_or_arrays_read':False,'identity_extractability_proven':False}
            record(info);c.need(recognized!='UNKNOWN_MAGIC','UNKNOWN_MAT_HEADER_PARTIAL_METADATA_PRESERVED')
        else:
            c.need(kind=='CSV_BYTES','EXACT_CATALOG_CONTAINER_REQUIRED')
            info={'container':kind,'CSV_records_counted':False,'CSV_values_decoded':False};record(info)
        output.flush();os.fsync(output.fileno())
    return dict(info,inventory_reference={'path':str(inventory_path),'bytes':inventory_bytes,'sha256':record_sha.hexdigest()},
      inventory_records=members,wall_seconds=time.monotonic()-start,current_thread_CPU_seconds=time.thread_time()-cpu)

def acquire(row,root,budget):
    id=row['source_id'];folder=root/id;folder.mkdir();payload=folder/'payload.bin';started=time.monotonic();cpu=time.thread_time()
    result={'source_id':id,'url':row['url'],'status':'STOPPED_UNKNOWN_PARTIALS_PRESERVED','thread_ident':threading.get_ident(),
      'native_thread_id':threading.get_native_id(),'GET_attempts':0,'retries':0,'network_configuration_changed':False,'normal_proxy_environment_inherited':True}
    try:
        result['phase']='CONDITIONAL_GET';budget.check();url=parse.urlsplit(row['url']);c.need(url.scheme=='https' and not url.username and not url.password and not url.query,'PUBLIC_EXACT_CATALOG_URL_REQUIRED')
        opener=request.build_opener(NoRedirect()) # Inherits ordinary env proxy configuration, including existing credentials.
        req=request.Request(row['url'],method='GET',headers={'If-Match':row['expected_etag'],'If-Unmodified-Since':row['expected_last_modified']})
        result['GET_attempts']=1
        try:response=opener.open(req,timeout=30)
        except error.HTTPError as exc:
            result['HTTP_status']=exc.code;result['response_headers']=safe_headers(exc.headers);raise
        with response:
            headers=safe_headers(response.headers);result.update(HTTP_status=response.status,response_headers=headers)
            c.need(response.status==200 and response.geturl()==row['url'],'NO_REDIRECT_PARTIAL_OR_ALTERNATE_PAYLOAD')
            c.need(headers['Content-Length']==str(row['expected_compressed_bytes']) and headers['ETag']==row['expected_etag'] and
              headers['Last-Modified']==row['expected_last_modified'] and headers['Content-Encoding'] in (None,'identity'),'FROZEN_HEAD_AND_CONDITIONAL_GET_VERSION_REQUIRED')
            c.write_new(folder/'response.json',{'status':response.status,'headers':headers,'official_URL':row['url']})
            received=0;h=hashlib.sha256()
            with payload.open('xb') as stream:
                while True:
                    budget.check();block=response.read(1024**2)
                    if not block:break
                    received+=len(block);c.need(received<=row['expected_compressed_bytes'],'HTTP_BODY_EXCEEDS_FROZEN_LENGTH')
                    stream.write(block);h.update(block)
                stream.flush();os.fsync(stream.fileno())
            c.need(received==row['expected_compressed_bytes'],'COMPLETE_HTTP_BODY_LENGTH_AND_EOF_REQUIRED')
            result['download_network_stream_sha256']=h.hexdigest();result['download_wall_seconds']=time.monotonic()-started
        result['phase']='CURRENT_DISK_FULL_SHA';pin,before=source_hash(payload,budget.check)
        c.need(pin['sha256']==result['download_network_stream_sha256'],'DISK_FULL_SHA_DIFFERS_FROM_RECEIVED_BYTES')
        result.update(payload_reference=pin,payload_frame=before,full_file_disk_SHA_verified=True,HTTP_body_EOF_verified=True)
        result['phase']='READONLY_CONTAINER_INVENTORY'
        container=inspect_container(payload,row['container'],folder/'container_inventory.jsonl',budget.check,256*1024**3)
        c.need(c.frame(payload.stat())==before,'PAYLOAD_CHANGED_DURING_CONTAINER_INSPECTION')
        result.update(status='COMPLETE_CONTAINER_OBSERVED',phase='COMPLETE',payload_reference=pin,payload_frame=before,container=container,
          full_file_disk_SHA_verified=True,HTTP_body_EOF_verified=True,identity_coverage_accepted=False)
    except Exception as exc:
        result['error_type']=type(exc).__name__ # Do not serialize proxy/userinfo-bearing exception text or response cookies.
        budget.set_stop('SOURCE_FAILED_STOP_NEW_WORK:'+id)
        if payload.exists():result['partial_file_bytes']=payload.stat().st_size
    result.update(wall_seconds=time.monotonic()-started,current_thread_CPU_seconds=time.thread_time()-cpu)
    c.write_new(folder/'receipt.json',result);return result

class BoundaryFixtures(unittest.TestCase):
    def test_crc_requires_real_eof(self):
        good=gzip.compress(b'identity-only acquisition fixture\n');self.assertEqual(gzip.decompress(good),b'identity-only acquisition fixture\n')
        with self.assertRaises((EOFError,OSError)):gzip.decompress(good[:-3])
        with self.assertRaises(tarfile.ReadError):
            with tarfile.open(fileobj=io.BytesIO(b'x'*512+b'\0'*1024),mode='r|',ignore_zeros=True,tarinfo=StrictTarInfo) as archive:
                list(archive)
        valid=tarfile.TarInfo('empty').tobuf(format=tarfile.USTAR_FORMAT)
        with self.assertRaises(tarfile.ReadError):
            with tarfile.open(fileobj=io.BytesIO(valid+b'x'*17),mode='r|',ignore_zeros=True,tarinfo=StrictTarInfo) as archive:
                list(archive)
    def test_exact_source_modes_do_not_redownload_sider(self):
        self.assertEqual(c.parameters('profile')['download_source_ids'],['sider'])
        self.assertEqual(len(c.parameters('full')['download_source_ids']),10)
        self.assertNotIn('sider',c.parameters('full')['download_source_ids']);self.assertEqual(sum(c.SIZES),2501171487)
    def test_header_whitelist_omits_credentials(self):
        headers={'ETag':'"x"','Authorization':'secret','Set-Cookie':'secret','Proxy-Authorization':'secret'}
        self.assertNotIn('secret',json.dumps(safe_headers(headers)))

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--plan',type=Path,required=True);parser.add_argument('--startup-proof',type=Path,required=True)
    args=parser.parse_args();plan,proof,rows,prior=c.startup(args.plan,args.startup_proof,__file__)
    out=c.literal(plan['output_directory']);c.need(c.ROOT/'artifacts' in out.parents and not out.exists(),'NEW_OWNED_OUTPUT_ONLY');out.mkdir(parents=True)
    began=time.monotonic();cpu=time.process_time();budget=Budget(plan,proof,out);sources=[]
    try:
        suite=unittest.defaultTestLoader.loadTestsFromTestCase(BoundaryFixtures);c.need(suite.countTestCases()==3,'EXACT_THREE_NEW_FIXTURES')
        tested=unittest.TextTestRunner(verbosity=2).run(suite)
        fixtures={'tests_run':tested.testsRun,'failures':len(tested.failures),'errors':len(tested.errors),'skips':len(tested.skipped),'before_network_IO':True}
        c.write_new(out/'fixtures.json',fixtures);c.need(tested.wasSuccessful() and tested.testsRun==3 and not tested.skipped,'FIXTURES_BEFORE_ANY_GET')
        budget.thread.start();budget.check()
        if prior:
            existing=prior['sources'][0];path=c.literal(existing['payload_reference']['path']);pin,frame=source_hash(path,budget.check)
            c.need(pin==existing['payload_reference'] and all(frame[k]==existing['payload_frame'][k] for k in ('inode','size','mtime_ns','uid')),
              'ACTUAL_PROFILE_SIDER_BYTES_PORTABLE_FRAME_REUSE_REQUIRED')
            sources.append(dict(existing,GET_attempts_this_parent=0,reused_actual_profile_reference=plan['accepted_profile_receipt_reference']))
            c.write_new(out/'reused_sider.json',sources[0])
        ids=c.parameters(plan['mode'])['download_source_ids']
        with cf.ThreadPoolExecutor(max_workers=16,thread_name_prefix='official-get') as pool:
            futures={pool.submit(acquire,rows[id],out,budget):id for id in ids}
            for future in cf.as_completed(futures):sources.append(future.result()) # Every URL wrote its own receipt before aggregation.
        complete=len(sources)==(1 if plan['mode']=='profile' else 11) and len({x['source_id'] for x in sources})==len(sources) and all(x['status']=='COMPLETE_CONTAINER_OBSERVED' for x in sources)
        budget.close();c.need(budget.owned()+2*1024**2<=plan['output_cap_bytes'],'ACTUAL_WHOLE_OUTPUT_CEILING')
        receipt={'schema':'SECONDARY_EXTERNAL_SOURCE_ACQUISITION_RECEIPT_V1','status':
          ('OFFICIAL_SINGLE_SOURCE_CONTAINER_PROFILE_COMPLETE' if plan['mode']=='profile' else 'OFFICIAL_ELEVEN_SOURCE_CONTAINER_ACQUISITION_COMPLETE') if complete else 'INCOMPLETE_ACQUISITION_UNKNOWN_PARTIALS_PRESERVED',
          'mode':plan['mode'],'job_id':str(proof['job_id']),'node':plan['node'],'uid':c.UID,'endpoint':c.q.ENDPOINT,
          'plan':c.pin(args.plan),'startup_proof':c.pin(args.startup_proof),'locator_catalog_sha256':plan['locator_catalog_reference']['sha256'],
          'kernel_source_references':[c.pin(Path(__file__).parent/x) for x in ('__init__.py','contracts.py','runtime.py','run.py')],
          'sources':sorted(sources,key=lambda x:x['source_id']),'fixtures':fixtures,'runtime':budget.receipt(),
          'wall_seconds':time.monotonic()-began,'parent_process_CPU_seconds':time.process_time()-cpu,
          'allocated_cpus':16,'maximum_download_threads':16,'actual_nonempty_download_threads':sorted({x['native_thread_id'] for x in sources if x.get('GET_attempts_this_parent',x['GET_attempts'])>0}),
          'normal_proxy_configuration_inherited':True,'network_configuration_changed':False,'automatic_retries':0,'sider_redownloaded_in_full':False,
          'profile_is_network_container_path_test_not_large_file_or_chemistry_forecast':True,'no_source_payload_deleted':True,
          'all_split_identity_coverage_accepted':False,'chemical_normalization':False,'pool_UFF_QM_training_release':False,
          'cost_overrun_action':'REPORT_AND_CONTINUE','actual_terminal_parent_accounting_required':True,'signals_sent':False}
        c.write_new(out/'receipt.json',receipt)
        return 0 if complete else 1
    except BaseException as exc:
        c.write_new(out/'failure.json',{'status':'ACQUISITION_UNKNOWN_PARTIALS_PRESERVED','error_type':type(exc).__name__,'no_signals':True,'old_inputs_modified':False})
        raise
    finally:
        if budget.thread.ident is not None and budget.thread.is_alive():budget.close()

if __name__=='__main__':raise SystemExit(main())
