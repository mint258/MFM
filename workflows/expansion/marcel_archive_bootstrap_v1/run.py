"""First allocated-CPU archive SHA, bounded directory and opaque CRC inventory."""
import argparse,hashlib,io,json,os,re,socket,stat,sys,time,traceback,unittest,zipfile
from pathlib import Path,PurePosixPath
from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2 import runtime as R
from . import contract as C,archive as A
Q=C.Q


def frame(s):return [s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns,s.st_uid]


class Budget:
    def __init__(self,plan,proof,out):
        self.plan,self.proof,self.out=plan,proof,out;self.start=time.monotonic();self.peak=0;self.minimum=None;self.samples=0
        p=Path('/proc/self/stat').read_text().rsplit(')',1)[1].split();self.start_ticks=int(p[19]);self.pid=os.getpid()
        job=Q.fields(proof['job_metadata']) if isinstance(proof['job_metadata'],str) else proof['job_metadata']
        m=re.fullmatch(r'(?:(\d+)-)?(\d+):(\d{2}):(\d{2})',job['RunTime']);Q.need(m is not None,'ACTUAL_ELAPSED_CLOCK')
        d,h,n,s=map(int,(m[1] or '0',m[2],m[3],m[4]));self.elapsed=d*86400+h*3600+n*60+s+max(0,time.time()-proof['memory_observation']['observed_unix_seconds'])
    def check(self):
        p=Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()
        Q.need(os.getpid()==self.pid and int(p[19])==self.start_ticks and os.getuid()==1278 and os.environ.get('SLURM_JOB_ID')==str(self.proof['job_id'])
            and socket.gethostname().split('.')[0]==self.proof['request']['node'] and Path('/proc/sys/kernel/random/boot_id').read_text().strip()==self.proof['boot_id'],
            'SAME_LIVE_ALLOCATION_CONTINUATION_NO_FRESHNESS_EXTENSION')
        rss=int(Path('/proc/self/statm').read_text().split()[1])*os.sysconf('SC_PAGE_SIZE')
        mem={v.split(':')[0]:int(v.split()[1])*1024 for v in Path('/proc/meminfo').read_text().splitlines() if v.startswith(('MemAvailable:','MemTotal:'))}
        self.samples+=1;self.peak=max(self.peak,rss);self.minimum=mem['MemAvailable'] if self.minimum is None else min(self.minimum,mem['MemAvailable'])
        used=sum(v.stat().st_size for v in self.out.iterdir() if v.is_file());s=os.statvfs(Q.ROOT)
        Q.need(rss<8<<30 and mem['MemAvailable']>=max(4<<30,.15*mem['MemTotal']),'ACTUAL_RSS_OR_MEMAVAILABLE_SOFT_STOP')
        Q.need(used+(1<<20)<64<<20 and s.f_bavail*s.f_frsize-((64<<20)-used)>=200000000000,'OUTPUT_OR_CURRENT_FREE_STOP')
        Q.need(self.elapsed+time.monotonic()-self.start<self.plan['wall_seconds']-60,'FINITE_WALL_NATURAL_DRAIN_RESERVE')


def fixtures(out):
    from .test_v1 import Boundaries
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(Boundaries);Q.need(suite.countTestCases()==3,'EXACT_THREE_BOOTSTRAP_FIXTURES')
    s=io.StringIO();r=unittest.TextTestRunner(stream=s,verbosity=2).run(suite)
    v={'tests_run':r.testsRun,'failures':len(r.failures),'errors':len(r.errors),'skips':len(r.skipped),
        'expected_failures':len(r.expectedFailures),'unexpected_successes':len(r.unexpectedSuccesses),'before_actual_opaque_body':True,'transcript':s.getvalue()}
    Q.write_new(out/'fixtures3.json',v);Q.need(r.wasSuccessful() and r.testsRun==3 and not(r.skipped or r.expectedFailures or r.unexpectedSuccesses),'PURE3_PASS_BEFORE_ANY_ORIGINAL_ARCHIVE_READ')
    return v


