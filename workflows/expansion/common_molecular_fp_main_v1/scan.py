"""Bounded full identity-column scan and actual all-Common census; no graph math."""
import hashlib,json,sqlite3
from workflows.expansion.common_molecular_fp_candidate_v1 import selection as S,census as Census
from . import contract as C
Q=C.Q

def profile_hash(mid):return hashlib.sha256(f'common-molecular-fp-profile-v1:{C.SEED}:{mid}'.encode()).hexdigest()

def validate_segment_count(member,count,mid):
    if member is not None and member[2]:Q.need(count==member[1],'EXACT_ALL_COMMON_NATIVE_RECORD_COUNT:'+mid)

def begin_segment(db,mid):
    try:db.execute('INSERT INTO seen VALUES(?,0)',(mid,))
    except sqlite3.IntegrityError as exc:raise ValueError('FORMAL_MID_REAPPEARED_AFTER_ANOTHER_SEGMENT:'+mid) from exc

def batches(body,columns):
    pf=body.parquet();Q.need(set(columns)<=set(pf.schema_arrow.names),'ACTUAL_REQUIRED_COLUMNS_MISSING')
    rows=0
    for batch in pf.iter_batches(columns=list(columns),batch_size=8192,use_threads=False):
        body.check();rows+=batch.num_rows;yield from batch.to_pylist()
    Q.need(rows==pf.metadata.num_rows,'COMPLETE_PARQUET_ROW_EOF_COUNT');body.check()

def prepare(out,bodies,members,role_parts,common,mode,budget):
    db=sqlite3.connect(out/'census.sqlite');db.executescript('PRAGMA journal_mode=DELETE;PRAGMA synchronous=FULL;PRAGMA temp_store=MEMORY;'
        'CREATE TABLE members(mid TEXT PRIMARY KEY,role TEXT,source_role TEXT,n INTEGER,common INTEGER);'
        'CREATE TABLE roles(mid TEXT PRIMARY KEY,role TEXT,source_role TEXT,n INTEGER);'
        'CREATE TABLE selected(mid TEXT PRIMARY KEY);CREATE TABLE seen(mid TEXT PRIMARY KEY,n INTEGER);'
        'CREATE TABLE results(mid TEXT PRIMARY KEY,status TEXT,strict5 TEXT);')
    for ref in members:
        for r in batches(bodies[ref['path']],('molecule_id','effective_role','source_role','records','common_population')):
            value=C.P.membership(r)
            db.execute('INSERT INTO members VALUES(?,?,?,?,?)',(r['molecule_id'],r['effective_role'],r['source_role'],r['records'],int(r['common_population'])))
        db.commit();budget.check()
    for ref in role_parts:
        for r in batches(bodies[ref['path']],('molecule_id','effective_role','source_role','records')):
            db.execute('INSERT INTO roles VALUES(?,?,?,?)',(r['molecule_id'],r['effective_role'],r['source_role'],r['records']))
        db.commit();budget.check()
    Q.need(db.execute('SELECT count(*) FROM members m LEFT JOIN roles r USING(mid) WHERE m.common=1 AND '
        '(r.mid IS NULL OR m.role<>r.role OR m.source_role<>r.source_role OR m.n<>r.n)').fetchone()[0]==0,'ALL_COMMON_WHOLE_ROLE_AND_RECORD_JOIN')
    expected=Census.Census()
    for mid,role,n in db.execute('SELECT mid,role,n FROM members WHERE common=1 ORDER BY mid'):expected.add(mid,role,n)
    e=expected.result();declared={r['effective_role']:r for r in common['roles']}
    Q.need(set(declared)=={'TRAIN','VAL'} and e['molecules']==common['denominator_molecules']-common['excluded_molecules']
        and all(e['molecules_by_role'][role]==declared[role]['molecules'] and e['native_records_by_role'][role]==declared[role]['pm7_records'] for role in declared),
        'ACTUAL_ALL16_MEMBERSHIP_CENSUS_EQUALS_FINAL_HEADER')
    if mode=='profile':
        db.create_function('profile_hash',1,profile_hash,deterministic=True)
        for role in ('TRAIN','VAL'):
            Q.need(e['molecules_by_role'][role]>=C.PROFILE_PER_ROLE,'ENOUGH_TRUE_COMMON_FOR_FIXED_ROLE_PILOT')
            db.execute('INSERT INTO selected SELECT mid FROM members WHERE common=1 AND role=? ORDER BY profile_hash(mid),mid LIMIT ?',(role,C.PROFILE_PER_ROLE))
    else:db.execute('INSERT INTO selected SELECT mid FROM members WHERE common=1')
    db.commit();return db,e

