"""Original grammar objects, bounded journal records and exact raw-byte binding."""
import collections,hashlib,json,os,random,stat
from pathlib import Path
from workflows.expansion.marcel_identity_format_probe_v1 import projection as P,run as M
from workflows.expansion.marcel_drugs_keys_main_v1 import rows as V
from . import contract as C
Q=C.Q


def selections():
    original=random.Random(C.SEED).sample(range(C.N),C.SOURCE_PROFILE_N)
    return original,original[:C.PROFILE_N]


def source_row(member,ordinal,details):
    return {'source_id':'marcel_drugs_zip','member':member,'physical_ordinal':ordinal,'name_pairing_basis':'EXACT_UNNORMALIZED_BYTES',
        'details':details,'chemical_key_computed':False}


def bind_raw(raw,row):
    V.validate(row);Q.need(row['member']=='Drugs.sdf','NATIVE_RECORD_REQUIRES_ORIGINAL_SDF_ROW')
    _,_,details=P.sdf_record(raw,row['details']['terminated']);Q.need(details==row['details'],'EXACT_RAW_SHA_BYTES_ALL_LITERAL_FIELDS_NOT_ORDINAL_ONLY')


class Blob:
    def __init__(self,path,budget):
        self.path,self.budget=path,budget;fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_APPEND,0o600)
        self.f=os.fdopen(fd,'ab');self.n=self.rows=0;self.h=hashlib.sha256()
    def append(self,raw):
        self.budget.check(True);Q.need(len(raw)<=16<<20 and self.budget.used()+len(raw)+(258<<20)<self.budget.cap,'ORIGINAL_RECORD_PLUS_ALL16_TEMP_FILES_AND_DRAIN_RESERVE')
        ref={'container_path':str(self.path),'offset':self.n,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'basis':'EXACT_ORIGINAL_RECORD_APPEND_ONLY_DURABLE_SEGMENT'}
        self.f.write(raw);self.f.flush();os.fsync(self.f.fileno());self.h.update(raw);self.n+=len(raw);self.rows+=1;return ref
    def close(self):
        if not self.f.closed:self.f.flush();os.fsync(self.f.fileno());self.f.close()
        Q.need(self.path.lstat().st_size==self.n,'ACTUAL_OWN_RAW_PREFIX_BYTE_COUNT')
        return {'path':str(self.path),'bytes':self.n,'sha256':self.h.hexdigest()}


def segment(ref):
    p=Path(ref['container_path']);n=ref['bytes'];offset=ref['offset']
    Q.need(p.is_absolute() and Q.ROOT/'artifacts' in p.parents and p.name=='selected_original_records.raw' and not any(v.is_symlink() for v in (p,*p.parents))
        and type(n) is int and 0<n<=16<<20 and type(offset) is int and offset>=0,'OWN_BOUNDED_DURABLE_ORIGINAL_RECORD_SEGMENT')
    with p.open('rb') as f:
        before=os.fstat(f.fileno());Q.need(stat.S_ISREG(before.st_mode) and before.st_uid==1278 and before.st_size>=offset+n,'SEGMENT_PREFIX_ALREADY_DURABLE')
        f.seek(offset);raw=f.read(n);after=os.fstat(f.fileno())
    # The parent may append later records. Existing selected bytes must match the
    # original full-record SHA; no future whole-file SHA or immutable size is assumed.
    Q.need((before.st_dev,before.st_ino)==(after.st_dev,after.st_ino) and after.st_size>=offset+n
        and len(raw)==n and hashlib.sha256(raw).hexdigest()==ref['sha256'],'EXACT_ALREADY_COMMITTED_PREFIX_BYTES');return raw


class TrackedRecord:
    """Only a byte-retention seam; P.sdf_rows/P.sdf_record are never copied."""
    def __init__(self,stream):self.stream=stream;self.current=bytearray()
    def readline(self,n):
        line=self.stream.readline(n);self.current.extend(line);Q.need(len(self.current)<=16<<20,'ORIGINAL_NATIVE_RECORD_BOUND');return line
    def take(self,row):
        raw=bytes(self.current);bind_raw(raw,row);self.current.clear();return raw


class Journal:
    def __init__(self,ref,fr,check):
        self.ref,self.fr,self.check=ref,fr,check;self.f=Path(ref['path']).open('rb');self.h=hashlib.sha256();self.n=self.rows=0
        Q.need(M.frame(os.fstat(self.f.fileno()))==fr,'SAME_HASHED_ORIGINAL_JOURNAL_FD')
    def next(self):
        self.check();line=self.f.readline((8<<20)+1)
        if not line:return None
        Q.need(len(line)<=8<<20 and line.endswith(b'\n'),'FULL_BOUNDED_ORIGINAL_JOURNAL_RECORD')
        self.h.update(line);self.n+=len(line);self.rows+=1;return json.loads(line)
    def finish(self,expected):
        Q.need(self.next() is None and self.rows==expected and self.n==self.ref['bytes'] and self.h.hexdigest()==self.ref['sha256']
            and M.frame(os.fstat(self.f.fileno()))==self.fr==M.frame(Path(self.ref['path']).lstat()),'WHOLE_JOURNAL_EOF_SHA_FSTAT_AND_ROW_CONSERVATION')
    def close(self):self.f.close()


