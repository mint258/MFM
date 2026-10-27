"""Bounded original full-key journal index and exact closed native1000 adoption."""
from __future__ import annotations
import collections,hashlib,json,os
from pathlib import Path
from workflows.expansion.marcel_drugs_native_graph_profile_v1 import reader as V
from . import contract as C
Q=C.Q


def digest(source):return hashlib.sha256(json.dumps(source,sort_keys=True,separators=(',',':')).encode()).hexdigest()


class FullKeys:
    def __init__(self,db,functions,expected=C.N):
        Q.need(type(expected) is int and 0<expected<=C.N,'BOUNDED_FULL_KEY_INDEX_ROWS')
        self.db,self.functions,self.expected=db,functions,expected;self.intents=self.results=0
        db.executescript('CREATE TABLE full_source_intents(ordinal INTEGER PRIMARY KEY,source_sha TEXT NOT NULL);'
            'CREATE TABLE full_source_cache(ordinal INTEGER PRIMARY KEY,source_sha TEXT NOT NULL,result_json TEXT NOT NULL);')
    def consume(self,event):
        if event['event']=='ORIGINAL_CONFORMER_SOURCE_DURABLE_BEFORE_DISPATCH':
            source=event['source'];V.V.validate(source);ordinal=source['physical_ordinal']
            Q.need(source['member']=='Drugs.sdf' and ordinal==self.intents and ordinal<self.expected,'FULL_SOURCE_INTENTS_IN_PHYSICAL_ORDER_ONCE')
            self.db.execute('INSERT INTO full_source_intents VALUES(?,?)',(ordinal,digest(source)));self.intents+=1
        else:
            Q.need(event['event']=='ORIGINAL_CONFORMER_IDENTITY_RESULT_DURABLE','ONLY_ORIGINAL1858_DURABLE_EVENT_TYPES')
            result=event['worker_observation']['result'];source=result['source'];ordinal=source['physical_ordinal']
            old=self.db.execute('SELECT source_sha FROM full_source_intents WHERE ordinal=?',(ordinal,)).fetchone()
            Q.need(old is not None and old[0]==digest(source),'FULL_RESULT_BINDS_PRECEDING_EXACT_SOURCE_INTENT')
            V.cached_result(result,source,self.functions)
            self.db.execute('INSERT INTO full_source_cache VALUES(?,?,?)',(ordinal,old[0],json.dumps(result,separators=(',',':'),allow_nan=False)))
            self.results+=1
    def finish(self):
        Q.need(self.intents==self.results==self.expected
            and self.db.execute('SELECT count(*) FROM full_source_cache').fetchone()[0]==self.expected,
            'ALL_ORIGINAL1858_SOURCE_RESULTS_EXACTLY_ONCE')
        self.db.commit()
    def get(self,source):
        row=self.db.execute('SELECT source_sha,result_json FROM full_source_cache WHERE ordinal=?',(source['physical_ordinal'],)).fetchone()
        Q.need(row is not None and row[0]==digest(source),'CURRENT_ZIP_FULL1858_CACHE_EXACT_SOURCE_ID_NAME_VARIANTS_SHA')
        result=json.loads(row[1]);return V.cached_result(result,source,self.functions)


def load_full(ref,frame,db,functions,budget):
    cache=FullKeys(db,functions);reader=V.Journal(ref,frame,lambda:budget.check(True))
    try:
        while True:
            event=reader.next()
            if event is None:break
            cache.consume(event)
            if reader.rows%512==0:db.commit()
        reader.finish(2*C.N);cache.finish()
    finally:reader.close()
    return cache


def adopted_observation(payload,observation,cache,raw_blob,blob_reference,functions):
    source=payload['source'];cached=payload['cached_source_keys'];ref=payload['raw_record_reference'];result=observation['result']
    Q.need(cache.get(source)==cached and result['source']==source and result['cached_source_SMILES_observation']==cached
        and result['raw_record_reference']==ref,'OLD_NATIVE_PROFILE_BINDS_SAME_FULL_SOURCE_CACHE')
    Q.need(ref['container_path']==blob_reference['path'] and type(ref['offset']) is int and ref['offset']>=0
        and type(ref['bytes']) is int and 0<ref['bytes']<=16<<20 and ref['offset']+ref['bytes']<=len(raw_blob),
        'EXACT_OLD_PROFILE_RAW_SEGMENT_WITHIN_DECLARED_COMPLETE_BLOB')
    raw=raw_blob[ref['offset']:ref['offset']+ref['bytes']]
    Q.need(hashlib.sha256(raw).hexdigest()==ref['sha256'],'ACTUAL_CLOSED_PROFILE_RAW_SEGMENT_SHA');V.bind_raw(raw,source)
    pairs=result['native_graph_full_key_and_WP5_pairs'];keys,invalid=functions['full_keys']([k for k,w in pairs],strict=False)
    Q.need(not invalid and len(keys)==1 and pairs==[[k,functions['wp5_key'](k)] for k in keys]
        and set(keys)=={k for k,w in cached['full_key_and_WP5_pairs']}
        and result['has_any_unknown'] is False and result['native_graph_vs_source_key_set_mismatch'] is False
        and result['identity_state']=='NATIVE_GRAPH_FULL_KEY_DERIVED'
        and sorted({tuple(p) for p in [*pairs,*cached['full_key_and_WP5_pairs']]})==[tuple(p) for p in result['conservative_all_observed_full_key_and_WP5_pairs']],
        'EXACT_SUCCESSFUL_NATIVE_PROFILE_KEYS_AND_CONSERVATIVE_UNION_NOT_REDERIVED')
    return {'original_payload':payload,'original_worker_observation':observation,'source_sha256':digest(source),
        'raw_record_sha256':ref['sha256'],'raw_record_bytes':ref['bytes']}


