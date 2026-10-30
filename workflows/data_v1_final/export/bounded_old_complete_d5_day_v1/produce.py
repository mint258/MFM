"""Original native/scaffold objects, fixed random identities, no RMSD/HOF scan."""
import collections,concurrent.futures as cf,hashlib,json,multiprocessing as mp,os,pathlib,stat
from . import contract as C
from workflows.data_v1_final.labels.existing_sprime_pilot_day_v1 import io as I,geometry as G
from workflows.data_v1_final.conformers.pm7_precache_hof_resume_day_v1 import worker_context as WORKER
from workflows.data_v1_final.export.d5_inputs_builder_v1 import reader as NativeReader
from workflows.data_v1_final.conformers import selection
from workflows.data_v1_final.export.d5_inputs_compound_day_v1 import core as Wire
NATIVE_FRAMES=NativeReader.NATIVE_FRAMES;IO=G.OriginalWorker.IO
BASE_INDEX_SQL="CREATE TABLE base_index AS SELECT f.molecule_id,'pm7' AS geometry_source,'pm7:'||sha256(f.record_id) AS geometry_id,f.record_id AS native_record_id,NULL::BIGINT AS sprime_conf_idx,f.source_path,f.real_index AS source_row_index,row_number() OVER(PARTITION BY f.molecule_id ORDER BY original_stable_order(f.molecule_id,'pm7',f.record_id),f.record_id)-1 AS rank FROM native_selected f UNION ALL SELECT u.mid,'uff_sprime','uff_sprime:'||sha256(u.mid||':'||CAST(u.idx AS VARCHAR)),NULL,u.idx,u.source,u.physical_row,row_number() OVER(PARTITION BY u.mid ORDER BY original_stable_order(u.mid,'uff_sprime',CAST(u.idx AS VARCHAR)),CAST(u.idx AS VARCHAR))-1 FROM uff_ids u"

def canonical_native_path(pointer):
    # Caller supplies only rows of the actual whole-SHA formal index, already
    # bidirectionally compared in adopt.restore (and Native G's same authority).
    # A canonical absolute/relative/.. or symlink locator is NOT a project-root
    # membership test. The original Native.read resolves the identical spelling.
    text=pointer['source_path']
    C.need(type(text)is str and text and '\x00' not in text
        and type(pointer['record_id'])is str and pointer['record_id']
        and type(pointer['molecule_id'])is str and pointer['molecule_id'],'EXACT_CANONICAL_FORMAL_NATIVE_POINTER_NOT_ARBITRARY_CLI_PATH')
    p=pathlib.Path(text)
    return p if p.is_absolute() else pathlib.Path('/share/home/zixiao/descriptor_analysis')/p

def native_record_and_value(pointer,native):
    p=canonical_native_path(pointer);target=p.resolve(strict=True)
    C.need(type(pointer['real_index']) is int and pointer['real_index']>=0 and type(pointer['total_atoms']) is int
        and pointer['total_atoms']>0 and len(pointer['record_payload_sha256'])==64,'EXACT_CANONICAL_NATIVE_POINTER')
    before=target.stat();C.need(stat.S_ISREG(before.st_mode) and before.st_uid==1278,'ORIGINAL_REGULAR_UID_NATIVE_FILE')
    C.need(NATIVE_FRAMES.setdefault(str(target),NativeReader.I.R.frame(before))==NativeReader.I.R.frame(before),'CACHED_ORIGINAL_LMDB_FRAME_UNCHANGED')
    fd=os.open(target,os.O_RDONLY|os.O_NOFOLLOW)
    try:
        C.need(NativeReader.I.R.frame(os.fstat(fd))==NativeReader.I.R.frame(before),'ACTUAL_NATIVE_FD_BEFORE_ORIGINAL_READER')
        raw=native.read(pointer)  # Actual original LMDB payload SHA and total_atoms guards.
        mol,z,xyz=native.graph(raw)
        C.need(len(z)==pointer['total_atoms'] and NativeReader.I.R.frame(os.fstat(fd))==NativeReader.I.R.frame(before)==NativeReader.I.R.frame(p.stat()) and p.resolve(strict=True)==target,'NATIVE_FRAME_AND_ATOM_COUNT_STABLE')
        return mol,z,xyz,raw
    finally:os.close(fd)


