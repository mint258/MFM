"""Metadata-only join of final membership, physical IDs, orders and D5 IDs."""
import json,sqlite3
from pathlib import Path
from ...labels.window2_normalization_v1 import io as I
from .local_metadata import MetadataBuild,database_path,public,runtime_result


def rows(ref,columns=None):
    import pyarrow.parquet as pq
    pf=pq.ParquetFile(ref['path'],pre_buffer=False)
    try:
        for batch in pf.iter_batches(batch_size=8192,columns=columns,use_threads=False):yield from batch.to_pylist()
    finally:pf.close()


def selected(role,common):return (str(role).upper()=='TRAIN' and common) or str(role).upper()=='FULL' or (str(role).upper() in ('VAL','ROUTINE') and common)


def prepare(plan,geometry_only=False):
    root=Path(plan['source_working_root']);root.mkdir(parents=True,exist_ok=True);final=root/('geometry_identities.json' if geometry_only else 'identities.json')
    inputs={key:plan[key] for key in (('common',) if geometry_only else ('common','orders','d5'))}
    inputs['extra_geometry_tables']=plan.get('extra_geometry_tables',[])
    if final.is_file():
        m=I.load(final)
        if m['inputs']!=inputs:raise ValueError('SOURCE_IDENTITIES_FROZEN_INPUTS_CHANGED')
        return runtime_result(m,plan)
    if not geometry_only:
        base=prepare(plan,geometry_only=True);build=MetadataBuild(plan,'orders_and_d5',inputs)
        if build.closed_result is not None:
            result=build.finish(build.closed_result,'orders_database');I.save(final,result);return runtime_result(result,plan)
        db=build.open('CREATE TABLE orders(mid TEXT PRIMARY KEY,row TEXT); CREATE TABLE held(src TEXT,mid TEXT,physical TEXT,PRIMARY KEY(src,mid,physical));')
        orders=I.load(plan['orders']);d5=I.load(plan['d5'])
        try:
            for ordinal,ref in enumerate(orders['order_tables']):
                if build.done('orders',ordinal,ref):continue
                db.executemany('INSERT INTO orders VALUES(?,?)',[(r['molecule_id'],json.dumps(r,separators=(',',':'))) for r in rows(ref)])
                build.commit('orders',ordinal,ref)
            if not build.done('d5_held',0,d5['diagnostic_base_reference']):
                geometry=sqlite3.connect('file:'+database_path(base)+'?mode=ro',uri=True)
                try:
                    for r in rows(d5['diagnostic_base_reference']):
                        src=r['geometry_source'];gid=r.get('geometry_id',r.get('base_geometry_id'))
                        hit=geometry.execute('SELECT physical FROM geometries WHERE gid=? AND mid=? AND src=?',(gid,r['molecule_id'],src)).fetchone()
                        if hit is None and src=='pm7':hit=geometry.execute('SELECT physical FROM geometries WHERE mid=? AND src=? AND physical=?',(r['molecule_id'],src,r['native_record_id'])).fetchone()
                        if hit is None:raise ValueError('FROZEN_D5_GEOMETRY_NOT_ADDRESSABLE:'+str(gid))
                        db.execute('INSERT INTO held VALUES(?,?,?)',(src,r['molecule_id'],hit[0]))
                finally:geometry.close()
                build.commit('d5_held',0,d5['diagnostic_base_reference'])
        finally:build.close()
        result=build.finish(dict(public(base),inputs=inputs),'orders_database');I.save(final,result);return runtime_result(result,plan)
    build=MetadataBuild(plan,'geometry_identities',inputs)
    if build.closed_result is not None:
        result=build.finish(build.closed_result,'database');I.save(final,result);return runtime_result(result,plan)
    db=build.open('CREATE TABLE members(mid TEXT PRIMARY KEY,role TEXT,common INTEGER); CREATE TABLE geometries(mid TEXT,src TEXT,physical TEXT,gid TEXT UNIQUE,ordinary INTEGER,pointer TEXT,PRIMARY KEY(mid,src,physical)); CREATE INDEX g_mid ON geometries(mid); CREATE TABLE orders(mid TEXT PRIMARY KEY,row TEXT); CREATE TABLE held(src TEXT,mid TEXT,physical TEXT,PRIMARY KEY(src,mid,physical));')
    common=I.load(plan['common'])
    try:
        for ordinal,ref in enumerate(common['membership_tables']):
            if build.done('members',ordinal,ref):continue
            db.executemany('INSERT INTO members VALUES(?,?,?)',[(r['molecule_id'],str(r['effective_role']).upper(),bool(r['common_population'])) for r in rows(ref,columns=['molecule_id','effective_role','common_population'])])
            build.commit('members',ordinal,ref)
        for ordinary,refs in ((True,common.get('full_source_physical_geometry_tables',common['physical_geometry_tables'])),(False,plan.get('extra_geometry_tables',[]))):
            stage='geometry_ordinary' if ordinary else 'geometry_extra'
            for ordinal,ref in enumerate(refs):
                if build.done(stage,ordinal,ref):continue
                for r in rows(ref):
                    src=r['geometry_source'];physical=r['native_record_id'] if src=='pm7' else r.get('storage_physical_alias') or str(int(r['sprime_conf_idx']))
                    same_gid=db.execute('SELECT mid,src FROM geometries WHERE gid=?',(r['geometry_id'],)).fetchone()
                    if same_gid:
                        if same_gid!=(r['molecule_id'],src):raise ValueError('GEOMETRY_ID_OWNER_CONFLICT')
                        continue
                    old=db.execute('SELECT gid,ordinary FROM geometries WHERE mid=? AND src=? AND physical=?',(r['molecule_id'],src,str(physical))).fetchone()
                    if old:
                        if old[0]!=r['geometry_id']:raise ValueError('PHYSICAL_ID_GEOMETRY_ALIAS_DIFFERS')
                        continue
                    db.execute('INSERT INTO geometries VALUES(?,?,?,?,?,?)',(r['molecule_id'],src,str(physical),r['geometry_id'],ordinary,json.dumps(r,separators=(',',':'))))
                build.commit(stage,ordinal,ref)
        result={'inputs':inputs,'selected_molecules':{},'expected_conformers':{}}
        for mid,role,common_flag in db.execute('SELECT mid,role,common FROM members ORDER BY mid'):
            if not selected(role,common_flag):continue
            split='TRAIN' if role=='TRAIN' else 'FULL';result['selected_molecules'][split]=result['selected_molecules'].get(split,0)+1
        for role,common_flag,src,count in db.execute('SELECT m.role,m.common,g.src,count(*) FROM geometries g JOIN members m ON m.mid=g.mid GROUP BY m.role,m.common,g.src'):
            if selected(role,common_flag):
                key=('TRAIN' if role=='TRAIN' else 'FULL')+('_P' if src=='pm7' else '_U')
                result['expected_conformers'][key]=result['expected_conformers'].get(key,0)+count
    finally:build.close()
    result=build.finish(result,'database');I.save(final,result);return runtime_result(result,plan)