"""Once-only P-prime raw projection, final physical first-two/TRAIN eligibility."""
from __future__ import annotations
import bisect,collections,concurrent.futures as cf,importlib,json,multiprocessing as mp,os,sqlite3,struct,sys
from pathlib import Path
from ..window2_normalization_v1 import io as I
from ..normalization_compact_runtime_v3 import codec as K
from ..common_train_normalization_day_v1 import bindings as B
from ..payload_audit_v1.payload import evaluate
from workflows.data_v1_final.pprime.window2_final_pprime_scope_v1.binding import binding,same_geometry,cached_base_rows
REPO=Path(__file__).absolute().parents[4]
STATE={}

class CachedCommon:
    def __init__(self,original):self.original=original;self.decoded={}
    def __getattr__(self,name):return getattr(self.original,name)
    def decode_cell(self,cell):
        key=id(cell)
        if key not in self.decoded:self.decoded[key]=self.original.decode_cell(cell)
        return self.decoded[key]


def need(value,message):
    if not value:raise ValueError(message)


def eligible(role,common,key,excluded):
    if role!='TRAIN':return False,'ROLE_'+str(role)
    if not common:return False,'OUTSIDE_FINAL_COMMON'
    if key in excluded:return False,'D5_UFF_BASE_AND_ALL_INPUT_VIEWS'
    return True,'FINAL_COMMON_TRAIN_FIRST2_NOT_D5'


def source_publications(plan):
    """Only closed original references and closed additional batch manifests."""
    index=I.load(plan['source_index']);files=I.load_data(index['files_reference']);byparent={};seen={};order=0
    def add(family,reference):
        nonlocal order
        if family=='QC':return
        path=reference['path'];ref={k:reference[k]for k in('path','bytes')}
        need(path not in seen or seen[path]==(family,ref),'CONFLICTING_PPRIME_SOURCE_REFERENCE')
        if path in seen:return
        seen[path]=(family,ref);parent=str(Path(path).parent)
        group=byparent.setdefault(parent,{'source_order':order,'families':{}})
        need(family not in group['families'],'TWO_FILES_FOR_SAME_BATCH_FAMILY')
        group['families'][family]=ref;order+=1
    for entry in files:
        if entry['domain']==1:add(entry['family'],entry['reference'])
    for root in plan.get('additional_pprime_roots',[]):
        manifest=I.load(Path(root)/'manifest.json')
        need(manifest['original_native_recipe_900s_unchanged']and manifest['no_Pprime_rank_ge_2'],'CLOSED_ORIGINAL_FIRST2_PRODUCER_REQUIRED')
        for batch in manifest['batches']:
            for ref in batch['files']:add(ref['family'],ref)
    result=[]
    for parent,group in sorted(byparent.items(),key=lambda x:x[1]['source_order']):
        need('base_geometry'in group['families'],'PPRIME_BATCH_BASE_REQUIRED')
        group.update(parent=parent);result.append(group)
    return result


