"""Fresh Main CPU source projection; no chemistry, download or pickle execution."""
import argparse,collections,hashlib,io,json,os,socket,sqlite3,stat,sys,time,traceback,unittest,zipfile,zlib
from pathlib import Path,PurePosixPath
from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2 import runtime as R
from workflows.expansion.marcel_archive_bootstrap_v1 import archive as A
from . import contract as C,projection as P,opcodes as O
Q=C.Q


def frame(s):return [s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns,s.st_uid]


class Budget:
    def __init__(self,plan,proof,out):
        self.plan,self.proof,self.out=plan,proof,out;self.start=time.monotonic();self.last=0;self.peak=0;self.minimum=None
        self.pid=os.getpid();self.ticks=Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19]
        self.initial_elapsed=time.time()-proof['memory_observation']['observed_unix_seconds']
        job=Q.fields(proof['job_metadata']) if isinstance(proof['job_metadata'],str) else proof['job_metadata']
        t=job['RunTime'];days,clock=t.split('-',1) if '-' in t else ('0',t);h,m,s=map(int,clock.split(':'))
        self.initial_elapsed+=int(days)*86400+h*3600+m*60+s
    def check(self,force=False):
        now=time.monotonic()
        if not force and now-self.last<1:return
        self.last=now;req=self.proof['request'];p=Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()
        Q.need(os.getpid()==self.pid and p[19]==self.ticks and os.getuid()==1278
            and os.environ.get('SLURM_JOB_ID')==str(self.proof['job_id']) and socket.gethostname().split('.')[0]==req['node']
            and Path('/proc/sys/kernel/random/boot_id').read_text().strip()==self.proof['boot_id'],'SAME_LIVE_PARENT_CONTINUATION')
        rss=int(Path('/proc/self/statm').read_text().split()[1])*os.sysconf('SC_PAGE_SIZE')
        mem={v.split(':')[0]:int(v.split()[1])*1024 for v in Path('/proc/meminfo').read_text().splitlines() if v.startswith(('MemAvailable:','MemTotal:'))}
        self.peak=max(self.peak,rss);self.minimum=mem['MemAvailable'] if self.minimum is None else min(self.minimum,mem['MemAvailable'])
        used=sum(p.stat().st_size for p in self.out.iterdir() if p.is_file());free=os.statvfs(Q.ROOT);cap=C.MODES[self.plan['mode']][2]
        Q.need(rss<8<<30 and mem['MemAvailable']>=max(4<<30,.15*mem['MemTotal']),'RSS_OR_MEMAVAILABLE_SOFT_STOP')
        Q.need(used+(1<<20)<cap and free.f_bavail*free.f_frsize-max(0,cap-used)>=200000000000,'OUTPUT_CAP_OR_CURRENT_FREE_SOFT_STOP')
        Q.need(self.initial_elapsed+now-self.start<self.plan['wall_seconds']-60,'WALL_NATURAL_DRAIN_RESERVE')


def fixtures(out):
    from .test_v1 import Boundaries
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(Boundaries);Q.need(suite.countTestCases()==3,'EXACT3_PURE_FIXTURES')
    stream=io.StringIO();r=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    v={'tests_run':r.testsRun,'failures':len(r.failures),'errors':len(r.errors),'skips':len(r.skipped),
        'expected_failures':len(r.expectedFailures),'unexpected_successes':len(r.unexpectedSuccesses),'transcript':stream.getvalue(),
        'before_archive_and_inventory_bodies':True}
    Q.write_new(out/'fixtures3.json',v);Q.need(r.wasSuccessful() and r.testsRun==3
        and not(r.skipped or r.expectedFailures or r.unexpectedSuccesses),'PURE3_PASS_BEFORE_ANY_ORIGINAL_BODY')
    return v