def scan_formal(db,body,source_writer,dispatch,budget):
    pf=body.parquet();available=set(pf.schema_arrow.names)
    Q.need(set(C.P.REQUIRED_IDENTITY_COLUMNS)|{'file_group'}<=available,'ACTUAL_FULL_IDENTITY_AND_ORDER_COLUMNS_REQUIRED')
    columns=[*C.P.REQUIRED_IDENTITY_COLUMNS,*[n for n in C.P.OPTIONAL_IDENTITY_COLUMNS if n in available],'file_group']
    current=None;member=None;selected=False;count=0;variants={};variant_bytes=0;hold=None;file_group=None;physical=0;source_bytes_by_role={'TRAIN':0,'VAL':0}
    def flush():
        if current is None:return
        db.execute('UPDATE seen SET n=? WHERE mid=?',(count,current))
        validate_segment_count(member,count,current)
        if selected:
            if hold is not None or not variants:dispatch.hold(current,hold or 'NO_ORIGINAL_SOURCE_GRAPH_VARIANTS')
            else:dispatch.enqueue({'molecule_id':current,'effective_role':member[0],'native_records':count,'variants':list(variants.values())})
        db.commit()
    for original in batches(body,columns):
        physical+=1;mid=original['molecule_id']
        if mid!=current:
            flush();budget.check();current=mid;C.P.need(type(mid)is str and mid,'NATIVE_MID_REQUIRED')
            begin_segment(db,mid) # Detect recurrence across the whole scan, not a prefix assumption.
            member=db.execute('SELECT role,n,common FROM members WHERE mid=?',(mid,)).fetchone()
            selected=db.execute('SELECT 1 FROM selected WHERE mid=?',(mid,)).fetchone() is not None
            count=0;variants={};variant_bytes=0;hold=None;file_group=original['file_group']
        Q.need(original['file_group']==file_group,'ONE_MID_MUST_REMAIN_WHOLE_FILE_GROUP')
        count+=1
        if not selected:continue
        row={k:v for k,v in original.items() if k!='file_group'};value=S.select(row)
        before=source_writer.bytes;source_writer.write({'phase':'SOURCE_IDENTITY','molecule_id':mid,'effective_role':member[0],
            'source_record_ordinal_within_MID':count-1,**value},True)
        source_bytes_by_role[member[0]]+=source_writer.bytes-before
        key=value['variant_id'];text=value['source_smiles_for_original_template'];size=len(text.encode()) if text else 0
        if key in variants:Q.need(variants[key]['source_smiles_for_original_template']==text,'VARIANT_SHA_COLLISION_HOLD')
        elif hold is None:
            if len(variants)>=4096 or size>1<<20 or variant_bytes+size>4<<20:hold='FINITE_VARIANT_CONTAINER_BOUND_HOLD_NO_CHEMICAL_EXCLUSION'
            else:
                variants[key]={k:value[k] for k in ('variant_id','status','source_smiles_for_original_template')};variant_bytes+=size
    flush();body.check()
    Q.need(db.execute('SELECT count(*) FROM members m LEFT JOIN seen s USING(mid) WHERE m.common=1 AND '
        '(s.mid IS NULL OR s.n<>m.n)').fetchone()[0]==0,'ALL_FINAL_COMMON_MIDs_AND_NATIVE_RECORDS_PRESENT_AT_EOF')
    observed=Census.Census()
    for mid,role,n in db.execute('SELECT m.mid,m.role,s.n FROM members m JOIN seen s USING(mid) WHERE m.common=1 ORDER BY m.mid'):observed.add(mid,role,n)
    return {'formal_physical_rows_scanned':physical,'all_common_observed_census':observed.result(),
            'formal_MIDs_contiguous_with_no_recurrence':True,'selected_MIDs':db.execute('SELECT count(*) FROM selected').fetchone()[0],
            'source_journal_actual_bytes_by_role':source_bytes_by_role}