def build_selection(plan,root):
    import pyarrow.parquet as pq
    common=I.load(plan['common']);d5=I.load(plan['d5']);first2=I.load(plan['first2']);members={}
    for ref in common['membership_tables']:
        pf=pq.ParquetFile(ref['path'])
        try:
            for batch in pf.iter_batches(columns=['molecule_id','effective_role','common_population'],batch_size=8192):
                for row in batch.to_pylist():
                    mid=row['molecule_id'];need(mid not in members,'FINAL_COMMON_DUPLICATE_MID')
                    members[mid]=(str(row['effective_role']).upper(),bool(row['common_population']))
        finally:pf.close()
    excluded=set();pf=pq.ParquetFile(d5['diagnostic_base_reference']['path'])
    try:
        gid_column='geometry_id' if 'geometry_id' in pf.schema_arrow.names else 'base_geometry_id'
        need(gid_column in pf.schema_arrow.names,'D5_ACTUAL_PHYSICAL_GEOMETRY_ID_REQUIRED')
        for batch in pf.iter_batches(columns=['geometry_source',gid_column],batch_size=8192):
            for row in batch.to_pylist():
                if row['geometry_source']=='uff_sprime':
                    need(bool(row[gid_column]),'D5_ACTUAL_UFF_GEOMETRY_ID_REQUIRED');excluded.add(row[gid_column])
    finally:pf.close()
    physical=I.load(plan['physical_binding_manifest']);need(physical['first2']==plan['first2'],'SAME_FINAL_FIRST2_BINDING_SOURCE')
    physical_ref=physical['physical_binding_database'];source_bindings=sqlite3.connect(Path(physical_ref['path']).as_uri()+'?mode=ro&immutable=1',uri=True)
    from workflows.data_v1_final.pprime.window2_final_pprime_scope_v1.binding import BindingStore
    def actual_binding(mid,conf):
        raw=source_bindings.execute('SELECT locator,raw FROM selected WHERE mid=? AND conf=?',(mid,conf)).fetchone()
        need(raw is not None,'FINAL_SELECTED_SOURCE_BINDING_REQUIRED')
        return binding(json.loads(raw[0]),json.loads(raw[1]))
    path=Path(root)/'eligibility.sqlite';db=sqlite3.connect(path)
    db.executescript('CREATE TABLE members(mid TEXT PRIMARY KEY,role TEXT,common INTEGER) WITHOUT ROWID; CREATE TABLE selected(mid TEXT,conf INTEGER,gid TEXT,role TEXT,common INTEGER,fit INTEGER,reason TEXT,binding TEXT,PRIMARY KEY(mid,conf)) WITHOUT ROWID; CREATE TABLE masks(rid TEXT,fid INTEGER,reason TEXT,PRIMARY KEY(rid,fid)) WITHOUT ROWID;')
    db.executemany('INSERT INTO members VALUES(?,?,?)',[(mid,role,int(member))for mid,(role,member)in members.items()]);db.commit()
    counts=collections.Counter();pf=pq.ParquetFile(first2['selected_geometry_table']['path'])
    try:
        for batch in pf.iter_batches(batch_size=8192):
            rows=[]
            for row in batch.to_pylist():
                mid=row['molecule_id'];conf=row['sprime_conf_idx'];need(type(conf)is int and mid in members,'ACTUAL_FINAL_FIRST2_ID_REQUIRED')
                need(row['fixed_random_rank']in(0,1),'PPRIME_THIRD_OR_LATER_FORBIDDEN')
                role,member=members[mid];fit,reason=eligible(role,member,row['geometry_id'],excluded)
                witness=actual_binding(mid,conf);need(witness['geometry_id']==row['geometry_id'],'FINAL_GID_AND_PHYSICAL_SOURCE_BINDING')
                rows.append((mid,conf,row['geometry_id'],role,int(member),int(fit),reason,json.dumps(witness,separators=(',',':'))));counts[reason]+=1
            db.executemany('INSERT INTO selected VALUES(?,?,?,?,?,?,?,?)',rows);db.commit()
        if plan.get('mask_exclusions'):
            source=I.load(plan['mask_exclusions'])
            for row in source['record_field_exclusions']:
                db.execute('INSERT INTO masks VALUES(?,?,?)',(row['record_id'],row['field_id'],row['reason']))
            db.commit()
    finally:pf.close();db.close();source_bindings.close()
    return {'path':str(path),'bytes':path.stat().st_size,'reason_counts':dict(counts),'D5_actual_UFF_heldout_bases':len(excluded),'physical_binding_database':physical_ref}


def initialize(plan,eligibility,field_map,root):
    import pyarrow as pa
    pa.set_cpu_count(1);pa.set_io_thread_count(1)
    parent=REPO/'workflows/data_v1_final/labels';sys.path.insert(0,str(parent))
    try:
        common=importlib.import_module('common');masks=importlib.import_module('pilot_masks')
        need(Path(common.__file__).absolute()==parent/'common.py'and Path(masks.__file__).absolute()==parent/'pilot_masks.py','ORIGINAL_LABEL_MASK_IMPORTS')
    finally:sys.path.pop(0)
    cfg=I.load(plan['science_config'])['science'];registry=I.load_data(cfg['sources']['registry'])['fields']
    # Preserve the exact original146 IDs. Pprime contains the original12 P tasks,
    # not the molecule D20 or per-conformer D3 descriptors.
    original=I.load_data(field_map);ids={f['field_key']:f['field_id']for f in original}
    declarations=[dict(f,field_id=ids.get(f['field_key']))for f in registry]
    STATE.update(plan=plan,db=sqlite3.connect(Path(eligibility['path']).as_uri()+'?mode=ro&immutable=1',uri=True),binding_cache=sqlite3.connect(Path(eligibility['physical_binding_database']['path']).as_uri()+'?mode=ro&immutable=1',uri=True),
        fields={task:[f for f in declarations if f['task']==task]for task in B.TASKS},common=common,masks=masks,root=Path(root),byid={f['field_id']:f for f in original},derived_fields=[f for f in original if f['field_id']in(146,147)])


