"""Main CPU header-only probe; original ZIP and CSV bytes are never edited."""
import argparse,hashlib,io,os,re,stat,sys,time,traceback,unittest,zipfile
from pathlib import Path,PurePosixPath
from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2 import runtime as R
from . import contract as C,projection as P
Q=C.Q


class Budget:
    def __init__(self,plan,proof,out):
        self.plan,self.proof,self.out=plan,proof,out;self.start=time.monotonic();self.samples=0;self.peak_RSS=0;self.min_available=None
        job=Q.fields(proof['job_metadata']) if isinstance(proof['job_metadata'],str) else proof['job_metadata']
        m=re.fullmatch(r'(?:(\d+)-)?(\d+):(\d{2}):(\d{2})',job['RunTime']);Q.need(m is not None,'ACTUAL_SLURM_ELAPSED_CLOCK')
        d,h,n,s=map(int,(m[1] or '0',m[2],m[3],m[4]));self.allocation_elapsed_start=d*86400+h*3600+n*60+s+max(0,time.time()-proof['memory_observation']['observed_unix_seconds'])
    def check(self):
        rss=int(Path('/proc/self/statm').read_text().split()[1])*os.sysconf('SC_PAGE_SIZE')
        mem={line.split(':')[0]:int(line.split()[1])*1024 for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith(('MemAvailable:','MemTotal:'))}
        self.samples+=1;self.peak_RSS=max(self.peak_RSS,rss);self.min_available=mem['MemAvailable'] if self.min_available is None else min(self.min_available,mem['MemAvailable'])
        used=sum(p.stat().st_size for p in self.out.iterdir() if p.is_file());space=os.statvfs(Q.ROOT)
        elapsed=self.allocation_elapsed_start+time.monotonic()-self.start
        Q.need(rss<8<<30 and mem['MemAvailable']>=max(4<<30,.15*mem['MemTotal']),'SOFT_RSS_OR_MEMAVAILABLE_STOP_NO_SIGNALS')
        Q.need(used+(1<<20)<64<<20 and space.f_bavail*space.f_frsize-((64<<20)-used)>=200000000000,'OUTPUT_OR_CURRENT_STORAGE_STOP_NO_SIGNALS')
        Q.need(max(elapsed,time.monotonic()-self.start)<self.plan['wall_seconds']-30,'WALL_DRAIN_RESERVE_NO_NEW_MEMBERS')


def frame(s):return [s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns,s.st_uid]


def fixture_gate(out):
    from . import test_v1
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(test_v1.Boundaries);Q.need(suite.countTestCases()==3,'EXACT_THREE_PURE_BOUNDARIES')
    stream=io.StringIO();result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    receipt={'tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'skips':len(result.skipped),
        'expected_failures':len(result.expectedFailures),'unexpected_successes':len(result.unexpectedSuccesses),'before_actual_body':True,'transcript':stream.getvalue()}
    Q.write_new(out/'fixtures3.json',receipt)
    Q.need(result.wasSuccessful() and result.testsRun==3 and not(result.skipped or result.expectedFailures or result.unexpectedSuccesses),'THREE_FIXTURES_PASS_BEFORE_ZIP_BODY')
    return receipt


def body_verify(reference,budget):
    path=Path(reference['path']);Q.need(path.is_absolute() and '..' not in path.parts and not any(p.is_symlink() for p in (path,*path.parents)),'ONLY_LITERAL_MAIN_INPUT_COPY')
    before=path.lstat();Q.need(stat.S_ISREG(before.st_mode) and before.st_uid==1278 and before.st_size==reference['bytes'],'ACTUAL_MAIN_COPY_UID_SIZE')
    digest=hashlib.sha256();total=0
    with path.open('rb') as stream:
        opened=os.fstat(stream.fileno());Q.need(frame(opened)==frame(before),'SAME_OPENED_INPUT_FRAME')
        for block in iter(lambda:stream.read(64<<10),b''):budget.check();digest.update(block);total+=len(block)
        after=os.fstat(stream.fileno())
    Q.need(total==reference['bytes'] and digest.hexdigest()==reference['sha256'] and frame(before)==frame(after)==frame(path.lstat()),'CURRENT_FULL_RAW_SHA_FSTAT_REQUIRED')
    return path,frame(after)