def verify_file(reference,check):
    p=Path(reference['path']);Q.need(p.is_absolute() and Q.ROOT in p.parents and '..' not in p.parts
        and not any(v.is_symlink() for v in (p,*p.parents)),'OWN_LITERAL_MAIN_DATA_PATH')
    before=p.lstat();Q.need(stat.S_ISREG(before.st_mode) and before.st_uid==1278 and before.st_size==reference['bytes'],'ACTUAL_DATA_OWNER_SIZE')
    h=hashlib.sha256();n=0
    with p.open('rb') as f:
        Q.need(frame(os.fstat(f.fileno()))==frame(before),'SAME_OPEN_FSTAT')
        for block in iter(lambda:f.read(1<<20),b''):check();h.update(block);n+=len(block)
        Q.need(frame(os.fstat(f.fileno()))==frame(before),'DATA_FRAME_AFTER_HASH')
    Q.need(n==reference['bytes'] and h.hexdigest()==reference['sha256'] and frame(p.lstat())==frame(before),'CURRENT_FULL_SHA_FSTAT')
    return frame(before)


class Member:
    def __init__(self,stream,row,check):self.stream,self.row,self.check=stream,row,check;self.n=0;self.h=hashlib.sha256();self.crc=0
    def track(self,b):
        self.n+=len(b);Q.need(self.n<=self.row['decoded_bytes'],'DECODED_MEMBER_LENGTH_BOUND');self.h.update(b);self.crc=zlib.crc32(b,self.crc);return b
    def read(self,n):
        Q.need(type(n) is int and 0<=n<=16<<20,'NO_UNBOUNDED_OR_LARGE_OPCODE_ARGUMENT_READ');self.check();return self.track(self.stream.read(n))
    def readline(self,n=(1<<20)+1):
        Q.need(type(n) is int and 0<n<=(1<<20)+1,'BOUNDED_NATIVE_LINE_READ');self.check();return self.track(self.stream.readline(n))
    def tell(self):return self.n
    def finish(self):
        Q.need(self.n==self.row['decoded_bytes'] and self.h.hexdigest()==self.row['decoded_sha256']
            and self.crc&0xffffffff==self.row['CRC32_observed'],'CURRENT_MEMBER_EOF_CRC_SHA_MATCHES_BOOTSTRAP')
        return {'name':self.row['name'],'decoded_bytes':self.n,'decoded_sha256':self.h.hexdigest(),
            'CRC32':self.crc&0xffffffff,'EOF_CRC_SHA_complete':True}