def cache_schema():
    import pyarrow as pa
    return pa.schema([('record_id',pa.string()),('molecule_id',pa.string()),('sprime_conf_idx',pa.int64()),('atomic_numbers',pa.list_(pa.int16())),
        ('fit_eligible',pa.bool_()),('effective_role',pa.string()),('geometry_id',pa.string()),('geometry_binding_evidence',pa.string()),('r73_pair_indices',pa.list_(pa.list_(pa.int64()))),('source_path',pa.string()),('source_bytes',pa.int64()),('row_group',pa.int32()),('row_within_group',pa.int64()),('physical_row',pa.int64()),('family',pa.string()),('calc_type',pa.string()),('field_ids',pa.list_(pa.uint16())),('lengths',pa.list_(pa.uint32())),
        ('data_f64',pa.large_binary()),('present',pa.binary()),('atom_indices',pa.large_binary()),('indexed',pa.binary()),('index_modes',pa.list_(pa.uint8())),
        ('source_mask',pa.binary()),('value_mask',pa.binary()),('reasons_json',pa.large_string())])


def apply_explicit_exclusions(entries,exclusions):
    for e in entries:
        reason=exclusions.get(e['field_id'])
        if reason:
            e['value_mask']=[False]*len(e['value_mask']);e['new_reasons']=list(dict.fromkeys([*e['new_reasons'],reason]))
    return entries

def bind_selection(base,selection):
    """Only an actual input-geometry match may assign final GID or fit role."""
    gid,role,common,fit,reason,witness=selection
    if gid is None:return (None,role,common,0,reason,'NOT_FINAL_SELECTED_PHYSICAL_GEOMETRY')
    matched,evidence=same_geometry(base,json.loads(witness))
    need(matched is not None,'RAW_BASE_REQUIRES_ACTUAL_SOURCE_GEOMETRY_EVIDENCE')
    if not matched:return (None,role,common,0,'DIFFERENT_ACTUAL_GEOMETRY_AT_SAME_MID_CONF',evidence)
    return (gid,role,common,fit,reason,evidence)

def bind_registered_source(base,bound,selected_gid,database):
    """A different registered diagnostic/source GID retains its own identity."""
    if bound[0] is not None:return bound
    from workflows.data_v1_final.pprime.window2_final_pprime_scope_v1.prepare import geometry
    for gid,locator in database.execute('SELECT gid,locator FROM candidates WHERE mid=? AND conf=?',(base['molecule_id'],base['sprime_conf_idx'])):
        if gid==selected_gid:continue
        row=json.loads(locator);matched,evidence=same_geometry(base,binding(row,geometry(row)))
        need(matched is not None,'REGISTERED_SOURCE_REQUIRES_REAL_GEOMETRY_EVIDENCE')
        if matched:return (gid,bound[1],bound[2],0,'REGISTERED_SOURCE_OUTSIDE_FINAL_SELECTED_GEOMETRY',evidence)
    return (None,bound[1],bound[2],0,'UNREGISTERED_ORIGINAL_PPRIME_SOURCE_GEOMETRY_RETAINED',bound[5])


