"""Actual full sources -> original projection -> the shared MFM4 assembler.

No synthetic physical identities, labels, ranks or missing conformers. The
metadata join is separate from numerical traversal; PM7 original typed masks
plus D4 sparse overrides and Pprime final typed masks are reused directly.
"""
import collections,concurrent.futures as cf,importlib.util,json,multiprocessing as mp,os,pickle,random,sqlite3,sys
from pathlib import Path
import numpy as np
from . import identities as A,physical as G
from .disk_guard import from_plan
from .projected_source import assemble_entries,apply_pprime_eligibility
from .run import channel_codes
from ..full_physical_index_v3.read_index import locators_for_mids,iter_source_rows
from ...labels.window2_normalization_v1 import io as I
from ...labels.normalization_compact_runtime_v3 import codec as K
from ...labels.common_train_normalization_day_v1 import bindings as B
from ...labels.window2_validity_v1.policy import apply_sparse_entry
STATE={}

def physical_key(source,mid,physical):return json.dumps([source,mid,str(physical)],separators=(',',':'))


def sql_ro(path):return sqlite3.connect('file:'+str(path)+'?mode=ro',uri=True)


def identity_db(index):
    db=sql_ro(A.database_path(index))
    if index.get('orders_database'):
        db.execute('ATTACH DATABASE ? AS final_aux',('file:'+A.database_path(index,'orders_database')+'?mode=ro',))
        db.executescript('CREATE TEMP VIEW orders AS SELECT * FROM final_aux.orders; CREATE TEMP VIEW held AS SELECT * FROM final_aux.held;')
    return db


def cache_index(plan):
    import pyarrow.parquet as pq
    root=Path(plan['source_working_root']);marker=root/'cache_index.json'
    inputs={key:plan[key] for key in ('pprime_cache','uff_d3_cache','pm7_normalization')}
    if marker.is_file():
        result=I.load(marker)
        if result['inputs']!=inputs:raise ValueError('FROZEN_CACHE_INDEX_INPUTS_CHANGED')
        return result
    physical=Path(plan.get('cache_index_working_root') or root)
    guard=from_plan(plan,admit=False)
    if guard:guard.wait(physical,inodes_needed=4);guard.wait(marker,inodes_needed=2)
    physical.mkdir(parents=True,exist_ok=True)
    path=physical/'cache_index.sqlite';attempt=0
    while path.exists():attempt+=1;path=physical/('cache_index_attempt_%03d.sqlite'%attempt)
    db=sqlite3.connect(path)
    db.executescript('CREATE TABLE pp(mid TEXT,conf INTEGER,task TEXT,path TEXT,row INTEGER,gid TEXT,PRIMARY KEY(mid,conf,task)); CREATE INDEX pp_mid ON pp(mid); CREATE TABLE d3(gid TEXT PRIMARY KEY,path TEXT); CREATE TABLE overrides(rid TEXT,fid INTEGER,row BLOB,PRIMARY KEY(rid,fid));')
    source_aliases={}
    for ref in plan.get('extra_geometry_tables',[]):
        for row in A.rows(ref):
            if row.get('source_pprime_record_id'):source_aliases[row['source_pprime_record_id']]=row['geometry_id']
    try:
        manifest=I.load(plan['pprime_cache'])
        for ref in manifest['part_manifests']:
            for part in I.load_data(ref)['parts']:
                offset=0;pf=pq.ParquetFile(part['path'])
                try:
                    for batch in pf.iter_batches(columns=['record_id','molecule_id','sprime_conf_idx','calc_type','geometry_id'],batch_size=8192):
                        values=[]
                        for i,r in enumerate(batch.to_pylist()):
                            gid=r['geometry_id'] or source_aliases.get(r['record_id'])
                            if gid is None:raise ValueError('ACTUAL_PPRIME_SOURCE_GEOMETRY_NOT_ADDRESSABLE:'+r['record_id'])
                            values.append((r['molecule_id'],r['sprime_conf_idx'],r['calc_type'],part['path'],offset+i,gid))
                        db.executemany('INSERT INTO pp VALUES(?,?,?,?,?,?)',values);offset+=batch.num_rows
                finally:pf.close()
                db.commit()
        for ref in I.load(plan['uff_d3_cache'])['files']:
            src=sql_ro(ref['path'])
            try:db.executemany('INSERT INTO d3 VALUES(?,?)',[(gid,ref['path']) for gid, in src.execute('SELECT gid FROM labels')])
            finally:src.close()
            db.commit()
        norm=I.load(plan['pm7_normalization'])
        for ref in I.load_data(norm['statistics']['mask_overrides_reference'])['files']:
            db.executemany('INSERT INTO overrides VALUES(?,?,?)',[(r['record_id'],r['field_id'],pickle.dumps(r,protocol=5)) for r in A.rows(ref)]);db.commit()
    finally:db.close()
    if guard:guard.wait(marker,inodes_needed=2)
    result={'inputs':inputs,'database':I.ref(path)};I.save(marker,result);return result


