"""Index closed full WP5/P-prime identity columns; never load numerical payloads.

Source-only candidate. Run on an admitted real 16-CPU Main allocation.
The closed canonical identity DB and the official family list remain authorities.
"""
import argparse, collections, concurrent.futures as cf, contextlib, hashlib, json
import multiprocessing as mp, os, pathlib, sqlite3
from workflows.data_v1_final.labels.full_logical_owner_plan_v2.io import opened
from workflows.data_v1_final.labels.source_status_cpu_auto_memory_v1.support import (
    need, identity, sqlite_ro, lookup_batch, classify_owner, OWNER, TASKS, TASK_FAMILIES)

P=pathlib.Path
QUANTUM=set(TASK_FAMILIES.values())-{'D20','D3'}
POINTERS=('source_path','real_index','source_payload_sha256','conformer_id','sprime_conf_idx',
 'geometry_status','geometry_source','source_record_id','uff_geometry_sha256',
 'uff_coordinate_sha256','pm7_source_geometry_sha256','native_atom_order_sha256',
 'source_native_geometry_sha256','stored_bond_graph_sha256')
EXTRAS=('geometry_source','effective_role','source_record_id','uff_geometry_sha256',
 'uff_coordinate_sha256','pm7_source_geometry_sha256')
SCHEMA='D6_FULL_ORIGINAL_PHYSICAL_LOCATOR_INDEX_V1'
RESOURCE_CHECK=None
OPEN_WRITERS=[]

def close_writers():
    while OPEN_WRITERS:OPEN_WRITERS.pop().close()


def set_resource_check(callback):
    global RESOURCE_CHECK
    RESOURCE_CHECK=callback

def resource_check():
    if RESOURCE_CHECK is not None:RESOURCE_CHECK()



def triple(r): return {k:r[k] for k in ('path','bytes','sha256')}

def small(r):
    with opened(r,hash_content=True) as (f,_):
        need(r['bytes']<=8<<20,'SMALL_METADATA');return json.load(f)