def probe(path,expected,out,budget,input_frame):
    reports=[];members=[];regular_bytes=0;csv_bytes=0;failures=[]
    with zipfile.ZipFile(path) as archive:
        Q.need(frame(os.fstat(archive.fp.fileno()))==input_frame,'ZIP_OPENED_SAME_FULL_SHA_VERIFIED_FRAME')
        infos=archive.infolist();P.checked_inventory(infos,expected)
        for ordinal,info in enumerate(infos):
            budget.check()
            if info.is_dir():
                members.append({'member_ordinal':ordinal,'member_name':info.filename,'type':'DIRECTORY','declared_bytes':info.file_size,'body_read':False})
                continue
            is_csv=info.filename.endswith('.csv');parser=P.HeaderOnly(info.filename) if is_csv else None
            sha=hashlib.sha256();crc=0;size=0;parse_error=None;archive_error=None
            try:
                import zlib
                with archive.open(info,'r') as stream:
                    while True:
                        block=stream.read(64<<10)
                        if not block:break
                        budget.check();size+=len(block);sha.update(block);crc=zlib.crc32(block,crc)
                        if parser is not None and parse_error is None:
                            try:parser.feed(block)
                            except (P.F.UnknownFormat,UnicodeError) as exc:parse_error=type(exc).__name__+': '+str(exc)
                if parser is not None and parse_error is None:
                    try:parser.finish()
                    except (P.F.UnknownFormat,UnicodeError) as exc:parse_error=type(exc).__name__+': '+str(exc)
                Q.need(size==info.file_size and (crc&0xffffffff)==info.CRC,'CURRENT_MEMBER_FULL_EOF_LENGTH_CRC')
            except (zipfile.BadZipFile,RuntimeError,EOFError) as exc:archive_error=type(exc).__name__+': '+str(exc)
            regular_bytes+=size
            if is_csv:
                csv_bytes+=size;parts=PurePosixPath(info.filename).parts
                role=PurePosixPath(info.filename).name
                r={'schema':'TDC_CSV_HEADER_STRUCTURE_METADATA_V1','member_ordinal':ordinal,'member_name':info.filename,
                    'source_endpoint_directory_literal':parts[-2],'source_split_filename_literal':role,
                    'status':'HEADER_AND_CSV_STRUCTURE_OBSERVED' if parse_error is None and archive_error is None else 'UNKNOWN_FORMAT_RETAINED',
                    'CSV':parser.summary(),'parser_error':parse_error,'archive_error':archive_error,'decoded_bytes':size,
                    'decoded_sha256':sha.hexdigest(),'CRC32_observed':crc&0xffffffff,'member_EOF_CRC_passed':archive_error is None,
                    'ID_or_SMILES_columns_inferred':False,'identity_or_population_accepted':False}
                ref=Q.write_new(out/('member_%03d.json'%ordinal),r);reports.append({'member_name':info.filename,'report_reference':ref,
                    'status':r['status'],'header_columns':r['CSV']['header_columns'],'record_counts':r['CSV']['record_counts']})
            members.append({'member_ordinal':ordinal,'member_name':info.filename,'type':'CSV' if is_csv else 'OTHER_REGULAR_NO_IDENTITY',
                'decoded_bytes':size,'decoded_sha256':sha.hexdigest(),'CRC32_observed':crc&0xffffffff,
                'EOF_CRC_passed':archive_error is None,'data_values_text_decoded':False})
            if parse_error is not None or archive_error is not None:failures.append({'member':info.filename,'parser_error':parse_error,'archive_error':archive_error})
        Q.need(frame(os.fstat(archive.fp.fileno()))==input_frame,'ZIP_FRAME_STABLE_THROUGH_ALL_MEMBERS')
    Q.need(len(reports)==44,'ALL44_CSV_MEMBERS_HAVE_TERMINAL_METADATA')
    complete=not failures and regular_bytes==5434789 and csv_bytes==5428641
    return {'reports':reports,'members':members,'regular_decoded_bytes':regular_bytes,'CSV_decoded_bytes':csv_bytes,'failures':failures,
        'all68_inventory_entries_matched':True,'all_regular_member_EOF_CRC_passed':not any(r['archive_error'] for r in failures),
        'all44_CSV_metadata_complete':complete}


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--plan',required=True,type=Path);ap.add_argument('--startup-proof',required=True,type=Path);a=ap.parse_args()
    plan=Q.load(a.plan);Q.need(plan['schema']=='TDC_ZIP44_HEADER_PROBE_PLAN_V1' and plan['scope_key']==C.KEY and plan['scope_parameters']==C.PARAMETERS,'EXACT_HEADER_ONLY_PLAN')
    obs,target,expected=C.inputs(plan['observation_reference'],plan['relocation_reference'])
    argv=[Q.PY,'-B','-m',C.MODULE,'--plan',str(a.plan),'--startup-proof',str(a.startup_proof)]
    proof=R.require_startup(a.startup_proof,expected_scope_key=C.KEY,expected_scope_parameters=C.PARAMETERS,expected_execution_argv=argv,
        expected_source=__file__,expected_kind='analysis',required_references=[Q.pin(a.plan),plan['observation_reference'],plan['relocation_reference'],
            plan['parent_get_accounting_reference'],plan['parent_raw_sacct_copy_reference'],plan['cost_decision_reference'],target])
    req=proof['request'];authority=C.meta(req['queue_authority_reference'])
    analysis_nodes={'compute-0-'+str(n) for n in authority['allowed_nodes']['analysis']}
    Q.need(req['node'] in analysis_nodes and req['pilot'] is False and req['wall_seconds']==plan['wall_seconds'] in (300,600)
        and req['estimated_peak_output_bytes']==64<<20 and req['data_references']==[target],'EXACT_AUTHORITY_ANALYSIS_CPU16_SHORT_HEADER_ONLY_SCOPE')
    review=C.meta(req['scope']['review']);Q.need(review['accept_only_closed_TDC_payload_from_failed1884799'] is True,'ROOT_ACCEPTS_ONE_COMPLETE_PAYLOAD_NOT_FAILED_PARENT_C0')
    Q.need(Path(sys.modules['__main__'].__file__).absolute()==C.HERE/'run.py' and sys.argv==[str(C.HERE/'run.py'),*argv[4:]],'ACTUAL_MAIN_AND_COMPLETE_ARGV')
    for name in C.FILES:Q.need(Q.pin(C.HERE/name) in req['source_references'],'EVERY_NEW_SOURCE_PIN')
    from .materialize import failed_parent
    failed_parent(plan)  # Independently verify whole failed Alpha parent cost metadata; no body access or Main/Alpha proof reuse.
    cost=C.meta(plan['cost_decision_reference']);Q.need(cost['status']=='USER_AUTHORIZED' and cost['on_overrun']=='REPORT_AND_CONTINUE'
        and cost['scientific_quality_thresholds_unchanged'] is True,'ACTUAL_COST_QUALITY_DECISION')
    Q.need(Path(P.F.__file__).absolute()==C.OLD/'formats.py' and Q.pin(P.F.__file__)==plan['original_formats_reference']
        and plan['original_formats_reference'] in req['source_references'],'ACTUAL_UNMODIFIED_ORIGINAL_FORMATS_MODULE')
    for name in ('feed','finish','finish_field','append'):Q.need(getattr(P.HeaderOnly,name) is getattr(P.F.CSVProjection,name),'ORIGINAL_GRAMMAR_OBJECT')
    out=Path(plan['output_directory']);Q.need(Q.ROOT/'artifacts' in out.parents and not out.exists(),'NEW_PROBE_OUTPUT_LEAF');out.mkdir(parents=True,mode=0o700)
    began=time.monotonic();budget=Budget(plan,proof,out);fixtures=None
    try:
        fixtures=fixture_gate(out);budget.check();source_proof={'original_formats_reference':Q.pin(C.OLD/'formats.py'),'inherited_method_objects':P.method_proof(),
            'new_seams_only':['constructor without six-source alias','header completion selected={} and unchanged record count branch','header-only summary'],
            'original_source_or_global_tables_modified':False}
        Q.write_new(out/'grammar_source_proof.json',source_proof);path,before=body_verify(target,budget)
        result=probe(path,expected,out,budget,before);Q.need(frame(path.lstat())==before,'INPUT_UNCHANGED_THROUGH_ZIP_AND_ALL_MEMBERS')
        receipt={'schema':'TDC_ZIP44_HEADER_PROBE_RECEIPT_V1','status':'ALL44_HEADER_STRUCTURE_METADATA_CLOSED_IDENTITY_MAPPING_PENDING' if result['all44_CSV_metadata_complete'] else 'UNKNOWN_FORMAT_METADATA_PARTIAL_RETAINED',
            'job_id':str(proof['job_id']),'uid':os.getuid(),'node':req['node'],'endpoint':'202.38.247.57:22',
            'plan_reference':Q.pin(a.plan),'startup_proof_reference':Q.pin(a.startup_proof),'scope_parameters':C.PARAMETERS,
            'input_reference':target,'input_current_full_SHA_fstat_verified':True,'input_frame_after':before,'fixtures':fixtures,
            'grammar_source_proof':source_proof,'result':result,'wall_seconds':time.monotonic()-began,
            'runtime':{'samples':budget.samples,'peak_RSS_bytes':budget.peak_RSS,'minimum_MemAvailable_bytes':budget.min_available,'forced_signals':False},
            'source_get_parent_job_id':'1884799','source_get_parent_was_C0':False,'source_get_parent_failed_cost_retained':True,
            'ID_or_SMILES_semantics':'UNKNOWN_PENDING_HEADER_AND_OFFICIAL_LOADER_REVIEW','physical_records_are_effective_molecules':False,
            'identity_values_or_assays_decoded_or_persisted':False,'new_network_key_X_UFF_QM_calls':0,'full_decontamination_pool_release':False,
            'new_actual_parent_terminal_cost':'PENDING_ROOT_ACCOUNTING','cost_overrun_action':'REPORT_AND_CONTINUE'}
        Q.write_new(out/'receipt.json',receipt);return 0 if result['all44_CSV_metadata_complete'] else 3
    except BaseException as exc:
        Q.write_new(out/'failure.json',{'schema':'TDC_ZIP44_HEADER_PROBE_FAILURE_V1','error':type(exc).__name__+': '+str(exc),
            'traceback':traceback.format_exc(),'fixtures':fixtures,'all_artifacts_retained':True,'identity_or_population_release':False,'new_terminal_cost':'PENDING_ROOT_ACCOUNTING'})
        raise


if __name__=='__main__':raise SystemExit(main())