def init(plan,index,cache,schema):
    for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[name]='1'
    import pyarrow as pa
    pa.set_cpu_count(1);pa.set_io_thread_count(1)
    from functools import partial
    from ..pilot_family_D3_census_resume_v3.source import extract
    extract=partial(extract,capture_native_payload=False)
    from ..native_body_frame32_v1.observe import input_coordinates
    enginepath=Path(plan.get('input_renderer','/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/scripts/wp5_engine_v3.py'))
    sys.path.insert(0,str(enginepath.parent))
    try:engine=G.module('_window2_original_input_renderer',enginepath)
    finally:sys.path.pop(0)
    protocol_entries=list(plan.get('protocols',[]))
    if plan.get('protocol_map'):
        for item in I.load(plan['protocol_map'])['entries']:
            protocol_entries.append({'package_sha256':item['reproduction_package_reference']['sha256'],'protocol_reference':item['protocol_reference']})
    protocols={}
    for item in protocol_entries:
        reference=item['protocol_reference'];protocol=I.load_data(reference) if 'bytes' in reference else I.load(reference['path'])
        key=item['package_sha256']
        if key in protocols and protocols[key]!=protocol:raise ValueError('CONFLICTING_ORIGINAL_PACKAGE_PROTOCOL')
        protocols[key]=protocol
    coverage=I.load(plan['coverage']);fields=I.load_data(coverage['field_map_reference'])
    from ...labels.window2_r73_views_v1.kernel import derived_fields
    fields=fields+derived_fields(fields);recipe=I.load(plan['projection_recipe'])
    inventory=I.load_data(coverage['source_inventory_reference']);byraw={r['path']:r for r in inventory['files']}
    STATE['disk_guard']=from_plan(plan,admit=False)
    STATE.update(plan=plan,index=index,cache=cache,schema=schema,extract=extract,input_coordinates=input_coordinates,engine=engine,
                 protocols=protocols,source_sample_keys=set(plan.get('source_sample_keys',[])),coverage=coverage,source_groups={str(g['source_job_id']):g for g in I.load_data(coverage['logical_group_plan_reference'])['groups']},normalization=I.load(plan['pm7_normalization']),fields={f['field_id']:f for f in fields},recipe=recipe,byraw=byraw)


def read_selected(path,positions,columns=None):
    """One forward selected source stream; never materialize an entire RG."""
    import pyarrow.parquet as pq
    pf=pq.ParquetFile(path,pre_buffer=False);positions=sorted(set(positions));cursor=0;lo=0
    try:
        for batch in pf.iter_batches(batch_size=16,columns=columns,use_threads=False):
            hi=lo+batch.num_rows
            while cursor<len(positions) and positions[cursor]<lo:cursor+=1
            while cursor<len(positions) and positions[cursor]<hi:
                pos=positions[cursor];cursor+=1
                yield pos,batch.slice(pos-lo,1).to_pylist()[0]
            lo=hi
            if positions and lo>positions[-1]:break
    finally:pf.close()


def metadata(base,role,ranks,task=None,view=None):
    result={key:base.get(key) for key in ('molecule_id','geometry_source','native_record_id','sprime_conf_idx','ordinary_sprime','storage_physical_alias','diagnostic_only','excluded_from_all_training')}
    result.update(effective_role=role,available_base_order_ranks=ranks)
    if task is not None:result.update(calc_type=task,parent_geometry_id=base['geometry_id'],view_id=view)
    return result


def geometry_arrays(z,xyz,bonds,codes):
    return {'atomic_numbers':np.asarray(z,dtype='<i8'),'positions_A':np.asarray(xyz,dtype='<f8'),
            'native_bond_index':np.asarray(bonds,dtype='<i8').reshape((-1,2)).T,'native_bond_order':np.asarray(codes,dtype='<i8')}


