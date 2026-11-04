"""Fixed terminal-parent closed parts only; no new native/graph/science calls."""
import contextlib,hashlib,json,os,pathlib,re,stat
from . import contract as C
OLD_KEY='bounded_old_complete_d5_day_v1'
OLD_HERE=C.REPO/'workflows/data_v1_final/export'/OLD_KEY
OLD_SOURCE_COUNTS={'4525160':11,'4525178':12}
from workflows.data_v1_final.labels.existing_sprime_pilot_day_v1 import io as I

def review(plan,*,nested=False):
    r=C.meta(plan['closed_feature_reuse_review_reference']);entry=r['failed_parent_registration']
    jid,actual=C.parent(entry);old=C.meta(r['old_plan_reference']);request=C.meta(entry['request_reference'])
    proof=C.meta(entry['proof_reference']);root=pathlib.Path(r['old_output_root'])
    C.need(nested or str(jid)=='4525178','TOP_LEVEL_ONLY_REAL_COMPLETED_FEATURE_FAILED5178_NOT_NATIVE_RETRY')
    C.need(r['schema']=='ROOT_REVIEWED_D5_FAILED_CLOSED_PART_REUSE_V1' and r['status']=='APPROVED_EXACT_READONLY_CLOSED_PARTS'
        and r['reviewer']=='root' and actual['state']=='FAILED' and actual['exit_code']=='1:0'
        and str(jid)==str(r['actual_failed_job_id']) and str(jid)in OLD_SOURCE_COUNTS and request['scope_key']==OLD_KEY and request['kind']=='analysis'
        and request['cpus']==16 and request['wall_seconds']==86400 and request['pilot']is False
        and request['execution_argv']==[C.PY,'-B','-m','workflows.data_v1_final.export.'+OLD_KEY+'.run','--plan',r['old_plan_reference']['path'],'--startup-proof',entry['proof_reference']['path']]
        and proof['request']==request and proof['request_reference']==entry['request_reference']
        and root==pathlib.Path(old['output_directory']) and root.parent==C.RUN/'artifacts/labels/source_status_v1/bounded_old_complete_d5_day_v1'
        and str(root)!=plan['output_directory'],'TRUE_FAILED_ORIGIN_AND_FRESH_RECOVERY_NOT_FAKE_C0')
    for key in ('base_cache_plan_reference','pilot_priority_review_reference','hof_closed_prefix_reuse_review_reference',
                'canonical_index','source_inventory_reference','footer_manifest_reference'):
        C.need(old[key]==plan[key],'EXACT_SAME_FROZEN_D5_POPULATION_AND_SOURCE:'+key)
    C.need(all(r[k]is True for k in ('first_CPU_FD_SHA_of_fixed_closed_parts_authorized','old_outputs_and_FAILED_costs_preserved',
        'no_native_or_QM_retry','diagnostic20000_and_bases40000_unchanged')),'EXACT_READONLY_REUSE_NOT_POPULATION_RELAXATION')
    C.need(type(r['maximum_feature_parts'])is int and 1<=r['maximum_feature_parts']<=100000
        and type(r['maximum_total_part_bytes'])is int and 0<r['maximum_total_part_bytes']<=32<<30,'BOUNDED_FIXED_PART_DISCOVERY')
    archive=C.meta(r['old_source_archive_reference']);wanted={v['path']:v for v in request['source_references'] if pathlib.Path(v['path']).parent==OLD_HERE}
    found={}
    for item in archive['entries']:
        origin=item['origin_reference'];snapshot=item['snapshot_reference'];p=pathlib.Path(snapshot['path'])
        C.need(C.RUN/'control/source_snapshots' in p.parents and C.P.pin(p)==snapshot
            and origin['bytes']==snapshot['bytes'] and origin['sha256']==snapshot['sha256'],'EXACT_OLD_SOURCE_SNAPSHOT_BYTES')
        found[origin['path']]=origin
    C.need(found==wanted and len(wanted)==OLD_SOURCE_COUNTS[str(jid)],'EXACT_FAILED_PARENT_ACTUAL_SOURCE11_OR12_NOT_NEW_NAMESPACE')
    refs=[plan['closed_feature_reuse_review_reference'],r['old_plan_reference'],r['old_source_archive_reference'],*entry.values()]
    refs=[v for v in refs if type(v)is dict and set(v)>={'path','bytes','sha256'}]
    if str(jid)=='4525178':
        previous=dict(plan,closed_feature_reuse_review_reference=old['closed_feature_reuse_review_reference'])
        prior,prior_root,prior_refs=review(previous,nested=True)
        C.need(str(prior['actual_failed_job_id'])=='4525160' and prior_root!=root,'EXACT_PRIOR5160_REUSE_CHAIN_NOT_ARBITRARY_RECURSION')
        refs.extend(prior_refs)
    return r,root,C.unique(refs+[x['snapshot_reference'] for x in archive['entries']])