def cached_result(result,source,functions):
    V.validate(source);Q.need(result['source']==source and source['member']=='Drugs.sdf','ALL_CACHED_ORIGINAL_SOURCE_FIELDS_MATCH')
    expected=source['details']['properties']['smiles'];variants=result['variant_observations'];union=set()
    Q.need(len(variants)==len(expected),'ALL_CACHED_ORIGINAL_SMILES_VARIANTS_RETAINED')
    for i,(item,token) in enumerate(zip(variants,expected)):
        Q.need(item['original_variant_index']==i and item['original_token']==token,'CACHED_LITERAL_SOURCE_VARIANT_BINDING')
        Q.need(item['state']=='FULL_KEYS_DERIVED' and not item['errors'],'ACTUAL1818_SELECTED_VARIANTS_ALL_RESOLVED_NOT_NEW_REPAIR')
        valid,invalid=functions['full_keys'](item['full_InChIKeys'],strict=False);Q.need(not invalid and valid==item['full_InChIKeys'],'FROZEN_VALID_FULL_KEYS_FROM_ACTUAL1818')
        union.update(valid)
    keys,invalid=functions['full_keys'](sorted(union),strict=False);pairs=[[k,functions['wp5_key'](k)] for k in keys]
    Q.need(not invalid and result['full_key_and_WP5_pairs']==pairs and result['has_any_unknown'] is False
        and result['identity_state']=='ALL_ORIGINAL_VARIANT_KEYS_DERIVED','ACTUAL1818_COMPLETE_SOURCE_VARIANT_RESULTS_NO_RECOMPUTATION')
    return result


def load_profile(ref,fr,functions,budget):
    original,_=selections();expected=set(original);source_digests={};results={};reader=Journal(ref,fr,lambda:budget.check(False))
    try:
        while True:
            row=reader.next()
            if row is None:break
            if row['event']=='ORIGINAL_CONFORMER_SOURCE_DURABLE_BEFORE_DISPATCH':
                source=row['source'];V.validate(source);ordinal=source['physical_ordinal'];Q.need(ordinal in expected and ordinal not in source_digests,'EXACT10000_SOURCE_INTENTS_ONCE')
                source_digests[ordinal]=hashlib.sha256(json.dumps(source,sort_keys=True,separators=(',',':')).encode()).hexdigest()
            else:
                Q.need(row['event']=='ORIGINAL_CONFORMER_IDENTITY_RESULT_DURABLE','ONLY_FROZEN1818_JOURNAL_EVENT_TYPES')
                result=row['worker_observation']['result'];source=result['source'];ordinal=source['physical_ordinal']
                Q.need(ordinal in source_digests and ordinal not in results and hashlib.sha256(json.dumps(source,sort_keys=True,separators=(',',':')).encode()).hexdigest()==source_digests[ordinal],
                    'RESULT_MATCHES_PRECEDING_DURABLE_INTENT_ONCE')
                results[ordinal]=cached_result(result,source,functions)
        reader.finish(2*C.SOURCE_PROFILE_N);Q.need(set(source_digests)==set(results)==expected,'ALL10000_SOURCE_PROFILE_ORDINALS_NOT_FIRST1000_COMPLETIONS')
    finally:reader.close()
    return results


def export_names(relations,writer,budget):
    db=relations.db;db.commit();counts=collections.Counter()
    for ordinal,name,details in db.execute('SELECT ordinal,name,details FROM csv_names ORDER BY ordinal'):
        budget.check(False);total=db.execute('SELECT count(*) FROM conformers WHERE name=?',(name,)).fetchone()[0]
        source_count=db.execute('SELECT count(*) FROM results r JOIN conformers s USING(ordinal) WHERE s.name=?',(name,)).fetchone()[0]
        native,unknown,mismatch,compared=db.execute('SELECT count(*),coalesce(sum(r.unknown),0),coalesce(sum(r.mismatch),0),count(r.mismatch) FROM native_results r JOIN conformers s USING(ordinal) WHERE s.name=?',(name,)).fetchone()
        source_variants=db.execute('SELECT count(DISTINCT value) FROM source_smiles WHERE name=?',(name,)).fetchone()[0]
        source_pairs=db.execute('SELECT DISTINCT k.full_key,k.wp5 FROM keys k JOIN conformers s USING(ordinal) WHERE s.name=?',(name,)).fetchall()
        native_pairs=db.execute('SELECT DISTINCT k.full_key,k.wp5 FROM native_keys k JOIN conformers s USING(ordinal) WHERE s.name=?',(name,)).fetchall()
        pairs=sorted(set(source_pairs)|set(native_pairs))
        writer.write({'source_id':'marcel_drugs_zip','original_CSV_physical_ordinal':ordinal,'original_name_fields':json.loads(details)['name_fields'],
            'source_conformers':total,'source_profile_keys_observed_conformers':source_count,'native_graph_observed_conformers':native,
            'native_graph_NOT_YET_EXAMINED_conformers':total-native,'unknown_observed_native_conformers':unknown,'native_source_key_mismatch_conformers':mismatch,
            'native_source_key_comparison_known_conformers':compared,'native_source_key_comparison_UNKNOWN_conformers':native-compared,
            'distinct_original_SMILES_byte_variants':source_variants,'original_multiple_SMILES_status':source_variants>1,
            'source_SMILES_full_key_union':sorted({k for k,w in source_pairs}),'native_graph_full_key_union':sorted({k for k,w in native_pairs}),
            'conservative_all_observed_full_InChIKey_union':[k for k,w in pairs],'conservative_all_observed_WP5_key_union':sorted({w for k,w in pairs}),
            'coverage':'PARTIAL_NATIVE1000_AND_SOURCE_KEY10000_PROFILE_ALL_PHYSICAL_RELATIONSHIPS_RETAINED','representative_chosen':False,
            'native_graph_full_or_pool_release':False},False)
        counts['names']+=1;counts['original_multi_SMILES_names']+=source_variants>1;counts['names_with_unknown_native']+=unknown>0;counts['names_with_native_source_mismatch']+=mismatch>0
    Q.need(counts['names']==C.D.CSV_N and counts['original_multi_SMILES_names']==290,'ALL75099_CSV_NAMES_AND290_GROUPS_RETAINED');return dict(counts)
