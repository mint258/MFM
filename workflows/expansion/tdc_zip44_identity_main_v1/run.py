"""Actual Main CPU: all44 original CSV identities, frozen keys, no Y materialization."""
import argparse,collections,concurrent.futures as cf,hashlib,io,json,multiprocessing as mp,os,socket,stat,sys,time,traceback,unittest,zipfile,zlib
from pathlib import Path
from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2 import runtime as R
from workflows.expansion.marcel_archive_bootstrap_v1 import archive as A
from workflows.expansion.tdc_zip44_header_probe_v2 import projection as H
from . import contract as C,projection as P,kernel as K
Q=C.Q


def frame(s):return [s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns,s.st_uid]


class Budget:
    def __init__(self,plan,proof,out):
        self.plan,self.proof,self.out=plan,proof,out;self.start=time.monotonic();self.last=0;self.peak=0;self.minimum=None
        self.pid=os.getpid();self.ticks=Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19]
        job=Q.fields(proof['job_metadata']) if isinstance(proof['job_metadata'],str) else proof['job_metadata'];t=job['RunTime']
        d,t=t.split('-',1) if '-' in t else ('0',t);h,m,s=map(int,t.split(':'))
        self.elapsed=int(d)*86400+h*3600+m*60+s+max(0,time.time()-proof['memory_observation']['observed_unix_seconds'])
    def check(self,dispatch=True,force=False):
        now=time.monotonic()
        if not force and now-self.last<1:return
        self.last=now;req=self.proof['request']
        Q.need(os.getpid()==self.pid and Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19]==self.ticks
            and os.getuid()==1278 and socket.gethostname().split('.')[0]==req['node'] and os.environ.get('SLURM_JOB_ID')==str(self.proof['job_id'])
            and Path('/proc/sys/kernel/random/boot_id').read_text().strip()==self.proof['boot_id'],'SAME_LIVE_CPU_PARENT_NO_FRESHNESS_EXTENSION')
        rss=0
        children=Path('/proc/self/task/'+str(self.pid)+'/children').read_text().split()
        for pid in [str(self.pid),*children]:
            try:rss+=int(Path('/proc/'+pid+'/statm').read_text().split()[1])*os.sysconf('SC_PAGE_SIZE')
            except FileNotFoundError:pass
        mem={v.split(':')[0]:int(v.split()[1])*1024 for v in Path('/proc/meminfo').read_text().splitlines() if v.startswith(('MemAvailable:','MemTotal:'))}
        self.peak=max(self.peak,rss);self.minimum=mem['MemAvailable'] if self.minimum is None else min(self.minimum,mem['MemAvailable'])
        used=sum(p.stat().st_size for p in self.out.iterdir() if p.is_file());v=os.statvfs(Q.ROOT)
        reserve=(256<<20) if dispatch else (1<<20)
        Q.need(used+reserve<C.CAP and v.f_bavail*v.f_frsize-max(0,C.CAP-used)>=200000000000,'OUTPUT_CURRENT_FREE_SOFT_STOP')
        if dispatch:
            Q.need(rss<16<<30 and mem['MemAvailable']>=max(4<<30,.15*mem['MemTotal']),'RSS_MEMAVAILABLE_STOP_NEW_ROWS_NATURAL_DRAIN')
            Q.need(self.elapsed+now-self.start<self.plan['wall_seconds']-90,'FINITE_WALL_STOP_NEW_ROWS_NATURAL_DRAIN')


def fixtures(out,source_refs):
    from .test_v1 import Boundaries
    functions,kernel=K.load(source_refs);Boundaries.functions=functions
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(Boundaries);Q.need(suite.countTestCases()==3,'EXACT3_PURE_METHODS')
    s=io.StringIO();r=unittest.TextTestRunner(stream=s,verbosity=2).run(suite)
    v={'tests_run':r.testsRun,'failures':len(r.failures),'errors':len(r.errors),'skips':len(r.skipped),
        'expected_failures':len(r.expectedFailures),'unexpected_successes':len(r.unexpectedSuccesses),'transcript':s.getvalue(),
        'before_archive_body':True,'kernel_proof':kernel}
    Q.write_new(out/'fixtures3.json',v);Q.need(r.wasSuccessful() and r.testsRun==3
        and not(r.skipped or r.expectedFailures or r.unexpectedSuccesses),'PURE3_PASS_BEFORE_ORIGINAL_ARCHIVE')
    return v


