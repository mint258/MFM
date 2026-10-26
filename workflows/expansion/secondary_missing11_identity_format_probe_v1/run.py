"""Existing missing11 containers: format/identity-input metadata, never keys."""
from __future__ import annotations
import argparse,collections,concurrent.futures as cf,contextlib,gzip,hashlib,importlib,io,json,os,stat,tarfile,threading,time,unittest
from pathlib import Path
from . import contracts as c
from .formats import CSVProjection,UnknownFormat,inventory_summary,sdf_metadata,mol2_metadata,mat_metadata,CSV_IDS,TAR_IDS,NATIVE_CAP
from secondary_external_sources_acquisition_v1.runtime import Budget
from secondary_external_sources_acquisition_v1.run import StrictTarInfo,Expanded

class Counted:
    def __init__(self,stream,check):self.stream=stream;self.check=check;self.bytes=0;self.reads=0;self.seeks=0
    def read(self,size=-1):
        self.check()
        if type(size) is not int or not 0<=size<=1<<20:raise UnknownFormat('FINITE_ONE_MIB_IO_CALL_ONLY')
        raw=self.stream.read(size);self.bytes+=len(raw);self.reads+=1;return raw
    def readinto(self,target):
        raw=self.read(len(target));target[:len(raw)]=raw;return len(raw)
    def seek(self,*args):self.check();self.seeks+=1;return self.stream.seek(*args)
    def __getattr__(self,name):return getattr(self.stream,name)

def current_payload(row):
    path=c.q.literal(row['payload_reference']['path']);s=path.lstat()
    c.need(stat.S_ISREG(s.st_mode) and s.st_uid==c.UID and c.frame(s)==row['payload_frame'] and s.st_size==row['payload_reference']['bytes'],
      'ACTUAL_PRODUCER_FULL_SHA_INPUT_FRAME_UNCHANGED')
    return path,c.frame(s),s.st_ctime_ns

def fixtures(root,budget):
    name='secondary_missing11_identity_format_probe_v1.test_profile';module=importlib.import_module(name)
    source=c.pin(Path(module.__file__));stream=io.StringIO();loader=unittest.TestLoader();suite=loader.loadTestsFromModule(module)
    c.need(not loader.errors and suite.countTestCases()==8,'EXACT_EIGHT_NEW_INPUT_FIXTURES')
    with contextlib.redirect_stdout(stream),contextlib.redirect_stderr(stream):result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    counts={'run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'skips':len(result.skipped),
      'expected_failures':len(result.expectedFailures),'unexpected_successes':len(result.unexpectedSuccesses)}
    passed=result.wasSuccessful() and counts['run']==8 and not any(v for k,v in counts.items() if k!='run') and c.pin(Path(module.__file__))==source
    value={'schema':'MISSING11_FORMAT_PROFILE_FIXTURE_GATE_V1','status':'PASS' if passed else 'FAIL_NO_DATA_BODY_READ',
      'counts':counts,'source_reference':source,'before_any_data_body':True,'transcript':stream.getvalue()}
    c.write_new(root/'fixtures.json',value);print(stream.getvalue(),end='',flush=True)
    c.need(passed,'EIGHT_INPUT_FIXTURES_REQUIRED_BEFORE_DATA');budget.check();return c.pin(root/'fixtures.json')

def csv_profile(source_id,row,path,budget):
    parser=CSVProjection(source_id);counter=None;expanded=None;complete=False;error=None
    try:
        with path.open('rb') as physical:
            counter=Counted(physical,budget.check)
            with contextlib.ExitStack() as stack:
                stream=stack.enter_context(gzip.GzipFile(fileobj=counter,mode='rb')) if row['container']['container']=='GZIP_CSV_BYTES' else counter
                expanded=Expanded(stream,budget.check,256<<30);prefix=expanded.read(3)
                if prefix!=b'\xef\xbb\xbf':parser.feed(prefix)
                while True:
                    data=expanded.read(64<<10)
                    if not data:break
                    parser.feed(data)
                summary=parser.finish();complete=True
    except (UnknownFormat,UnicodeError) as exc:error=type(exc).__name__+': '+str(exc);summary=parser.summary()
    state='CSV_INPUT_METADATA_OBSERVED' if complete and summary['smiles_schema_state']=='EXACT_LOADER_COLUMN_OBSERVED' else 'UNKNOWN_CSV_IDENTITY_INPUT'
    return {'status':state,'CSV':summary,'error':error,'compressed_bytes_read':counter.bytes if counter else 0,
      'decoded_bytes_read':expanded.n if expanded else 0,'current_CSV_EOF_verified':complete,
      'current_gzip_EOF_CRC_verified':complete and row['container']['container']=='GZIP_CSV_BYTES',
      'current_decoded_stream_sha256':expanded.sha.hexdigest() if complete else None}