def project_row(spool,base,entries,typed,raw,source,z,xyz,bonds,codes,ranks,role,held):
    task=raw.get('calc_type',source['family']);tr=STATE['recipe']['tasks'][task]
    from .derived_pair import bind_cached_pairs
    derived=[e for e in entries if e['field_id']in(146,147)];entries=[e for e in entries if e['field_id']<146]
    # D6 never independently re-evaluates the EA anomaly predicate.
    typed=dict(typed);typed['compact_mask_json']=K.binary_json_dumps(B.compact.encode(typed.get('record_ordinal',0),B.TASKS[task],entries))
    gid=base['geometry_id'];meta=metadata(base,role,ranks)
    if tr['input_kind']=='ORIGINAL_REGISTRY_CELL_PARQUET':
        package=raw.get('reproduction_package_sha256')
        if package not in STATE['protocols']:raise ValueError('ORIGINAL_CALL_PROTOCOL_NOT_REGISTERED:'+str(package))
        protocol=STATE['protocols'][package];definition=next(t for t in protocol['tasks'] if t['name']==task)
        from rdkit import Chem
        symbols=[Chem.GetPeriodicTable().GetElementSymbol(int(n)) for n in z]
        rendered=STATE['engine'].render_inputs(definition,{'symbols':symbols,'coords':xyz},{'record_id':raw['record_id']},protocol)
        name='input.mop' if definition['family']=='mopac' else 'input.xyz'
        xyz=STATE['input_coordinates'](rendered[name],name,symbols,float)
        view='actual_wp5_perturbed_input_v1' if definition.get('perturbed') else 'actual_wp5_unperturbed_program_input_view_v1'
        gid=base['geometry_id']+'/actual-input/'+task+'/'+str(raw.get('input_bundle_sha256'))
        meta=metadata(base,role,ranks,task,view);meta['actual_input_bundle_sha256']=raw.get('input_bundle_sha256');meta['actual_input_file_sha256']=raw.get('input_file_sha256')
        add_piece(spool,base['molecule_id'],gid,'geometry',meta,geometry_arrays(z,xyz,bonds,codes),held)
    arrays={};locators={}
    for tid in tr['targets']:
        target=STATE['schema']['target_layout'][tid]['mapping_target']
        values,_=STATE['extract'](entries,typed,raw,len(z),tr,target)
        if set(arrays)&set(values):raise ValueError('PROJECTED_TARGET_ARRAY_COLLISION')
        arrays.update(values);locators[tid]={'source_reference':source,'physical_row':typed.get('physical_row'),'row_group':typed.get('row_group'),
            'row_within_group':typed.get('row_within_group'),'record_id':raw.get('record_id'),'molecule_id':base['molecule_id'],'task':task}
    if derived:bind_cached_pairs(arrays,derived,STATE['schema']['derived_r73_pair_targets'])
    meta['permanent_source_locators']=locators
    add_piece(spool,base['molecule_id'],gid,'labels',meta,arrays,held)


def add_piece(db,mid,gid,kind,meta,arrays,held):
    # Only the training F32 representation is spooled; original F64 sources
    # and the independently generated UFF D3 cache remain the authority.
    cast={name:np.asarray(value,dtype='<f4') if np.asarray(value).dtype.kind=='f' else np.asarray(value) for name,value in arrays.items()}
    physical=meta['native_record_id'] if meta['geometry_source']=='pm7' else meta.get('storage_physical_alias') or meta['sprime_conf_idx']
    key=physical_key(meta['geometry_source'],mid,physical)
    if key in STATE.get('source_sample_keys',set()):
        note=STATE['sample_notes'].setdefault(key,{'valid_float_leaves':0,'max_absolute_error':0.,'max_relative_error':0.,'within_tolerance':True,'source_F64_before_single_F32_cast':True})
        for name,original in arrays.items():
            original=np.asarray(original)
            if original.dtype.kind!='f':continue
            maskname='valid/'+name[7:] if name.startswith('values/') else 'valid/'+name[:-6] if name.startswith('transport/') and name.endswith('values') else None
            valid=np.asarray(arrays[maskname],dtype=bool) if maskname in arrays else np.isfinite(original)
            expected=original[valid].astype('<f8');observed=cast[name][valid].astype('<f8')
            delta=np.abs(observed-expected);note['valid_float_leaves']+=len(expected)
            if len(expected):
                note['max_absolute_error']=max(note['max_absolute_error'],float(np.max(delta)))
                relative=np.divide(delta,np.abs(expected),out=np.zeros_like(delta),where=expected!=0)
                note['max_relative_error']=max(note['max_relative_error'],float(np.max(relative)))
                note['within_tolerance']&=bool(np.all(np.isfinite(observed)) and np.all(delta<=1e-6+1e-6*np.abs(expected)))
    entry={'gid':gid,'metadata':meta,'arrays':cast,'descriptor':{'kind':kind,'geometry_source':meta['geometry_source'],'path':'original-source-projection','is_holdout':held}}
    packed=pickle.dumps(entry,protocol=5)
    if STATE.get('disk_guard'):STATE['disk_guard'].wait(STATE['spool_path'],len(packed),2)
    db.execute('INSERT INTO pieces VALUES(?,?)',(mid,packed))


