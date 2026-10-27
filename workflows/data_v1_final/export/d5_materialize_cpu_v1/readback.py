"""Independent complete list readback and original TRAIN projection, no labels."""
from __future__ import annotations
import hashlib,json,os,struct
from . import contract as C,resources as R
from .produce import originals


def no_rows(db,sql,code,args=()):
    C.need(db.execute(sql,args).fetchone() is None,code)


def check_semantics(db,seed):
    _,_,I,_,_=originals()
    expected={'train_120000':120000,'train_240000':240000,'train_600000':600000,'pilot_train':50000,'pilot_val':5000}
    for subset,n in expected.items():C.need(I.scalar(db,'SELECT count(*) FROM subset_members WHERE subset=?',(subset,))==n,'EXACT_GUIDE_SUBSET_COUNT:'+subset)
    for small,large in (('pilot_train','train_120000'),('train_120000','train_240000'),('train_240000','train_600000'),('train_600000','train_all'),('pilot_val','val_all')):
        no_rows(db,'SELECT molecule_id FROM subset_members WHERE subset=? EXCEPT SELECT molecule_id FROM subset_members WHERE subset=?','NESTED_MEMBERSHIP_DIFFERS',(small,large))
    no_rows(db,"SELECT 1 FROM subset_members s JOIN roles r USING(molecule_id) WHERE (s.subset IN('pilot_val','val_all') AND r.effective_role!='VAL') OR (s.subset NOT IN('pilot_val','val_all') AND r.effective_role!='TRAIN')",'TRAIN_VAL_LEAKAGE')
    no_rows(db,"SELECT 1 FROM diagnostic_molecules d JOIN roles r USING(molecule_id) WHERE r.effective_role!='TRAIN'",'DIAGNOSTIC_MID_NOT_TRAIN')
    no_rows(db,"SELECT molecule_id FROM diagnostic_molecules EXCEPT SELECT molecule_id FROM subset_members WHERE subset='train_all'",'SEEN_DIAGNOSTIC_MID_REMOVED_FROM_TRAIN')
    C.need(I.scalar(db,'SELECT count(*) FROM diagnostic_molecules')==20000 and I.scalar(db,'SELECT count(*) FROM diagnostic_base')==40000,'EXACT20K_AND_TWO_BASES')
    no_rows(db,"SELECT molecule_id FROM diagnostic_molecules EXCEPT SELECT molecule_id FROM geometries WHERE parent_geometry_id IS NULL GROUP BY molecule_id HAVING sum(geometry_source='pm7')>=2 AND sum(geometry_source='uff_sprime')>=2",'DIAGNOSTIC_ORDINARY_GEOMETRY_BOTH_AT_LEAST_TWO')
    no_rows(db,"SELECT 1 FROM diagnostic_base d JOIN orders o USING(geometry_id) WHERE o.order_type='fixed_random' AND o.rank!=(SELECT max(x.rank) FROM orders x WHERE x.molecule_id=o.molecule_id AND x.geometry_source=o.geometry_source AND x.order_type='fixed_random')",'HELDOUT_IS_NOT_FIXED_RANDOM_LAST')
    exact_targets='SELECT g.molecule_id,g.geometry_source,g.geometry_id FROM geometries g WHERE EXISTS(SELECT 1 FROM diagnostic_base d WHERE d.geometry_id=g.geometry_id OR d.geometry_id=g.parent_geometry_id)'
    no_rows(db,exact_targets+' EXCEPT SELECT * FROM diagnostic_targets','HELDOUT_CHILD_MISSING')
    no_rows(db,'SELECT * FROM diagnostic_targets EXCEPT '+exact_targets,'EXTRA_DIAGNOSTIC_TARGET')
    expected_training='SELECT g.* FROM geometries g WHERE NOT EXISTS(SELECT 1 FROM diagnostic_targets d WHERE d.geometry_id=g.geometry_id)'
    no_rows(db,expected_training+' EXCEPT SELECT * FROM training_geometry','TRAINING_GEOMETRY_MISSING')
    no_rows(db,'SELECT * FROM training_geometry EXCEPT '+expected_training,'DIAGNOSTIC_BASE_OR_CHILD_LEAK')
    no_rows(db,'SELECT 1 FROM training_geometry g JOIN diagnostic_targets d ON g.geometry_id=d.geometry_id OR g.parent_geometry_id=d.geometry_id','DIAGNOSTIC_PARENT_LEAK')
    no_rows(db,'SELECT 1 FROM training_orders GROUP BY molecule_id,geometry_source,order_type HAVING min(training_rank)!=0 OR max(training_rank)+1!=count(*)','TRAINING_RANK_GAP')
    no_rows(db,'SELECT 1 FROM training_geometry g LEFT JOIN training_orders o USING(geometry_id) WHERE g.parent_geometry_id IS NULL GROUP BY g.geometry_id HAVING count(o.order_type)!=3','THREE_COMPLETE_RETAINED_ORDERS')
    no_rows(db,'SELECT 1 FROM training_orders a JOIN training_orders b ON a.molecule_id=b.molecule_id AND a.geometry_source=b.geometry_source AND a.order_type=b.order_type WHERE a.rank<b.rank AND a.training_rank>=b.training_rank','ORIGINAL_ORDER_NOT_PRESERVED')
    previous={};observed=0
    for row in db.execute('SELECT molecule_id,effective_role,selection_rank FROM ranked ORDER BY effective_role,selection_rank'):
        key=(I.rank_hash(seed,row['effective_role'],row['molecule_id']),row['molecule_id']);role=row['effective_role']
        last=previous.get(role);C.need(last is None or (last[0]<key and last[1]+1==row['selection_rank']),'ORIGINAL_UNIFORM_HASH_RANK_DIFFERS')
        if last is None:C.need(row['selection_rank']==0,'UNIFORM_RANK_STARTS_AT_ZERO')
        previous[role]=(key,row['selection_rank']);observed+=1
    return {'ranked_molecules_checked':observed,'diagnostic_molecules':20000,'diagnostic_base_rows':40000,
        'diagnostic_target_rows':I.scalar(db,'SELECT count(*) FROM diagnostic_targets'),
        'subset_counts':{r[0]:r[1] for r in db.execute('SELECT subset,count(*) FROM subset_members GROUP BY subset')},
        'retained_conformer_counts_by_role_source_N':[
            dict(r) for r in db.execute("SELECT r.effective_role,g.geometry_source,g.n AS retained_N,count(*) AS molecules FROM (SELECT molecule_id,geometry_source,count(*) AS n FROM training_geometry WHERE parent_geometry_id IS NULL GROUP BY molecule_id,geometry_source) g JOIN roles r USING(molecule_id) GROUP BY r.effective_role,g.geometry_source,g.n ORDER BY 1,2,3")]}


