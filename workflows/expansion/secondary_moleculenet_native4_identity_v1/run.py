"""All physical native relationships, then bounded keys; no automatic full stage."""
import argparse,collections,concurrent.futures as cf,gzip,hashlib,io,json,multiprocessing as mp,os,sqlite3,time,traceback,unittest
from pathlib import Path
import tarfile
from secondary_external_sources_acquisition_v1.run import StrictTarInfo,Expanded,source_hash
from secondary_moleculenet_csv6_identity_v1.runtime import Budget
from secondary_moleculenet_csv6_identity_v1 import journal as J
from secondary_missing11_identity_format_probe_v1.formats import classify_member
from . import contracts as C,guard as G,native as N
Q=C.Q


def fixtures(out,budget,plan):
    from .test_v1 import Boundaries
    functions,proof=N.load(plan);Boundaries.functions=functions;N.FUNCTIONS=functions
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(Boundaries);Q.need(suite.countTestCases()==3,'EXACT_NEW3_PURE_METHODS')
    s=io.StringIO();r=unittest.TextTestRunner(stream=s,verbosity=2).run(suite);value={'tests_run':r.testsRun,'failures':len(r.failures),'errors':len(r.errors),
        'skips':len(r.skipped),'expected_failures':len(r.expectedFailures),'unexpected_successes':len(r.unexpectedSuccesses),'transcript':s.getvalue(),
        'kernel_function_proof':proof,'before_original_DATA':True,'old_B3_reexecuted':False}
    J.write_json(out/'fixtures3.json',value,budget);Q.need(r.wasSuccessful() and r.testsRun==3 and not(r.skipped or r.expectedFailures or r.unexpectedSuccesses),'PURE3_BEFORE_ALL_ORIGINAL_DATA');return value,functions


class Member:
    def __init__(self,f,expected,budget):self.f,self.expected,self.budget=f,expected,budget;self.n=0;self.h=hashlib.sha256()
    def track(self,b):self.n+=len(b);Q.need(self.n<=self.expected['declared_bytes'],'CURRENT_MEMBER_DECLARED_BOUND');self.h.update(b);return b
    def read(self,n):Q.need(0<=n<=1<<20,'BOUNDED_MEMBER_READ');self.budget.check();return self.track(self.f.read(n))
    def readline(self,n):Q.need(0<n<=C.NATIVE_CAP+1,'BOUNDED_NATIVE_LINE');self.budget.check();return self.track(self.f.readline(n))
    def finish(self):Q.need(self.n==self.expected['declared_bytes'] and self.h.hexdigest()==self.expected['regular_member_sha256'],'ALL_MEMBER_CURRENT_BYTES_AND_SHA')