def frame(s):return (s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns,s.st_uid,s.st_mode,s.st_nlink)

@contextlib.contextmanager
def closed(path,root,ctx,expected=None):
    path=pathlib.Path(path);C.need((path.parent==root/'native_features' or
        (path.parent==root and path.name in ('closed_feature_readback.json','held_bases.parquet','held_random_orders.parquet','held_roster.parquet')))
        and not any(p.is_symlink() for p in (path,*path.parents)),
        'ONLY_EXACT_FIXED_OLD_NATIVE_FEATURE_CHILD')
    before=path.lstat();C.need(stat.S_ISREG(before.st_mode) and before.st_uid==1278 and before.st_nlink==1
        and 0<before.st_size<=128<<20,'CLOSED_PART_REAL_UID_REGULAR_SIZE')
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
    with os.fdopen(fd,'rb') as stream:
        C.need(frame(os.fstat(stream.fileno()))==frame(before),'CLOSED_PART_SAME_FD_BEFORE_SHA')
        h=hashlib.sha256();n=0
        while block:=stream.read(1<<20):ctx.check();h.update(block);n+=len(block)
        ref={'path':str(path),'bytes':n,'sha256':h.hexdigest()}
        C.need(frame(os.fstat(stream.fileno()))==frame(before)==frame(path.lstat()) and n==before.st_size,'CLOSED_PART_FULL_SHA_STABLE_FD')
        if expected is not None:C.need(ref==expected,'ORIGINAL_CHECKPOINT_POSITIVE_PART_SHA')
        stream.seek(0)
        try:yield stream,ref,frame(before)
        finally:C.need(frame(os.fstat(stream.fileno()))==frame(before)==frame(path.lstat()),'CLOSED_PART_FRAME_AFTER_PARSE')

def feature(row,expected):
    z=row['elements_atomic_numbers'];mid=row['molecule_id']
    C.need(type(mid)is str and mid and type(z)is list and z and all(type(a)is int and 1<=a<=118 for a in z)
        and z==sorted(set(z)) and type(row['heavy_atoms'])is int and row['heavy_atoms']>=0,'EXACT_CLOSED_NATIVE_FEATURE_SCALARS')
    C.need(z==list(expected['elements_atomic_numbers']) and row['heavy_atoms']==expected['heavy_atoms'],'CLOSED_FEATURE_NATIVE_ELEMENT_HEAVY_EQUALS_MOTHER')
    return mid

def needs_work(mid,diagnostic,features,paired):return mid not in features or (mid in diagnostic and mid not in paired)