def spool_paths(plan,number,split):
    """Only new physical SQLite moves; shared canonical metadata stays put."""
    logical=Path(plan['source_working_root'])/split
    physical=Path(plan.get('source_spool_root') or plan['source_working_root'])/split
    return physical/('block_%07d.sqlite'%number),logical/('block_%07d.json'%number)


def order_ranks(source_orders,identity):
    ranks={}
    for name in ('fixed_random','energy','diversity'):
        values=source_orders.get(name)
        if values is not None and identity in values:ranks[name]=values.index(identity)
    return ranks


def uff_candidate_index(bases):
    lookup=collections.defaultdict(list)
    for key,base in bases.items():
        if key[1]=='uff_sprime':lookup[(key[0],base['geometry_id'])].append(key)
    return lookup


def pprime_candidate_key(lookup,mid,conf,bound_gid):
    candidates=lookup.get((mid,bound_gid),())
    if len(candidates)!=1:raise ValueError('ACTUAL_PPRIME_PHYSICAL_GEOMETRY_MUST_BE_UNAMBIGUOUS:'+repr((mid,conf,bound_gid)))
    return candidates[0]


def work(task):
    number,mids,split=task;STATE['sample_notes']={}
    path,marker=spool_paths(STATE['plan'],number,split)
    if marker.is_file():
        closed=I.load(marker)
        if Path(closed['path']).is_file():return closed
    # A changed storage hint never bypasses an already closed canonical ref.
    # Both physical scratch and canonical metadata must be admitted before mkdir.
    if STATE.get('disk_guard'):
        STATE['disk_guard'].wait(path,inodes_needed=4);STATE['disk_guard'].wait(marker,inodes_needed=2)
    path.parent.mkdir(parents=True,exist_ok=True);marker.parent.mkdir(parents=True,exist_ok=True)
    attempt=0;original=path
    while path.exists():attempt+=1;path=original.with_name(original.stem+'_attempt_%03d.sqlite'%attempt)
    STATE['spool_path']=str(path)
    if STATE.get('disk_guard'):STATE['disk_guard'].wait(path,inodes_needed=4)
    spool=sqlite3.connect(path);spool.executescript('CREATE TABLE pieces(mid TEXT,row BLOB); CREATE INDEX pieces_mid ON pieces(mid); CREATE TABLE molecules(mid TEXT PRIMARY KEY,row BLOB);')
    identities=identity_db(STATE['index']);cache=sql_ro(STATE['cache']['database']['path'])
    bases={};contexts={};zmap={};base_xyz={};topology={};ranks={};held=set();pprime_fit={};routine_by_mid={}
    try:
        for mid in mids:
            role,common=identities.execute('SELECT role,common FROM members WHERE mid=?',(mid,)).fetchone()
            order=json.loads(identities.execute('SELECT row FROM orders WHERE mid=?',(mid,)).fetchone()[0]);contexts[mid]=(role,bool(common));routine_by_mid[mid]=role in ('VAL','ROUTINE')
            for src,physical in identities.execute('SELECT src,physical FROM held WHERE mid=?',(mid,)):held.add((mid,src,physical))
            for src,physical,gid,ordinary,pointer in identities.execute('SELECT src,physical,gid,ordinary,pointer FROM geometries WHERE mid=?',(mid,)):
                p=json.loads(pointer);p.update(molecule_id=mid,geometry_source=src,native_record_id=physical if src=='pm7' else None,sprime_conf_idx=int(p['sprime_conf_idx']) if src=='uff_sprime' else None,geometry_id=gid,ordinary_sprime=bool(ordinary))
                if 'legacy_routine_molecule' in p:routine_by_mid[mid]=bool(p['legacy_routine_molecule'])
                if src=='uff_sprime' and physical!=str(p['sprime_conf_idx']):p['storage_physical_alias']=physical
                bases[(mid,src,physical)]=p
                source_orders=json.loads(order['pm7_orders_json'] if src=='pm7' else order['sprime_orders_json']);identity=physical if src=='pm7' else p['sprime_conf_idx']
                ranks[(mid,src,physical)]=order_ranks(source_orders,identity) if ordinary else {}
        uff_by_mid_gid=uff_candidate_index(bases)
        locations=list(locators_for_mids(STATE['plan']['source_index'],mids,domains=(0,),families=('base_geometry',)))
        base_locs=[loc for loc in locations if loc['family']=='base_geometry']
        for loc,raw in iter_source_rows(base_locs,['atomic_numbers','positions_A','bond_pairs','bond_order_codes']):
            key=(loc['molecule_id'],'pm7',loc['record_id']);p=bases[key];role,_=contexts[key[0]]
            z=raw['atomic_numbers'];xyz=raw['positions_A'];bonds=raw['bond_pairs'];codes=raw['bond_order_codes']
            zmap[key]=z;topology[key]=(bonds,codes);base_xyz[key]=xyz
            add_piece(spool,key[0],p['geometry_id'],'geometry',metadata(p,role,ranks[key]),geometry_arrays(z,xyz,bonds,codes),key in held)
        for key,p in bases.items():
            if key[1]!='uff_sprime':continue
            _,xyz=G.physical(p);base_xyz[key]=xyz;mid=key[0];role,_=contexts[mid]
            hit=cache.execute('SELECT path FROM d3 WHERE gid=?',(p['geometry_id'],)).fetchone()
            if hit is None:raise ValueError('FULL_UFF_D3_CACHE_MISSING:'+repr(key))
            ddb=sql_ro(hit[0])
            try:
                packed,anchor=ddb.execute('SELECT entries,anchor FROM labels WHERE gid=?',(p['geometry_id'],)).fetchone()
                witness=ddb.execute('SELECT z,bonds,codes FROM graphs WHERE anchor=?',(anchor,)).fetchone()
                if witness is None:raise ValueError('UFF_D3_ORIGINAL_NATIVE_GRAPH_WITNESS_MISSING')
                z,bonds,codes=[pickle.loads(v) for v in witness]
                zmap[key]=z;topology[key]=(bonds,codes)
                add_piece(spool,mid,p['geometry_id'],'geometry',metadata(p,role,ranks[key]),geometry_arrays(z,xyz,bonds,codes),key in held)
            finally:ddb.close()
            entries=K.unpack_entries(pickle.loads(packed),STATE['fields'])
            project_row(spool,p,entries,{}, {'calc_type':'D3','record_id':p['geometry_id']},{'path':hit[0],'family':'D3'},zmap[key],xyz,bonds,codes,ranks[key],role,key in held)
        from ...labels.window2_normalization_v1.reader import observations
        from ...labels.window2_normalization_v1.selected import RowGroupForwardRaw as ForwardRaw
        cfg=dict(STATE['normalization']['inputs'],statistics_purpose='D6_export',emit_source=True,filter_mids=set(mids),d6_selected_row_groups=True,
                 field_map_reference=STATE['normalization']['inputs']['field_map_reference'],
                 r73_derived_reference=STATE['normalization']['statistics']['r73_derived_reference'],
                 mask_overrides_reference=STATE['normalization']['statistics']['mask_overrides_reference'])
        fields=list(STATE['fields'].values())
        source_jobs={str(loc['canonical_or_QC_identity']['job_id']) for loc in base_locs};raws={};tasksets=collections.defaultdict(set);projected=0
        try:
            for job in sorted(source_jobs):
                for owner,z,entries,row,source in observations(cfg,STATE['source_groups'][job],fields):
                    mid=owner['molecule_id'];key=(mid,'pm7',owner['record_id']);p=bases[key]
                    if list(z)!=list(zmap[key]):raise ValueError('PM7_TYPED_ORIGINAL_BASE_ATOM_ORDER_ALIGNMENT')
                    task=next(t for t,c in B.TASKS.items() if c==row['task_code']);tasksets[key].add(task)
                    if STATE['recipe']['tasks'][task]['input_kind']=='ORIGINAL_REGISTRY_CELL_PARQUET':
                        pm7_raw_path=source['path']
                        if pm7_raw_path not in raws:raws[pm7_raw_path]=ForwardRaw(pm7_raw_path,['record_id','molecule_id','calc_type','total_atoms','values','numeric_issues','reproduction_package_sha256','input_bundle_sha256','input_file_sha256'])
                        raw=raws[pm7_raw_path].get(row['physical_row'])
                        if raw['record_id']!=owner['record_id'] or raw['molecule_id']!=mid or raw['calc_type']!=task:raise ValueError('ORIGINAL_RAW_TYPED_PHYSICAL_ROW_ALIGNMENT')
                    else:raw={'record_id':owner['record_id'],'molecule_id':mid,'calc_type':task}
                    role,_=contexts[mid];bonds,codes=topology[key]
                    project_row(spool,p,entries,row,raw,dict(source,family=source['family']),zmap[key],base_xyz[key],bonds,codes,ranks[key],role,key in held)
                    projected+=1
                    if projected%10000==0:print(json.dumps({'phase':'PM7_SOURCE_PROJECTION','source_job':job,'block':number,'task_records':projected}),flush=True)
            for key in bases:
                if key[1]=='pm7' and tasksets[key]!=set(B.TASKS):raise ValueError('ALL_ORIGINAL_PM7_TASKS_MUST_BE_PROJECTED:'+repr(key))
        finally:
            for raw in raws.values():raw.close()
        wanted=collections.defaultdict(dict)
        for mid in mids:
            for conf,task,typed_path,row,gid in cache.execute('SELECT conf,task,path,row,gid FROM pp WHERE mid=? ORDER BY path,row',(mid,)):wanted[typed_path][row]=(mid,conf,task,gid)
        for typed_path,positions in wanted.items():
            # Read each selected typed Pprime row, then its exact original raw
            # CELL once. The cache already owns all final validity decisions.
            rows=list(read_selected(typed_path,positions));raws=collections.defaultdict(dict)
            for position,row in rows:
                row['geometry_id']=positions[position][3]
                raws[row['source_path']][row['physical_row']]=(position,row)
            for rawpath,physical_rows in raws.items():
                for physical,raw in read_selected(rawpath,physical_rows,['record_id','molecule_id','calc_type','total_atoms','values','numeric_issues','reproduction_package_sha256','input_bundle_sha256','input_file_sha256']):
                    _,row=physical_rows[physical];mid=row['molecule_id']
                    if raw.get('record_id')!=row['record_id'] or raw.get('molecule_id')!=mid or raw.get('calc_type')!=row['calc_type']:raise ValueError('PPRIME_ORIGINAL_RAW_TYPED_PHYSICAL_ROW_ALIGNMENT')
                    bound_gid=row['geometry_id'];key=pprime_candidate_key(uff_by_mid_gid,mid,row['sprime_conf_idx'],bound_gid)
                    if bound_gid in pprime_fit and pprime_fit[bound_gid]!=bool(row['fit_eligible']):raise ValueError('INCONSISTENT_PRODUCED_PPRIME_FIT_FLAGS')
                    pprime_fit[bound_gid]=bool(row['fit_eligible'])
                    entries=K.unpack_entries(row,STATE['fields']);role,_=contexts[mid];bonds,codes=topology[key]
                    if row.get('r73_pair_indices') is not None:
                        for entry in entries:
                            if entry['field_id']in(146,147):entry['pair_indices']=row['r73_pair_indices']
                    if list(row['atomic_numbers'])!=list(zmap[key]):raise ValueError('PPRIME_AND_REGISTERED_PHYSICAL_ATOM_ORDER_ALIGNMENT')
                    project_row(spool,bases[key],entries,row,raw,{'path':rawpath,'bytes':row['source_bytes'],'family':row['family']},row['atomic_numbers'],base_xyz[key],bonds,codes,ranks[key],role,key in held)
        spool.commit();book=['__ABSENT__'];codes={}
        for mid in mids:
            entries=[pickle.loads(row[0]) for row in spool.execute('SELECT row FROM pieces WHERE mid=?',(mid,))]
            item=assemble_entries(mid,entries,STATE['schema']);apply_pprime_eligibility(item,pprime_fit);item['common_population']=contexts[mid][1];item['routine']=routine_by_mid[mid]
            for record in item['p_records']+item['u_records']:
                channel_codes(record,book,codes);record['r73_codebook']=book.copy();record.pop('r73_channels',None)
                identity=record['identity'];key=physical_key(identity['geometry_source'],mid,identity['native_record_id'] if identity['geometry_source']=='pm7' else identity.get('storage_physical_alias') or identity['sprime_conf_idx'])
                if key in STATE['sample_notes']:record['source_F64_cast_comparison']=STATE['sample_notes'][key]
            packed=pickle.dumps(item,protocol=5)
            if STATE.get('disk_guard'):STATE['disk_guard'].wait(path,len(packed),2)
            spool.execute('INSERT INTO molecules VALUES(?,?)',(mid,packed));spool.execute('DELETE FROM pieces WHERE mid=?',(mid,));spool.commit()
    finally:identities.close();cache.close();spool.close()
    result={'path':str(path),'mids':mids};I.save(marker,result);return result