def checked_uff(sprime,numbers,mol,stereo_signature,science):
    import numpy as np
    from rdkit import Chem
    atom_sha=hashlib.sha256(numbers.astype('<i8').tobytes()).hexdigest();uff=[]
    for row in sprime:
        coordinates = np.asarray(row["coordinates"], dtype=np.float64)
        geometry_sha = IO.geometry_sha(numbers, coordinates)
        if row["status"] != "SUCCESS" or row["converged"] is not True or row["atom_order_sha256"] != atom_sha or row["stereo_signature"] != stereo_signature:
            raise ValueError("D7_ACCEPTED_SPRIME_STATUS_ATOMS_OR_STEREO_MISMATCH")
        conformer = Chem.Conformer(len(numbers))
        for index, xyz in enumerate(coordinates):
            conformer.SetAtomPosition(index, xyz.tolist())
        conformer.Set3D(True)
        cid = mol.AddConformer(conformer, assignId=True)
        valid_stereo = science.check_geometry_stereo(mol, cid)
        mol.RemoveConformer(cid)
        if not valid_stereo:
            raise ValueError("D7_SPRIME_GEOMETRIC_STEREO_CHECK_FAILED")
        energy = float(row["uff_energy_kcal_mol"])
        if not np.isfinite(energy):
            raise ValueError("D7_SPRIME_NONFINITE_ENERGY")
        uff.append({"conformer_id": int(row["sprime_conf_idx"]), "coordinates": coordinates.tolist(),
                    "energy": energy, "geometry_sha256": geometry_sha})
    return uff

def feature_chunk(tasks):
    import numpy as np
    native=WORKER.SCIENCE;features=[];bases=[];errors=[]
    for task in tasks:
        mid=task['molecule_id'];records=task['records'];by={r['record_id']:r for r in records};cache={}
        try:
            anchor=task['uff']['source_record_id'] if task['diagnostic'] else records[0]['record_id']
            C.need(anchor in by,'ORIGINAL_ACCEPTED_SPRIME_ANCHOR_IN_SAME_MID')
            def read(rid):
                if rid not in cache:cache[rid]=native_record_and_value(by[rid],native)
                return cache[rid]
            mol,z,xyz,raw=read(anchor);smiles=str(native.field(raw,'smiles'));graph=native.ordered_graph(mol)
            C.need(all(r['molecule_id']==mid for r in records),'EXACT_SAME_SOURCE_MID_NATIVE_POINTERS')
            scaffold=G.OriginalMath.scaffold_chunk([(mid,smiles)])
            C.need(len(scaffold)==1 and scaffold[0]['molecule_id']==mid,'DIRECT_ORIGINAL_GENERIC_SCAFFOLD_SAME_NATIVE_ANCHOR')
            feature={'molecule_id':mid,'elements_atomic_numbers':sorted(set(z.tolist())),
                'heavy_atoms':int(np.count_nonzero(z!=1)),**{k:scaffold[0][k] for k in ('generic_scaffold','scaffold_status')}}
            C.need(feature['elements_atomic_numbers']==sorted(set(task['elements_atomic_numbers']))
                and feature['heavy_atoms']==task['heavy_atoms'],'NATIVE_GRAPH_ATOMS_EQUALS_FROZEN_MOTHER_SCALAR_FEATURES')
            if not task['diagnostic']:
                features.append(feature);continue
            for rid in by:
                other,other_z,_,_=read(rid)
                C.need(np.array_equal(z,other_z) and graph==native.ordered_graph(other),'DIAGNOSTIC_ALL_ORIGINAL_PM7_GRAPHS_AND_ATOM_ORDER_EQUAL')
            _,stereo=native.fix_stereo(mol,smiles);original=task['uff'];uff=checked_uff([original],z,mol,stereo,native)[0]
            rid=task['held_pm7_record_id'];_,_,coords,_=read(rid);pointer=by[rid]
            C.need(np.isfinite(coords).all() and np.isfinite(np.asarray(uff['coordinates'])).all(),'ORIGINAL_PHYSICAL_COORDINATES_FINITE_NO_REPAIR')
            common={'molecule_id':mid,'parent_geometry_id':None,'view_id':None,'atomic_numbers':z.tolist(),
                'atom_order_sha256':hashlib.sha256(z.astype('<i8').tobytes()).hexdigest(),'order_energy':None,
                'energy_source':'NOT_CONSUMED_RANDOM_ONLY_D5_NO_HOF_VALUE_OR_ZERO_FILL'}
            bases.append(dict(common,geometry_source='pm7',geometry_id=G.gid('pm7',mid,rid),native_record_id=rid,sprime_conf_idx=None,
                positions_A=coords.tolist(),geometry_sha256=G.OriginalWorker.IO.geometry_sha(z,coords),source_path=pointer['source_path'],
                source_row_index=pointer['real_index'],source_format='native_lmdb',source_provenance_json=json.dumps(pointer,sort_keys=True),
                actual_input_origin='ORIGINAL_NATIVE_PAYLOAD_SHA_GRAPH_FIXED_INDEX_F64'))
            idx=original['sprime_conf_idx'];ref=original['__source']
            bases.append(dict(common,geometry_source='uff_sprime',geometry_id=G.gid('uff_sprime',mid,idx),native_record_id=None,sprime_conf_idx=idx,
                positions_A=uff['coordinates'],geometry_sha256=uff['geometry_sha256'],source_path=ref['path'],source_sha256=ref['sha256'],source_bytes=ref['bytes'],
                source_row_index=original['__physical_row'],source_format='parquet',source_conformer_id=idx,original_sprime_conf_idx=idx,
                canonical_sprime_conf_idx=idx,identity_namespace='accepted_original_sprime',seed=original['seed'],native_anchor_record_id=anchor,
                source_provenance_json=json.dumps({'source':ref,'physical_row':original['__physical_row']},sort_keys=True),actual_input_origin='ACTUAL_OLD_SPRIME_FULL_SHA_ROW_GRAPH_ATOM_STEREO_F64'))
            for row in bases[-2:]:G.Geometry.physical_key(row)
            features.append(feature)
        except Exception as exc:errors.append({'molecule_id':mid,'error':repr(exc),'no_source_or_threshold_changed':True})
    return features,bases,errors