def same_value(a,b):
    if type(a) is float or type(b) is float:return type(a) is type(b) and struct.pack('<d',a)==struct.pack('<d',b)
    return type(a) is type(b) and a==b


def parquet_matches(db,ref,query,parameters=()):
    import pyarrow.parquet as pq
    p=pq.ParquetFile(ref['path']);cursor=db.execute(query,parameters);n=0
    try:
        for batch in p.iter_batches(batch_size=512,use_threads=False):
            expected=cursor.fetchmany(len(batch));actual=batch.to_pylist()
            C.need(len(expected)==len(actual),'PARQUET_EXTRA_ROWS')
            for left,right in zip(expected,actual):
                C.need(set(left.keys())==set(right) and all(same_value(left[k],right[k]) for k in right),'PARQUET_SQLITE_TYPED_ROW_DIFFERS')
            n+=len(actual)
        C.need(cursor.fetchone() is None,'PARQUET_MISSING_ROWS')
    finally:p.close()
    return n


def projection_worker(task):
    database,lo,hi,control=task
    _,_,I,_,P=originals();R.worker_check(control);db=I.connect(database,readonly=True)
    digest=hashlib.sha256();mids=entries=0
    try:
        sql="SELECT molecule_id FROM ranked WHERE effective_role='TRAIN' AND molecule_id>=?"
        args=[lo]
        if hi is not None:sql+=' AND molecule_id<?';args.append(hi)
        for item in db.execute(sql+' ORDER BY molecule_id',args):
            R.worker_check(control);mid=item[0]
            geometries=[dict(r) for r in db.execute('SELECT * FROM training_geometry WHERE molecule_id=? ORDER BY geometry_id',(mid,))]
            orders=[dict(r) for r in db.execute('SELECT * FROM training_orders WHERE molecule_id=? ORDER BY geometry_source,order_type,training_rank',(mid,))]
            excluded=[dict(r) for r in db.execute('SELECT * FROM diagnostic_targets WHERE molecule_id=? ORDER BY geometry_id',(mid,))]
            atoms={r['geometry_id']:r['n_atoms'] for r in db.execute('SELECT a.* FROM atom_counts a JOIN training_geometry g USING(geometry_id) WHERE g.molecule_id=? AND g.parent_geometry_id IS NULL',(mid,))}
            value=P.project_training_sources(mid,effective_role='TRAIN',training_geometries=geometries,training_orders=orders,
                diagnostic_targets=excluded,native_atom_counts=atoms,group_mask={'S':False,'D':False,'P':False},
                family_mask={'D5_STRUCTURAL_READBACK_ONLY':False})
            for src,entry in value['source_entries'].items():
                minimum=db.execute("SELECT geometry_id FROM training_orders WHERE molecule_id=? AND geometry_source=? AND order_type='energy' AND training_rank=0",(mid,src)).fetchone()[0]
                C.need(entry['minimum_energy_conformer_id']==minimum,'RETAINED_ENERGY_MINIMUM_NOT_ORIGINAL_ZERO')
                entries+=len(entry['conformers'])
            digest.update(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()+b'\n');mids+=1
    finally:db.close()
    return {'molecules':mids,'base_entries':entries,'projection_stream_sha256':digest.hexdigest(),'pid':os.getpid(),
        'actual_original_projection_object':True,'synthetic_exposure_flags_are_not_a_Model_recipe':True}