def load(ctx,db):
    from . import produce as P
    import pyarrow.parquet as pq
    r,root,_=review(ctx.plan);latest_r,latest_root=r,root;origins=[(r,root)]
    if str(r['actual_failed_job_id'])=='4525178':
        old=C.meta(r['old_plan_reference'])
        previous=dict(ctx.plan,closed_feature_reuse_review_reference=old['closed_feature_reuse_review_reference'])
        prior,prior_root,_=review(previous,nested=True);origins.insert(0,(prior,prior_root))
    db.execute('CREATE TABLE reused_native_features(molecule_id VARCHAR PRIMARY KEY,elements_atomic_numbers BIGINT[],heavy_atoms BIGINT,generic_scaffold VARCHAR,scaffold_status VARCHAR)')
    db.execute('CREATE TABLE reused_held_rows(gid VARCHAR PRIMARY KEY,mid VARCHAR,source VARCHAR,row BLOB)')
    refs=[];held_refs=[];frames={};roots_by_path={};total=0;seen=0;origin_results={}
    for r,root in origins:
        start_refs=len(refs);start_held=len(held_refs)
        folder=root/'native_features';C.need(folder.is_dir() and not folder.is_symlink(),'FIXED_FAILED_NATIVE_PART_DIRECTORY')
        files={p.name:p for p in folder.iterdir()};feature_names=sorted(n for n in files if re.fullmatch(r'features_[0-9]{6}\.parquet',n))
        C.need(feature_names and len(feature_names)<=r['maximum_feature_parts'],'EXISTING_BOUNDED_CLOSED_FEATURE_PARTS')
        C.need(all(re.fullmatch(r'(features_|held_)[0-9]{6}\.parquet|checkpoint_[0-9]{6}\.json|unknown_chunk_[0-9]{6}\.DATA\.json',n) for n in files),
            'NO_UNCLASSIFIED_PARTIAL_OR_EXTRA_OLD_OUTPUT_FILE')
        C.need(all(('features_'+n[len('held_'):]) in files for n in files if n.startswith('held_')),'NO_UNVALIDATED_ORPHAN_HELD_PARQUET')
        for name in feature_names:
            ctx.check();suffix=name[len('features_'):-len('.parquet')];checkpoint=files.get('checkpoint_'+suffix+'.json')
            C.need(checkpoint is not None,'ONLY_PART_WITH_PRODUCER_POST_WRITE_CHECKPOINT')
            C.need(checkpoint.lstat().st_size<=1<<20,'SMALL_ORIGINAL_CHECKPOINT_NOT_SCIENCE_CONTAINER')
            with closed(checkpoint,root,ctx) as (stream,cp,fr):note=json.load(stream)
            C.need(str(note['actual_parent_job_id'])==str(r['actual_failed_job_id']),'CHECKPOINT_TRUE_FAILED_PARENT')
            with closed(files[name],root,ctx,note['last_feature_part']) as (stream,ref,fr):
                src=pq.ParquetFile(stream)
                try:
                    C.need(src.schema_arrow.equals(P.schema_features(),check_metadata=False),'EXACT_ORIGINAL_FEATURE_SCHEMA')
                    table=src.read(use_threads=False)
                    db.register('closed_feature_batch',table)
                    try:
                        expected={a[0]:a[1:] for a in db.execute('SELECT m.molecule_id,m.elements_atomic_numbers,m.heavy_atoms FROM mother m JOIN closed_feature_batch f USING(molecule_id)').fetchall()}
                        C.need(len(expected)==table.num_rows,'CLOSED_FEATURE_MIDS_UNIQUE_AND_IN_UNCHANGED_MOTHER')
                        for row in table.to_pylist():
                            e=expected[row['molecule_id']];feature(row,{'elements_atomic_numbers':e[0],'heavy_atoms':e[1]})
                        db.execute('INSERT INTO reused_native_features SELECT * FROM closed_feature_batch')
                    finally:db.unregister('closed_feature_batch')
                    seen+=table.num_rows
                finally:src.close()
            I.allow(ref,origin=root);refs.append(ref);frames[ref['path']]=fr;roots_by_path[ref['path']]=root;total+=ref['bytes']
            C.need(note['anchors_closed']==seen and type(note['errors'])is int and note['errors']>=0,'ORIGINAL_CUMULATIVE_CLOSED_FEATURE_MASS')
            held=files.get('held_'+suffix+'.parquet')
            if held is not None:
                with closed(held,root,ctx) as (stream,hr,hf):
                    src=pq.ParquetFile(stream)
                    try:
                        C.need(src.schema_arrow.equals(P.Wire.schemas()['geometries'],check_metadata=False),'EXACT_ORIGINAL_HELD_GEOMETRY_SCHEMA')
                        for batch in src.iter_batches(batch_size=256,use_threads=False):
                            for row in batch.to_pylist():
                                import numpy as np
                                P.G.Geometry.physical_key(row);z=np.asarray(row['atomic_numbers'],dtype='<i8');xyz=np.asarray(row['positions_A'],dtype='<f8')
                                C.need(xyz.shape==(len(z),3) and np.isfinite(xyz).all()
                                    and hashlib.sha256(z.tobytes()).hexdigest()==row['atom_order_sha256']
                                    and P.IO.geometry_sha(z,xyz)==row['geometry_sha256'],'CLOSED_BASE_REAL_FLOAT64_ATOM_GEOMETRY_SHA')
                                expected=db.execute('SELECT geometry_id,native_record_id,sprime_conf_idx FROM held_ids WHERE molecule_id=? AND geometry_source=?',
                                    [row['molecule_id'],row['geometry_source']]).fetchone()
                                C.need(expected==(row['geometry_id'],row.get('native_record_id'),row.get('sprime_conf_idx'))
                                    and row.get('parent_geometry_id')is None and row.get('view_id')is None,'CLOSED_BASE_FIXED_ORIGINAL_20K_SOURCE_ID')
                                db.execute('INSERT INTO reused_held_rows VALUES(?,?,?,?)',[row['geometry_id'],row['molecule_id'],row['geometry_source'],P.Wire.encode(row)])
                    finally:src.close()
                I.allow(hr,origin=root);held_refs.append(hr);frames[hr['path']]=hf;roots_by_path[hr['path']]=root;total+=hr['bytes']
            C.need(total<=r['maximum_total_part_bytes'],'FIXED_OLD_PART_TOTAL_READ_BOUND')
        origin_results[str(r['actual_failed_job_id'])]={'features':refs[start_refs:],'held':held_refs[start_held:],'seen':seen}
        if str(r['actual_failed_job_id'])=='4525160' and len(origins)==2:
            # Same original usable-pair rule: an orphan prior base is evidence,
            # not an accepted geometry. Preserve its file/ref; omit only that
            # unpaired current SQL row before admitting the later closed pair.
            db.execute('DELETE FROM reused_held_rows WHERE mid NOT IN (SELECT b.mid FROM reused_held_rows b JOIN reused_native_features f ON f.molecule_id=b.mid GROUP BY b.mid HAVING count(*)=2 AND count(DISTINCT b.source)=2)')
    C.need(seen==db.execute('SELECT count(*) FROM reused_native_features').fetchone()[0],'ALL_CLOSED_FEATURE_ROWS_UNIQUE')
    db.execute("CREATE TABLE reused_base_mids AS SELECT b.mid FROM reused_held_rows b JOIN reused_native_features f ON f.molecule_id=b.mid GROUP BY b.mid HAVING count(*)=2 AND count(DISTINCT b.source)=2")
    paired={x[0] for x in db.execute('SELECT mid FROM reused_base_mids').fetchall()}
    # Validate every existing part, but only completed feature+base pairs are
    # reusable. Missing diagnostic bases stay in the new native work set.
    usable=[]
    for ref in held_refs:
        with closed(ref['path'],roots_by_path[ref['path']],ctx,ref) as (stream,_,_):
            src=pq.ParquetFile(stream)
            try:rows=src.read(columns=['molecule_id'],use_threads=False).column(0).to_pylist()
            finally:src.close()
        if all(mid in paired for mid in rows):usable.append(ref)
        elif any(mid in paired for mid in rows):
            # Rare mixed orphan chunk: keep the original bytes; export only the
            # validated pair rows to a fresh tiny part, never redo graph math.
            rows=[P.Wire.decode(bytes(x[0])) for x in db.execute('SELECT row FROM reused_held_rows b JOIN reused_base_mids m USING(mid) WHERE b.gid IN (SELECT geometry_id FROM read_parquet(?))',[ref['path']]).fetchall()]
            usable.append(I.write_parquet(ctx.out/('reused_held_'+str(len(usable))+'.parquet'),iter(rows),P.Wire.schemas()['geometries']))
    for path,fr in frames.items():C.need(frame(pathlib.Path(path).lstat())==fr,'OLD_PART_FRAME_BEFORE_NEW_NATIVE_DISPATCH')
    aggregate=None
    if str(latest_r['actual_failed_job_id'])=='4525178':
        aggregate=completed_views(ctx,db,latest_root,origin_results,seen,len(paired))
    audit={'schema':'BOUNDED_D5_FAILED_CLOSED_PART_READBACK_V1','old_failed_parent':latest_r['failed_parent_registration'],
        'related_failed_parents':[r['failed_parent_registration'] for r,_ in origins],
        'closed_complete_tables':aggregate,
        'feature_rows_reused':seen,'feature_parts':refs,'held_parts':held_refs,'diagnostic_MIDs_with_both_closed_bases':len(paired),
        'whole_FD_SHA_schema_MID_unique_element_heavy_checked':True,'old_FAILED_or_outputs_modified':False,'new_graph_QM_UFF_calls':0}
    audit_ref=I.allow(ctx.io.save(ctx.out/'closed_feature_readback.json',audit))
    if aggregate is not None:
        ctx.validated_closed_physical={'table_references':aggregate,'closed_feature_readback_reference':audit_ref}
        usable=[aggregate['geometries']]
    return refs,usable,seen

