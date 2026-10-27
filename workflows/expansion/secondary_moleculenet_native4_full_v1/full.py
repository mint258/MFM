"""Closed-context readback and routing; original native worker objects stay unchanged."""
import collections,concurrent.futures as cf,hashlib,importlib,json,os,sqlite3,stat,sys
from pathlib import Path
from urllib.parse import quote
from secondary_moleculenet_csv6_identity_v1 import journal as J
from secondary_native4_key_journal_audit_v1 import reducer as A
from . import contracts as C
Q=C.Q


def frame(s):return (s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns,s.st_uid)
def decode(raw):return json.loads(raw,object_pairs_hook=A.pairs_unique,parse_constant=lambda x:(_ for _ in ()).throw(ValueError('NONFINITE_JSON')))
def need(value,message):Q.need(value,message)


def coverage(census,observed,ids,reused):
    need(all(observed.get((s,k),0)==census[s][k] for s in C.IDS for k in ('SDF','MOL2')) and
        all(ids.get(s,0)==census[s]['IDs'] for s in C.IDS) and dict(reused)==C.REUSED,'ALL_PHYSICAL_NATIVE_IDS_AND_REUSE_COUNTS')
    need(sum(census[s]['SDF'] for s in C.IDS)==C.N and sum(C.NEW.values())==C.MAX_NEW,'PHYSICAL39633_NOT_ENTITY_DEDUP')


def route(record_id,reused,claimed):
    if record_id in reused:
        need(record_id not in claimed,'REUSED_PROFILE_MUST_NEVER_BE_NEW_CLAIM');return 'PROFILE_REUSE'
    need(record_id not in claimed,'CLAIMED_WITHOUT_REUSABLE_RESULT_HOLD_NO_RETRY');return 'NEW_CALL'


def aggregate(members):
    keys=set();wp=set();unknown=[];seen=set();counts=collections.Counter()
    for row,result in members:
        physical=(row['source_id'],row['format'],row['source_format_ordinal']);need(physical not in seen,'NO_PHYSICAL_MEMBER_DEDUP_OR_DUPLICATE');seen.add(physical);counts[row['source_id']]+=1
        if row['format']=='MOL2':
            need(result is None,'NO_MOL2_GRAPH_RESULT_CREATED');unknown.append({'physical_identity':list(physical),'reason':'MOL2_GRAPH_CHARGE_STEREO_UNKNOWN',
                'native_non_H_composition_evidence':row['native_non_H_composition_evidence']});continue
        need(result is not None and result['source']==row,'EVERY_SDF_HAS_EXACT_ORIGINAL_RESULT');keys.update(result['observed_full_key_union']);wp.update(result['WP5_key_union'])
        if result['has_unknown']:unknown.append({'physical_identity':list(physical),'reason':'SDF_GRAPH_OR_PRESENT_VARIANT_OR_TECHNICAL_UNKNOWN',
            'native_non_H_composition_evidence':row['native_non_H_composition_evidence']})
    return {'physical_record_count':len(seen),'source_component_counts':dict(counts),'all_observed_full_key_union':sorted(keys),'all_observed_WP5_union':sorted(wp),
        'unresolved_variant_composition_evidence':unknown,'same_ID_implies_same_graph':False,'automatic_composition_exclusion_for_known_key_entity':False,
        'MOL2_partial_charge_is_formal_charge':False,'full_or_pool_acceptance':False}


def view_observation(source,value,origin,segment,functions):
    variants={k for v in value.get('variant_observations',[]) for k in v['full_keys']}
    row=source['original_native_source']
    return {'source':source,'physical_identity':Q.canonical([row['source_id'],row['format'],row['source_format_ordinal']]).decode(),
        'SMILES_derived_full_keys':sorted(variants),'WP5_keys':sorted({functions['wp5_key'](k) for k in variants}),
        'key_state':'SOURCE_SMILES_KEYS_ONLY_NATIVE_RESULT_SEPARATE','missing_full_key':not variants,
        'native_result':value,'all_native_and_source_key_union':value['observed_full_key_union'],'native_union_missing':not value['observed_full_key_union'],
        'authoritative_native_result_segment':segment,'origin':origin,'Parquet_full_keys_means_source_SMILES_only':True,'full_or_pool_acceptance':False}