def run(plan,parent,out,budget):
    _,_,I,_,_=originals();refs=parent['artifacts'];manifest=I.read_json(refs['d5_manifest']['path'])
    C.need(manifest['status']=='D5_PARQUET_LISTS_FROZEN' and manifest['fixture'] is False
        and manifest['seed']==plan['seed'],'EXACT_ACTUAL_PRODUCER_D5_MANIFEST')
    db=I.connect(refs['database']['path'],readonly=True)
    try:
        C.need(db.execute('PRAGMA quick_check').fetchone()[0]=='ok','ACTUAL_SQLITE_READBACK_INTEGRITY')
        report=check_semantics(db,plan['seed']);rows={}
        queries={
            'geometry_map':'SELECT g.*,r.effective_role,r.source_role FROM geometries g JOIN roles r USING(molecule_id) ORDER BY g.geometry_id',
            'diagnostic_base':'SELECT * FROM diagnostic_base ORDER BY molecule_id,geometry_source',
            'diagnostic_targets':'SELECT * FROM diagnostic_targets ORDER BY molecule_id,geometry_source,geometry_id',
            'training_orders':'SELECT * FROM training_orders ORDER BY molecule_id,geometry_source,order_type,training_rank',
            'training_geometry':'SELECT g.*,r.effective_role,r.source_role FROM training_geometry g JOIN roles r USING(molecule_id) ORDER BY g.geometry_id',
            'native_atom_counts':'SELECT * FROM atom_counts ORDER BY geometry_id'}
        for key,sql in queries.items():budget.check();rows[key]=parquet_matches(db,refs[key],sql)
        for name in manifest['subsets']:
            budget.check();rows['subset_'+name]=parquet_matches(db,refs['subset_'+name],
                'SELECT * FROM subset_members WHERE subset=? ORDER BY selection_rank',(name,))
        n=I.scalar(db,"SELECT count(*) FROM ranked WHERE effective_role='TRAIN'")
        width=max(1,(n+15)//16);boundaries=[]
        for index in range(16):
            row=db.execute("SELECT molecule_id FROM ranked WHERE effective_role='TRAIN' ORDER BY molecule_id LIMIT 1 OFFSET ?",(index*width,)).fetchone()
            if row is not None:boundaries.append(row[0])
        tasks=[(refs['database']['path'],lo,boundaries[i+1] if i+1<len(boundaries) else None,budget.control) for i,lo in enumerate(boundaries)]
    finally:db.close()
    projections=list(R.ordered_map(projection_worker,tasks,budget))
    C.need(sum(r['molecules'] for r in projections)==n and len(projections)==16,'ALL_TRAIN_ORIGINAL_PROJECTION_NOT_PROFILE')
    stats=I.connect(refs['distributions_database']['path'],readonly=True)
    try:
        C.need(stats.execute('PRAGMA quick_check').fetchone()[0]=='ok','DISTRIBUTIONS_DATABASE_INTEGRITY')
        query="""SELECT t.subset,b.dimension,b.category,coalesce(c.molecules,0) AS molecules,
          1.0*coalesce(c.molecules,0)/t.molecules AS fraction,b.subset AS baseline_subset,b.molecules AS baseline_molecules,
          1.0*b.molecules/bt.molecules AS baseline_fraction,
          1.0*coalesce(c.molecules,0)/t.molecules-1.0*b.molecules/bt.molecules AS fraction_difference
          FROM totals t JOIN counts b ON b.subset=CASE WHEN t.subset IN('pilot_val','val_all') THEN 'val_all' ELSE 'train_all' END
          JOIN totals bt ON bt.subset=b.subset LEFT JOIN counts c ON c.subset=t.subset AND c.dimension=b.dimension AND c.category=b.category
          ORDER BY t.subset,b.dimension,b.category"""
        budget.check();rows['distributions_table']=parquet_matches(stats,refs['distributions_table'],query)
    finally:stats.close()
    report.update({'parquet_rows_exact':rows,'projection_workers':projections,'all_TRAIN_molecules_projected':n,
        'VAL_role_lists_verified_without_coercing_VAL_to_TRAIN':True})
    return report