def complete_counts(features,mother,paired,bases):
    C.need(all(type(v)is int and v>=0 for v in (features,mother,paired,bases))
        and features==mother and paired==20000 and bases==40000,
        'COMPLETE_FAILED5178_ALL_MOTHER_20K_PAIRS_40K_BASES_NOT_PARTIAL_REUSE')

def completed_views(ctx,db,root,origins,seen,paired):
    from . import produce as P
    import pyarrow.parquet as pq
    complete_counts(seen,db.execute('SELECT count(*) FROM mother').fetchone()[0],paired,
        db.execute('SELECT count(*) FROM reused_held_rows').fetchone()[0])
    # The old readback was emitted after validating only the inherited5160
    # parts. Its exact list must match the independently re-read prior origin.
    with closed(root/'closed_feature_readback.json',root,ctx) as (stream,ref,fr):
        note=json.load(stream)
        C.need(note['schema']=='BOUNDED_D5_FAILED_CLOSED_PART_READBACK_V1'
            and str(C.parent(note['old_failed_parent'])[0])=='4525160'
            and note['feature_rows_reused']==origins['4525160']['seen']
            and note['feature_parts']==origins['4525160']['features']
            and note['held_parts']==origins['4525160']['held']
            and note['whole_FD_SHA_schema_MID_unique_element_heavy_checked']is True,
            'OLD5178_INHERITED5160_READBACK_LIST_EQUALS_ACTUAL_REVALIDATED_PARTS')
        I.allow(ref,origin=root)
    tables={};seen_gids=set()
    with closed(root/'held_bases.parquet',root,ctx) as (stream,ref,fr):
        src=pq.ParquetFile(stream)
        try:
            C.need(src.schema_arrow.equals(P.Wire.schemas()['geometries'],check_metadata=False),'WHOLE_CLOSED40K_ORIGINAL_GEOMETRY_SCHEMA')
            for batch in src.iter_batches(batch_size=256,use_threads=False):
                ctx.check()
                for row in batch.to_pylist():
                    gid=row['geometry_id'];prior=db.execute('SELECT row FROM reused_held_rows WHERE gid=?',[gid]).fetchone()
                    C.need(gid not in seen_gids and prior is not None and bytes(prior[0])==P.Wire.encode(row),
                        'FINAL40K_F64_ALL_FIELDS_BYTE_EQUAL_VALIDATED_ORIGINAL_PART_UNION')
                    seen_gids.add(gid)
        finally:src.close()
        C.need(len(seen_gids)==40000,'WHOLE_FINAL40K_NO_MISSING_DUPLICATE_OR_EXTRA')
        tables['geometries']=I.allow(ref,origin=root)
    queries={
        'orders':("held_random_orders.parquet","SELECT molecule_id,geometry_source,geometry_id,'fixed_random' AS order_type,'fixed_random' AS method,rank FROM held_ids",40000),
        'roster':('held_roster.parquet','SELECT row_number() OVER(ORDER BY m.molecule_id)-1 AS logical_ordinal,m.molecule_id,m.S_conformers AS PM7_N,m.Sprime_conformers AS UFF_N,0::BIGINT AS child_count FROM mother m JOIN diagnostic_mids d USING(molecule_id) ORDER BY m.molecule_id',20000)}
    for name,(filename,query,count) in queries.items():
        with closed(root/filename,root,ctx) as (stream,ref,fr):
            src=pq.ParquetFile(stream)
            try:
                table=src.read(use_threads=False);exact_table(db,table,query,count)
            finally:src.close()
            tables[name]=I.allow(ref,origin=root)
    return tables
def exact_table(db,table,query,count):
    expected=db.execute('SELECT * FROM ('+query+') LIMIT 0').fetch_arrow_table().schema
    C.need(table.schema.equals(expected,check_metadata=False),'EXACT_CLOSED_RANDOM_ORDER_OR_ROSTER_SCHEMA')
    C.need(table.num_rows==count,'EXACT_CLOSED_ORDER_OR_ROSTER_MASS')
    db.register('closed_final_table',table)
    try:
        C.need(db.execute('SELECT count(*) FROM (SELECT * FROM closed_final_table EXCEPT ALL SELECT * FROM ('+query+'))').fetchone()[0]==0
            and db.execute('SELECT count(*) FROM (SELECT * FROM ('+query+') EXCEPT ALL SELECT * FROM closed_final_table)').fetchone()[0]==0,
            'WHOLE_CLOSED_TABLE_TWO_WAY_EXACT_ORIGINAL_FROZEN_RANDOM_IDS_RANKS_N')
    finally:db.unregister('closed_final_table')