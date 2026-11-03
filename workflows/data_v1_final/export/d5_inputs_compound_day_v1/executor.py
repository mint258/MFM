"""One bounded worker pool; actual whole-molecule checkpoints, no child Slurm."""
from __future__ import annotations
import concurrent.futures as cf,json,multiprocessing as mp,os,pathlib,sqlite3,traceback
from workflows.data_v1_final.export.d5_inputs_builder_v1 import io as I,geometry as G,children as H,verify as V
from . import contract as C,core as B,reader as R
OBJECTS=None


class Executor:
    def __init__(self,budget):self.budget=budget;self.pool=None
    def __enter__(self):
        self.pool=cf.ProcessPoolExecutor(max_workers=16,mp_context=mp.get_context('spawn'));return self
    def map(self,function,tasks):
        it=iter(tasks);pending={};send=take=0
        try:
            while True:
                while len(pending)<32:
                    self.budget.check()
                    try:task=next(it)
                    except StopIteration:break
                    pending[send]=self.pool.submit(function,task);send+=1
                if not pending:break
                future=pending.pop(take);take+=1;yield future.result()
        except BaseException:
            I.OBS.mark_stop('D5_DAY_STOP_NEW_POOL_WORK_NATURAL_DRAIN',{'submitted':send,'yielded':take})
            for f in pending.values():
                try:f.result()
                except BaseException:pass
            raise
    def __exit__(self,*args):self.pool.shutdown(wait=True,cancel_futures=False)


def worker(work):
    global OBJECTS
    task,declared,out,control=work;I.worker_check(control)
    if OBJECTS is None:OBJECTS=G.originals(initialize=True)
    try:value=B.molecule(task,declared,lambda:I.worker_check(control),OBJECTS,R)
    except Exception as exc:
        value={'molecule_id':task['molecule_id'],'logical_ordinal':task['logical_ordinal'],'bases':[],'orders':[],'atom_counts':[],'audit_identity':[],
            'status':'UNKNOWN_HOLD_SOURCE_VALIDATION_EXCEPTION','errors':[{'type':type(exc).__name__,'error':str(exc),'traceback':traceback.format_exc()}],
            'actual_descriptor':task,'original_DATA_retained':True,'new_QM_UFF_calls':0}
    raw=B.encode(value);I.worker_check(control,len(raw));path=pathlib.Path(out)/('molecule_%08d.lossless.json'%task['logical_ordinal'])
    with path.open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
    return {'reference':I.actual_ref(path),'logical_ordinal':task['logical_ordinal'],'held':value['status']!='COMPLETE_BASE_AND_ORIGINAL_ORDERS','pid':os.getpid()}


def packet_tables(plan,range_meta,out,budget,pool,postdb,authority):
    workers=out/'workers';workers.mkdir();declared=C.unique([*plan['data_references'],*range_meta['data_references'],range_meta['descriptor_reference']])
    for r in declared:authority.add(r)
    post=C.meta(plan['postprocess_entry_reference'])
    def work():
        for task in I.jsonl(range_meta['descriptor_reference'],authority,budget.check):
            found=postdb.execute('SELECT ref,status,d7 FROM post WHERE mid=?',(task['molecule_id'],)).fetchone()
            C.need(found is not None and found[1]=='DURABLE_READONLY_MOLECULE_RESULT' and found[2]==1,'SAME_FULL_ACCEPTED_POSTPROCESS_CATALOGUE_MOLECULE')
            r=C.reference(json.loads(found[0]));authority.add(r)
            task.update(accepted_postprocess_packet_reference=r,accepted_postprocess_job_id=str(post['job_id']),
                accepted_postprocess_entry_reference=plan['postprocess_entry_reference'])
            yield task,C.unique([*declared,r]),str(workers),dict(budget.control)
    reports=list(pool.map(worker,work()));lo,hi=range_meta['logical_range']
    C.need([r['logical_ordinal'] for r in reports]==list(range(lo,hi)),'ALL_WHOLE_MOLECULE_ORDINALS_COMPLETED_OR_UNKNOWN')
    for r in reports:authority.add(r['reference'])
    def values(kind):
        for r in reports:
            v=B.decode(I.body(r['reference'],authority,budget.check,I.ROW_CAP))
            if kind=='roster':yield {'logical_ordinal':v['logical_ordinal'],'molecule_id':v['molecule_id'],
                'PM7_N':sum(x['geometry_source']=='pm7' for x in v['bases']),
                'UFF_N':sum(x['geometry_source']=='uff_sprime' for x in v['bases']),'child_count':0}
            else:yield from v['bases' if kind=='geometries' else kind]
    tables={kind:I.parquet_rows(out/(kind+'.parquet'),values(kind),schema,budget) for kind,schema in B.schemas().items()}
    for r in tables.values():authority.add(r)
    return {'table_references':tables,'logical_range':[lo,hi],'molecules':hi-lo,'held_molecules':sum(r['held'] for r in reports),
        'table_domain':'BASE_ONLY','worker_packet_references':[r['reference'] for r in reports],
        'effective_worker_pids':sorted({r['pid'] for r in reports}),'all_actual_children_closed':False,
        'full_typed_source_order_identity_parity':False}


