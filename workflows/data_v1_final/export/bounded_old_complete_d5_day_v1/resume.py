"""Fixed terminal-parent closed parts only; no new native/graph/science calls."""
import contextlib,hashlib,json,os,pathlib,re,stat
from . import contract as C
from workflows.data_v1_final.labels.existing_sprime_pilot_day_v1 import io as I

def review(plan):
    r=C.meta(plan['closed_feature_reuse_review_reference']);entry=r['failed_parent_registration']
    jid,actual=C.parent(entry);old=C.meta(r['old_plan_reference']);request=C.meta(entry['request_reference'])
    proof=C.meta(entry['proof_reference']);root=pathlib.Path(r['old_output_root'])
    C.need(r['schema']=='ROOT_REVIEWED_D5_FAILED_CLOSED_PART_REUSE_V1' and r['status']=='APPROVED_EXACT_READONLY_CLOSED_PARTS'
        and r['reviewer']=='root' and actual['state']=='FAILED' and actual['exit_code']=='1:0'
        and str(jid)==str(r['actual_failed_job_id'])=='4525160' and request['scope_key']==C.KEY and request['kind']=='analysis'
        and request['cpus']==16 and request['wall_seconds']==86400 and request['pilot']is False
        and request['execution_argv']==[C.PY,'-B','-m',C.MODULE,'--plan',r['old_plan_reference']['path'],'--startup-proof',entry['proof_reference']['path']]
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
    archive=C.meta(r['old_source_archive_reference']);wanted={v['path']:v for v in request['source_references'] if pathlib.Path(v['path']).parent==C.HERE}
    found={}
    for item in archive['entries']:
        origin=item['origin_reference'];snapshot=item['snapshot_reference'];p=pathlib.Path(snapshot['path'])
        C.need(C.RUN/'control/source_snapshots' in p.parents and C.P.pin(p)==snapshot
            and origin['bytes']==snapshot['bytes'] and origin['sha256']==snapshot['sha256'],'EXACT_OLD_SOURCE_SNAPSHOT_BYTES')
        found[origin['path']]=origin
    C.need(found==wanted and len(wanted)==11,'EXACT_FAILED_SOURCE11_NOT_CURRENT_SOURCE12')
    refs=[plan['closed_feature_reuse_review_reference'],r['old_plan_reference'],r['old_source_archive_reference'],*entry.values()]
    refs=[v for v in refs if type(v)is dict and set(v)>={'path','bytes','sha256'}]
    return r,root,C.unique(refs+[x['snapshot_reference'] for x in archive['entries']])

def frame(s):return (s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns,s.st_uid,s.st_mode,s.st_nlink)

@contextlib.contextmanager
def closed(path,root,ctx,expected=None):
    path=pathlib.Path(path);C.need(path.parent==root/'native_features' and not any(p.is_symlink() for p in (path,*path.parents)),
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
    r,root,_=review(ctx.plan);folder=root/'native_features';C.need(folder.is_dir() and not folder.is_symlink(),'FIXED_FAILED_NATIVE_PART_DIRECTORY')
    files={p.name:p for p in folder.iterdir()};feature_names=sorted(n for n in files if re.fullmatch(r'features_[0-9]{6}\.parquet',n))
    C.need(feature_names and len(feature_names)<=r['maximum_feature_parts'],'EXISTING_BOUNDED_CLOSED_FEATURE_PARTS')
    C.need(all(re.fullmatch(r'(features_|held_)[0-9]{6}\.parquet|checkpoint_[0-9]{6}\.json|unknown_chunk_[0-9]{6}\.DATA\.json',n) for n in files),
        'NO_UNCLASSIFIED_PARTIAL_OR_EXTRA_OLD_OUTPUT_FILE')
    C.need(all(('features_'+n[len('held_'):]) in files for n in files if n.startswith('held_')),'NO_UNVALIDATED_ORPHAN_HELD_PARQUET')
    db.execute('CREATE TABLE reused_native_features(molecule_id VARCHAR PRIMARY KEY,elements_atomic_numbers BIGINT[],heavy_atoms BIGINT,generic_scaffold VARCHAR,scaffold_status VARCHAR)')
    db.execute('CREATE TABLE reused_held_rows(gid VARCHAR PRIMARY KEY,mid VARCHAR,source VARCHAR,row BLOB)')
    refs=[];held_refs=[];frames={};total=0;seen=0
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
        I.allow(ref,origin=root);refs.append(ref);frames[ref['path']]=fr;total+=ref['bytes']
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
            I.allow(hr,origin=root);held_refs.append(hr);frames[hr['path']]=hf;total+=hr['bytes']
        C.need(total<=r['maximum_total_part_bytes'],'FIXED_OLD_PART_TOTAL_READ_BOUND')
    C.need(seen==db.execute('SELECT count(*) FROM reused_native_features').fetchone()[0],'ALL_CLOSED_FEATURE_ROWS_UNIQUE')
    db.execute("CREATE TABLE reused_base_mids AS SELECT b.mid FROM reused_held_rows b JOIN reused_native_features f ON f.molecule_id=b.mid GROUP BY b.mid HAVING count(*)=2 AND count(DISTINCT b.source)=2")
    paired={x[0] for x in db.execute('SELECT mid FROM reused_base_mids').fetchall()}
    # Validate every existing part, but only completed feature+base pairs are
    # reusable. Missing diagnostic bases stay in the new native work set.
    usable=[]
    for ref in held_refs:
        with closed(ref['path'],root,ctx,ref) as (stream,_,_):
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
    audit={'schema':'BOUNDED_D5_FAILED_CLOSED_PART_READBACK_V1','old_failed_parent':r['failed_parent_registration'],
        'feature_rows_reused':seen,'feature_parts':refs,'held_parts':held_refs,'diagnostic_MIDs_with_both_closed_bases':len(paired),
        'whole_FD_SHA_schema_MID_unique_element_heavy_checked':True,'old_FAILED_or_outputs_modified':False,'new_graph_QM_UFF_calls':0}
    I.save(ctx.out/'closed_feature_readback.json',audit)
    return refs,usable,seen