class Dispatcher:
    def __init__(self,pool,out,budget):
        self.pool,self.budget=pool,budget;self.events=(out/'all_original_identity_events.jsonl').open('xb');self.pending={}
        self.submitted=0;self.completed=0;self.states=collections.Counter();self.members=collections.Counter();self.next=collections.Counter()
        self.worker_rows=collections.Counter();self.worker_CPU=collections.Counter();self.h=hashlib.sha256();self.bytes=0
    def write(self,row,dispatch):
        raw=(json.dumps(row,ensure_ascii=True,separators=(',',':'),allow_nan=False)+'\n').encode();Q.need(len(raw)<=8<<20,'BOUNDED_IDENTITY_EVENT_ROW')
        self.budget.check(dispatch=dispatch);used=sum(p.stat().st_size for p in self.budget.out.iterdir() if p.is_file())
        reserve=(258<<20) if dispatch else (1<<20)
        Q.need(used+len(raw)+reserve<C.CAP,'EXACT_NEXT_EVENT_OUTPUT_AND_DRAIN_CAP');self.events.write(raw);self.events.flush();os.fsync(self.events.fileno())
        self.h.update(raw);self.bytes+=len(raw)
    def enqueue(self,row):
        self.budget.check();name=row['member_name'];Q.need(row['physical_record_ordinal']==self.next[name],'EXACT_SOURCE_PHYSICAL_ORDINAL_SEQUENCE')
        self.write({'event':'SOURCE_ROW_DURABLE_BEFORE_WORKER_DISPATCH','source':row},True)
        self.pending[self.pool.submit(K.work,row)]=row;self.submitted+=1;self.next[name]+=1
        if len(self.pending)>=32:self.collect(False)
    def collect(self,all_rows):
        while self.pending:
            done,_=cf.wait(self.pending,timeout=1,return_when=cf.FIRST_COMPLETED)
            self.budget.check(dispatch=False)
            for future in done:
                source=self.pending.pop(future)
                try:value=future.result();Q.need(value['result']['source']==source,'WORKER_ORIGINAL_SOURCE_IDENTITY_UNCHANGED')
                except Exception as exc:value={'worker_pid':None,'worker_CPU_seconds':None,'result':{'source':source,'identity_state':'TECHNICAL_UNRESOLVED',
                    'full_InChIKeys':[],'WP5_keys':[],'error':type(exc).__name__+': '+str(exc),'technical_unknown_is_chemical_exclusion':False}}
                self.write({'event':'ORIGINAL_ROW_IDENTITY_RESULT_COMPLETE','worker_observation':value},False)
                self.completed+=1;self.states[value['result']['identity_state']]+=1;self.members[source['member_name']]+=1
                pid=value['worker_pid'];self.worker_rows[str(pid)]+=1
                if value['worker_CPU_seconds'] is not None:self.worker_CPU[str(pid)]+=value['worker_CPU_seconds']
            if done and not all_rows:return
    def close(self):self.events.close()