def project_partition(work):
    import pyarrow as pa,pyarrow.parquet as pq
    from ..window2_validity_v1.policy import apply_ea_entry
    from ..window2_r73_views_v1.kernel import derive_entries
    part,publications=work;folder=STATE['root']/('cache_%02d'%part);folder.mkdir(parents=True,exist_ok=False)
    writers={};paths={};file_counts=collections.Counter();counts=collections.Counter();field_counts=collections.defaultdict(collections.Counter);records=[];overrides=[]
    try:
        for publication in publications:
            base_ref=publication['families']['base_geometry'];bases={};pf=None
            cached_bases=cached_base_rows(STATE['binding_cache'],base_ref['path'])
            if cached_bases is None:
                pf=pq.ParquetFile(base_ref['path']);base_batches=(batch.to_pylist() for batch in pf.iter_batches(batch_size=256))
            else:base_batches=[cached_bases]
            try:
                for rows in base_batches:
                    for row in rows:
                        rid=row['record_id'];need(rid not in bases,'DUPLICATE_RAW_BASE_RECORD')
                        key=(row['molecule_id'],row['sprime_conf_idx']);selection=STATE['db'].execute('SELECT gid,role,common,fit,reason,binding FROM selected WHERE mid=? AND conf=?',key).fetchone()
                        if selection is None:
                            member=STATE['db'].execute('SELECT role,common FROM members WHERE mid=?',(row['molecule_id'],)).fetchone()
                            need(member is not None,'RAW_PPRIME_MID_IN_FINAL_SOURCE_POPULATION');selection=(None,member[0],member[1],0,'NOT_FINAL_FIXED_RANDOM_FIRST2',None)
                        selected_gid=selection[0];selection=bind_selection(row,selection)
                        selection=bind_registered_source(row,selection,selected_gid,STATE['binding_cache'])
                        need(type(row['sprime_conf_idx'])is int and row['geometry_source']=='uff_sprime','EXPLICIT_RAW_UFF_IDENTITY')
                        z=row['atomic_numbers'];xyz=row['positions_A'];need(len(z)==len(xyz)and all(len(p)==3 for p in xyz),'PPRIME_BASE_ATOM_GEOMETRY_ALIGNMENT')
                        bases[rid]=(row,selection);records.append(dict(record_id=rid,molecule_id=key[0],sprime_conf_idx=key[1],geometry_id=selection[0],
                            geometry_binding_evidence=selection[5],fit_eligible=bool(selection[3]),base_source_path=base_ref['path'],
                            atomic_numbers=z,positions_A=xyz,source_record_id=row['source_record_id'],
                            uff_geometry_sha256=row.get('uff_geometry_sha256'),uff_coordinate_sha256=row.get('uff_coordinate_sha256'),native_atom_order_sha256=row.get('native_atom_order_sha256')))
            finally:
                if pf is not None:pf.close()
            tasks_seen={rid:set()for rid in bases}
            for family,ref in publication['families'].items():
                if family=='base_geometry':continue
                pf=pq.ParquetFile(ref['path']);buffers=collections.defaultdict(list);physical=-1;offsets=[0]
                for rg in range(pf.num_row_groups):offsets.append(offsets[-1]+pf.metadata.row_group(rg).num_rows)
                try:
                    for batch in pf.iter_batches(batch_size=16,use_threads=False):
                        for row in batch.to_pylist():
                            rid=row['record_id'];physical+=1;rg=bisect.bisect_right(offsets,physical)-1
                            if rid not in bases:continue
                            base,selection=bases[rid];gid,role,common_member,fit,reason,binding_evidence=selection
                            need(row['molecule_id']==base['molecule_id']and row['geometry_source']=='uff_sprime','RAW_TASK_AND_BASE_MID_ALIGNMENT')
                            if row.get('uff_coordinate_sha256')and base.get('uff_coordinate_sha256'):need(row['uff_coordinate_sha256']==base['uff_coordinate_sha256'],'EXISTING_TASK_BASE_GEOMETRY_WITNESS')
                            task=row['calc_type'];need(row.get('total_atoms')is None or row['total_atoms']==len(base['atomic_numbers']),'TASK_BASE_ATOM_COUNT_ALIGNMENT');row['total_atoms']=len(base['atomic_numbers'])
                            need(task not in tasks_seen[rid],'DUPLICATE_PPRIME_RECORD_TASK');tasks_seen[rid].add(task)
                            need(task in STATE['fields']and task not in('D20','D3'),'ORIGINAL_TWELVE_PPRIME_TASK')
                            cached=CachedCommon(STATE['common'])
                            entries,*_=evaluate(row,family,STATE['fields'][task],cached,STATE['masks'],B.pair_keys,{})
                            exclusions=dict(STATE['db'].execute('SELECT fid,reason FROM masks WHERE rid=?',(rid,)))
                            apply_explicit_exclusions(entries,exclusions)
                            for entry in entries:
                                override=apply_ea_entry(entry,converged=row.get('converged'))
                                if override:overrides.append(dict(override,record_id=rid,molecule_id=base['molecule_id'],sprime_conf_idx=base['sprime_conf_idx']))
                            for entry in list(entries):
                                original_field=STATE['byid'][entry['field_id']]
                                if original_field.get('registry_id')==73 and entry['field_id']<146:
                                    cell=next((cell for cell in row.get('values',[])if cell.get('registry_id')==73),None)
                                    raw=cached.decode_cell(cell)if cell is not None and entry['values_float64']else[]
                                    if not entry['values_float64']:raw=[]
                                    entries.extend(derive_entries(raw,dict(entry,field=original_field),field_map=STATE['derived_fields']))
                            owner=str(row['job_id']);file_key=(owner,part)
                            if file_key not in writers:
                                path=folder/('job_'+owner+'_partition_%02d.parquet'%part)
                                writers[file_key]=pq.ParquetWriter(path,cache_schema(),compression='zstd');paths[file_key]=path
                            pair_indices=next((entry['pair_indices'] for entry in entries if entry['field_id']==146),[])
                            need(all(entry.get('pair_indices')==pair_indices for entry in entries if entry['field_id'] in (146,147)),'DERIVED_R73_PAIR_ORDER_ALIGNMENT')
                            buffers[file_key].append(dict(record_id=rid,molecule_id=base['molecule_id'],sprime_conf_idx=base['sprime_conf_idx'],atomic_numbers=base['atomic_numbers'],fit_eligible=bool(fit),effective_role=role,geometry_id=gid,geometry_binding_evidence=binding_evidence,r73_pair_indices=pair_indices,source_path=ref['path'],source_bytes=ref['bytes'],row_group=rg,row_within_group=physical-offsets[rg],physical_row=physical,family=family,calc_type=task,**K.pack_entries(entries)))
                            counts['task_rows']+=1;counts['fit_task_rows']+=bool(fit)
                            for e in entries:
                                c=field_counts[str(e['field_id'])];c['records']+=1;c['source_valid_records']+=bool(any(e['source_value_mask']));c['valid_records']+=bool(any(e['value_mask']))
                                c['newly_masked_records']+=any(a and not b for a,b in zip(e['source_value_mask'],e['value_mask']))
                        for key,rows in buffers.items():
                            if rows:writers[key].write_table(pa.Table.from_pylist(rows,schema=cache_schema()),row_group_size=16);file_counts[key]+=len(rows)
                        buffers.clear()
                finally:pf.close()
            expected=set(B.TASKS)-{'D20','D3'}
            need(all(tasks==expected for tasks in tasks_seen.values()),'EXACT_TWELVE_TASKS_PER_PPRIME_RECORD')
            print(json.dumps({'cache_partition':part,'source_order':publication['source_order'],'raw_task_rows':counts['task_rows']}),flush=True)
    finally:
        for writer in writers.values():writer.close()
    # IDs are the minimal producer alignment manifest, not hashes or receipts.
    idpath=folder/'physical_records.parquet';id_schema=pa.schema([('record_id',pa.string()),('molecule_id',pa.string()),('sprime_conf_idx',pa.int64()),('geometry_id',pa.string()),('geometry_binding_evidence',pa.string()),('fit_eligible',pa.bool_()),('base_source_path',pa.string()),('source_record_id',pa.string()),('atomic_numbers',pa.list_(pa.int16())),('positions_A',pa.large_list(pa.list_(pa.float64(),3))),('uff_geometry_sha256',pa.string()),('uff_coordinate_sha256',pa.string()),('native_atom_order_sha256',pa.string())]);pq.write_table(pa.Table.from_pylist(records,schema=id_schema),idpath,compression='zstd')
    override_ref=I.save(folder/'EA_mask_overrides.json',{'record_field_exclusions':overrides,'new_mask_fraction_is_report_only':True,'values_modified':False})
    result={'partition':part,'counts':dict(counts),'EA_mask_overrides_reference':override_ref,'records':dict(I.ref(idpath),records=len(records)),
        'field_counts':{k:dict(v)for k,v in field_counts.items()},'parts':[dict(I.ref(path),source_job_id=key[0],source_order=key[1],records=file_counts[key])for key,path in paths.items()]}
    return I.save(folder/'manifest.json',result)