def read_inventory(source_id,row,budget):
    pin=row['container']['inventory_reference'];path=c.q.literal(pin['path']);before=path.lstat()
    c.need(stat.S_ISREG(before.st_mode) and before.st_uid==c.UID and before.st_size==pin['bytes'],'CURRENT_OWNED_INVENTORY_FRAME')
    digest=hashlib.sha256();observed=0
    def rows(stream):
        nonlocal observed
        while True:
            budget.check();raw=stream.readline(4097)
            if not raw:break
            c.need(len(raw)<=4096 and raw.endswith(b'\n'),'EXACT_COMPLETE_BOUNDED_INVENTORY_RECORD')
            digest.update(raw);observed+=len(raw);yield json.loads(raw,object_pairs_hook=c.q.pairs_unique)
    with path.open('rb') as stream:
        opened=os.fstat(stream.fileno());c.need(c.frame(opened)==c.frame(before),'OPENED_SAME_INVENTORY_FRAME')
        result=inventory_summary(source_id,rows(stream));after=os.fstat(stream.fileno())
    c.need(c.frame(before)==c.frame(after)==c.frame(path.lstat()) and before.st_ctime_ns==after.st_ctime_ns==path.lstat().st_ctime_ns,'INVENTORY_CHANGED_DURING_PROFILE')
    c.need(observed==pin['bytes'] and digest.hexdigest()==pin['sha256'],'CURRENT_FULL_INVENTORY_SHA_REQUIRED')
    c.need(result['members']==row['container']['inventory_records']==row['container']['tar_members']
      and result['regular_member_bytes']==row['container']['regular_member_total_bytes'],'ALL_ARCHIVE_INVENTORY_MASS_REQUIRED')
    return dict(result,inventory_reference=pin,current_full_inventory_SHA_verified=True,current_inventory_frame=c.frame(after))

def first_record(stream,kind,budget):
    data=bytearray();molecule=False
    while True:
        budget.check();line=stream.readline(NATIVE_CAP-len(data)+1)
        if not line:
            if kind=='MOL2' and molecule:return bytes(data),True
            raise UnknownFormat('NO_COMPLETE_FIRST_NATIVE_RECORD_WITHIN_MEMBER')
        if kind=='MOL2' and line.strip()==b'@<TRIPOS>MOLECULE':
            if molecule:return bytes(data),False
            molecule=True
        data.extend(line)
        if len(data)>NATIVE_CAP:raise UnknownFormat('FIRST_NATIVE_RECORD_EXCEEDS_ONE_MIB_UNKNOWN')
        if kind=='SDF' and line.strip()==b'$$$$':return bytes(data),False

