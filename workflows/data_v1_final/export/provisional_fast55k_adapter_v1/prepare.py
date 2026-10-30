"""Build the actual local metadata/index binding in the existing GPU Parent."""
from __future__ import annotations
from dataclasses import asdict
import json,os,sqlite3
from pathlib import Path
from .common import need,read,write,reference,frame,local,digest,compute_context,actual_parent,VERSION
from . import statistics
_NATIVE=None

def _index_document(rows,role,geometry_source,group_mask,family_mask):
    from phychem_mfm.phase1.v3_sampling import ConformerRef,MoleculeEntry,InMemorySamplingIndex
    grouped={}
    for r in rows:
        grouped.setdefault(r['mid'],[]).append(ConformerRef(r['gid'],r['rank'],r['n_atoms'],
          ((geometry_source,r['gid']),)))
    molecules=tuple(MoleculeEntry(mid,tuple(values),tuple(sorted(group_mask.items())),tuple(sorted(family_mask.items())))
      for mid,values in sorted(grouped.items()))
    if not molecules:return None
    index=InMemorySamplingIndex(molecules,VERSION,role,'data_line')
    return {'schema':'ACTUAL_PROVISIONAL_MODEL_SAMPLING_INDEX_V1','role':role,'version':VERSION,
      'authority':'data_line','molecules':[asdict(m)for m in molecules],'content_sha256':index.content_sha256,
      'geometry_source':geometry_source,'orders':['fixed_random'],'not_energy_or_diversity':True}

def load_index(reference_value):
    from phychem_mfm.phase1.v3_sampling import ConformerRef,MoleculeEntry,InMemorySamplingIndex
    d=read(reference_value);need(d['schema']=='ACTUAL_PROVISIONAL_MODEL_SAMPLING_INDEX_V1','ACTUAL_INDEX_SCHEMA')
    molecules=[]
    for m in d['molecules']:
        cs=tuple(ConformerRef(**c)for c in m['conformers'])
        molecules.append(MoleculeEntry(m['molecule_id'],cs,tuple(tuple(x)for x in m['group_mask']),
          tuple(tuple(x)for x in m['family_mask']),m['mixed_geometry_source'],m['minimum_energy_conformer_id']))
    index=InMemorySamplingIndex(tuple(molecules),d['version'],d['role'],'data_line')
    need(index.content_sha256==d['content_sha256'],'ACTUAL_INDEX_CANONICAL_IDENTITY')
    return index

def _model_registry(source,mapping,pooling,structural_fields):
    from phychem_mfm.phase1.v3_contract import FieldSpec,LabelRegistry
    fs={r['field_key']:r for r in source['fields']if r['status']=='enabled'};out=[]
    need(len(fs)==146,'EXACT146_DEFINITIONS_NOT_146_MODEL_HEADS')
    for t in mapping['physical_targets']:
        level='ordered_entry'if t.get('wire_kind')=='SOURCE_ORDERED_RECORDS_V1'else {'molecule':'graph','atom':'atom','pair':'pair'}[t['level']]
        representation={'symmetric_tensor':'symmetric_tensor6','vector':'vector','scalar':'scalar'}[t['kind']]
        need(t['target_id']in pooling,'EXPLICIT_MODEL_POOLING_CHOICE:'+t['target_id'])
        out.append(FieldSpec(t['target_id'],t['group'],t['family'],level,
          representation=representation,pooling=pooling[t['target_id']],unit=t['unit']))
    structural=tuple(FieldSpec(**f)for f in structural_fields)
    need(len(structural)==3 and all(f.group=='S'for f in structural),'EXPLICIT_EXISTING_MODEL_STRUCTURAL_SPEC')
    return LabelRegistry(tuple([*structural,*out]),VERSION,digest({'registry':source,'mapping':mapping}),'data_line')