def scalar_indices(ctx,db,pre):
    import pyarrow as pa,pyarrow.parquet as pq
    paths=pre['old_Sprime_coordinate_source_references'];C.need(len(paths)==5,'EXACT_FIVE_ORIGINAL_ACCEPTED_SPRIME_SOURCES')
    db.execute('CREATE TABLE native_selected AS SELECT f.* FROM formal f JOIN mother m USING(molecule_id)')
    db.execute('CREATE INDEX native_mid ON native_selected(molecule_id)')
    C.need(db.execute('SELECT count(*) FROM (SELECT m.molecule_id FROM mother m LEFT JOIN native_selected f USING(molecule_id) GROUP BY m.molecule_id,m.S_conformers HAVING count(f.record_id)<>m.S_conformers)').fetchone()[0]==0,'ALL_OLD_COMPLETE_MOTHER_ORIGINAL_PM7_N')
    db.execute('CREATE TABLE uff_ids(mid VARCHAR,idx BIGINT,anchor VARCHAR,source VARCHAR,physical_row BIGINT,PRIMARY KEY(mid,idx))')
    for ref in paths:
        I.allow(ref,origin=pathlib.Path(ref['path']).parent);path=I.require(ref);before=I.S.identity(path);src=pq.ParquetFile(path);offset=0
        try:
            for batch in src.iter_batches(batch_size=4096,columns=['molecule_id','sprime_conf_idx','source_record_id','status','converged'],use_threads=False):
                ctx.check();batch=batch.append_column('_row',pa.array(range(offset,offset+batch.num_rows),type=pa.int64()))
                batch=batch.append_column('_src',pa.array([ref['path']]*batch.num_rows));db.register('uff_batch',batch)
                db.execute("INSERT INTO uff_ids SELECT b.molecule_id,b.sprime_conf_idx,b.source_record_id,b._src,b._row FROM uff_batch b JOIN mother m ON m.molecule_id=b.molecule_id WHERE b.status='SUCCESS' AND b.converged")
                db.unregister('uff_batch');offset+=batch.num_rows
        finally:src.close()
        C.need(I.S.identity(path)==before,'WHOLE_SHA_ORIGINAL_SPRIME_SOURCE_FRAME_STILL_STABLE')
    C.need(db.execute('SELECT count(*) FROM (SELECT m.molecule_id FROM mother m LEFT JOIN uff_ids u ON u.mid=m.molecule_id GROUP BY m.molecule_id,m.Sprime_conformers HAVING count(u.idx)<>m.Sprime_conformers OR count(DISTINCT u.anchor)<>1)').fetchone()[0]==0,'ALL_MOTHER_ACCEPTED_OLD_SPRIME_N_AND_SINGLE_NATIVE_ANCHOR_NO_STATUS_INFERENCE')
    C.need(db.execute('SELECT count(*) FROM uff_ids WHERE idx<0 OR anchor IS NULL').fetchone()[0]==0,'REAL_NONNEGATIVE_INT64_OLD_SPRIME_IDS_AND_NATIVE_ANCHOR')
    db.create_function('original_stable_order',lambda mid,source,key:selection.stable_key(20261025,mid,source,key),['VARCHAR','VARCHAR','VARCHAR'],'VARCHAR')
    db.execute(BASE_INDEX_SQL)
    db.execute('CREATE UNIQUE INDEX base_gid ON base_index(geometry_id)');db.execute('CREATE INDEX base_mid ON base_index(molecule_id)')
    db.execute("CREATE TABLE held_ids AS SELECT b.* FROM base_index b JOIN diagnostic_mids d USING(molecule_id) WHERE b.rank=(SELECT max(x.rank) FROM base_index x WHERE x.molecule_id=b.molecule_id AND x.geometry_source=b.geometry_source)")
    C.need(db.execute('SELECT count(*),count(DISTINCT molecule_id),count(DISTINCT geometry_id) FROM held_ids').fetchone()==(40000,20000,40000),'EXACT40K_HELDOUT_BASE_IDENTITIES_NOT55K_INTERSECTION')
    db.execute('CREATE TABLE held_uff(mid VARCHAR PRIMARY KEY,row BLOB)')
    wanted={}
    for mid,path,row in db.execute("SELECT molecule_id,source_path,source_row_index FROM held_ids WHERE geometry_source='uff_sprime'").fetchall():wanted.setdefault(path,{})[row]=mid
    columns=['molecule_id','sprime_conf_idx','coordinates','atom_order_sha256','source_record_id','seed','status','converged','uff_energy_kcal_mol','stereo_signature']
    for ref in paths:
        if ref['path']not in wanted:continue
        path=I.require(ref);before=I.S.identity(path);src=pq.ParquetFile(path);offset=0
        positions=sorted(wanted[ref['path']]);from bisect import bisect_left
        try:
            for batch in src.iter_batches(batch_size=256,columns=columns,use_threads=False):
                ctx.check()
                for position in positions[bisect_left(positions,offset):bisect_left(positions,offset+batch.num_rows)]:
                    k=position-offset
                    row=batch.slice(k,1).to_pylist()[0];C.need(row['molecule_id']==wanted[ref['path']][offset+k],'EXACT_OLD_COORDINATE_PHYSICAL_ROW_MID')
                    row.update(__source=ref,__physical_row=offset+k);db.execute('INSERT INTO held_uff VALUES(?,?)',[row['molecule_id'],Wire.encode(row)])
                offset+=batch.num_rows
        finally:src.close()
        C.need(I.S.identity(path)==before,'ACCEPTED_OLD_COORDINATE_SOURCE_SAME_FRAME_AFTER_SELECTED_READ')
    C.need(db.execute('SELECT count(*) FROM held_uff').fetchone()[0]==20000,'ALL20K_ACTUAL_UFF_LAST_ROWS_PRESERVED')