class DrugLedger:
    def __init__(self,out,check):
        self.check=check;self.log=(out/'source_identity_rows.jsonl').open('xb');self.db=sqlite3.connect(out/'new_job_name_pairing.sqlite')
        self.db.execute('PRAGMA journal_mode=DELETE');self.db.execute('PRAGMA temp_store=FILE');self.db.execute('PRAGMA cache_size=-65536')
        self.db.execute('CREATE TABLE rows(kind TEXT,ordinal INTEGER,name BLOB,id_value BLOB,smiles BLOB,state TEXT,PRIMARY KEY(kind,ordinal))')
        self.pending=[];self.counts=collections.Counter();self.issues=collections.Counter()
    def emit(self,kind,ordinal,name,id_value,smiles,state,details):
        row={'source_id':'marcel_drugs_zip','member':'Drugs.'+('csv' if kind=='CSV' else 'sdf'),'physical_ordinal':ordinal,
            'name_pairing_basis':'EXACT_UNNORMALIZED_BYTES','details':details,'chemical_key_computed':False}
        raw=(json.dumps(row,ensure_ascii=True,separators=(',',':'))+'\n').encode();Q.need(len(raw)<=8<<20,'BOUNDED_DURABLE_IDENTITY_ROW')
        self.log.write(raw);self.pending.append((kind,ordinal,name,id_value,smiles,state));self.counts[kind]+=1;self.issues[state]+=1
        if len(self.pending)>=256:self.flush()
    def flush(self):
        # Original identity log becomes durable before its derivative SQL batch.
        self.log.flush();os.fsync(self.log.fileno());self.db.executemany('INSERT INTO rows VALUES(?,?,?,?,?,?)',self.pending)
        self.db.commit();self.pending=[];self.check()
    def csv(self,ordinal,name,details):self.emit('CSV',ordinal,name,None,None,details['mapping_state'],details)
    def sdf(self,ordinal,name,fields,details):
        self.emit('SDF',ordinal,name,fields['ID'][0] if len(fields['ID'])==1 else None,
            fields['smiles'][0] if len(fields['smiles'])==1 else None,details['format_state'],details)
    def finish(self):
        self.flush();self.log.close();self.db.execute('CREATE INDEX names ON rows(kind,name)');self.db.commit()
        def n(sql):self.check();return self.db.execute(sql).fetchone()[0]
        q={}
        for k in ('CSV','SDF'):
            q[k]={'rows':n("SELECT COUNT(*) FROM rows WHERE kind='"+k+"'"),
                'missing_names':n("SELECT COUNT(*) FROM rows WHERE kind='"+k+"' AND name IS NULL"),
                'empty_names':n("SELECT COUNT(*) FROM rows WHERE kind='"+k+"' AND name=x''"),
                'duplicate_name_groups':n("SELECT COUNT(*) FROM (SELECT name FROM rows WHERE kind='"+k+"' AND name IS NOT NULL GROUP BY name HAVING COUNT(*)>1)")}
        q['SDF_rows_without_exact_CSV_name']=n("SELECT COUNT(*) FROM rows s WHERE s.kind='SDF' AND (s.name IS NULL OR NOT EXISTS(SELECT 1 FROM rows c WHERE c.kind='CSV' AND c.name=s.name))")
        q['CSV_rows_without_exact_SDF_name']=n("SELECT COUNT(*) FROM rows c WHERE c.kind='CSV' AND (c.name IS NULL OR NOT EXISTS(SELECT 1 FROM rows s WHERE s.kind='SDF' AND s.name=c.name))")
        q['SDF_name_groups_with_distinct_smiles_bytes']=n("SELECT COUNT(*) FROM (SELECT name FROM rows WHERE kind='SDF' AND name IS NOT NULL GROUP BY name HAVING COUNT(DISTINCT smiles)>1)")
        q['SDF_duplicate_ID_groups']=n("SELECT COUNT(*) FROM (SELECT id_value FROM rows WHERE kind='SDF' AND id_value IS NOT NULL GROUP BY id_value HAVING COUNT(*)>1)")
        Q.need(q['CSV']['rows']==self.counts['CSV'] and q['SDF']['rows']==self.counts['SDF'],'DURABLE_ALL_PHYSICAL_ROW_CONSERVATION')
        self.db.close();return {'physical_row_counts':dict(self.counts),'format_state_counts':dict(self.issues),'exact_byte_pairing':q,
            'blank_invalid_duplicate_missing_and_orphan_rows_retained':True,'new_job_SQLite_only':True,'chemical_identity_or_stereo_accepted':False}