def source_molecule_groups(plan,index):
    marker=Path(plan['source_working_root'])/'source_molecule_groups.json'
    if marker.is_file():return I.load(marker)['groups']
    coverage=I.load(plan['coverage']);db=sql_ro(A.database_path(index))
    members={mid:(role,common) for mid,role,common in db.execute('SELECT mid,role,common FROM members')};db.close()
    source=sql_ro(coverage['canonical_index']['path']);groups=collections.OrderedDict()
    query='''SELECT r.molecule_id,r.job_id,r.record_ordinal FROM records r
        JOIN (SELECT molecule_id,min(record_ordinal) first FROM records GROUP BY molecule_id) f
        ON r.record_ordinal=f.first ORDER BY r.job_id,r.record_ordinal'''
    try:
        for mid,job,ordinal in source.execute(query):
            role,common=members[mid]
            if not A.selected(role,common):continue
            split='TRAIN' if role=='TRAIN' else 'FULL';group=groups.setdefault(str(job),{'source_job_id':str(job),'TRAIN':[],'FULL':[]});group[split].append(mid)
    finally:source.close()
    result=list(groups.values());I.save(marker,{'groups':result,'primary_order':'original source job then original canonical ordinal; each MID selected once'})
    return result

def report_source_block_failure(number,future):
    if future.cancelled():error=repr(cf.CancelledError())
    else:
        failure=future.exception()
        if failure is None:return
        error=repr(failure)
    print(json.dumps({'phase':'SOURCE_BLOCK_FAILED','block':number,'error':error}),flush=True)