def build(plan):
    import pyarrow.parquet as pq
    root=Path(plan['output'])/'projection';root.mkdir(parents=True,exist_ok=True)
    if(root/'manifest.json').exists():return I.load(root/'manifest.json')
    coverage=I.load(plan['coverage']);source_fields=I.load_data(coverage['field_map_reference']);pfields=[f for f in source_fields if f['task']not in('D20','D3')]
    from ..window2_r73_views_v1.kernel import derived_fields
    field_ref=I.save(root/'Pprime_field_map.json',pfields+derived_fields(pfields));eligibility=build_selection(plan,root)
    sources=source_publications(plan);workers=plan.get('workers',16);parts=[sources[len(sources)*i//workers:len(sources)*(i+1)//workers]for i in range(workers)]
    with cf.ProcessPoolExecutor(workers,mp_context=mp.get_context('spawn'),initializer=initialize,initargs=(plan,eligibility,field_ref,str(root)))as pool:
        refs=list(pool.map(project_partition,list(enumerate(parts))))
    seen={};groups=collections.defaultdict(list);stats=collections.defaultdict(collections.Counter)
    for ref in refs:
        manifest=I.load_data(ref)
        for part in manifest['parts']:groups[part['source_job_id']].append(part)
        for fid,count in manifest['field_counts'].items():stats[fid].update(count)
        pf=pq.ParquetFile(manifest['records']['path'])
        try:
            for batch in pf.iter_batches(batch_size=8192):
                for row in batch.to_pylist():
                    identity=row['geometry_id'] or row['uff_geometry_sha256'];need(bool(identity),'ORIGINAL_GEOMETRY_INPUT_WITNESS_REQUIRED')
                    key=(row['molecule_id'],row['sprime_conf_idx'],identity);need(key not in seen,'DUPLICATE_ACTUAL_PHYSICAL_PPRIME_GEOMETRY_ACROSS_PRODUCERS');seen[key]=row['record_id']
        finally:pf.close()
    logical=[{'group_index':i,'source_job_id':job,'typed_parts':sorted(values,key=lambda p:p['source_order'])}for i,(job,values)in enumerate(sorted(groups.items()))]
    group_ref=I.save(root/'logical_groups.json',{'groups':logical})
    result={'schema':'PPRIME_FINAL_FIRST2_TYPED_FLOAT64_CACHE_V1','geometry_source':'uff_sprime','field_map_reference':field_ref,'logical_group_plan_reference':group_ref,
        'eligibility':eligibility,'physical_binding_manifest':plan['physical_binding_manifest'],'element_basis':coverage['element_basis'],'part_manifests':refs,'records':len(seen),'field_mask_counts':{k:dict(v)for k,v in stats.items()},'EA_mask_overrides_references':[I.load_data(r)['EA_mask_overrides_reference']for r in refs],
        'source_geometry_pointer_tables':[I.load_data(r)['records'] for r in refs],
        'unregistered_geometry_policy':'original F64/Z/anchor and raw base source pointer retained with geometry_id null; never relabelled to selected GID; no fit',
        'cache_scope':'ALL_EXISTING_PPRIME_RECORDS_ALL_ROLES; fit only final Common TRAIN first2 minus D5','r73_pair_views':{'sigma_field_id':146,'pi_field_id':147,'raw_r73_retained':True,'definition':'USER_APPROVED_PURE_SIGMA_SIGMA_PI_PI'},'source_raw_reads':1,'new_content_hashes':False,'independent_readback':False,'physical_first2_selection':plan['first2'],'Common':plan['common'],'D5':plan['d5']}
    I.save(root/'manifest.json',result);return result