class Inputs:
    def __init__(self,refs,budget):
        self.refs=refs;self.budget=budget;self.files=[];self.frames=[];self.db=None
        try:
            for ref in refs:
                p=Q.literal(ref['path']);need(not any(v.is_symlink() for v in (p,*p.parents)),'ONLY_LITERAL_CLOSED_SOURCE_FILE')
                s=p.lstat();need(stat.S_ISREG(s.st_mode) and s.st_uid==1264 and s.st_size==ref['bytes'],'EXACT_CLOSED_SOURCE_OWNER_AND_SIZE')
                f=p.open('rb');self.files.append(f);fr=frame(s);self.frames.append(fr);need(frame(os.fstat(f.fileno()))==fr,'OPENED_SAME_SOURCE_FRAME')
                h=hashlib.sha256();n=0
                while True:
                    budget.check();b=f.read(1<<20)
                    if not b:break
                    n+=len(b);need(n<=ref['bytes'],'BOUNDED_CLOSED_SOURCE_SIZE');h.update(b)
                need(n==ref['bytes'] and h.hexdigest()==ref['sha256'] and frame(os.fstat(f.fileno()))==fr==frame(p.lstat()),'FIVE_CURRENT_WHOLE_SHA_STABLE_FD_BEFORE_BODY_DECODE');f.seek(0)
            index=Path(refs[2]['path'])
            for suffix in ('-wal','-shm','-journal'):need(not Path(str(index)+suffix).exists(),'CLOSED_INDEX_NO_SIDECAR_NOT_ACTIVE_SQLITE')
            uri='file:'+quote('/proc/self/fd/'+str(self.files[2].fileno()),safe='/')+'?mode=ro&immutable=1'
            self.db=sqlite3.connect(uri,uri=True);self.db.execute('PRAGMA query_only=ON');self.db.execute('PRAGMA temp_store=MEMORY')
            need(self.db.execute('PRAGMA integrity_check').fetchall()==[('ok',)],'CLOSED_ORIGINAL_SQLITE_INTEGRITY')
            schemas={'records':['id','source','kind','ordinal','pdb','body','offset','bytes','sha'],'ids':['source','ordinal','value','details'],
                'keys':['id','fullkey','wp5'],'results':['id','unknown'],'entity_members':['entity','record_id']}
            for name,cols in schemas.items():need([r[1] for r in self.db.execute('PRAGMA table_info('+name+')')]==cols,'EXACT_ORIGINAL_RECORD_INDEX_SCHEMA:'+name)
            self.check()
        except BaseException:self.close();raise

    def check(self):
        for ref,f,fr in zip(self.refs,self.files,self.frames):need(frame(os.fstat(f.fileno()))==fr==frame(Path(ref['path']).lstat()),'ALL_ORIGINAL_FD_AND_PATH_FRAMES_UNCHANGED')

    def lines(self,index):
        f=self.files[index];f.seek(0);offset=0;h=hashlib.sha256()
        while True:
            self.budget.check();raw=f.readline(C.LINE_CAP+1)
            if not raw:break
            need(len(raw)<=C.LINE_CAP and raw.endswith(b'\n'),'WHOLE_BOUNDED_DURABLE_SOURCE_LINE');h.update(raw)
            locator={'input_reference':self.refs[index],'offset':offset,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()};offset+=len(raw)
            yield decode(raw),locator
        need(offset==self.refs[index]['bytes'] and h.hexdigest()==self.refs[index]['sha256'],'COMPLETE_SECOND_PASS_SOURCE_SHA_AND_EOF');self.check()

    def raw(self,row):
        segment=row['own_raw_blob_segment'];n=segment['bytes'];need(0<n<=1<<20 and segment['sha256']==row['raw_record_sha256'] and n==row['raw_record_bytes'],'EXACT_ORIGINAL_NATIVE_SEGMENT')
        self.budget.check();f=self.files[0];f.seek(segment['offset']);raw=f.read(n)
        need(len(raw)==n and hashlib.sha256(raw).hexdigest()==segment['sha256'] and frame(os.fstat(f.fileno()))==self.frames[0],'SAME_FD_NATIVE_BYTES_NO_REPAIR');return raw

    def selection(self):
        ref=self.refs[4];need(ref['bytes']<=2<<20,'BOUNDED_ORIGINAL3195_SELECTION_DATA');f=self.files[4];f.seek(0);raw=f.read(ref['bytes']+1)
        need(len(raw)==ref['bytes'] and hashlib.sha256(raw).hexdigest()==ref['sha256'],'SAME_FD_SELECTION_CURRENT_SHA');v=decode(raw)
        need(v['actual_SDF_N']==C.SDF and v['seed']==20261026 and v['Python']=='3.11.14','EXACT_ACTUAL39633_POPULATION_NOT_ENTITY_COUNT')
        selected=v['selected_actual_ordinals'];need(set(selected)==set(C.IDS),'ALL_FOUR_ORIGINAL_SELECTION_LISTS')
        for sid in C.IDS:need(len(selected[sid])==C.REUSED[sid] and selected[sid]==sorted(set(selected[sid]))
            and all(type(n) is int and 0<=n<C.SDF[sid] for n in selected[sid]),'EXACT_ORIGINAL_UNIFORM_SELECTION_NO_RESAMPLING')
        self.check();return {s:set(selected[s]) for s in C.IDS}

    def close(self):
        if self.db:self.db.close();self.db=None
        for f in self.files:f.close()
        self.files=[]