def submit_source_block(pool,task):
    future=pool.submit(work,task)
    callback=getattr(future,'add_done_callback',None)
    if callback is not None:callback(lambda done,number=task[0]:report_source_block_failure(number,done))
    return future


SOURCE_TASK_PREFIX_GROUPS=18
SOURCE_TASK_NUMBER_STRIDE=1<<20


def source_tasks(plan,groups,split,start_after=None):
    width=plan.get('source_task_molecules')
    if width is not None and (type(width)is not int or width<=0):raise ValueError('SOURCE_TASK_MOLECULES_MUST_BE_POSITIVE_INTEGER_OR_NULL')
    if width is None and start_after is not None and start_after>=SOURCE_TASK_NUMBER_STRIDE:
        raise ValueError('ENCODED_SOURCE_CURSOR_REQUIRES_ORIGINAL_CHUNK_HINT')
    legacy=start_after is not None and start_after<SOURCE_TASK_NUMBER_STRIDE
    def tasks():
        for group,values in enumerate(groups):
            mids=values[split]
            if not mids:continue
            if width is None or group<SOURCE_TASK_PREFIX_GROUPS:
                if start_after is None or group>start_after:yield group,mids,split
                continue
            if legacy and group<=start_after:continue
            chunks=(len(mids)+width-1)//width
            if chunks>SOURCE_TASK_NUMBER_STRIDE:raise ValueError('SOURCE_TASK_SUBINDEX_EXCEEDS_NUMBER_STRIDE')
            for subindex,lo in enumerate(range(0,len(mids),width)):
                number=group*SOURCE_TASK_NUMBER_STRIDE+subindex
                if start_after is None or legacy or number>start_after:yield number,mids[lo:lo+width],split
    return tasks()