def _native_status(pointer):
    """Read only the original literal S status using its existing SHA reader.

    This optional preparation step uses the historical readonly native decoder,
    not pickle in a new training format. No graph/UFF/QM function is called.
    """
    global _NATIVE
    from workflows.data_v1_final.export.d5_inputs_builder_v1.geometry import originals
    if _NATIVE is None:_NATIVE=originals(initialize=False)[0]
    # read() itself verifies the original record payload SHA/atom count. Do not
    # call native.graph()/worker_init(): no graph calculation or host-thread reset.
    p=Path(pointer['source_path']);p=p if p.is_absolute()else Path('/share/home/zixiao/descriptor_analysis')/p
    before=frame(p);raw=_NATIVE.read(pointer);need(frame(p)==before,'ORIGINAL_NATIVE_SOURCE_FRAME')
    status=_NATIVE.field(raw,'rdkit_bond_status');fail=_NATIVE.field(raw,'rdkit_bond_fail_reason')
    need(status is None or type(status)is str,'LITERAL_NATIVE_BOND_STATUS_NOT_INFERRED_OK')
    need(fail is None or type(fail)is str,'LITERAL_NATIVE_BOND_FAIL_REASON')
    return status,fail

def build(inputs,output,*,check_host_resources,diagnostic_supplement_reference=None,
          diagnostic_local_copy_reference=None,include_native_bond_status=False):
    """Called after actual D3/local I/O, never on login or before future C0.

    inputs is small runtime configuration: D2/D3/D4/D5/joint/local-I/O refs,
    original reason-codebook ref, explicit Model pooling and structural fields.
    No source statistics are fitted here and no scientific mask is changed.
    """
    compute_context();need(callable(check_host_resources),'EXISTING_LIVE_HOST_GUARD');check_host_resources()
    d3=read(inputs['D3_export_reference']);d4=read(inputs['D4_normalization_reference']);d5=read(inputs['D5_delivery_reference'])
    io=read(inputs['local_io_receipt_reference']);root=Path(io['local_root']);out=Path(output)
    need(root in out.parents and not out.exists(),'FRESH_PREPARATION_IN_ACTUAL_LOCAL_COPY_ROOT');out.mkdir()
    need(d3['schema']=='DATA_V1_PILOT_D3_FORMAL_EXPORT_DELIVERY_V1'and d3['version']==VERSION
      and d3['pilot_counts']=={'TRAIN':50000,'VAL':5000}
      and io['schema']=='ACTUAL_PROVISIONAL_D3_GPU_HOST_LOCAL_IO_RECEIPT_V1'
      and io['D3_export_reference']==inputs['D3_export_reference']
      and io['status']=='EXACT_D3_LOCAL_COPY_AND16_READER_IO_COMPLETE_NOT_MODEL_ACK','ACTUAL_CLOSED_PROVISIONAL_D3_AND_LOCAL_IO')
    need(d4['schema']=='DATA_V1_PILOT_D4_FORMAL_NORMALIZATION_DELIVERY_V1'and d4['fit_role']=='TRAIN'
      and d4['fit_pilot_molecules']==50000 and d4['VAL_used_for_fitting']is False,'ACTUAL_TRAIN_ONLY_D4')
    cfg=d3['actual_configuration_references'];reg=read(cfg['registry_reference']);mapping=read(cfg['mapping_reference'])
    policies=read(cfg['target_policy_reference']);numeric=read(d4['statistics_reference']);other=read(d4['independent_equal_replay_reference'])
    need(digest(numeric)==digest(other),'ACTUAL_D4_TWO_REPLAYS_EQUAL')
    report=read(d4['r674_report_reference']);need(report['population_version_reference']==d4['population_reference'],'ACTUAL_R674_POPULATION')
    projection=statistics.extract(reg,mapping,numeric,report,numeric_reference=d4['statistics_reference'],
      population_reference=d4['population_reference'],heldout_reference=inputs['D5_delivery_reference'])
    d4_projection=write(out/'D4_projection.json',projection)
    registry=_model_registry(reg,mapping,inputs['model_field_pooling'],inputs['structural_fields'])
    from phychem_mfm.phase1.v3_structural import StructuralFieldBinding
    structural=StructuralFieldBinding(**inputs['structural_binding']);structural.validate(registry)
    registry_ref=write(out/'model_registry.json',{'fields':[asdict(f)for f in registry.fields],
      'version':VERSION,'source_sha256':registry.source_sha256,'authority':'data_line',
      'content_sha256':registry.content_sha256,'all146_source_registry_reference':cfg['registry_reference']})
    dbpath=out/'catalog.sqlite';db=sqlite3.connect(dbpath);db.row_factory=sqlite3.Row
    db.executescript('CREATE TABLE geometries(gid TEXT PRIMARY KEY,mid TEXT,source TEXT,role TEXT,n_atoms INTEGER,rank INTEGER,ordinary INTEGER,store TEXT,geometry_sha TEXT,atom_sha TEXT,metadata TEXT,native_bond_status TEXT,native_bond_fail_reason TEXT);'
      'CREATE INDEX mid_idx ON geometries(mid,source,role);CREATE TABLE labels(gid TEXT,tid TEXT,store TEXT,PRIMARY KEY(gid,tid));')
    sources=[(io,False)];supplement=None;diagnostic_members={};diagnostic_mids=set()
    if diagnostic_supplement_reference is not None:
        supplement=read(diagnostic_supplement_reference)
        need(supplement['schema']=='ACTUAL_D3_DIAGNOSTIC_SUPPLEMENT_V1'
          and supplement['role']=='TRAIN_UNSEEN_CONFORMATION'
          and supplement['store_namespace']=='pilot_D3_diagnostic_supplement_v1'
          and supplement['consumer_alias_prefix']=='diagnostic/'
          and supplement['D3_export_reference']==inputs['D3_export_reference']
          and supplement['D4_normalization_reference']==inputs['D4_normalization_reference']
          and supplement['D5_delivery_reference']==inputs['D5_delivery_reference'],'EXACT_ACTUAL_DIAGNOSTIC_INTERSECTION_NOT_ALL20K_FICTION')
        actual_parent(supplement['actual_parent_accounting_reference'],supplement['actual_parent_job_id'])
        import pyarrow.parquet as pq
        member_ref=supplement['selected_diagnostic_geometry_ids_reference']
        need(reference(member_ref['path'])==member_ref,'ACTUAL_DIAGNOSTIC_MEMBERSHIP_SHA')
        for m in pq.read_table(member_ref['path']).to_pylist():
            need(m['geometry_id']not in diagnostic_members and m['sample_role']=='TRAIN_UNSEEN_CONFORMATION'
              and m['training_excluded']is True,'UNIQUE_ACTUAL_DIAGNOSTIC_GID_MEMBERSHIP')
            diagnostic_members[m['geometry_id']]=m
        mid_ref=supplement['actual_seen_diagnostic_molecule_ids_reference']
        need(reference(mid_ref['path'])==mid_ref,'ACTUAL_DIAGNOSTIC_MID_INTERSECTION_SHA')
        mid_rows=pq.read_table(mid_ref['path'],columns=['molecule_id']).to_pylist()
        diagnostic_mids={m['molecule_id']for m in mid_rows}
        need(len(diagnostic_mids)==len(mid_rows)and diagnostic_mids=={m['molecule_id']for m in diagnostic_members.values()},
          'EXACT_ACTUAL_SEEN_DIAGNOSTIC_MID_AND_GID_INDEX_INTERSECTION')
        need(diagnostic_local_copy_reference is not None,'ACTUAL_DIAGNOSTIC_LOCAL_COPY_REQUIRED_NOT_SHARED_PATH')
        diaglocal=read(diagnostic_local_copy_reference)
        need(diaglocal['diagnostic_supplement_reference']==diagnostic_supplement_reference,
          'DIAGNOSTIC_LOCAL_ORIGIN_BINDING');sources.append((diaglocal,True))
    cls,source=__import__('workflows.data_v1_final.export.provisional_fast55k_adapter_v1.reader',fromlist=['modules']).modules()
    stores=[];frames={};targets={t['target_id']:t for t in mapping['physical_targets']};tokens=set();masks=None
    status_cache={};all_store_names=set()
    for origin,isdiag in sources:
        inventory=read(origin['local_copy_inventory_reference']);copies={r['origin']['path']:r for r in inventory}
        for item in origin['local_stores']:
            check_host_resources();old=read(item['origin_reference']);origin_name=old['name']
            name=(supplement['consumer_alias_prefix']+origin_name)if isdiag else origin_name
            need(name not in all_store_names,'UNIQUE_REAL_MAIN_AND_DIAGNOSTIC_STORE_NAMES');all_store_names.add(name)
            for key in('data','manifest_reference'):
                need(old[key]['path']in copies and copies[old[key]['path']]['origin']==old[key],'EXACT_COPY_ORIGIN')
            f64=old['f64_authority']['reference'];need(copies[f64['path']]['origin']==f64,'EXACT_LOCAL_F64_ORIGIN')
            s=dict(old,name=name,origin_store_name=origin_name,path=item['path'],data=copies[old['data']['path']]['local'],
              manifest_reference=copies[old['manifest_reference']['path']]['local'],f64_authority=copies[f64['path']]['local'])
            for r in(s['data'],s['manifest_reference'],s['f64_authority']):local(r['path'],root);frames[r['path']]=frame(r['path'])
            stores.append(s)
            with cls(s['path'],expected_schema_sha256=s['schema_sha256'])as reader:
                need(reader.count==s['records']and reader.molecule_count==s['molecules'],'ACTUAL_ALL_STORE_COUNTS')
                with reader.env.begin()as tx,tx.cursor(db=reader.records)as cursor:
                    for key,_ in cursor:
                        check_host_resources();gid=key.decode();m,a=reader.get(gid)
                        if s['kind']=='geometry':
                            status=fail=None
                            if include_native_bond_status:
                                provenance=m['actual_geometry_provenance'];pointer=json.loads(provenance['source_provenance_json'])
                                if {'source_path','real_index','record_payload_sha256','total_atoms'}<=set(pointer):
                                    anchor=pointer['record_payload_sha256']
                                    if anchor not in status_cache:status_cache[anchor]=_native_status(pointer)
                                    status,fail=status_cache[anchor]
                            ordinary=m.get('ordered_base_only')is True
                            rank=m['available_base_order_ranks'].get('fixed_random')if ordinary else None
                            if isdiag:
                                member=diagnostic_members.get(gid)
                                need(member is not None and member['molecule_id']==m['molecule_id']
                                  and member['geometry_source']==m['geometry_source']
                                  and m['effective_role']=='TRAIN'and m['sample_role']=='TRAIN_UNSEEN_CONFORMATION'
                                  and m['diagnostic_only']is True and m['training_excluded']is True,
                                  'ACTUAL_DIAGNOSTIC_MEMBERSHIP_NOT_OLD_TRAIN_ROLE_ALIAS')
                                rank=member['original_fixed_random_rank']if member['is_base']else None
                                need(member['native_record_id']==m['native_record_id']
                                  and member['sprime_conf_idx']==m['sprime_conf_idx']
                                  and member['parent_geometry_id']==m['parent_geometry_id']
                                  and member['view_id']==m['view_id'],'SAME_DIAGNOSTIC_SOURCE_NATIVE_ORDER_AND_PARENT')
                                if member['is_base']:
                                    need(ordinary and type(rank)is int and type(member['original_N'])is int
                                      and 0<=rank<member['original_N'],'REAL_ORIGINAL_BASE_ORDER_NOT_RENUMBERED_N')
                            db.execute('INSERT INTO geometries VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(
                              gid,m['molecule_id'],m['geometry_source'],'TRAIN_UNSEEN_CONFORMATION'if isdiag else m['effective_role'],
                              m['n_atoms'],rank,int(ordinary),name,m['geometry_sha256'],m['atom_order_sha256'],json.dumps(m),status,fail))
                        else:
                            if isdiag:need(gid in diagnostic_members,'EVERY_DIAGNOSTIC_FAMILY_GID_IN_EXPLICIT_D5_INDEX')
                            these={**reader.schema.get('compiled',{}).get('physical_targets',{}),**reader.schema.get('ordered_record_targets',{})}
                            for tid,t in these.items():
                                need(tid in targets and digest(t)==digest(targets[tid]),'SAME_ACTUAL_TARGET_MAPPING_IN_STORE')
                                db.execute('INSERT INTO labels VALUES(?,?,?)',(gid,tid,name))
                                if t.get('wire_kind')=='SOURCE_ORDERED_RECORDS_V1':
                                    from workflows.data_v1_final.export.family_export_day_v1.transport import decode_strings
                                    p='transport/'+tid+'/'
                                    tokens.update(decode_strings(a[p+'basis_i_utf8'],a[p+'basis_i_offsets']))
                                    tokens.update(decode_strings(a[p+'basis_j_utf8'],a[p+'basis_j_offsets']))
                            current=(m['group_exposure_mask'],m['family_exposure_mask'])
                            need(masks is None or current==masks,'EXPLICIT_UNCHANGED_RECIPE_EXPOSURE_MASKS');masks=current
            db.commit()
    need(masks is not None,'ACTUAL_NONEMPTY_LABEL_PAYLOAD')
    need(db.execute('SELECT count(*) FROM labels l LEFT JOIN geometries g USING(gid) WHERE g.gid IS NULL').fetchone()[0]==0,
      'EVERY_FAMILY_AT_ACTUAL_EXPORTED_GEOMETRY')
    if diagnostic_members:
        need({r[0]for r in db.execute("SELECT gid FROM geometries WHERE role='TRAIN_UNSEEN_CONFORMATION'")}==set(diagnostic_members),
          'ALL_ACTUAL_DIAGNOSTIC_GIDS_EXACTLY_CONSERVED')
        train_mids={r[0]for r in db.execute("SELECT DISTINCT mid FROM geometries WHERE role='TRAIN'")}
        need(diagnostic_mids<=train_mids,'DIAGNOSTIC_MOLECULES_MUST_ALREADY_BE_PILOT_TRAIN_SEEN')
    counts={r['role']:r['n']for r in db.execute('SELECT role,count(DISTINCT mid) n FROM geometries GROUP BY role')}
    need(counts.get('TRAIN')==50000 and counts.get('VAL')==5000,'EXACT_ACTUAL_PILOT_ROLE_COUNTS')
    group_mask,family_mask=map(dict,masks)
    for f in registry.fields:
        if f.group=='S':family_mask[f.family]=group_mask['S']
    indexes={};index_hash={};index_sources={};role_headers={};selections=inputs['geometry_source']
    need(selections in('PM7','Sprime_UFF'),'ONE_EXPLICIT_PER_SOURCE_INDEX_NOT_PM7_UFF_ID_MERGE')
    src={'PM7':'pm7','Sprime_UFF':'uff_sprime'}[selections]
    for role in('TRAIN','VAL','TRAIN_UNSEEN_CONFORMATION'):
        rows=[dict(r)for r in db.execute('SELECT * FROM geometries WHERE role=? AND source=? AND rank IS NOT NULL ORDER BY mid,rank,gid',(role,src))]
        d=_index_document(rows,role,selections,group_mask,family_mask)
        if d is not None:
            indexes[role]=write(out/(role+'_index.json'),d);index_hash[role]=d['content_sha256'];index_sources[role]=selections
            role_headers[role]=write(out/(role+'_membership_header.json'),{
              'schema':'ACTUAL_PROVISIONAL_MODEL_ROLE_MEMBERSHIP_V1','version':VERSION,'role':role,
              'molecules':len(d['molecules']),'canonical_index_sha256':d['content_sha256'],
              'actual_source_index_reference':indexes[role],'D3_export_reference':inputs['D3_export_reference'],
              'diagnostic_supplement_reference':diagnostic_supplement_reference if role=='TRAIN_UNSEEN_CONFORMATION'else None})
    book=write(out/'channel_codebook.json',{'schema':'ACTUAL_R73_LITERAL_ENDPOINT_CHANNEL_CODEBOOK_V1','tokens':sorted(tokens),
      'source_D3_export_reference':inputs['D3_export_reference'],'no_channel_alias_or_spelling_normalization':True})
    need(not inputs.get('numeric_source_frames'),'NO_SOURCE_PROVEN_NUMERIC_R73_FRAME_IN_CURRENT_NONAXIAL_DELIVERY')
    bindings={};fields={f['field_key']:f for f in reg['fields']if f['status']=='enabled'}
    for tid,t in targets.items():
        f=fields[t['members'][0]['field_key']];definition=f['bounded_physical_definition'];frame0=f['reference_frame']
        fb={'target_id':tid,'condition':t['condition'],'unit':t['unit'],'sign':definition['sign_definition'],
          'frame':'SOURCE_DECLARED_NONAXIAL'if frame0 is None else json.dumps(frame0,sort_keys=True),
          'origin_policy':'SOURCE_DEFINITION_ONLY_NO_INVENTED_NUMERIC_ORIGIN','joint_policy':inputs['joint_contract_reference']}
        if t.get('wire_kind')=='SOURCE_ORDERED_RECORDS_V1':fb['source_frame_metadata']=cfg['registry_reference']
        bindings[tid]={'frame_binding':fb,'source_frame_metadata':cfg['registry_reference'],
          'source_definition':definition,'numeric_source_frame':None}
    db.close();catalog=reference(dbpath)
    if _NATIVE is not None:
        for handle in _NATIVE.HANDLES.values():handle.close()
        _NATIVE.HANDLES.clear()
    geometry_header=write(out/'local_geometry_binding.json',{
      'schema':'ACTUAL_PROVISIONAL_D3_LOCAL_GEOMETRY_BINDING_V1','local_io_receipt_reference':inputs['local_io_receipt_reference'],
      'catalog_reference':catalog,'D3_export_reference':inputs['D3_export_reference'],
      'diagnostic_supplement_reference':diagnostic_supplement_reference,'diagnostic_local_copy_reference':diagnostic_local_copy_reference,
      'node_local_root':str(root),'values_not_reencoded_in_this_header':True})
    result={'schema':'ACTUAL_PROVISIONAL_FAST55K_MODEL_BINDING_V1','version':VERSION,
      'inputs':inputs,'D3_export_reference':inputs['D3_export_reference'],'D4_delivery_reference':inputs['D4_normalization_reference'],
      'D5_delivery_reference':inputs['D5_delivery_reference'],'local_io_receipt_reference':inputs['local_io_receipt_reference'],
      'diagnostic_supplement_reference':diagnostic_supplement_reference,'diagnostic_local_copy_reference':diagnostic_local_copy_reference,
      'local_root':str(root),'catalog_reference':catalog,'stores':stores,'local_file_frames':frames,
      'targets':targets,'target_bindings':bindings,'target_policy_reference':cfg['target_policy_reference'],
      'model_registry_reference':registry_ref,'D4_projection_reference':d4_projection,
      'channel_codebook_reference':book,'reason_codebook_reference':inputs['reason_codebook_reference'],
      'indices':indexes,'role_index_sha256':index_hash,'index_sources':index_sources,'role_headers':role_headers,
      'geometry_binding_header_reference':geometry_header,
      'structural_binding':inputs['structural_binding'],'definition_components_preserved':146,
      'source_references':inputs['source_references'],'actual_parent_job_id':os.environ['SLURM_JOB_ID'],
      'no_QM_UFF_or_new_scientific_masks':True,'Model_payload_ACK':False}
    return write(out/'binding.json',result)