def save(p,v):
    raw=(json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
    with P(p).open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
    return dict(path=str(p),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())

def closed_file(p):return dict(path=str(p),bytes=P(p).stat().st_size,frame=identity(p),closed=True,whole_file_SHA_recomputed=False)

def writable(p):
    db=sqlite3.connect(p);OPEN_WRITERS.append(db);db.execute('PRAGMA journal_mode=DELETE');db.execute('PRAGMA synchronous=FULL')
    db.execute('PRAGMA cache_size=-16384');return db

def location_db(p):
    db=writable(p);db.executescript('''
      CREATE TABLE locations(domain INTEGER,ordinal INTEGER,file INTEGER,rg INTEGER,r INTEGER,task INTEGER,owner INTEGER,
        PRIMARY KEY(domain,ordinal,file,task)) WITHOUT ROWID;
      CREATE TABLE pointers(domain INTEGER,ordinal INTEGER,file INTEGER,locator TEXT,
        PRIMARY KEY(domain,ordinal,file)) WITHOUT ROWID;
      CREATE TABLE observed_owners(id INTEGER PRIMARY KEY,tuple_json TEXT UNIQUE NOT NULL);
      CREATE TABLE shadow_locations(file INTEGER,rg INTEGER,r INTEGER,classification TEXT,identity_json TEXT,
        PRIMARY KEY(file,rg,r)) WITHOUT ROWID;
    ''');db.execute('INSERT INTO observed_owners VALUES(0,?)',(json.dumps({'binding':'DOMAIN0_MATCHED_CLOSED_CANONICAL_OWNER_OR_DOMAIN1_ROW_WITHOUT_JOB_TUPLE'}),));return db

@contextlib.contextmanager
def parquet(entry):
    import pyarrow.parquet as pq
    with opened(entry['reference'],hash_content=False) as (f,frame):
        h=pq.ParquetFile(f,pre_buffer=False)
        try:
            need(h.metadata.num_rows==entry['rows'],'CLOSED_PRODUCER_PHYSICAL_ROWS')
            yield h,frame
        finally:h.close()

def iter_identity(h,columns):
    """Project only explicit scalar identity columns, never values or geometry."""
    base=0
    for rg in range(h.num_row_groups):
        local=0
        for batch in h.iter_batches(row_groups=[rg],columns=columns,batch_size=8192,use_threads=False):
            resource_check()
            yield rg,base,local,batch.to_pylist();local+=batch.num_rows
        need(local==h.metadata.row_group(rg).num_rows,'IDENTITY_PROJECTION_ROW_OFFSETS');base+=local


def owner_id(db,row,cache):
    values={k:row[k] for k in ('attempt_id','job_id','task_id','lane') if k in row}
    if not values:return 0
    key=json.dumps(values,sort_keys=True,separators=(',',':'))
    if key not in cache:
        db.execute('INSERT OR IGNORE INTO observed_owners(tuple_json) VALUES(?)',(key,))
        cache[key]=db.execute('SELECT id FROM observed_owners WHERE tuple_json=?',(key,)).fetchone()[0]
    return cache[key]


def pprime_lookup(db,ids):
    out={};ids=list(dict.fromkeys(ids))
    for a in range(0,len(ids),256):
        part=ids[a:a+256]
        for row in db.execute('SELECT ordinal,record_id,mid,role,source_record_id,geometry_source FROM pprime_records WHERE record_id IN ('+','.join('?'*len(part))+')',part):out[row[1]]=row
    return out


def build_identity(plan,root,files):
    """Reuse original canonical metadata; QC supplies independent P-prime IDs."""
    db=writable(root/'identity.sqlite');db.executescript('''
      CREATE TABLE mid_records(domain INTEGER,mid TEXT,ordinal INTEGER,PRIMARY KEY(domain,mid,ordinal)) WITHOUT ROWID;
      CREATE TABLE pprime_records(ordinal INTEGER PRIMARY KEY,record_id TEXT UNIQUE NOT NULL,mid TEXT NOT NULL,
        role TEXT NOT NULL,source_record_id TEXT NOT NULL,geometry_source TEXT NOT NULL);
    ''')
    qdb=None;ordinal=0;rg_counts={}
    try:
        with opened(plan['wp5_canonical_reference'],hash_content=False) as (f,_):
            source=sqlite_ro(P('/proc/self/fd')/str(f.fileno()))
            try:
                cur=source.execute('SELECT molecule_id,record_ordinal FROM records ORDER BY record_ordinal')
                n=0
                while rows:=cur.fetchmany(8192):
                    db.executemany('INSERT INTO mid_records VALUES(0,?,?)',rows);n+=len(rows)
                    db.commit();resource_check()
                need(n==plan['wp5_records'],'FULL_CANONICAL_SCOPE_NOT_55K')
            finally:source.close()
        qdb=location_db(root/'qc_locations.sqlite')
        for item in files:
            resource_check()
            if item['domain']!=1 or item['family']!='QC':continue
            with parquet(item) as (h,_):
                cols=['record_id','molecule_id','effective_role','source_record_id','geometry_source']
                need(set(cols)<=set(h.schema_arrow.names),'REAL_PPRIME_QC_IDENTITY_SCHEMA')
                rg_counts[str(item['id'])]=[h.metadata.row_group(i).num_rows for i in range(h.num_row_groups)]
                for rg,base,local,rows in iter_identity(h,cols):
                    for j,row in enumerate(rows):
                        need(all(type(row[k]) is str and row[k] for k in cols),'NO_NULL_QC_IDENTITY')
                        need(row['effective_role'] in ('TRAIN','VAL') and row['geometry_source']=='uff_sprime','INHERITED_PPRIME_INPUT_VIEW')
                        db.execute('INSERT INTO pprime_records VALUES(?,?,?,?,?,?)',(ordinal,row['record_id'],row['molecule_id'],row['effective_role'],row['source_record_id'],row['geometry_source']))
                        db.execute('INSERT INTO mid_records VALUES(1,?,?)',(row['molecule_id'],ordinal))
                        qdb.execute('INSERT INTO locations VALUES(1,?,?,?,?,?,0)',(ordinal,item['id'],rg,local+j,-2));ordinal+=1
                    db.commit();qdb.commit()
            print(json.dumps({'stage':'PPRIME_QC_IDENTITY','file':item['id'],'records':ordinal}),flush=True)
        need(ordinal==plan['pprime_records'],'FULL_CLOSED_PPRIME_QC_SCOPE')
    finally:
        if qdb is not None:qdb.close()
        db.close()
    return dict(records=n,pprime_records=ordinal,QC_row_groups=rg_counts)

def scan_partition(work):
    plan,root,partition,files=work;root=P(root)
    import pyarrow as pa
    pa.set_cpu_count(1);pa.set_io_thread_count(1)
    out=root/('locations_%02d.sqlite'%partition);dst=location_db(out)
    canonical_cm=opened(plan['wp5_canonical_reference'],hash_content=False)
    counts=collections.Counter();results=[];cache={}
    with canonical_cm as (canonical,_):
        can=sqlite_ro(P('/proc/self/fd')/str(canonical.fileno()));ids=sqlite_ro(root/'identity.sqlite')
        try:
            for item in files:
                resource_check()
                rows_seen=0;groups=[];local_counts=collections.Counter()
                with parquet(item) as (h,frame):
                    names=set(h.schema_arrow.names);need('record_id' in names,'ACTUAL_RECORD_KEY_REQUIRED')
                    groups=[h.metadata.row_group(i).num_rows for i in range(h.num_row_groups)]
                    quantum=item['family'] in QUANTUM
                    required=set(OWNER)-{'molecule_id'} if item['domain']==0 else {'record_id'}
                    if quantum:required|={'attempt_id','job_id','task_id','lane','total_atoms','calc_type'}
                    if item['domain']==1:required|={'geometry_source','source_record_id','effective_role'}
                    if item['family']=='base_geometry':required|={'source_path','real_index','source_payload_sha256'}
                    if item['domain']==0 and item['family']=='base_geometry':required.add('geometry_status')
                    need(required<=names,'MISSING_ACTUAL_OWNER_OR_NATIVE_POINTER:'+str(item['reference']['path']))
                    cols=sorted((set(OWNER)|{'lane','total_atoms','calc_type'}|set(POINTERS)|set(EXTRAS))&names)
                    for rg,base,local,rows in iter_identity(h,cols):
                        owners=lookup_batch(can,[r['record_id'] for r in rows]) if item['domain']==0 else pprime_lookup(ids,[r['record_id'] for r in rows])
                        for j,row in enumerate(rows):
                            rows_seen+=1;rid=row['record_id'];owner=owners.get(rid)
                            if item['domain']==0:
                                joined=dict(row)
                                if 'molecule_id' not in row and owner:joined['molecule_id']=owner['molecule_id']
                                classification=classify_owner(joined,owner,quantum)
                                if classification!='CANONICAL':
                                    dst.execute('INSERT INTO shadow_locations VALUES(?,?,?,?,?)',(item['id'],rg,local+j,classification,json.dumps(row,sort_keys=True)))
                                    local_counts[classification]+=1;continue
                                ordinal=owner['record_ordinal'];local_counts['MID_FROM_CLOSED_CANONICAL_JOIN' if 'molecule_id' not in row else 'MID_OBSERVED']+=1
                            else:
                                need(owner is not None,'PPRIME_RECORD_NOT_IN_CLOSED_QC_IDENTITY')
                                need('molecule_id' not in row or row['molecule_id']==owner[2],'PPRIME_MID_DIFFERS_FROM_QC')
                                need((row['effective_role'],row['source_record_id'],row['geometry_source'])==(owner[3],owner[4],owner[5]),'PPRIME_ROLE_NATIVE_ALIAS_VIEW_DIFFERS_FROM_QC')
                                ordinal=owner[0]
                            task=row.get('calc_type',item['family']);code=TASKS[task] if task in TASKS else -1
                            if quantum:need(task in TASK_FAMILIES and TASK_FAMILIES[task]==item['family'],'ORIGINAL_TASK_FAMILY')
                            oid=owner_id(dst,row,cache) if item['domain']==1 else 0
                            dst.execute('INSERT INTO locations VALUES(?,?,?,?,?,?,?)',(item['domain'],ordinal,item['id'],rg,local+j,code,oid))
                            if item['family']=='base_geometry':
                                pointer={k:row[k] for k in POINTERS if k in row}
                                need(type(pointer['source_path']) is str and type(pointer['real_index']) is int and type(pointer['source_payload_sha256']) is str,'REAL_NATIVE_SOURCE_KEY')
                                dst.execute('INSERT INTO pointers VALUES(?,?,?,?)',(item['domain'],ordinal,item['id'],json.dumps(pointer,sort_keys=True,separators=(',',':'))))
                            local_counts['canonical_locations']+=1
                        dst.commit()
                    need(rows_seen==item['rows'],'ALL_SOURCE_PHYSICAL_ROWS_INDEXED_OR_SHADOW_DISCLOSED')
                counts.update(local_counts);results.append(dict(file_id=item['id'],frame=frame,row_group_rows=groups,counts=dict(local_counts),physical_rows=rows_seen))
                print(json.dumps({'stage':'IDENTITY_LOCATIONS','partition':partition,'file':item['id'],'physical_rows':rows_seen}),flush=True)
        finally:can.close();ids.close();dst.close()
    return dict(partition=partition,storage=closed_file(out),files=results,counts=dict(counts))


def scan_partition_closed(work):
    try:return scan_partition(work)
    finally:close_writers()

def source_files(plan):
    group=small(plan['wp5_group_plan_reference']);book=small(plan['wp5_source_inventory_reference'])
    need(group['mode']=='full' and group['records']==plan['wp5_records'] and group['canonical_index']==plan['wp5_canonical_reference'],'ORIGINAL_ALL_SOURCE_OWNER_PLAN')
    need(group['source_inventory_reference']==plan['wp5_source_inventory_reference'],'ORIGINAL_WP5_SOURCE_BOOK')
    need(group['footer_manifest_reference']==plan['wp5_footer_manifest_reference'],'CLOSED_FOOTER_CHAIN')
    footer=small(plan['wp5_footer_manifest_reference'])
    need(footer['status']=='ALL2208_SOURCE_FOOTERS_OBSERVED_VALUES_PENDING' and footer['pending_file_ids']==[] and footer['errors']==[],'ORIGINAL_CLOSED_FULL_FOOTERS')
    files=[]
    for row in book['files']:
        resource_check()
        files.append(dict(id=len(files),domain=0,reference=triple(row),family=row['family'],rows=row['rows'],source_inventory_entry=row))
    need(len(files)==2208,'ALL2208_WP5_FILES')
    completion=small(plan['pprime_completion_reference']);analysis=small(completion['analysis_reference'])
    need(completion['status']=='COMPLETE_FROZEN_READY_CALCULATIONS_AND_VERIFIED_COVERAGE' and analysis['missing_conformers']==0 and analysis['unexpected_conformers']==0,'CLOSED_ORIGINAL_PPRIME_SCOPE')
    need(analysis['completed_conformers']==plan['pprime_records'],'ORIGINAL_FROZEN_READY_COUNT')
    ref=completion['family_manifest_reference'];need(ref==plan['pprime_family_manifest_reference'],'OFFICIAL_PPRIME_FAMILY_LIST')
    seen=set()
    with opened(ref,hash_content=False) as (f,_):
        for line in f:
            resource_check()
            row=json.loads(line);r=triple(row['reference']);need(r['path'] not in seen,'OFFICIAL_LIST_HAS_DUPLICATE_PATH');seen.add(r['path'])
            files.append(dict(id=len(files),domain=1,reference=r,family=row['family'],rows=row['rows'],closed_family_manifest_entry=row))
    need(len(seen)==analysis['verified_files'],'ALL_OFFICIAL_PPRIME_FAMILIES')
    return files


def build(plan,output,*,worker_initializer=None,worker_initargs=()):
    need(os.getuid()==1278 and os.environ.get('SLURM_CPUS_PER_TASK')=='16' and os.environ.get('SLURM_JOB_ID'),'REAL_16CPU_MAIN_JOB')
    need(plan['schema']=='D6_FULL_PHYSICAL_INDEX_SOURCE_PLAN_V1' and plan['workers']==16,'DECLARED_FULL_IDENTITY_INDEX_PLAN')
    root=P(output);need(root.is_absolute() and str(root).startswith('/lfshome/zixiao/'),'ACTUAL_LUSTRE_OUTPUT_ROOT')
    need(str(root)==plan['output_directory'],'SAME_ROOT_ADMITTED_OUTPUT')
    need(not root.exists(),'FRESH_INDEX_ROOT');root.mkdir(parents=True)
    resource_check()
    files=source_files(plan);initial=build_identity(plan,root,files)
    tasks=[[] for _ in range(16)];weights=[0]*16
    for item in sorted((f for f in files if not(f['domain']==1 and f['family']=='QC')),key=lambda x:-x['rows']):
        k=min(range(16),key=lambda k:weights[k]);tasks[k].append(item);weights[k]+=item['rows']
    with cf.ProcessPoolExecutor(max_workers=16,mp_context=mp.get_context('spawn'),initializer=worker_initializer,initargs=worker_initargs) as pool:
        parts=list(pool.map(scan_partition_closed,[(plan,str(root),k,tasks[k]) for k in range(16)]))
    resource_check()
    catalog=save(root/'files.json',files)
    manifest=dict(schema=SCHEMA,status='CLOSED_ORIGINAL_SOURCE_IDENTITY_LOCATORS_NOT_FULL_COMMON_OR_TRAINING_RELEASE',
      actual_job_id=os.environ['SLURM_JOB_ID'],source_plan=plan,files_reference=catalog,
      canonical_reference=plan['wp5_canonical_reference'],identity_database=closed_file(root/'identity.sqlite'),
      QC_locations=closed_file(root/'qc_locations.sqlite'),QC_row_groups=initial['QC_row_groups'],partitions=parts,
      original_WP5_records=initial['records'],original_Pprime_records=initial['pprime_records'],
      full_original_source_scan=True,final_Common_filter_applied=False,numeric_payload_columns_read=False,
      scientific_mask_value_or_ID_modified=False,source_whole_SHA_recomputed=False,
      geometry_positions_read=False,new_QM_UFF_calls=0,training_release=False)
    result=save(root/'manifest.json',manifest);print(json.dumps(result),flush=True);return result


def main():
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--plan',required=True);a.add_argument('--output',required=True)
    args=a.parse_args();build(json.loads(P(args.plan).read_text(encoding='utf-8-sig')),args.output)
if __name__=='__main__':main()