def stream_split(plan,index,cache,schema,split,start_after=None):
    groups=source_molecule_groups(plan,index)
    tasks=source_tasks(plan,groups,split,start_after);workers=int(plan['workers'])
    buffer=int(plan.get('streaming_buffer_blocks',workers))
    if not 1<=buffer<=workers:raise ValueError('STREAMING_BUFFER_MUST_BE_BETWEEN_ONE_AND_WORKERS')
    # Same source-job/MID order; only the bounded pending window is adjustable.
    with cf.ProcessPoolExecutor(max_workers=workers,mp_context=mp.get_context('spawn'),initializer=init,initargs=(plan,index,cache,schema)) as pool:
        pending=collections.deque()
        for _ in range(buffer):
            task=next(tasks,None)
            if task is not None:pending.append((task[0],submit_source_block(pool,task)))
        while pending:
            number,future=pending.popleft();ref=future.result();db=sql_ro(ref['path']);ack={'committed':False}
            try:
                for position,mid in enumerate(ref['mids']):
                    row=db.execute('SELECT row FROM molecules WHERE mid=?',(mid,)).fetchone()
                    if row is None:raise ValueError('SOURCE_BLOCK_MOLECULE_MISSING')
                    item=pickle.loads(row[0])
                    if position==len(ref['mids'])-1:item['_source_block_end']={'number':number,'ack':ack}
                    yield item
            finally:db.close()
            # A block is recyclable only after the writer has synced its LMDB,
            # closed its ID fragment and atomically checkpointed the next cursor.
            if not ack['committed']:raise ValueError('SOURCE_BLOCK_CONSUMPTION_NOT_CHECKPOINTED')
            Path(ref['path']).unlink()
            task=next(tasks,None)
            if task is not None:pending.append((task[0],submit_source_block(pool,task)))