def bootstrap(locator,plan,out,budget):
    path=Path(locator['path']);Q.need(path.is_absolute() and '..' not in path.parts and not any(p.is_symlink() for p in (path,*path.parents)),'LITERAL_OWN_MAIN_OPAQUE_ARCHIVE')
    before=path.lstat();Q.need(stat.S_ISREG(before.st_mode) and before.st_uid==1278 and before.st_size==locator['bytes'],'CURRENT_TRANSPORT_EOF_SIZE_MAIN_FRAME')
    digest=hashlib.sha256();observed=0;inventory=out/'inventory.jsonl';inventory_sha=hashlib.sha256();inventory_bytes=0;expanded=0;basenames={};first=None
    with path.open('rb') as physical:
        Q.need(frame(os.fstat(physical.fileno()))==frame(before),'SAME_OPENED_OPAQUE_FILE')
        for block in iter(lambda:physical.read(1<<20),b''):budget.check();digest.update(block);observed+=len(block)
        Q.need(observed==locator['bytes'] and frame(os.fstat(physical.fileno()))==frame(before)==frame(path.lstat()),'FIRST_WHOLE_SHA_STABLE_FSTAT_LENGTH')
        first={'path':str(path),'bytes':observed,'sha256':digest.hexdigest()}
        Q.write_new(out/'first_observed_archive_SHA.json',{'schema':'MARCEL_ACTUAL_FIRST_CPU_ARCHIVE_SHA_V1','data_reference':first,
            'expected_SHA_before_this_CPU_run':None,'transport_authority_reference':locator['authority_reference'],'frame':frame(before),'CRC_or_identity_accepted':False})
        pre=A.preflight(physical,observed);physical.seek(0)
        with zipfile.ZipFile(physical,mode='r',allowZip64=True) as archive:
            infos,declared=A.directory(archive,pre,plan['expanded_byte_cap'])
            with inventory.open('xb') as stream:
                for ordinal,info in enumerate(infos):
                    budget.check();row=A.member(archive,info,budget.check,plan['expanded_byte_cap']-expanded)
                    row.update(ordinal=ordinal,directory=info.is_dir());expanded+=row['decoded_bytes']
                    base=PurePosixPath(info.filename).name
                    if not info.is_dir():basenames[base]=basenames.get(base,0)+1
                    raw=(json.dumps(row,ensure_ascii=False,separators=(',',':'))+'\n').encode();Q.need(len(raw)<=8192,'BOUNDED_MEMBER_METADATA_ROW')
                    stream.write(raw);stream.flush();os.fsync(stream.fileno());inventory_sha.update(raw);inventory_bytes+=len(raw)
                Q.need(expanded==declared,'ALL_MEMBERS_DECLARED_DECODED_BYTE_CONSERVATION')
            Q.need(frame(os.fstat(physical.fileno()))==frame(before),'FRAME_STABLE_THROUGH_FULL_CRC')
    Q.need(frame(path.lstat())==frame(before),'UNCHANGED_ARCHIVE_PATH_AFTER_FULL_BOOTSTRAP')
    expected=('Kraken.pickle',) if locator['source_id']=='marcel_kraken_zip' else ('Drugs.sdf','Drugs.csv')
    return {'first_actual_archive_reference':first,'ZIP_preflight':pre,'entries':len(infos),'expanded_bytes':expanded,
        'inventory_reference':{'path':str(inventory),'bytes':inventory_bytes,'sha256':inventory_sha.hexdigest()},
        'all_member_EOF_CRC_SHA_complete':True,'expected_author_member_basename_occurrences':{n:basenames.get(n,0) for n in expected},
        'expected_names_unique':all(basenames.get(n,0)==1 for n in expected),'member_format_names_are_not_identity_verification':True}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',type=Path,required=True);p.add_argument('--startup-proof',type=Path,required=True);a=p.parse_args()
    plan=Q.load(a.plan);transport,locator=C.transport(plan['transport_receipt_reference'],plan.get('relocation_reference'));params=C.parameters(transport,plan['expanded_byte_cap'])
    Q.need(plan['schema']=='MARCEL_OFFICIAL_ARCHIVE_BOOTSTRAP_PLAN_V1' and plan['scope_parameters']==params,'EXACT_BOOTSTRAP_PLAN')
    argv=[Q.PY,'-B','-m',C.MODULE,'--plan',str(a.plan),'--startup-proof',str(a.startup_proof)]
    proof=R.require_startup(a.startup_proof,expected_scope_key=C.KEY,expected_scope_parameters=params,expected_execution_argv=argv,
        expected_source=__file__,expected_kind='analysis',required_references=[Q.pin(a.plan),plan['transport_receipt_reference'],plan['cost_decision_reference'],*([plan['relocation_reference']] if plan.get('relocation_reference') else [])])
    req=proof['request'];authority=C.meta(req['queue_authority_reference'])
    allowed={'compute-0-'+str(n) for n in authority['allowed_nodes']['analysis']}
    Q.need(req['node'] in allowed and req['pilot'] is False and req['wall_seconds']==plan['wall_seconds']
        and type(plan['wall_seconds']) is int and 300<=plan['wall_seconds']<=7200 and plan['wall_seconds']%60==0
        and req['data_references']==[] and req['deferred_authority_references']==[locator] and req['estimated_peak_output_bytes']==64<<20,'EXACT_ONE_UNKNOWN_SHA_DEFERRED_TRANSPORT_AUTHORITY')
    review=C.meta(req['scope']['review']);Q.need(review['first_unknown_archive_SHA_CPU_bootstrap_authorized'] is True,'ROOT_EXPLICIT_UNKNOWN_SHA_BOOTSTRAP_REVIEW')
    cost=C.meta(plan['cost_decision_reference']);Q.need(cost['status']=='USER_AUTHORIZED' and cost['on_overrun']=='REPORT_AND_CONTINUE'
        and cost['scientific_quality_thresholds_unchanged'] is True,'ACTUAL_REPORT_CONTINUE_QUALITY_AUTHORITY')
    for name in C.FILES:Q.need(Q.pin(C.HERE/name) in req['source_references'],'ACTUAL_NEW_SOURCE_PIN_SET')
    Q.need(Path(sys.modules['__main__'].__file__).absolute()==C.HERE/'run.py' and sys.argv==[str(C.HERE/'run.py'),*argv[4:]],'EXACT_MAIN_FULL_ARGV')
    out=Path(plan['output_directory']);Q.need(Q.ROOT/'artifacts' in out.parents and not out.exists(),'NEW_OUTPUT_CHILD');out.mkdir(parents=True,mode=0o700)
    budget=Budget(plan,proof,out);gate=None;started=time.monotonic()
    try:
        gate=fixtures(out);budget.check();result=bootstrap(locator,plan,out,budget)
        Q.write_new(out/'receipt.json',{'schema':'MARCEL_OFFICIAL_ARCHIVE_BOOTSTRAP_RECEIPT_V1',
            'status':'FIRST_SHA_ALL_MEMBER_CRC_INVENTORY_COMPLETE_IDENTITY_PENDING' if result['expected_names_unique'] else 'CRC_COMPLETE_AUTHOR_MEMBER_NAMES_UNKNOWN_HOLD',
            'source_id':locator['source_id'],'official_file_id':transport['official_file_id'],'transport_receipt_reference':plan['transport_receipt_reference'],
            'job_id':str(proof['job_id']),'uid':1278,'node':req['node'],'endpoint':'202.38.247.57:22','plan_reference':Q.pin(a.plan),
            'actual_python_version':sys.version,'actual_zipfile_module_path':zipfile.__file__,
            'startup_proof_reference':Q.pin(a.startup_proof),'scope_parameters':params,'fixtures':gate,'result':result,'wall_seconds':time.monotonic()-started,
            'actual_RSS_peak_bytes':budget.peak,'actual_minimum_MemAvailable_bytes':budget.minimum,'pickle_or_native_identity_parsed':False,
            'source_molecule_conformer_counts_or_stereo_accepted':False,'pool_or_full_identity_release':False,'new_network_QM_UFF_calls':0,
            'new_actual_terminal_cost':'PENDING_ROOT_ACCOUNTING','cost_overrun_action':'REPORT_AND_CONTINUE'})
        return 0 if result['expected_names_unique'] else 3
    except BaseException as exc:
        Q.write_new(out/'failure.json',{'schema':'MARCEL_ARCHIVE_BOOTSTRAP_FAILURE_V1','error':type(exc).__name__+': '+str(exc),
            'traceback':traceback.format_exc(),'fixtures':gate,'actual_first_SHA_if_completed':Q.load(out/'first_observed_archive_SHA.json') if (out/'first_observed_archive_SHA.json').exists() else None,
            'all_files_retained':True,'expected_SHA_invented':False,'archive_or_identity_acceptance':False,'actual_cost':'PENDING_ROOT_ACCOUNTING'})
        raise


if __name__=='__main__':raise SystemExit(main())