def post_catalogue(plan,out,budget,authority):
    post=C.meta(plan['postprocess_entry_reference']);ref=post['catalog_reference']
    db=sqlite3.connect(out/'post_catalogue.sqlite');db.execute('CREATE TABLE post(mid TEXT PRIMARY KEY,ref TEXT,status TEXT,d7 INTEGER)')
    for row in I.rows(ref,authority,budget.check):
        r=C.reference(row['packet_reference']);db.execute('INSERT INTO post VALUES(?,?,?,?)',
            (row['molecule_id'],json.dumps(r,separators=(',',':')),row['status'],int(row['d7_closed'])))
    db.commit();return db


def source_ranges(prepared):
    for pref in prepared['range_registry_page_references']:
        page=C.meta(pref);C.need(page['schema']=='D5_INPUTS_RANGE_REGISTRY_PAGE_V1','ORIGINAL_CPU_PREPARED_RANGE_REGISTRY')
        for ref in page['range_manifest_references']:
            value=C.meta(ref);C.need(value['schema']=='D5_INPUTS_ACTUAL_RANGE_LOCATORS_V1','ORIGINAL_CPU_PREPARED_RANGE_LOCATORS');yield ref,value


def add_refs(authority,value):
    for r in value['table_references'].values():authority.add(r)
    for r in value.get('worker_packet_references',[]):authority.add(r)


def catalogue_rows(refs,authority,budget):
    for ref in refs:
        yield from I.jsonl(ref,authority,budget.check)


def validate_prefix(rows,expected_start=0):
    cursor=expected_start
    for row in rows:
        lo,hi=row['logical_range'];C.need(type(lo) is int and type(hi) is int and lo==cursor and hi>lo
            and type(row['molecules']) is int and row['molecules']==hi-lo and type(row['held_molecules']) is int and row['held_molecules']==0 and row['full_typed_source_order_identity_parity'] is True,
            'CONTIGUOUS_ACTUALLY_VERIFIED_PREFIX_NO_GAP_UNKNOWN_OR_DUPLICATE')
        cursor=hi
    return cursor


def children(plan,parent,out,budget,authority):
    """Disk-index ordinary parents; original observed_call numerical body intact."""
    child=C.meta(plan['actual_child_input_authority_reference']);objects=H.sources();evidence=R.ChildEvidence(out/'actual_child_sources.sqlite')
    db=sqlite3.connect(out/'children.sqlite');db.execute('CREATE TABLE bases(gid TEXT PRIMARY KEY,mid TEXT,value BLOB)')
    db.execute('CREATE INDEX base_mid ON bases(mid)');db.execute('CREATE TABLE children(parent TEXT,gid TEXT UNIQUE,value BLOB)')
    db.execute('CREATE INDEX child_parent ON children(parent)');db.execute('CREATE TABLE calls(parent TEXT,rid TEXT,calc TEXT,execution TEXT,PRIMARY KEY(parent,rid,calc,execution))')
    try:
        for row in I.rows(parent['table_references']['geometries'],authority,budget.check):
            if row['parent_geometry_id'] is None:db.execute('INSERT INTO bases VALUES(?,?,?)',(row['geometry_id'],row['molecule_id'],B.encode(row)))
            else:
                C.need(row['geometry_source']=='pm7','CANONICAL_PREFIX_CHILD_DOMAIN_ONLY_PM7')
                db.execute('INSERT INTO children VALUES(?,?,?)',(row['parent_geometry_id'],row['geometry_id'],B.encode(row)))
        db.commit();count=0
        for row in I.jsonl(child['binding_index_reference'],authority,budget.check):
            budget.check();rid=row['parent_geometry_id'];key=(rid,row['record_id'],row['calc_type'],row['execution_id'])
            db.execute('INSERT INTO calls VALUES(?,?,?,?)',key);found=db.execute('SELECT value FROM bases WHERE gid=?',(rid,)).fetchone()
            C.need(found is not None and B.decode(found[0])['geometry_source']=='uff_sprime','ONLY_ADDITIONAL_ACTUAL_ORDINARY_UFF_CHILD_DOMAIN')
            C.need(row['protocol_reference'] in child['protocol_source_references'],'EXACT_ROOT_REVIEWED_ACTUAL_PROTOCOL_SOURCE')
            result=B.observed_call(row,B.decode(found[0]),authority,budget.check,objects,C.meta(row['protocol_reference']),evidence)
            db.execute('INSERT INTO children VALUES(?,?,?)',(rid,result['geometry_id'],B.encode(result)));db.commit();count+=1
        C.need(count==child['actual_direct_child_count'],'EXACT_ALL_ACTUAL_CHILD_CENSUS_NOT_QA_OR_INVENTED_N1')
        def geometries():
            for gid,raw in db.execute('SELECT gid,value FROM bases ORDER BY gid'):
                yield B.decode(raw)
                for (v,) in db.execute('SELECT value FROM children WHERE parent=? ORDER BY gid',(gid,)):yield B.decode(v)
        tables={};schemas=B.schemas();tables['geometries']=I.parquet_rows(out/'geometries.parquet',geometries(),schemas['geometries'],budget)
        for kind in ('orders','atom_counts','audit_identity'):
            tables[kind]=I.parquet_rows(out/(kind+'.parquet'),I.rows(parent['table_references'][kind],authority,budget.check),schemas[kind],budget)
        def roster():
            for row in I.rows(parent['table_references']['roster'],authority,budget.check):
                row['child_count']=db.execute('SELECT count(*) FROM children c JOIN bases b ON b.gid=c.parent WHERE b.mid=?',(row['molecule_id'],)).fetchone()[0];yield row
        tables['roster']=I.parquet_rows(out/'roster.parquet',roster(),schemas['roster'],budget)
        value={'table_references':tables,'logical_range':parent['logical_range'],'molecules':parent['molecules'],'held_molecules':0,
            'worker_packet_references':parent.get('worker_packet_references',[]),'table_domain':'BASE_WITH_ALL_ACTUAL_CHILDREN',
            'all_actual_children_closed':True,'actual_direct_children':count,'full_typed_source_order_identity_parity':False}
        add_refs(authority,value);return value
    finally:evidence.close();db.close()