def factory(plan):
    index=A.prepare(plan);cache=cache_index(plan);schema=I.load(plan['schema'])
    total=sum(index['expected_conformers'].values());rng=random.Random(plan['sample_seed']);positions=set(rng.sample(range(total),min(1000,total)))
    db=sql_ro(A.database_path(index));sample=[];position=0
    try:
        for src,mid,physical,role,common in db.execute('SELECT g.src,g.mid,g.physical,m.role,m.common FROM geometries g JOIN members m ON m.mid=g.mid ORDER BY g.mid,g.src,g.physical'):
            if not A.selected(role,common):continue
            if position in positions:sample.append(physical_key(src,mid,physical))
            position+=1
    finally:db.close()
    if position!=total or len(sample)!=min(1000,total):raise ValueError('PHYSICAL_SOURCE_SAMPLE_SELECTION_COUNT')
    plan['source_sample_keys']=sample
    from .derived_pair import augment_schema
    augment_schema(schema)
    schema['role_codebook']={'TRAIN':0,'VAL':1,'ROUTINE':1,'FULL':2}
    schema['data_version']=plan['data_version'];schema['normalization_reference']=I.ref(plan['pm7_normalization'])
    schema['Pprime_normalization_reference']=plan.get('pprime_normalization')
    schema['full_population_sources']=True
    schema['historical_schema_versions']=schema.get('versions',{})
    schema['code_commit']=os.environ.get('D6_CODE_COMMIT',plan.get('code_commit','UNKNOWN_SOURCE_REVISION'))
    schema['versions']=dict(data_version=plan['data_version'],Common=I.ref(plan['common']),D4_PM7=I.ref(plan['pm7_normalization']),D4_Pprime=I.ref(plan['pprime_normalization']),D5=I.ref(plan['d5']),D7=I.ref(plan['orders']))
    schema['source_catalog_references']={name:I.ref(plan[name]) for name in ('source_index','coverage','pprime_cache','uff_d3_cache')}
    schema['order_availability']={'per_molecule':'Exact final D7 table; NULL energy/diversity omitted, never filled','reference':I.ref(plan['orders'])}
    schema['r73_order']='Raw K order/directions/onsite/duplicates remain in31-34; approved cached F64 same-symmetry sums additionally occupy two pair_labels columns'
    schema['normalization_by_source_condition']={'PM7_P_D':{'dataset':'P_D','reference':I.ref(plan['pm7_normalization'])},'UFF_D3_and_atomicSASA':{'dataset':'P_D','reference':I.ref(plan['pm7_normalization']),'independent_UFF_fit_performed':False,'PM7_UFF_mixed_refit_performed':False},'Pprime':{'dataset':'Pprime','reference':I.ref(plan['pprime_normalization'])}}
    schema['normalization_condition_contract']='workflows.data_v1_final.labels.final_release_v1.produce.normalization: Pprime condition -> Pprime dataset; every other label condition including D3 -> P_D'
    schema['final_mask_authority_references']=[I.ref(plan['pm7_normalization']),I.ref(plan['pprime_cache'])]
    plan['expected_molecules']=index['selected_molecules'];plan['expected_conformers']=index['expected_conformers']
    plan['source_dependencies']={k:plan[k] for k in ('common','orders','d5','coverage','source_index','pm7_normalization','pprime_cache','uff_d3_cache')}
    if plan.get('pprime_comparison'):schema['P_vs_Pprime_summary_reference']=I.ref(plan['pprime_comparison'])
    return schema,{split:(lambda start_after=None,s=split:stream_split(plan,index,cache,schema,s,start_after)) for split in ('TRAIN','FULL')}