def archive_profile(source_id,row,path,budget):
    inventory=read_inventory(source_id,row,budget);chosen=inventory['first_candidate_members_in_physical_order'];native={};counter=None;expanded=None
    targets={member['ordinal']:(kind,member) for kind,member in chosen.items()}
    if targets:
        with path.open('rb') as physical:
            counter=Counted(physical,budget.check)
            with gzip.GzipFile(fileobj=counter,mode='rb') as gz:
                expanded=Expanded(gz,budget.check,256<<30)
                with tarfile.open(fileobj=expanded,mode='r|',ignore_zeros=True,tarinfo=StrictTarInfo,bufsize=10240) as archive:
                    for ordinal,member in enumerate(archive):
                        budget.check()
                        if ordinal not in targets:continue
                        kind,expected=targets[ordinal]
                        c.need(member.isfile() and member.name==expected['name'] and member.size==expected['declared_bytes'] and member.type.hex()==expected['type_hex'],
                          'ACTUAL_SELECTED_MEMBER_MATCHES_PINNED_PHYSICAL_INVENTORY')
                        body=archive.extractfile(member);c.need(body is not None,'SELECTED_REGULAR_NATIVE_MEMBER_REQUIRED')
                        try:
                            with body:raw,eof=first_record(body,kind,budget)
                            metadata=sdf_metadata(raw) if kind=='SDF' else mol2_metadata(raw,True)
                            native[kind]={'status':'FIRST_COMPLETE_NATIVE_RECORD_METADATA_OBSERVED','selected_member':expected,'format_metadata':metadata,
                              'current_member_EOF_reached':eof,'current_full_member_SHA_reverified':False,'producer_full_member_SHA_reused':expected['regular_member_sha256']}
                        except UnknownFormat as exc:
                            native[kind]={'status':'UNKNOWN_FIRST_NATIVE_RECORD','selected_member':expected,'error':str(exc),'current_full_member_SHA_reverified':False}
                        if ordinal==max(targets):break
        c.need(set(native)==set(chosen),'ALL_BOUNDED_SELECTED_FORMATS_ACCOUNTED')
    for kind in ('SDF','MOL2'):
        if kind not in native:native[kind]={'status':'NO_MATCHING_NATIVE_MEMBER_IN_COMPLETE_INVENTORY','identity_implication':'UNKNOWN_NO_EMPTY_IDENTITY_ACCEPTANCE'}
    return {'status':'ARCHIVE_FORMAT_METADATA_OBSERVED_IDENTITY_MAPPING_PENDING','inventory':inventory,'bounded_native_formats':native,
      'compressed_bytes_read_to_selected_members':counter.bytes if counter else 0,'decoded_tar_stream_bytes_read':expanded.n if expanded else 0,
      'current_complete_gzip_EOF_CRC_reverified':False,'native_charge_stereo_or_graph_normalization_performed':False}

def qm7b_profile(path,budget):
    try:
        import scipy
        from scipy.io import whosmat
        with path.open('rb') as physical:
            stream=Counted(physical,budget.check);header=stream.read(128);stream.seek(0)
            variables=whosmat(stream,appendmat=False);result=mat_metadata(variables)
        marker=header[126:128];endian='little' if marker==b'IM' else 'big' if marker==b'MI' else None
        return {'status':'QM7B_VARIABLE_METADATA_OBSERVED_IDENTITY_UNRESOLVED','scipy_version':scipy.__version__,'MAT':result,
          'MAT_header_prefix_sha256':hashlib.sha256(header).hexdigest(),'MAT_endian_marker':marker.hex(),'MAT_endianness':endian,
          'MAT_version_integer':int.from_bytes(header[124:126],endian) if endian else None,
          'actual_file_bytes_read':stream.bytes,'actual_seek_calls':stream.seeks,'MAT_values_or_coordinates_loaded':False}
    except (ImportError,ValueError,NotImplementedError) as exc:
        return {'status':'UNKNOWN_QM7B_VARIABLE_METADATA','error':type(exc).__name__+': '+str(exc),
          'direct_source_graph_identity':'UNKNOWN_NOT_INVENTED','MAT_values_or_coordinates_loaded':False,'QM7_adapter_called':False}