def observe(plan,out,budget):
    arc=plan['archive_reference'];inv=plan['inventory_reference'];fr=verify_file(arc,budget.check);ifr=verify_file(inv,budget.check)
    Q.need(inv['bytes']<=64<<10,'SMALL_PRODUCER_INVENTORY_AFTER_FIXTURES')
    with Path(inv['path']).open('rb') as index:
        Q.need(frame(os.fstat(index.fileno()))==ifr,'SAME_PRODUCER_INVENTORY_PARSE_FRAME');raw=index.read((64<<10)+1)
        Q.need(len(raw)==inv['bytes'] and hashlib.sha256(raw).hexdigest()==inv['sha256']
            and frame(os.fstat(index.fileno()))==ifr==frame(Path(inv['path']).lstat()),'PARSED_INVENTORY_EXACT_PRODUCER_BYTES')
    rows=[json.loads(x) for x in raw.splitlines()];expected=C.MODES[plan['mode']][1]
    Q.need(len(rows)==len(expected) and {PurePosixPath(r['name']).name for r in rows}==set(expected),'EXACT_ORIGINAL_MEMBER_SET')
    members=[];result=None;ledger=None
    with Path(arc['path']).open('rb') as f:
        Q.need(frame(os.fstat(f.fileno()))==fr,'SAME_HASHED_ARCHIVE_FRAME');pre=A.preflight(f,arc['bytes']);f.seek(0)
        with zipfile.ZipFile(f,'r') as z:
            infos,decoded=A.directory(z,pre,sum(r['decoded_bytes'] for r in rows));Q.need(len(infos)==len(rows),'EXACT_ARCHIVE_INVENTORY_COUNT')
            if plan['mode']=='drugs_identity':ledger=DrugLedger(out,budget.check)
            try:
                for info,row in zip(infos,rows):
                    Q.need(info.filename==row['name'] and info.file_size==row['decoded_bytes'] and info.compress_size==row['compressed_bytes']
                        and info.CRC==row['CRC32_observed'] and not info.is_dir() and row['EOF_CRC_passed'] is True,'EXACT_BOOTSTRAP_MEMBER_DIRECTORY_FIELDS')
                    with z.open(info) as raw_member:
                        stream=Member(raw_member,row,budget.check);base=PurePosixPath(info.filename).name
                        if base=='Kraken.pickle':result=O.inventory(stream,budget.check)
                        elif base=='Drugs.csv':
                            parser=P.NameCSV(ledger.csv)
                            while True:
                                block=stream.read(1<<20)
                                if not block:break
                                parser.feed(block)
                            csv_result=parser.finish()
                        elif base=='Drugs.sdf':sdf_records=P.sdf_rows(stream,ledger.sdf,budget.check)
                        members.append(stream.finish())
                if ledger:
                    result=ledger.finish();ledger=None;result.update(CSV=csv_result,SDF_physical_records=sdf_records,grammar_method_proof=P.grammar_proof())
            finally:
                if ledger:
                    ledger.log.flush();os.fsync(ledger.log.fileno());ledger.log.close();ledger.db.close()
        Q.need(frame(os.fstat(f.fileno()))==fr,'STABLE_ARCHIVE_FRAME_AFTER_ALL_MEMBER_READS')
    Q.need(frame(Path(arc['path']).lstat())==fr,'STABLE_ARCHIVE_PATH_AFTER_OBSERVATION')
    return {'archive_reference':arc,'archive_frame':fr,'producer_inventory_reference':inv,'members':members,'observation':result,
        'all_member_EOF_CRC_SHA_complete':True,'source_graph_stereo_and_population_acceptance':False,'pool_release':False}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',type=Path,required=True);p.add_argument('--startup-proof',type=Path,required=True);a=p.parse_args()
    plan=Q.load(a.plan);b,parents,cap=C.authority(plan);params=C.parameters(plan['mode'])
    Q.need(plan['schema']=='MARCEL_IDENTITY_FORMAT_PROBE_PLAN_V1' and plan['scope_parameters']==params,'EXACT_PROBE_PLAN')
    argv=[Q.PY,'-B','-m',C.MODULE,'--plan',str(a.plan),'--startup-proof',str(a.startup_proof)]
    proof=R.require_startup(a.startup_proof,expected_scope_key=C.KEY,expected_scope_parameters=params,expected_execution_argv=argv,
        expected_source=__file__,expected_kind='analysis',required_references=[Q.pin(a.plan),*parents,plan['cost_decision_reference']])
    req=proof['request'];auth=C.meta(req['queue_authority_reference']);allowed={'compute-0-'+str(n) for n in auth['allowed_nodes']['analysis']}
    Q.need(req['node'] in allowed and req['pilot'] is False and req['wall_seconds']==plan['wall_seconds']
        and type(plan['wall_seconds']) is int and 600<=plan['wall_seconds']<=28800 and plan['wall_seconds']%60==0
        and req['estimated_peak_output_bytes']==cap and req['data_references']==[plan['archive_reference'],plan['inventory_reference']]
        and not req.get('deferred_authority_references'),'EXACT_ANALYSIS_RESOURCE_AND_TWO_DATA_REFS')
    review=C.meta(req['scope']['review']);Q.need(review['source_identity_only_no_pickle_execution_or_pool_release_authorized'] is True,'ROOT_EXACT_LIMITED_PROBE_REVIEW')
    cost=C.meta(plan['cost_decision_reference']);Q.need(cost['status']=='USER_AUTHORIZED' and cost['on_overrun']=='REPORT_AND_CONTINUE'
        and cost['scientific_quality_thresholds_unchanged'] is True,'ACTUAL_COST_QUALITY_AUTHORITY')
    for path in [*(C.HERE/n for n in C.FILES),*(Q.REPO/n for n in C.OLD)]:Q.need(Q.pin(path) in req['source_references'],'ALL_CURRENT_SOURCE_MODULE_PINS')
    Q.need(Path(sys.modules['__main__'].__file__).absolute()==C.HERE/'run.py' and sys.argv==[str(C.HERE/'run.py'),*argv[4:]],'EXACT_PRIMARY_FULL_ARGV')
    out=Path(plan['output_directory']);Q.need(Q.ROOT/'artifacts' in out.parents and not out.exists(),'NEW_PROBE_OUTPUT');out.mkdir(parents=True,mode=0o700)
    budget=Budget(plan,proof,out);gate=None
    try:
        gate=fixtures(out);budget.check(True);result=observe(plan,out,budget);budget.check(True)
        outputs=[]
        for path in sorted(out.iterdir()):
            if path.is_file():
                h=hashlib.sha256();n=0
                with path.open('rb') as f:
                    for block in iter(lambda:f.read(1<<20),b''):budget.check();h.update(block);n+=len(block)
                outputs.append({'path':str(path),'bytes':n,'sha256':h.hexdigest()})
        Q.write_new(out/'receipt.json',{'schema':'MARCEL_IDENTITY_FORMAT_PROBE_RECEIPT_V1','status':'SOURCE_FORMAT_OBSERVATION_COMPLETE_IDENTITY_RELEASE_PENDING',
            'mode':plan['mode'],'job_id':str(proof['job_id']),'uid':1278,'node':req['node'],'endpoint':'202.38.247.57:22',
            'plan_reference':Q.pin(a.plan),'startup_proof_reference':Q.pin(a.startup_proof),'accepted_bootstrap_receipt_reference':plan['accepted_bootstrap_receipt_reference'],
            'accepted_bootstrap_accounting_reference':plan['accepted_bootstrap_accounting_reference'],'fixtures':gate,'result':result,'output_references':outputs,
            'actual_RSS_peak_bytes':budget.peak,'actual_minimum_MemAvailable_bytes':budget.minimum,'actual_python_version':sys.version,
            'new_actual_terminal_cost':'PENDING_ROOT_ACCOUNTING','cost_overrun_action':'REPORT_AND_CONTINUE','native_graph_stereo_full_identity_or_pool_release':False})
        return 0
    except BaseException as exc:
        Q.write_new(out/'failure.json',{'schema':'MARCEL_IDENTITY_FORMAT_PROBE_FAILURE_V1','error':type(exc).__name__+': '+str(exc),
            'traceback':traceback.format_exc(),'fixtures':gate,'all_partial_outputs_retained':True,'identity_acceptance':False,'actual_cost':'PENDING_ROOT_ACCOUNTING'})
        raise


if __name__=='__main__':raise SystemExit(main())