def sampler(plan,parent,common,out,budget,authority):
    """Original full selection, 20k anti-join and every-row/list readback objects."""
    from workflows.data_v1_final.export.d5_materialize_cpu_v1 import produce as P,readback as V0
    C.need(parent['all_actual_children_closed'] is True and parent['whole_true_Common_coverage_verified'] is True
        and parent['full_typed_source_order_identity_parity'] is True,'NO_FULL_GUIDE_SAMPLING_FROM_PARTIAL_OR_CHILDLESS_GEOMETRIES')
    view=C.meta(plan['D5_input_view_review_reference']);config=C.meta(common['config']);roles_ref=config['roles_authority'];roles=C.meta(roles_ref)
    C.need(roles['source_role_manifest']==common['roles_manifest'] and roles['validation_source']=='ROUTINE','WHOLE_ORIGINAL_ROUTINE_VAL_ROLE_AUTHORITY')
    role_tables=[C.reference(r) for r in C.meta(roles['source_role_manifest'])['outputs'] if '/molecule_roles/' in r['path']]
    C.need(role_tables and set(view['columns'])==set(C.D.TABLES) and view['feature_filter_column']=='common_population','EXACT_ORIGINAL_EXPLICIT_COLUMN_AND_FEATURE_FILTER_VIEW')
    tables={'roles':role_tables,'common':common['membership_tables'],'features':common['membership_tables'],
        **{k:[parent['table_references'][k]] for k in ('geometries','orders','atom_counts')}}
    # Internal order metadata is truthful current-parent derived authority. It
    # makes no independent Root/C0 claim; produce.run does not call old derive().
    order=C.Q.write_new(out/'derived_orders.json',{'schema':'CURRENT_PARENT_DERIVED_VERIFIED_ORDERS_V1','status':'CPU_VERIFIED_WITHIN_REAL_PARENT_NOT_CHILD_C0',
        'order_tables':tables['orders'],'common_manifest_reference':plan['common_closure_references']['manifest'],
        'seed':20261025,'D5_jointly_frozen':False})
    data=C.unique([*(r for seq in tables.values() for r in seq),*common['physical_geometry_tables']]);frames={}
    for r in data:
        authority.add(r)
        with I.held(r,authority,budget.check) as (_,_,f):frames[r['path']]=f
    leaves=dict(plan,output_cap_bytes=max(0,plan['output_cap_bytes']-budget.usage()),parent_references={'roles_authority':roles_ref,'common_manifest':plan['common_closure_references']['manifest'],
        'order_manifest':order,'input_view_review':plan['D5_input_view_review_reference']})
    producer=P.run(leaves,tables,view['columns'],frames,out,budget)
    for r in producer['artifacts'].values():authority.add(r)
    # Hash all produced DATA before original independent typed/SQL/projection
    # readback, retaining true original selection and all-TRAIN projection.
    for r in producer['artifacts'].values():
        with I.held(r,authority,budget.check):pass
    checked=V0.run(leaves,producer,out,budget)
    return {'producer':producer,'readback':checked,'eligibility':{
        'effective_role':'TRAIN','common_only':True,'excluded_geometry_keys':['molecule_id','geometry_source','geometry_id'],
        'diagnostic_base_reference':producer['artifacts']['diagnostic_base'],
        'diagnostic_targets_reference':producer['artifacts']['diagnostic_targets'],
        'all_direct_actual_children_of_heldout_bases_excluded':True,'sampling_anti_join_before_first_k':True},
        'current_parent_derived_order_manifest_reference':order,'Root_joint_D5_acceptance':False}