def observe(plan,headers,entries,parent,out,budget,source_refs):
    ref=plan['archive_reference'];path=Path(ref['path']);Q.need(path.is_absolute() and Q.ROOT in path.parents and '..' not in path.parts
        and not any(p.is_symlink() for p in (path,*path.parents)),'LITERAL_MAIN_ORIGINAL_COPY')
    before=path.lstat();Q.need(stat.S_ISREG(before.st_mode) and before.st_uid==1278 and before.st_size==ref['bytes'],'ACTUAL_MAIN_ZIP_OWNER_SIZE')
    h=hashlib.sha256();n=0;member_results=[];dispatch=None
    expected_members={v['member_name']:v for v in parent['result']['members']}
    with path.open('rb') as f:
        Q.need(frame(os.fstat(f.fileno()))==frame(before),'SAME_OPENED_INPUT')
        for block in iter(lambda:f.read(1<<20),b''):budget.check();h.update(block);n+=len(block)
        Q.need(n==ref['bytes'] and h.hexdigest()==ref['sha256'] and frame(os.fstat(f.fileno()))==frame(before),'CURRENT_RAW_WHOLE_SHA_FSTAT')
        pre=A.preflight(f,n);f.seek(0)
        with zipfile.ZipFile(f,'r') as z,cf.ProcessPoolExecutor(max_workers=16,mp_context=mp.get_context('spawn'),initializer=K.initialize,initargs=(source_refs,)) as pool:
            infos,_=A.directory(z,pre,5434789);H.checked_inventory(infos,entries);dispatch=Dispatcher(pool,out,budget)
            try:
                for info in infos:
                    if info.is_dir():continue
                    expected=expected_members[info.filename];parser=P.IdentityCSV(info.filename,dispatch.enqueue) if info.filename in headers else None
                    sha=hashlib.sha256();crc=0;decoded=0
                    with z.open(info) as stream:
                        while True:
                            budget.check();block=stream.read(1<<16)
                            if not block:break
                            decoded+=len(block);Q.need(decoded<=info.file_size,'MEMBER_DECODED_LENGTH_BOUND');sha.update(block);crc=zlib.crc32(block,crc)
                            if parser:parser.feed(block)
                    summary=parser.finish() if parser else None
                    Q.need(decoded==info.file_size==expected['decoded_bytes'] and sha.hexdigest()==expected['decoded_sha256']
                        and crc&0xffffffff==info.CRC==expected['CRC32_observed'],'ALL_REGULAR_CURRENT_MEMBER_EOF_CRC_SHA_MATCHES_4521689')
                    if parser:Q.need(summary['record_counts']==headers[info.filename]['CSV']['record_counts'],'ALL_PHYSICAL_ROWS_MATCH_ACTUAL_HEADER_PARENT')
                    member_results.append({'member_name':info.filename,'decoded_bytes':decoded,'decoded_sha256':sha.hexdigest(),
                        'CRC32':crc&0xffffffff,'EOF_CRC_SHA_complete':True,'CSV':summary})
                dispatch.collect(True)
                Q.need(dispatch.submitted==dispatch.completed==81809 and len(dispatch.members)==44
                    and all(dispatch.members[name]==headers[name]['CSV']['record_counts']['physical_data_records'] for name in headers),'ALL81809_SOURCE_RESULT_ROWS_AND44_MEMBERS_CONSERVED')
                result={'physical_rows_dispatched':dispatch.submitted,'physical_rows_with_durable_results':dispatch.completed,
                    'identity_state_counts':dict(dispatch.states),'member_result_counts':dict(dispatch.members),'worker_record_counts':dict(dispatch.worker_rows),
                    'worker_CPU_seconds':dict(dispatch.worker_CPU),'journal_reference':{'path':str(out/'all_original_identity_events.jsonl'),
                        'bytes':dispatch.bytes,'sha256':dispatch.h.hexdigest()},'members':member_results,'grammar_proof':P.grammar_proof(),
                    'unknowns_dropped_or_reclassified_as_chemical_exclusions':False,'all_original_splits_and_native_IDs_retained':True}
            finally:
                # All submitted calls are allowed to finish; no signal/cancel/retry.
                try:dispatch.collect(True)
                finally:dispatch.close()
        Q.need(frame(os.fstat(f.fileno()))==frame(before)==frame(path.lstat()),'INPUT_STABLE_AFTER_ALL_MEMBER_READS')
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',type=Path,required=True);p.add_argument('--startup-proof',type=Path,required=True);a=p.parse_args()
    plan=Q.load(a.plan);parent,data,entries,headers,parents=C.inputs(plan)
    Q.need(plan['schema']=='TDC_ZIP44_IDENTITY_PLAN_V1' and plan['scope_parameters']==C.PARAMETERS,'EXACT_IDENTITY_PLAN')
    argv=[Q.PY,'-B','-m',C.MODULE,'--plan',str(a.plan),'--startup-proof',str(a.startup_proof)]
    proof=R.require_startup(a.startup_proof,expected_scope_key=C.KEY,expected_scope_parameters=C.PARAMETERS,expected_execution_argv=argv,
        expected_source=__file__,expected_kind='analysis',required_references=[Q.pin(a.plan),*parents,plan['cost_decision_reference']])
    req=proof['request'];authority=C.meta(req['queue_authority_reference']);allowed={'compute-0-'+str(n) for n in authority['allowed_nodes']['analysis']}
    Q.need(req['node'] in allowed and req['pilot'] is False and req['wall_seconds']==plan['wall_seconds']
        and type(plan['wall_seconds']) is int and 600<=plan['wall_seconds']<=7200 and plan['wall_seconds']%60==0
        and req['estimated_peak_output_bytes']==C.CAP and req['data_references']==[data] and not req.get('deferred_authority_references'),
        'EXACT_FULL44_ANALYSIS_SCOPE_NO_NEW_QUEUE_OR_DATA')
    review=C.meta(req['scope']['review']);Q.need(review['all44_original_splits_identity_only_full_projection_authorized'] is True,'EXPLICIT_ROOT_ALL44_IDENTITY_REVIEW')
    cost=C.meta(plan['cost_decision_reference']);Q.need(cost['status']=='USER_AUTHORIZED' and cost['on_overrun']=='REPORT_AND_CONTINUE'
        and cost['scientific_quality_thresholds_unchanged'] is True,'COST_AND_SCIENTIFIC_AUTHORITY')
    for p in [*(C.HERE/n for n in C.FILES),*(Q.REPO/n for n in C.OLD)]:Q.need(Q.pin(p) in req['source_references'],'COMPLETE_CURRENT_SOURCE_PINS')
    Q.need(Path(sys.modules['__main__'].__file__).absolute()==C.HERE/'run.py' and sys.argv==[str(C.HERE/'run.py'),*argv[4:]],'PRIMARY_FULL_ARGV_SOURCE')
    for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='1'
    out=Path(plan['output_directory']);Q.need(Q.ROOT/'artifacts' in out.parents and not out.exists(),'FRESH_IDENTITY_OUTPUT_ONLY');out.mkdir(parents=True,mode=0o700)
    budget=Budget(plan,proof,out);gate=None
    try:
        gate=fixtures(out,req['source_references']);budget.check(force=True);result=observe(plan,headers,entries,parent,out,budget,req['source_references'])
        Q.write_new(out/'receipt.json',{'schema':'TDC_ZIP44_IDENTITY_RECEIPT_V1','status':'ALL81809_ORIGINAL_ROWS_IDENTITY_KEYS_OBSERVED_UNKNOWNS_RETAINED',
            'job_id':str(proof['job_id']),'uid':1278,'node':req['node'],'endpoint':'202.38.247.57:22','input_reference':data,
            'accepted_header_receipt_reference':plan['accepted_header_receipt_reference'],'accepted_header_accounting_reference':plan['accepted_header_accounting_reference'],
            'plan_reference':Q.pin(a.plan),'startup_proof_reference':Q.pin(a.startup_proof),'fixtures':gate,'result':result,
            'observed_parent_and_direct_children_RSS_peak_bytes':budget.peak,'minimum_MemAvailable_bytes':budget.minimum,
            'actual_python_version':sys.version,'new_actual_terminal_cost':'PENDING_ROOT_ACCOUNTING','cost_overrun_action':'REPORT_AND_CONTINUE',
            'source_1884799_failed3_and4521650_failed1_preserved':True,'global_decontamination_pool_or_training_release':False})
        return 0
    except BaseException as exc:
        Q.write_new(out/'failure.json',{'schema':'TDC_ZIP44_IDENTITY_FAILURE_V1','error':type(exc).__name__+': '+str(exc),
            'traceback':traceback.format_exc(),'fixtures':gate,'durable_source_result_prefixes_retained':True,'all_population_closed':False,
            'global_decontamination_pool_release':False,'actual_cost':'PENDING_ROOT_ACCOUNTING'})
        raise


if __name__=='__main__':raise SystemExit(main())