def schema_features():
    import pyarrow as pa
    return pa.schema([('molecule_id',pa.string()),('elements_atomic_numbers',pa.list_(pa.int64())),('heavy_atoms',pa.int64()),('generic_scaffold',pa.string()),('scaffold_status',pa.string())])

def features_and_bases(ctx,db):
    from workflows.data_v1_final.labels.source_status_cpu_auto_memory_v1.support import sqlite_ro,lookup_batch
    import pyarrow as pa
    from . import resume as Recovery
    root=ctx.out/'native_features';root.mkdir();parts,geometries,seen=Recovery.load(ctx,db);errors=[]
    diagnostic={r[0] for r in db.execute('SELECT molecule_id FROM diagnostic_mids').fetchall()}
    cursor=db.cursor();cursor.execute('SELECT f.*,m.effective_role,m.source_role,m.S_conformers,m.Sprime_conformers,m.elements_atomic_numbers,m.heavy_atoms FROM native_selected f JOIN mother m USING(molecule_id) WHERE f.record_id=(SELECT min(x.record_id) FROM native_selected x WHERE x.molecule_id=f.molecule_id) AND (NOT EXISTS(SELECT 1 FROM reused_native_features rf WHERE rf.molecule_id=f.molecule_id) OR (EXISTS(SELECT 1 FROM diagnostic_mids dm WHERE dm.molecule_id=f.molecule_id) AND NOT EXISTS(SELECT 1 FROM reused_base_mids rb WHERE rb.mid=f.molecule_id))) ORDER BY f.molecule_id')
    names=[d[0] for d in cursor.description];sequence=0
    def chunks():
        while True:
            ctx.check();rows=cursor.fetchmany(128)
            if not rows:break
            tasks=[]
            for values in rows:
                a=dict(zip(names,values));mid=a['molecule_id'];diag=mid in diagnostic
                records=db.execute('SELECT * FROM native_selected WHERE molecule_id=? ORDER BY record_id',[mid]).fetch_arrow_table().to_pylist() if diag else [{k:a[k] for k in ('record_id','molecule_id','source_path','real_index','record_payload_sha256','total_atoms','smiles','file_group','conformer_id')}]
                tasks.append({'molecule_id':mid,'records':records,'diagnostic':diag,'elements_atomic_numbers':a['elements_atomic_numbers'],'heavy_atoms':a['heavy_atoms'],
                  'held_pm7_record_id':db.execute("SELECT native_record_id FROM held_ids WHERE molecule_id=? AND geometry_source='pm7'",[mid]).fetchone()[0] if diag else None,
                  'uff':Wire.decode(bytes(db.execute('SELECT row FROM held_uff WHERE mid=?',[mid]).fetchone()[0])) if diag else None})
            yield tasks
    iterator=iter(chunks());pending={}
    try:
        with cf.ProcessPoolExecutor(max_workers=16,mp_context=mp.get_context('spawn'),initializer=WORKER.initialize,initargs=({'proof':ctx.proof},)) as pool:
            while True:
                while len(pending)<16 and not I.stop_requested():
                    try:tasks=next(iterator)
                    except StopIteration:break
                    pending[pool.submit(feature_chunk,tasks)]=len(tasks)
                if not pending:break
                done,_=cf.wait(pending,return_when=cf.FIRST_COMPLETED)
                for future in done:
                    expected=pending.pop(future);f,b,e=future.result()
                    C.need(len(f)+len(e)==expected,'ALL_NEW_OR_MISSING_DIAGNOSTIC_TASKS_ACCOUNTED')
                    novel=[]
                    for row in f:
                        previous=db.execute('SELECT * FROM reused_native_features WHERE molecule_id=?',[row['molecule_id']]).fetchone()
                        if previous is None:novel.append(row)
                        else:C.need(Wire.encode(row)==Wire.encode(dict(zip(schema_features().names,previous))),'MISSING_BASE_REBUILD_REPEATS_IDENTICAL_CLOSED_FEATURE_NOT_REPLACEMENT')
                    f=novel;seen+=len(f);errors.extend(e)
                    if e:I.save(root/('unknown_chunk_%06d.DATA.json'%(sequence+1)),{'errors':e,'new_QM_UFF_calls':0,'no_retry':True})
                    C.need(len(f)+len(e)<=expected,'NO_NEW_OR_UNKNOWN_RESULT_OUTSIDE_TASKS')
                    sequence+=1;parts.append(I.write_parquet(root/('features_%06d.parquet'%sequence),iter(f),schema_features()))
                    if b:geometries.append(I.write_parquet(root/('held_%06d.parquet'%sequence),iter(b),Wire.schemas()['geometries']))
                    I.save(root/('checkpoint_%06d.json'%sequence),{'anchors_closed':seen,'errors':len(errors),'last_feature_part':parts[-1],'actual_parent_job_id':str(ctx.proof['job_id'])})
    finally:cursor.close()
    C.need(not errors,'NATIVE_ANCHOR_OR_GRAPH_STEREO_UNKNOWN_NOT_A_LOSS_DISABLED_FALLBACK:'+json.dumps(errors[:8]))
    C.need(seen==db.execute('SELECT count(*) FROM mother').fetchone()[0],'ALL_COMPLETE_OLD_MOTHER_FEATURES_NOT_A_PARTIAL_SUCCESS')
    # Existing bases and newly rebuilt missing bases remain one exact40k union.
    q=lambda x:"'"+str(x).replace("'","''")+"'"
    db.execute('CREATE VIEW native_features AS SELECT * FROM read_parquet(['+','.join(q(r['path']) for r in parts)+'])')
    C.need(db.execute('SELECT count(*),count(DISTINCT molecule_id) FROM native_features').fetchone()==(seen,seen),'EXACT_UNIQUE_FULL_MOTHER_NATIVE_FEATURE_ROWS')
    geom=I.write_parquet(ctx.out/'held_bases.parquet',(row for ref in geometries for row in _rows(ref)),Wire.schemas()['geometries'])
    C.need(db.execute('SELECT count(*),count(DISTINCT geometry_id),count(DISTINCT molecule_id) FROM read_parquet(?)',[geom['path']]).fetchone()==(40000,40000,20000),'ALL_REUSED_AND_NEW_BASES_EXACT40K_NO_DUPLICATES')
    C.need(db.execute('SELECT count(*) FROM held_ids h ANTI JOIN read_parquet(?) g USING(geometry_id)',[geom['path']]).fetchone()[0]==0,'NO_MISSING_ORIGINAL_HELDOUT_ID')
    selected=sqlite3_catalog(ctx,db);orders=parquet_query(ctx,db,'SELECT molecule_id,geometry_source,geometry_id,\'fixed_random\' AS order_type,\'fixed_random\' AS method,rank FROM held_ids ORDER BY molecule_id,geometry_source',ctx.out/'held_random_orders.parquet')
    roster=parquet_query(ctx,db,'SELECT row_number() OVER(ORDER BY m.molecule_id)-1 AS logical_ordinal,m.molecule_id,m.S_conformers AS PM7_N,m.Sprime_conformers AS UFF_N,0::BIGINT AS child_count FROM mother m JOIN diagnostic_mids d USING(molecule_id) ORDER BY m.molecule_id',ctx.out/'held_roster.parquet')
    return {'table_references':{'geometries':geom,'orders':orders,'roster':roster},'bias_feature_part_references':parts,'closed_feature_readback_reference':I.allow(I.pin(ctx.out/'closed_feature_readback.json'))},selected