class CachedIO:
    held=staticmethod(R.source_fd);R=I.R;ROW_CAP=I.ROW_CAP;rows=staticmethod(I.rows);body=staticmethod(I.body)


def expected_physical(prepared_db,lo,hi,out,budget,authority):
    """Same-parent SQL projection of exact whole original 32-table physical map."""
    import duckdb
    authority.add(prepared_db)
    with R.source_fd(prepared_db,authority,budget.check):
        db=duckdb.connect(prepared_db['path'],read_only=True)
        try:
            sql='SELECT p.* FROM physical p JOIN roster r USING(molecule_id) WHERE r.logical_ordinal>=? AND r.logical_ordinal<? ORDER BY p.geometry_id'
            schema=db.execute(sql+' LIMIT 0',[lo,hi]).fetch_arrow_table().schema
            stream=db.execute(sql,[lo,hi]).fetch_record_batch(rows_per_batch=I.BATCH_ROWS)
            def rows():
                for batch in stream:
                    budget.check();C.need(batch.nbytes<=I.ROW_CAP,'FULL_EXPECTED_PHYSICAL_BATCH_NO_TRUNCATION');yield from batch.to_pylist()
            ref=I.parquet_rows(out/'expected_original_physical.parquet',rows(),schema,budget);authority.add(ref);return ref
        finally:db.close()


def whole_union(plan,parent,common,catalogue_refs,out,budget,authority):
    """Exact union of disjoint original-function-verified partitions, no C0 fiction."""
    import duckdb
    db=duckdb.connect(str(out/'union.duckdb'));db.execute("SET memory_limit='3GB'");db.execute('SET threads=16')
    quote=V.quote;tables=parent['table_references'];end=validate_prefix(catalogue_rows(catalogue_refs,authority,budget))
    try:
        C.need(end==parent['logical_range'][1] and parent['logical_range'][0]==0,'ALL_VERIFIED_PARTITION_PREFIX_INTERVALS')
        for kind,ref in tables.items():
            with I.held(ref,authority,budget.check):pass
            db.execute('CREATE VIEW '+kind+' AS SELECT * FROM read_parquet('+quote(ref['path'])+')')
        C.need(db.execute('SELECT count(*),count(DISTINCT molecule_id),count(DISTINCT logical_ordinal),min(logical_ordinal),max(logical_ordinal) FROM roster').fetchone()
            ==(end,end,end,0,end-1),'EXACT_ALL_LOGICAL_ORDINALS_AND_UNIQUE_MOLECULES')
        C.need(not db.execute('SELECT geometry_id FROM geometries GROUP BY geometry_id HAVING count(*)<>1 LIMIT 1').fetchall(),'NO_PHYSICAL_ID_COLLISION_ACROSS_PARTITIONS')
        C.need(not db.execute('SELECT 1 FROM orders GROUP BY geometry_id,order_type HAVING count(*)<>1 LIMIT 1').fetchall(),'NO_DUPLICATE_ORDER_ROW_ACROSS_PARTITIONS')
        refs=common['membership_tables']
        for r in refs:
            with R.source_fd(r,authority,budget.check):pass
        db.execute('CREATE VIEW members AS SELECT * FROM read_parquet(['+','.join(quote(r['path']) for r in refs)+'])')
        total=sum(x['molecules'] for x in common['roles']);full=end==total
        expected='SELECT molecule_id FROM members WHERE common_population ORDER BY molecule_id'
        if not full:expected+=' LIMIT '+str(end)
        C.need(not db.execute('SELECT molecule_id FROM roster EXCEPT ('+expected+')').fetchall()
            and not db.execute('('+expected+') EXCEPT SELECT molecule_id FROM roster').fetchall(),'EXACT_ORIGINAL_COMMON_DOMAIN_NOT_COUNT_ONLY')
        return dict(parent,full_typed_source_order_identity_parity=True,whole_true_Common_coverage_verified=full,
            original_function_per_partition_readback_and_exact_union=True,actual_verified_partitions=sum(1 for _ in catalogue_rows(catalogue_refs,authority,budget)))
    finally:db.close()