class Ledger:
    def __init__(self,out,budget):
        self.out,self.budget=out,budget;self.log=(out/'source_rows.jsonl').open('xb');self.blob=(out/'native_records.raw').open('xb');self.offset=0;self.counts=collections.Counter();self.compositions=collections.Counter()
        self.db=sqlite3.connect(out/'native_relationships.sqlite');self.db.execute('PRAGMA journal_mode=MEMORY');self.db.execute('PRAGMA temp_store=MEMORY')
        self.db.executescript('CREATE TABLE records(id INTEGER PRIMARY KEY,source TEXT,kind TEXT,ordinal INTEGER,pdb TEXT,body TEXT,offset INTEGER,bytes INTEGER,sha TEXT);'
            'CREATE UNIQUE INDEX physical ON records(source,kind,ordinal);'
            'CREATE TABLE ids(source TEXT,ordinal INTEGER,value TEXT,details TEXT);CREATE TABLE keys(id INTEGER,fullkey TEXT,wp5 TEXT,PRIMARY KEY(id,fullkey));'
            'CREATE TABLE results(id INTEGER PRIMARY KEY,unknown INTEGER);')
    def source(self,row,raw):
        self.budget.check(len(raw));segment={'offset':self.offset,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
        self.blob.write(raw);self.blob.flush();os.fsync(self.blob.fileno());self.offset+=len(raw)
        value={**row,'own_raw_blob_segment':segment};J.append(self.log,{'event':'ORIGINAL_NATIVE_BYTES_AND_ROW_DURABLE_BEFORE_INDEX','source':value},self.budget)
        self.db.execute('INSERT INTO records(source,kind,ordinal,pdb,body,offset,bytes,sha) VALUES(?,?,?,?,?,?,?,?)',
            (row['source_id'],row['format'],row['source_format_ordinal'],row['native_PDB_path_ID'],Q.canonical(value).decode(),segment['offset'],segment['bytes'],segment['sha256']))
        self.counts[(row['source_id'],row['format'])]+=1
        self.compositions[(row['source_id'],row['format'],'available' if row['native_non_H_composition_evidence'] is not None else 'UNKNOWN')]+=1
    def identifier(self,source,ordinal,raw,details):
        value=N.token(raw);J.append(self.log,{'event':'ORIGINAL_INDEX_ID_DURABLE_BEFORE_INDEX','source_id':source,'ordinal':ordinal,'ID':value,'details':details},self.budget)
        self.db.execute('INSERT INTO ids VALUES(?,?,?,?)',(source,ordinal,Q.canonical(value).decode(),Q.canonical(details).decode()))
    def close_sources(self):
        self.log.flush();os.fsync(self.log.fileno());self.log.close();self.blob.flush();os.fsync(self.blob.fileno());self.blob.close();self.db.commit()
    def relations(self):
        rows=[]
        for source in C.IDS:
            native=self.counts[(source,'SDF')];indices=self.db.execute('SELECT count(*) FROM ids WHERE source=?',(source,)).fetchone()[0]
            missing=orphan=invalid=None
            bad=0
            for value,details in self.db.execute('SELECT value,details FROM ids WHERE source=?',(source,)):
                v=json.loads(value);d=json.loads(details);bad+=v['state']!='LITERAL_UTF8' or ('row_width' in d and (d['row_width']!=d['header_width'] or not d['unambiguous_literal_ID_column']))
            duplicates=self.db.execute('SELECT count(*) FROM (SELECT value FROM ids WHERE source=? GROUP BY value HAVING count(*)>1)',(source,)).fetchone()[0]
            if source=='qm8_sdf':same=native==indices and not bad;basis='OFFICIAL_LOADER_PHYSICAL_ORDINAL_CONCAT_NO_TITLE_VALUE_GUESS'
            else:
                known={json.loads(v[0]).get('text') for v in self.db.execute('SELECT value FROM ids WHERE source=?',(source,))};invalid=sum(v is None or len(v)!=4 for v in known)
                actual={v[0] for v in self.db.execute('SELECT DISTINCT pdb FROM records WHERE source=?',(source,))};missing=sorted(str(v) for v in actual-known);orphan=sorted(str(v) for v in known-actual)
                same=not(missing or orphan or invalid or bad);basis='EXACT_NATIVE_MEMBER_PDB_ID_VS_LITERAL_OFFICIAL_INDEX'
            rows.append({'source_id':source,'physical_SDF_records':native,'physical_MOL2_records':self.counts[(source,'MOL2')],
                'physical_index_rows':indices,'invalid_or_ambiguous_index_rows':bad,'duplicate_index_ID_groups':duplicates,
                'mapping_basis':basis,'mapping_closed':same,'native_IDs_without_index':missing,'index_IDs_without_native':orphan,'invalid_index_IDs':invalid})
        return rows


def project_all(plan,a,out,budget,functions,ledger):
    verified={}
    for ref in plan['data_references']:
        got,fr=source_hash(Path(ref['path']),budget.check);Q.need(got==ref,'CURRENT_PRODUCER_BODY_FULL_SHA');verified[ref['path']]=fr
    results=[]
    for source in a['sources']:
        sid=source['source_id'];inv=source['inventory_reference'];path=Path(source['payload_reference']['path']);index=[]
        with Path(inv['path']).open('rb') as f:
            for line in f:
                budget.check();Q.need(len(line)<=4096 and line.endswith(b'\n'),'COMPLETE_BOUNDED_ORIGINAL_INVENTORY_ROW');index.append(json.loads(line,object_pairs_hook=Q.pairs_unique))
        Q.need(len(index)==source['tar_members'],'ACTUAL792_COMPLETE_MEMBER_COUNT');member_count=0;native_ord=collections.Counter();id_summary=None
        with path.open('rb') as raw,gzip.GzipFile(fileobj=raw,mode='rb') as gz:
            expanded=Expanded(gz,budget.check,256<<30)
            with tarfile.open(fileobj=expanded,mode='r|',ignore_zeros=True,tarinfo=StrictTarInfo,bufsize=10240) as archive:
                for ordinal,member in enumerate(archive):
                    budget.check();Q.need(ordinal<len(index),'NO_UNREGISTERED_MEMBER');expected=index[ordinal];category=classify_member(sid,expected)
                    Q.need(expected['ordinal']==ordinal and expected['name']==member.name and expected['type_hex']==member.type.hex() and expected['declared_bytes']==member.size,'EXACT_ALL_MEMBER_PHYSICAL_INVENTORY')
                    member_count+=1
                    if not member.isfile():continue
                    with archive.extractfile(member) as f:
                        stream=Member(f,expected,budget)
                        kind='SDF' if category in ('qm8_native_SDF_candidate','native_ligand_SDF_candidate','other_SDF_unknown_mapping') else 'MOL2' if category in ('native_ligand_MOL2_candidate','other_MOL2_unknown_mapping') else None
                        if kind:
                            def emit(record_ordinal,body,complete):
                                n=native_ord[kind];row=N.project(sid,member.name,ordinal,record_ordinal,n,kind,body,complete,functions)
                                ledger.source(row,body);native_ord[kind]+=1
                            N.records(stream,kind,emit,budget.check)
                        elif category in ('qm8_companion_ID_CSV_candidate','official_loader_index_basename_candidate'):
                            Q.need(member.name==('qm8.sdf.csv' if sid=='qm8_sdf' else C.INDEX[sid]),'EXACT_OFFICIAL_INDEX_MEMBER_LOCATION_NO_PREFIX_GUESS')
                            if sid in ('qm8_sdf','pdbbind_core'):
                                parser=N.IDCSV(0 if sid=='qm8_sdf' else 'pdb_id',lambda n,value,details:ledger.identifier(sid,n,value,details))
                                while True:
                                    block=stream.read(64<<10)
                                    if not block:break
                                    parser.feed(block)
                                id_summary=parser.finish()
                            else:
                                n=0
                                while True:
                                    line=stream.readline(C.NATIVE_CAP+1)
                                    if not line:break
                                    Q.need(len(line)<=C.NATIVE_CAP,'BOUNDED_ORIGINAL_PDB_INDEX_LINE')
                                    if line.startswith(b'#'):continue
                                    ledger.identifier(sid,n,line[:4],{'official_rule':'NON_COMMENT_LINE_FIRST4_BYTES','line_bytes':len(line),'line_sha256':hashlib.sha256(line).hexdigest()});n+=1
                                id_summary={'physical_non_comment_rows':n,'assay_values_decoded':False}
                        else:
                            while stream.read(1<<20):pass
                        stream.finish()
            while expanded.read(1<<20):pass
        Q.need(member_count==len(index),'ALL_ORIGINAL_TAR_MEMBERS_CONSERVED')
        Q.need(native_ord['SDF']>0 and (sid=='qm8_sdf' or native_ord['MOL2']>0),'NO_EMPTY_NATIVE_POPULATION_ACCEPTANCE')
        results.append({'source_id':sid,'members':member_count,'native_record_counts':dict(native_ord),'index_observation':id_summary,
            'native_composition_counts':{kind:{state:ledger.compositions[(sid,kind,state)] for state in ('available','UNKNOWN')} for kind in ('SDF','MOL2')},
            'complete_gzip_EOF_CRC':True,'decoded_tar_bytes':expanded.n,'decoded_tar_sha256':expanded.sha.hexdigest()})
    ledger.close_sources()
    # Verify all already-used files again before any bounded key worker. A mutable
    # path or a changed compressed stream cannot be mistaken for original inputs.
    for ref in plan['data_references']:
        got,fr=source_hash(Path(ref['path']),budget.check);Q.need(got==ref and fr==verified[ref['path']],'SOURCE_FRAMES_AND_FULL_SHA_STABLE_AFTER_ALL_PHYSICAL_READS')
    return results


def keys_profile(plan,out,budget,ledger,functions):
    selected={sid:N.sample(sid,ledger.counts[(sid,'SDF')]) for sid in C.IDS}
    selection_ref=J.write_json(out/'actual_population_and_selected_ordinals.json',{'actual_SDF_N':{s:ledger.counts[(s,'SDF')] for s in C.IDS},'selected_actual_ordinals':selected,
        'seed':20261026,'Python':'3.11.14','population_predeclared_or_guessed':False},budget)
    stream=(out/'key_events.jsonl').open('xb');pending={};counts=collections.Counter();unknowns=collections.Counter();resolved=collections.Counter();worker=collections.Counter();cpu=collections.Counter();completed=0
    def collect(all_rows):
        nonlocal completed
        while pending:
            done,_=cf.wait(pending,timeout=1,return_when=cf.FIRST_COMPLETED)
            for future in done:
                rid,row=pending.pop(future)
                try:value=future.result();Q.need(value['source']==row,'EXACT_ORIGINAL_SOURCE_RETURN')
                except Exception as exc:value={'source':row,'observed_full_key_union':[],'WP5_key_union':[],'has_unknown':True,'technical_error':repr(exc),'worker_pid':None,'worker_CPU_seconds':None}
                J.append(stream,{'event':'RESULT_DURABLE_BEFORE_INDEX_OR_UNION','result':value},budget)
                ledger.db.execute('INSERT INTO results VALUES(?,?)',(rid,int(value['has_unknown'])))
                for k in value['observed_full_key_union']:ledger.db.execute('INSERT INTO keys VALUES(?,?,?)',(rid,k,functions['wp5_key'](k)))
                completed+=1;counts[row['source_id']]+=1;worker[str(value['worker_pid'])]+=1
                unknowns[row['source_id']]+=value['has_unknown'];resolved[row['source_id']]+=bool(value['observed_full_key_union'])
                if value['worker_CPU_seconds'] is not None:cpu[str(value['worker_pid'])]+=value['worker_CPU_seconds']
            if done and not all_rows:return
    try:
        with cf.ProcessPoolExecutor(max_workers=16,mp_context=mp.get_context('spawn'),initializer=N.initialize,initargs=(plan,)) as pool:
            try:
                with (out/'native_records.raw').open('rb') as raw:
                    for sid in C.IDS:
                        for ordinal in selected[sid]:
                            budget.check();record=ledger.db.execute("SELECT id,body,offset,bytes,sha FROM records WHERE source=? AND kind='SDF' AND ordinal=?",(sid,ordinal)).fetchone()
                            Q.need(record is not None,'ACTUAL_SELECTED_NATIVE_RECORD');rid,text,offset,n,sha=record;row=json.loads(text);raw.seek(offset);body=raw.read(n)
                            Q.need(len(body)==n and hashlib.sha256(body).hexdigest()==sha,'DURABLE_BLOB_EXACT_NATIVE_RECORD_BEFORE_SUBMIT')
                            J.append(stream,{'event':'SOURCE_DURABLE_BEFORE_KEY_DISPATCH','source':row},budget);pending[pool.submit(N.key_work,row,body)]=(rid,row)
                            if len(pending)>=32:collect(False)
            finally:collect(True)
        Q.need(completed==sum(map(len,selected.values())) and all(counts[s]==len(selected[s]) for s in C.IDS),'ALL_ACTUAL_SELECTED_KEY_RESULTS_DURABLE')
    finally:stream.flush();os.fsync(stream.fileno());stream.close()
    ledger.db.commit();return {'actual_profile_counts':dict(counts),'selected_rows_with_unknown_by_source':dict(unknowns),'selected_rows_with_observed_full_keys_by_source':dict(resolved),
        'actual_population_and_selection_reference':selection_ref,'actual_workers':dict(worker),'worker_CPU_seconds':dict(cpu),'key_result_journal_reference':J.pin(out/'key_events.jsonl'),
        'unselected_native_graphs':'NOT_YET_EXAMINED_NOT_GRAPH_UNAVAILABLE','full_identity_or_pool_release':False}


def entity_unions(out,budget,ledger):
    db=ledger.db;db.execute('CREATE INDEX pdb_entity ON records(pdb)');db.execute('CREATE INDEX native_source ON records(source,ordinal)')
    db.execute('CREATE INDEX source_ids ON ids(source,ordinal)');db.execute('CREATE TABLE entity_members(entity TEXT,record_id INTEGER PRIMARY KEY)')
    for rid,sid,ordinal,pdb in db.execute('SELECT id,source,ordinal,pdb FROM records ORDER BY id'):
        budget.check(drain=True)
        if sid=='qm8_sdf':
            item=db.execute('SELECT value,details FROM ids WHERE source=? AND ordinal=?',(sid,ordinal)).fetchone();valid=False
            if item:
                value,details=map(json.loads,item);valid=value['state']=='LITERAL_UTF8' and details['unambiguous_literal_ID_column'] and details['row_width']==details['header_width']
            entity=['QM8_ORIGINAL_LITERAL_ID',value] if valid else ['QM8_UNRESOLVED_PHYSICAL_ORDINAL',ordinal]
        else:entity=['PDB_ID_ALL_COMPONENTS',pdb] if pdb is not None else ['UNRESOLVED_PHYSICAL_NATIVE_RECORD',rid]
        db.execute('INSERT INTO entity_members VALUES(?,?)',(Q.canonical(entity).decode(),rid))
    db.execute('CREATE INDEX entity_key ON entity_members(entity)');db.commit();stream=(out/'entity_key_unions.jsonl').open('xb');n=0
    try:
        # Never assert equal graph or deduplicate physical members by a shared ID.
        for (identity,) in db.execute('SELECT DISTINCT entity FROM entity_members ORDER BY entity'):
            budget.check(drain=True);entity=json.loads(identity)
            records=db.execute('SELECT r.id,r.kind,r.body FROM records r JOIN entity_members e ON r.id=e.record_id WHERE e.entity=? ORDER BY r.id',(identity,)).fetchall()
            keys=set();wp=set();unknown=[];unexamined=0;memberships=set()
            for rid,kind,text in records:
                row=json.loads(text);memberships.add(row['source_id']);pairs=db.execute('SELECT fullkey,wp5 FROM keys WHERE id=?',(rid,)).fetchall();keys.update(k for k,w in pairs);wp.update(w for k,w in pairs)
                observed=db.execute('SELECT unknown FROM results WHERE id=?',(rid,)).fetchone()
                if kind=='SDF' and observed is None:unexamined+=1
                if kind=='MOL2' or (observed and observed[0]):unknown.append({'member':row['member_name'],'record_ordinal':row['record_ordinal'],
                    'native_non_H_composition_evidence':row['native_non_H_composition_evidence'],'reason':'MOL2_GRAPH_CHARGE_STEREO_UNKNOWN' if kind=='MOL2' else 'SELECTED_SDF_GRAPH_OR_PRESENT_VARIANT_UNKNOWN'})
            J.append(stream,{'entity_identity':entity,'original_QM8_companion_ID':entity[1] if entity[0]=='QM8_ORIGINAL_LITERAL_ID' else None,
                'physical_record_count':len(records),'all_observed_full_key_union':sorted(keys),'all_observed_WP5_union':sorted(wp),'unresolved_variant_composition_evidence':unknown,
                'original_source_component_memberships':sorted(memberships),
                'unexamined_SDF_records':unexamined,'automatic_composition_exclusion_for_known_key_entity':False,'same_ID_implies_same_graph':False,
                'cross_component_overlap_preserved_in_relationship_index':True,'full_identity_or_pool_release':False},budget);n+=1
    finally:stream.close()
    return {'entities':n,'reference':J.pin(out/'entity_key_unions.jsonl'),'unknown_and_original_variants_retained':True,'automatic_full_release':False}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',type=Path,required=True);p.add_argument('--startup-proof',type=Path,required=True);a=p.parse_args()
    plan,proof,authority=G.require_startup(a.plan,a.startup_proof);out=Q.literal(plan['output_directory']);Q.need(C.ROOT/'artifacts' in out.parents and not out.exists(),'FRESH_NATIVE4_OUTPUT');out.mkdir(parents=True)
    budget=Budget(plan,proof,out);ledger=None;gate=None;started=time.monotonic()
    try:
        gate,functions=fixtures(out,budget,plan);ledger=Ledger(out,budget);projection=project_all(plan,authority,out,budget,functions,ledger)
        relations=ledger.relations();J.write_json(out/'actual_relationship_checks.json',relations,budget)
        profile=keys_profile(plan,out,budget,ledger,functions);unions=entity_unions(out,budget,ledger);ledger.db.commit();ledger.db.close();budget.check(drain=True)
        J.write_json(out/'receipt.json',{'schema':'SECONDARY_MOLECULENET_NATIVE4_IDENTITY_PROFILE_RECEIPT_V1','status':'ALL_PHYSICAL_NATIVE_CONTEXT_AND_BOUNDED_KEYS_RECORDED_UNKNOWNS_RETAINED',
            'job_id':str(proof['job_id']),'endpoint':Q.ENDPOINT,'uid':1264,'node':plan['node'],'scope_key':C.KEY,'scope_parameters':C.PARAMETERS,
            'data_references':plan['data_references'],'format_authority_reference':plan['format_authority_reference'],
            'plan_reference':Q.ref(a.plan),'startup_proof_reference':Q.ref(a.startup_proof),
            'fixtures':gate,'projection':projection,'relationship_checks':relations,'profile':profile,'unions':unions,
            'raw_native_blob_reference':J.pin(out/'native_records.raw'),'source_rows_reference':J.pin(out/'source_rows.jsonl'),
            'native_relationship_index_reference':J.pin(out/'native_relationships.sqlite'),'runtime':budget.receipt(),
            'wall_seconds':time.monotonic()-started,'mapping_closure_is_identity_ACCEPTANCE':False,'all_source_identity_keys_closed':False,
            'MOL2_formal_charge_stereo_graph':'UNKNOWN_NOT_INFERRED','full_or_pool_or_decontamination_release':False,'actual_terminal_parent_accounting':'PENDING_ROOT_ACTUAL'},budget)
        return 0
    except BaseException as exc:
        J.write_json(out/'failure.json',{'error':repr(exc),'traceback':traceback.format_exc(),'fixtures':gate,'durable_prefixes_retained':True,'full_or_pool_release':False,'actual_cost':'PENDING_ROOT_ACCOUNTING'},budget);raise
    finally:
        if ledger is not None:
            try:ledger.close_sources();ledger.db.close()
            except Exception:pass
        budget.finish()


if __name__=='__main__':raise SystemExit(main())