def _rows(ref):
    import pyarrow.parquet as pq
    src=pq.ParquetFile(I.require(ref))
    try:
        for batch in src.iter_batches(batch_size=256,use_threads=False):yield from batch.to_pylist()
    finally:src.close()

def parquet_query(ctx,db,query,path,args=()):
    ctx.check();cur=db.cursor();cur.execute(query,args);reader=cur.fetch_record_batch(4096);schema=reader.schema
    def rows():
        for batch in reader:
            ctx.check();yield from batch.to_pylist()
    try:return I.write_parquet(path,rows(),schema,row_group_size=4096)
    finally:cur.close()

def sqlite3_catalog(ctx,db):
    import sqlite3
    from workflows.data_v1_final.labels.source_status_cpu_auto_memory_v1.support import sqlite_ro,lookup_batch
    source=sqlite_ro(I.require(ctx.plan['canonical_index']));path=ctx.out/'selected_owner_jobs.sqlite';out=sqlite3.connect(path);out.execute('CREATE TABLE selected(job TEXT PRIMARY KEY)')
    try:
        ids=[r[0] for r in db.execute("SELECT native_record_id FROM held_ids WHERE geometry_source='pm7'").fetchall()]
        owners=lookup_batch(source,ids);C.need(set(owners)==set(ids),'ALL_HELD_PM7_SOURCE_OWNER_IDENTITIES')
        out.executemany('INSERT OR IGNORE INTO selected VALUES(?)',[(str(v['job_id']),) for v in owners.values()]);out.commit()
    finally:source.close();out.close()
    return I.allow(I.pin(path))