def source_profile(source_id,row,root,budget):
    budget.check();path,before,ctime=current_payload(row);started=time.monotonic()
    try:
        if source_id in CSV_IDS:result=csv_profile(source_id,row,path,budget)
        elif source_id in TAR_IDS:result=archive_profile(source_id,row,path,budget)
        else:c.need(source_id=='qm7b_mat','EXACT_ELEVEN_FORMAT_DISPATCH');result=qm7b_profile(path,budget)
        after=path.lstat();c.need(c.frame(after)==before and after.st_ctime_ns==ctime,'SOURCE_FRAME_CHANGED_DURING_FORMAT_PROFILE')
        result.update(source_id=source_id,payload_reference=row['payload_reference'],producer_full_SHA_verified=True,
          current_full_payload_SHA_reverified=False,current_payload_before_frame=before,current_payload_after_frame=c.frame(after),
          current_payload_ctime_ns=ctime,wall_seconds=time.monotonic()-started,native_thread_id=threading.get_native_id(),
          identity_coverage_accepted=False,chemical_normalization=False,pool_UFF_QM_training_release=False)
        output=root/(source_id+'.json');c.write_new(output,result)
        return {'source_id':source_id,'status':result['status'],'report_reference':c.pin(output),'native_thread_id':threading.get_native_id()}
    except BaseException as exc:
        c.write_new(root/(source_id+'_failure.json'),{'source_id':source_id,'status':'SOURCE_FORMAT_PROFILE_NOT_ACCEPTED_PARTIALS_PRESERVED',
          'error':type(exc).__name__+': '+str(exc),'identity_coverage_accepted':False,'payload_reference':row['payload_reference']})
        raise

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',type=Path,required=True);p.add_argument('--startup-proof',type=Path,required=True);a=p.parse_args()
    plan,proof,sources=c.startup(a.plan,a.startup_proof,__file__);root=c.q.literal(plan['output_directory']);root.mkdir(parents=True,exist_ok=False,mode=0o700)
    budget=Budget(plan,proof,root);budget.thread.start();started=time.monotonic();closed=[];fixture_gate=None
    try:
        budget.check();fixture_gate=fixtures(root,budget)
        with cf.ThreadPoolExecutor(max_workers=16) as pool:
            pending={pool.submit(source_profile,id,sources[id],root,budget):id for id in c.IDS}
            for future in cf.as_completed(pending):
                closed.append(future.result());budget.check()
        c.need(len(closed)==11 and {r['source_id'] for r in closed}==set(c.IDS),'ALL_ELEVEN_FORMAT_SOURCES_ACCOUNTED')
        budget.close();budget.owned()
        result={'schema':'MISSING11_IDENTITY_INPUT_FORMAT_PROFILE_RECEIPT_V1','status':'FORMAT_METADATA_PROFILE_COMPLETE_IDENTITY_ACCEPTANCE_PENDING',
          'endpoint':c.q.ENDPOINT,'uid':os.getuid(),'node':plan['node'],'job_id':str(proof['job_id']),
          'plan_reference':c.pin(a.plan),'startup_proof_reference':c.pin(a.startup_proof),'scope_key':c.KEY,'stage':c.STAGE,
          'parent_acquisition_job_id':'1884784','reused_sider_parent_job_id':'1884783','fixtures_reference':fixture_gate,
          'reports':sorted(closed,key=lambda r:r['source_id']),'input_payloads':11,'input_TAR_inventories':4,
          'current_full_payload_SHA_reverified':False,'payload_validation':'PRODUCER_FULL_SHA_PLUS_UNCHANGED_FRAME',
          'current_four_TAR_inventory_full_SHA_reverified':True,'actual_nonempty_source_threads':sorted({r['native_thread_id'] for r in closed}),
          'allocated_cpus':16,'maximum_source_threads':16,'runtime':budget.receipt(),'wall_seconds':time.monotonic()-started,
          'current_frame_checks_are_not_new_full_payload_SHA':True,'CSV_counts_are_physical_rows_not_accepted_chemical_identities':True,
          'QM7b_graph_identity_unresolved':True,'native_MOL2_formal_charge_stereo_not_inferred':True,
          'all_split_identity_coverage_accepted':False,'chemical_normalization':False,'new_GETs':0,'new_UFF_QM_calls':0,
          'pool_UFF_QM_training_export_release':False,'no_source_payload_deleted':True,'cost_overrun_action':'REPORT_AND_CONTINUE',
          'actual_terminal_parent_accounting_required':True,'signals_sent':False}
        c.write_new(root/'receipt.json',result);c.need(budget.owned()<=plan['output_cap_bytes'],'WHOLE64MIB_PROFILE_OUTPUT_CAP')
        print(json.dumps({'status':result['status'],'sources':11,'identity_coverage_accepted':False}),flush=True)
    except BaseException as exc:
        budget.close();c.write_new(root/'failure.json',{'schema':'MISSING11_IDENTITY_INPUT_FORMAT_PROFILE_RECEIPT_V1',
          'status':'FORMAT_PROFILE_FAILED_PARTIALS_PRESERVED_NO_AUTORETRY','error':type(exc).__name__+': '+str(exc),
          'closed_reports':closed,'fixtures_reference':fixture_gate,'runtime':budget.receipt(),'all_split_identity_coverage_accepted':False,'signals_sent':False});raise
if __name__=='__main__':main()