def load_native(ref,frame,blobref,blobframe,cache,functions,budget,native_receipt,native_proof):
    _,selected=V.selections();expected=set(selected);intents={};results={};seen=0
    Q.need(blobref['bytes']<=32<<20,'ACTUAL_NATIVE1000_RAW_BLOB_BOUNDED_MEMORY')
    with Path(blobref['path']).open('rb') as f:
        Q.need(V.M.frame(os.fstat(f.fileno()))==blobframe,'SAME_WHOLE_SHA_VERIFIED_NATIVE_PROFILE_BLOB_FD')
        raw=f.read((32<<20)+1)
        Q.need(len(raw)==blobref['bytes'] and hashlib.sha256(raw).hexdigest()==blobref['sha256']
            and V.M.frame(os.fstat(f.fileno()))==blobframe==V.M.frame(Path(blobref['path']).lstat()),'CLOSED_NATIVE_PROFILE_RAW_BLOB_CURRENT_SHA_FSTAT')
    reader=V.Journal(ref,frame,lambda:budget.check(True))
    try:
        while True:
            event=reader.next()
            if event is None:break
            if event['event']=='EXACT_ORIGINAL_RECORD_AND_CACHED_SOURCE_KEYS_DURABLE_BEFORE_NATIVE_DISPATCH':
                payload=event['payload'];source=payload['source'];ordinal=source['physical_ordinal'];allocation=payload['allocation']
                Q.need(ordinal in expected and ordinal not in intents and allocation['job_id']==str(native_receipt['job_id'])
                    and allocation['node']==native_receipt['node'] and allocation['boot_id']==native_proof['boot_id'],
                    'HISTORICAL_ACTUAL3547_PROFILE_INTENT_NOT_CURRENT_WORKER_IDENTITY')
                intents[ordinal]=payload
            else:
                Q.need(event['event']=='NATIVE_GRAPH_RESULT_DURABLE_BEFORE_SQL_AND_NAME_UNION','ONLY_ORIGINAL3547_NATIVE_EVENTS')
                observation=event['worker_observation'];ordinal=observation['result']['source']['physical_ordinal']
                Q.need(ordinal in intents and ordinal not in results,'OLD_NATIVE_RESULT_WITH_PRECEDING_UNIQUE_INTENT')
                results[ordinal]=adopted_observation(intents[ordinal],observation,cache,raw,blobref,functions)
        reader.finish(2*C.INHERITED)
        Q.need(set(intents)==set(results)==expected,'EXACT1000_ORIGINAL_DRAW_ORDER_MEMBERS_ADOPTED_NO_NEW_SELECTION')
    finally:reader.close()
    return results


class FullNames:
    """Original union export object; only full-coverage metadata is relabelled."""
    def __init__(self,writer):self.writer=writer;self.names=self.rows=0
    def write(self,row,dispatch=False):
        total=row['source_conformers']
        Q.need(row['source_profile_keys_observed_conformers']==row['native_graph_observed_conformers']==total
            and row['native_graph_NOT_YET_EXAMINED_conformers']==0,'FULL_NAME_HAS_ALL_ORIGINAL_SOURCE_AND_NATIVE_CONFORMERS')
        value=dict(row);value['coverage']='FULL558002_NATIVE_1000_ACTUAL_C0_ADOPTED557002_NEW_ALL_VARIANTS_AND_NAMES_RETAINED'
        value['source_full_keys_observed_conformers']=row['source_profile_keys_observed_conformers']
        value['original_source_profile_count_field_retained_as_legacy_alias']=True
        value['unknown_or_mismatch_is_chemical_exclusion']=False
        self.writer.write(value,dispatch);self.names+=1;self.rows+=total