class Ledger:
    def __init__(self,out,budget):
        self.out,self.budget=out,budget;self.db=sqlite3.connect(out/'full_inventory_index.sqlite')
        self.db.execute('PRAGMA journal_mode=MEMORY');self.db.execute('PRAGMA temp_store=MEMORY')
        self.db.executescript('CREATE TABLE context(id INTEGER PRIMARY KEY,source TEXT,kind TEXT,ordinal INTEGER,source_segment TEXT);'
            'CREATE TABLE old_result(id INTEGER PRIMARY KEY,value TEXT,input_segment TEXT);'
            'CREATE TABLE finished(id INTEGER PRIMARY KEY,unknown INTEGER,origin TEXT,segment TEXT);'
            'CREATE TABLE keys(id INTEGER,key TEXT,wp5 TEXT,PRIMARY KEY(id,key));'
            'CREATE TABLE claims(id INTEGER PRIMARY KEY,state TEXT);')
        self.result_path=out/'native_key_results.jsonl';self.result_file=self.result_path.open('xb');self.claim_file=(out/'new_record_claims.jsonl').open('xb')
        self.writer=J.Writer(out,budget);self.functions=None;self.claimed=set();self.reused=set();self.done=collections.Counter();self.origins=collections.Counter();self.unknown=collections.Counter();self.has_keys=collections.Counter();self.workers=collections.Counter();self.closed=False

    def context(self,record_id,row,locator):self.db.execute('INSERT INTO context VALUES(?,?,?,?,?)',(record_id,row['source_id'],row['format'],row['source_format_ordinal'],Q.canonical(locator).decode()))

    def old(self,record_id,value,locator):
        need(record_id not in self.reused,'OLD_PROFILE_RESULT_UNIQUE');self.reused.add(record_id)
        self.db.execute('INSERT INTO old_result VALUES(?,?,?)',(record_id,Q.canonical(value).decode(),Q.canonical(locator).decode()))

    def source(self,record_id,row):
        return {'source_id':row['source_id'],'source_row_ordinal':row['source_format_ordinal'],'role':row['role'],'source_offset':row['own_raw_blob_segment']['offset'],
            'source_record_bytes':row['raw_record_bytes'],'source_record_sha256':row['raw_record_sha256'],'original_record_id':record_id,'original_native_source':row}

    def claim(self,record_id,row):
        need(route(record_id,self.reused,self.claimed)=='NEW_CALL','ONLY_UNSELECTED_SOURCE_CAN_BE_NEW_CLAIM');self.budget.check()
        self.writer.dispatch(self.source(record_id,row))
        J.append(self.claim_file,{'event':'CLAIM_DURABLE_BEFORE_ORIGINAL_KEY_WORK_SUBMIT','record_id':record_id,'source':row,'no_automatic_retry':True},self.budget)
        self.claimed.add(record_id);self.db.execute('INSERT INTO claims VALUES(?,?)',(record_id,'CLAIMED'))

    def complete(self,record_id,row,value,origin,input_segment=None,invocation=None):
        need(value['source']==row and origin in ('PROFILE_REUSE','NEW_CALL'),'EXACT_ORIGINAL_WORKER_SOURCE_AND_ORIGIN')
        if origin=='PROFILE_REUSE':need(route(record_id,self.reused,self.claimed)=='PROFILE_REUSE','OLD_SUCCESS_OR_UNKNOWN_NEVER_REDISPATCH');self.writer.dispatch(self.source(record_id,row))
        else:need(record_id in self.claimed and record_id not in self.reused,'REAL_NEW_RECORD_CLAIM')
        offset=self.result_file.tell();event={'event':'ORIGINAL_RESULT_DURABLE_BEFORE_FULL_INDEX_OR_UNION','record_id':record_id,'origin':origin,
            'profile_result_input_segment':input_segment,'invocation_observation':invocation,'result':value,'result_object_canonical_sha256':hashlib.sha256(Q.canonical(value)).hexdigest()}
        raw=Q.canonical(event)+b'\n';J.append(self.result_file,event,self.budget);segment={'path':str(self.result_path),'offset':offset,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
        observation=view_observation(self.source(record_id,row),value,origin,segment,self.functions)
        # The frozen Writer's full_keys column keeps its source-SMILES meaning;
        # native results are never renamed as SMILES-derived observations.
        self.writer.complete({'observation':observation,'worker_pid':value.get('worker_pid')})
        self.db.execute('INSERT INTO finished VALUES(?,?,?,?)',(record_id,int(value['has_unknown']),origin,Q.canonical(segment).decode()))
        wp=value['WP5_key_union'];keys=value['observed_full_key_union']
        for key in keys:self.db.execute('INSERT INTO keys VALUES(?,?,?)',(record_id,key,self.functions['wp5_key'](key)))
        need(sorted({self.functions['wp5_key'](k) for k in keys})==wp,'ORIGINAL_FROZEN_FULLKEY_TO_WP5_RELATION_RETAINED')
        if origin=='NEW_CALL':self.db.execute('UPDATE claims SET state=? WHERE id=?',('RESULT_DURABLE',record_id))
        sid=row['source_id'];self.done[sid]+=1;self.origins[(sid,origin)]+=1;self.unknown[sid]+=bool(value['has_unknown']);self.has_keys[sid]+=bool(keys);self.workers[str(value.get('worker_pid'))]+=1
        if sum(self.done.values())%128==0:self.db.commit()

    def result(self,record_id):
        v=self.db.execute('SELECT segment FROM finished WHERE id=?',(record_id,)).fetchone();need(v is not None,'ALL_SDF_HAVE_DURABLE_RESULT_SEGMENT');segment=decode(v[0])
        with self.result_path.open('rb') as f:f.seek(segment['offset']);raw=f.read(segment['bytes'])
        need(hashlib.sha256(raw).hexdigest()==segment['sha256'],'DURABLE_RESULT_SEGMENT_READBACK');return decode(raw)['result'],segment

    def close(self):
        if self.closed:return None
        self.db.commit();self.writer.close();self.result_file.flush();os.fsync(self.result_file.fileno());self.result_file.close();self.claim_file.flush();os.fsync(self.claim_file.fileno());self.claim_file.close();self.db.close();self.closed=True
        return {'native_result_journal':J.pin(self.result_path),'record_claim_journal':J.pin(self.out/'new_record_claims.jsonl'),
            'record_key_result_index':J.pin(self.out/'full_inventory_index.sqlite'),'CSV6_view_journal':J.pin(self.out/'identity_events.jsonl'),
            'CSV6_compatibility_Parquet':J.pin(self.out/'identity_observations.parquet'),'Parquet_full_keys_are_source_SMILES_only':True}


def bind_context(inputs,ledger,census):
    db=inputs.db;counts=collections.Counter();ids=collections.Counter();seen=set();index_seen=set()
    for value,locator in inputs.lines(1):
        kind=value['event']
        if kind=='ORIGINAL_NATIVE_BYTES_AND_ROW_DURABLE_BEFORE_INDEX':
            row=value['source'];sid=row['source_id'];form=row['format'];ordinal=row['source_format_ordinal'];key=(sid,form,ordinal)
            need(sid in C.IDS and form in ('SDF','MOL2') and key not in seen,'UNIQUE_ALL_NATIVE_SOURCE_CONTEXT');seen.add(key)
            found=db.execute('SELECT id,body,offset,bytes,sha FROM records WHERE source=? AND kind=? AND ordinal=?',key).fetchall();need(len(found)==1,'ONE_ORIGINAL_NATIVE_INDEX_RECORD')
            rid,text,offset,n,sha=found[0];need(decode(text)==row and row['own_raw_blob_segment']=={'offset':offset,'bytes':n,'sha256':sha},'RAW_BLOB_INDEX_AND_DURABLE_SOURCE_LITERAL_EQUAL')
            inputs.raw(row);ledger.context(rid,row,locator);counts[(sid,form)]+=1
        else:
            need(kind=='ORIGINAL_INDEX_ID_DURABLE_BEFORE_INDEX','ONLY_NATIVE_AND_ORIGINAL_INDEX_EVENTS');sid=value['source_id'];ordinal=value['ordinal'];key=(sid,ordinal)
            need(key not in index_seen and sid in C.IDS,'ALL_INDEX_ID_ORDINALS_PRESERVED');index_seen.add(key)
            found=db.execute('SELECT value,details FROM ids WHERE source=? AND ordinal=?',key).fetchall()
            need(len(found)==1 and decode(found[0][0])==value['ID'] and decode(found[0][1])==value['details'],'LITERAL_ORIGINAL_ID_AND_DETAILS_NOT_ASSAY_VALUES');ids[sid]+=1
    cursor=0;record_counts=collections.Counter()
    for sid,form,offset,n in db.execute('SELECT source,kind,offset,bytes FROM records ORDER BY offset'):
        need(offset==cursor and n>0,'ENTIRE_RAW_BLOB_CONTIGUOUS_NO_GAP_OVERLAP');cursor+=n;record_counts[(sid,form)]+=1
    need(cursor==inputs.refs[0]['bytes'] and dict(record_counts)==dict(counts),'NO_UNJOURNALED_NATIVE_BLOB_OR_INDEX_RECORD')
    need(db.execute('SELECT COUNT(*) FROM ids').fetchone()[0]==sum(ids.values()),'NO_UNJOURNALED_ID_ROWS')
    need(db.execute('SELECT COUNT(*) FROM entity_members').fetchone()[0]==sum(counts.values()) and
        db.execute('SELECT COUNT(*) FROM records r LEFT JOIN entity_members e ON r.id=e.record_id WHERE e.record_id IS NULL').fetchone()[0]==0,
        'EVERY_NATIVE_PHYSICAL_RECORD_IN_ORIGINAL_ENTITY_CONTEXT')
    return counts,ids


def bind_profile(inputs,ledger,selected):
    audit=A.Reducer(C.REUSED,C.SDF,32);counts=collections.Counter()
    for value,locator in inputs.lines(3):
        pair=audit.feed(value,locator)
        if pair is None:continue
        sid,ordinal=pair['key'];need(ordinal in selected[sid],'ONLY_ORIGINAL_SELECTED_ORDINALS_REUSED')
        found=inputs.db.execute("SELECT id,body FROM records WHERE source=? AND kind='SDF' AND ordinal=?",(sid,ordinal)).fetchall()
        need(len(found)==1 and decode(found[0][1])==pair['source'],'OLD_RESULT_SOURCE_EQUALS_CLOSED_FULL_RECORD_INDEX');rid=found[0][0];result=pair['result']
        old=inputs.db.execute('SELECT unknown FROM results WHERE id=?',(rid,)).fetchall();need(old==[(int(result['has_unknown']),)],'ORIGINAL_SELECTED_RESULT_INDEX_STATUS')
        keys=inputs.db.execute('SELECT fullkey,wp5 FROM keys WHERE id=? ORDER BY fullkey',(rid,)).fetchall()
        need([k for k,w in keys]==result['observed_full_key_union'] and sorted({w for k,w in keys})==result['WP5_key_union'],'ORIGINAL_SELECTED_KEY_INDEX_EQUALS_RESULT_JOURNAL')
        ledger.old(rid,result,locator);counts[sid]+=1
    report=audit.finish();need(len(ledger.reused)==3195 and dict(counts)==C.REUSED,'ALL_OLD_SUCCESS_AND_UNKNOWN_REUSED_ONCE');return counts,report


def register_once(plan,proof,out):
    path=Q.literal(plan['population_once_path']);need(path==ROOT_ONCE(plan),'FIXED_SCIENCE_POPULATION_ONCE_REGISTRY')
    path.parent.mkdir(parents=True,exist_ok=True);raw=Q.canonical({'schema':'NATIVE4_FULL_POPULATION_ONCE_V1','science_fingerprint':C.fingerprint(plan),
        'job_id':str(proof['job_id']),'uid':1264,'endpoint':Q.ENDPOINT,'node':plan['node'],'output_directory':str(out),
        'plan_reference':proof['plan_reference'],'startup_proof_reference':Q.ref(plan['startup_proof_path']),'no_automatic_retry':True})+b'\n'
    need(len(raw)<=C.ADMIN,'BOUNDED_ADMIN_ONCE_WITHIN_WHOLE_CAP')
    try:fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    except FileExistsError:raise RuntimeError('EXISTING_FULL_POPULATION_ATTEMPT_HOLD_NO_AUTOMATIC_RETRY')
    with os.fdopen(fd,'wb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
    return Q.ref(path)


def ROOT_ONCE(plan):return C.ROOT/'control/native4_full_once_v1'/('population_'+C.fingerprint(plan)+'.json')


def load_native(plan):
    native=importlib.import_module('secondary_moleculenet_native4_identity_v1.native');need(Path(native.__file__).absolute()==C.OLD/'native.py'
        and Q.ref(native.__file__) in plan['source_references'],'DIRECT_UNCHANGED_ORIGINAL_NATIVE_WORKER_FILE')
    functions,proof=native.load(plan)
    return native,functions,proof


def worker_initialize(plan,logs):
    # Only I/O wrapping: old initialize and key_work objects and kwargs unchanged.
    directory=Path(logs);directory.mkdir(parents=True,exist_ok=True)
    for fd,name in ((1,'stdout'),(2,'stderr')):
        f=os.open(directory/(str(os.getpid())+'.'+name+'.txt'),os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600);os.dup2(f,fd);os.close(f)
    native=importlib.import_module('secondary_moleculenet_native4_identity_v1.native');native.initialize(plan)


def work(record_id,row,raw,logs):
    native=importlib.import_module('secondary_moleculenet_native4_identity_v1.native');path=Path(logs)/(str(os.getpid())+'.calls.jsonl')
    proof={'record_id':record_id,'worker_pid':os.getpid(),'uid':os.getuid(),'job_id':os.environ.get('SLURM_JOB_ID'),
        'function_module':native.key_work.__module__,'function_filename':native.key_work.__code__.co_filename,'function_first_line':native.key_work.__code__.co_firstlineno,
        'source_sha256':row['raw_record_sha256']}
    with path.open('ab') as f:
        f.write(Q.canonical({'event':'OLD_KEY_WORK_CALL_INTENT_DURABLE','proof':proof})+b'\n');f.flush();os.fsync(f.fileno())
        result=native.key_work(row,raw)
        returned={**proof,'original_function_return_observed':True,'original_result_canonical_sha256':hashlib.sha256(Q.canonical(result)).hexdigest()}
        f.write(Q.canonical({'event':'OLD_KEY_WORK_RETURN_DURABLE','proof':returned})+b'\n');f.flush();os.fsync(f.fileno())
    return {'original_result':result,'invocation_observation':returned}


def key_inventory(plan,inputs,ledger,budget,native):
    import multiprocessing as mp
    pending={};new=collections.Counter({s:0 for s in C.IDS});native_returns=collections.Counter({s:0 for s in C.IDS});technical=collections.Counter({s:0 for s in C.IDS});new_workers=collections.Counter()
    def collect(all_rows):
        while pending:
            done,_=cf.wait(pending,timeout=1,return_when=cf.FIRST_COMPLETED)
            for future in done:
                rid,row=pending.pop(future)
                invocation=None;returned=None
                try:
                    returned=future.result();value=returned['original_result'];invocation=returned['invocation_observation'];need(value['source']==row
                        and invocation['original_function_return_observed'] is True and invocation['original_result_canonical_sha256']==hashlib.sha256(Q.canonical(value)).hexdigest()
                        and invocation['uid']==1264 and invocation['job_id']==os.environ['SLURM_JOB_ID'] and invocation['worker_pid']==value['worker_pid']
                        and invocation['function_filename']==str(C.OLD/'native.py'),
                        'ORIGINAL_WORKER_RETURN_SOURCE_AND_NATIVE_RESULT_HASH');native_returns[row['source_id']]+=1;new_workers[str(value['worker_pid'])]+=1
                except Exception as exc:
                    value={'source':row,'observed_full_key_union':[],'WP5_key_union':[],'has_unknown':True,'technical_error':repr(exc),'worker_pid':None,'worker_CPU_seconds':None,
                        'unvalidated_worker_return_preserved_not_accepted':returned}
                    invocation={'original_function_return_observed':'UNKNOWN','no_automatic_retry':True};technical[row['source_id']]+=1
                ledger.complete(rid,row,value,'NEW_CALL',invocation=invocation);new[row['source_id']]+=1
            if done and not all_rows:return
    with cf.ProcessPoolExecutor(max_workers=16,mp_context=mp.get_context('spawn'),initializer=worker_initialize,initargs=(plan,str(ledger.out/'worker_logs'))) as pool:
        try:
            for rid,text in inputs.db.execute("SELECT id,body FROM records WHERE kind='SDF' ORDER BY source,ordinal"):
                budget.check();row=decode(text);action=route(rid,ledger.reused,ledger.claimed)
                if action=='PROFILE_REUSE':
                    old=ledger.db.execute('SELECT value,input_segment FROM old_result WHERE id=?',(rid,)).fetchone();need(old is not None,'FULL_OLD_PROFILE_RESULT_PRESENT')
                    ledger.complete(rid,row,decode(old[0]),'PROFILE_REUSE',decode(old[1]));continue
                raw=inputs.raw(row);ledger.claim(rid,row);budget.check();need(len(ledger.claimed)<=C.MAX_NEW,'MAX36438_NEW_WORKER_CALLS')
                pending[pool.submit(work,rid,row,raw,str(ledger.out/'worker_logs'))]=(rid,row)
                if len(pending)>=32:collect(False)
        finally:collect(True)
    need(dict(new)==C.NEW and dict(ledger.done)==C.SDF and len(ledger.claimed)==C.MAX_NEW,'FULL39633_RESULTS_3195REUSE_36438NEW')
    return {'new_dispatched_task_results_by_source':dict(new),'new_claimed_tasks':sum(new.values()),'native_function_returns_observed_by_source':dict(native_returns),
        'technical_results_with_native_return_unknown_by_source':dict(technical),'actual_new_function_calls_upper_bound':sum(new.values()),'reused_profile_results':3195,
        'result_counts':dict(ledger.done),'has_unknown_counts':dict(ledger.unknown),'any_key_counts':dict(ledger.has_keys),'new_worker_return_counts_by_PID':dict(new_workers),
        'workers_by_result_origin_mixed_PID_space':dict(ledger.workers)}


def unions(inputs,ledger,out,budget):
    path=out/'full_entity_key_unions.jsonl';f=path.open('xb');entities=0;physical=0
    try:
        for (entity,) in inputs.db.execute('SELECT DISTINCT entity FROM entity_members ORDER BY entity'):
            budget.check();members=[];references=[]
            for rid,text in inputs.db.execute('SELECT r.id,r.body FROM records r JOIN entity_members e ON r.id=e.record_id WHERE e.entity=? ORDER BY r.id',(entity,)):
                row=decode(text);physical+=1;result,seg=ledger.result(rid) if row['format']=='SDF' else (None,None);members.append((row,result))
                references.append({'record_id':rid,'source_id':row['source_id'],'kind':row['format'],'ordinal':row['source_format_ordinal'],
                    'original_source_segment':decode(ledger.db.execute('SELECT source_segment FROM context WHERE id=?',(rid,)).fetchone()[0]),'native_result_segment':seg})
            J.append(f,{'entity_identity':decode(entity),'members':references,**aggregate(members)},budget);entities+=1
    finally:f.flush();os.fsync(f.fileno());f.close()
    return {'reference':J.pin(path),'entities':entities,'physical_native_records':physical,'entity_and_physical_SDF_populations_are_distinct_count_axes':True,'all_contexts_retained':True,'scientific_acceptance':False}


def index_relations(inputs,out,budget):
    path=out/'all_original_index_identity_relations.jsonl';f=path.open('xb');counts=collections.Counter();unmatched=collections.Counter()
    try:
        for sid,ordinal,text,details in inputs.db.execute('SELECT source,ordinal,value,details FROM ids ORDER BY source,ordinal'):
            budget.check();value=decode(text);native=[]
            if sid=='qm8_sdf':native=inputs.db.execute("SELECT e.entity FROM records r JOIN entity_members e ON r.id=e.record_id WHERE r.source=? AND r.kind='SDF' AND r.ordinal=?",(sid,ordinal)).fetchall()
            elif value.get('state')=='LITERAL_UTF8' and isinstance(value.get('text'),str):
                entity=Q.canonical(['PDB_ID_ALL_COMPONENTS',value['text']]).decode();native=inputs.db.execute('SELECT DISTINCT entity FROM entity_members WHERE entity=?',(entity,)).fetchall()
            matched=[decode(v) for v in sorted({v[0] for v in native})]
            J.append(f,{'source_id':sid,'original_index_ordinal':ordinal,'original_ID':value,'original_details':decode(details),
                'matching_existing_native_entities':matched,'relation_basis':'ORIGINAL_ORDINAL_OR_EXACT_LITERAL_PDB_ID_ONLY_NOT_GRAPH_EQUIVALENCE',
                'no_native_context_in_all_components':not native,'graph_charge_stereo_if_no_native':'UNKNOWN','same_ID_implies_same_graph':False,
                'original_index_row_not_dropped':True,'full_or_pool_release':False},budget);counts[sid]+=1;unmatched[sid]+=not native
    finally:f.flush();os.fsync(f.fileno());f.close()
    return {'reference':J.pin(path),'all_ID_rows_by_source':dict(counts),'ID_rows_without_matching_existing_native_context':dict(unmatched),'all_IDs_preserved':True,'mapping_is_identity_acceptance':False}
