"""Exact ordinary source rows to typed tables, original three orders, no UFF/QM."""
from __future__ import annotations
import hashlib,json,math,os,pathlib,struct,traceback
from . import contract as C,io as I,reader as R,geometry as G
OBJECTS=None


def schemas():
    import pyarrow as pa
    fields=[(k,pa.int64() if k=='sprime_conf_idx' else pa.string()) for k in C.D.COLUMNS['geometries']]
    for name in ('native_anchor_record_id','source_path','source_sha256','source_format','source_member','atom_order_sha256',
        'geometry_sha256','identity_namespace','task_key','once_ledger_path','once_ledger_sha256','source_provenance_json',
        'energy_source','actual_input_bundle_sha256','actual_protocol_sha256','actual_input_origin'):
        fields.append((name,pa.large_string() if name=='source_provenance_json' else pa.string()))
    for name in ('source_bytes','source_row_index','original_sprime_conf_idx','kernel_sprime_conf_idx','seed','candidate_id',
        'source_conformer_id','source_attempt_max_sprime_conf_idx','original_N','once_ledger_bytes'):
        fields.append((name,pa.int64()))
    fields += [('order_energy',pa.float64()),('atomic_numbers',pa.large_list(pa.int16())),('positions_A',pa.large_list(pa.list_(pa.float64(),3)))]
    return {'geometries':pa.schema(fields),
        'orders':pa.schema([(k,pa.int64() if k=='rank' else pa.string()) for k in ('molecule_id','geometry_source','order_type','method','rank','geometry_id')]),
        'atom_counts':pa.schema([('geometry_id',pa.string()),('n_atoms',pa.int64())]),
        'audit_identity':pa.schema([('molecule_id',pa.string()),('geometry_id',pa.string()),('physical_identity_json',pa.string())]),
        'roster':pa.schema([('logical_ordinal',pa.int64()),('molecule_id',pa.string()),('PM7_N',pa.int64()),('UFF_N',pa.int64()),('child_count',pa.int64())])}


def encode(value):
    from workflows.data_v1_final.labels.lossless_projection_pilot_v1.projection import encode as E,decode,signature
    tree,floats=E(value);C.need(signature(decode(tree,floats))==signature(value),'ORIGINAL_FULL_LOSSLESS_TREE_CODEC')
    raw=(json.dumps({'schema':'D5_INPUTS_LOSSLESS_MOLECULE_V1','tree':tree,'f64_le':[struct.pack('<d',v).hex() for v in floats],
        'signature':signature(value)},ensure_ascii=False,allow_nan=False)+'\n').encode()
    C.need(len(raw)<=I.ROW_CAP,'COMPLETE_MOLECULE_PACKET_SOFTWARE_CAP_NO_TRUNCATION');return raw


def decode(raw):
    from workflows.data_v1_final.labels.lossless_projection_pilot_v1.projection import decode as D,signature
    v=json.loads(raw);C.need(v['schema']=='D5_INPUTS_LOSSLESS_MOLECULE_V1','EXACT_NEW_LOSSLESS_PACKET')
    floats=[struct.unpack('<d',bytes.fromhex(v))[0] for v in v['f64_le']];result=D(v['tree'],floats)
    C.need(signature(result)==v['signature'],'FULL_F64_BITS_TYPES_SIGNATURE');return result


def molecule(task,declared,check,objects):
    native,science,common=objects;mid=task['molecule_id'];by={r['native_record_id']:r for r in task['ordinary_physical_rows'] if r['geometry_source']=='pm7'}
    hof,observations=R.hof_values(task,declared,check);bases=[];errors=[];mol=numbers=graph=None;producer_orders=[]
    for pointer in task['records']:
        check();other,z,xyz=R.native_record(pointer,native);sig=native.ordered_graph(other)
        if mol is None:mol,numbers,graph=other,z,sig
        import numpy as np
        C.need(np.array_equal(numbers,z) and graph==sig,'ORIGINAL_SOURCE_ATOM_ORDER_AND_GRAPH_ACROSS_ALL_PM7')
        rid=pointer['record_id'];row=dict(by[rid]);G.physical_key(row);value=hof.get(rid)
        if value is None or value['valid'] is not True:
            errors.append({'record_id':rid,'state':'UNKNOWN_CANONICAL_HOF','original_reason':value.get('reason') if value else 'CANONICAL_CELL_MISSING'})
            energy=None
        else:
            from workflows.data_v1_final.conformers.pm7_independent_cache32_v1.contract import validate_hof
            validate_hof(value);energy=float(value['value_kcal_mol'])
        row.update(parent_geometry_id=None,view_id=None,positions_A=xyz.tolist(),atomic_numbers=z.tolist(),
            geometry_sha256=common.geometry_sha(z,xyz),atom_order_sha256=hashlib.sha256(z.astype('<i8').tobytes()).hexdigest(),
            source_row_index=pointer['real_index'],source_bytes=None,source_sha256=None,order_energy=energy,
            energy_source='CANONICAL_PM7_B_REGISTRY60_KCAL_MOL',source_provenance_json=json.dumps(pointer,sort_keys=True),
            actual_input_origin='ORIGINAL_LMDB_RECORD_PER_PAYLOAD_SHA_NOT_RECONSTRUCTION')
        bases.append(row)
    C.need(mol is not None and len(bases)==task['expected_PM7_N'],'ALL_REAL_PM7_BASES_PRESERVED')
    for physical in task['ordinary_physical_rows']:
        if physical['geometry_source']!='uff_sprime':continue
        check();value,packet=R.physical_row(physical,declared,check);row=dict(physical);G.physical_key(row)
        C.need(value['atomic_numbers']==numbers.tolist(),'ORIGINAL_UFF_NATIVE_ATOM_SEQUENCE_EQUALS_FIXED_SOURCE_GRAPH')
        xyz=value['coordinates'];geo=common.geometry_sha(numbers,xyz)
        C.need(hashlib.sha256(numbers.astype('<i8').tobytes()).hexdigest()==value['atom_order_sha256']
            and (not value.get('geometry_sha256') or geo==value['geometry_sha256']), 'ACTUAL_UFF_F64_COORDINATES_ATOM_SHA')
        energy=float(value['uff_energy_kcal_mol']);C.need(math.isfinite(energy),'ACTUAL_FINITE_UFF_ENERGY_NO_NATIVE_PM7_FALLBACK')
        if value.get('origin') in ('data_v1_fill_10N','data_v1_fill_retry1'):
            C.need(value['seed']==science.seed_for(mid,value['origin']=='data_v1_fill_retry1'),'ORIGINAL_SEED_FOR_GENERATED_EVENT')
        row.update(parent_geometry_id=None,view_id=None,native_record_id=None,positions_A=xyz,atomic_numbers=numbers.tolist(),
            geometry_sha256=geo,atom_order_sha256=value['atom_order_sha256'],order_energy=energy,energy_source='ACTUAL_UFF_KCAL_MOL',
            source_provenance_json=json.dumps(physical,sort_keys=True),actual_input_origin='ACTUAL_ORDINARY_SOURCE_ROW_NOT_N1_EXTRA')
        bases.append(row)
        if packet is not None:producer_orders.append({'source_reference':C.reference({'path':physical['source_path'],'bytes':physical['source_bytes'],'sha256':physical['source_sha256']}),
            'native_orders':packet.get('orders'),'native_kernel_rank_not_promoted_to_physical_random_identity':True})
    C.need(len({G.physical_key(r) for r in bases})==len(bases),'DISTINCT_REAL_TWO_SOURCE_PHYSICAL_IDENTITIES')
    orders=G.order_rows(mid,bases,mol,native,check) if not errors else []
    # Closure of cached original native handles uses the original file frame,
    # not a newly invented whole-LMDB SHA requirement.
    for path,frame in R.NATIVE_FRAMES.items():C.need(I.R.frame(pathlib.Path(path).lstat())==frame,'ALL_NATIVE_RECORD_FILE_FRAMES_STILL_STABLE')
    for path,(_,frame) in R.SOURCE_FRAMES.items():C.need(I.R.frame(pathlib.Path(path).lstat())==frame,'ALL_HASHED_ORDINARY_SOURCE_FRAMES_STILL_STABLE')
    identities=[]
    for row in bases:
        if row['geometry_source']!='uff_sprime':continue
        ns=row['identity_namespace'];C.need(ns in ('accepted_original_sprime','data_v1_fill'),'REAL_ORDINARY_AUDIT_NAMESPACE_NO_N1_EXTRA')
        identity={'namespace':ns,'source_conformer_id':row['source_conformer_id']} if ns=='accepted_original_sprime' else {
            'namespace':ns,'task_key':row['task_key'],'seed':row['seed'],'candidate_id':row['candidate_id']}
        identities.append({'molecule_id':mid,'geometry_id':row['geometry_id'],'physical_identity_json':json.dumps(identity,sort_keys=True,separators=(',',':'))})
    return {'schema':'D5_ORDINARY_MOLECULE_SOURCE_OBSERVATION_V1','molecule_id':mid,'logical_ordinal':task['logical_ordinal'],
        'bases':bases,'orders':orders,'atom_counts':[{'geometry_id':r['geometry_id'],'n_atoms':len(r['atomic_numbers'])} for r in bases],
        'canonical_HOF_observations':observations,'canonical_HOF_values':hof,'producer_native_order_provenance':producer_orders,
        'audit_identity':identities,
        'errors':errors,'status':'COMPLETE_BASE_AND_ORIGINAL_ORDERS' if not errors else 'UNKNOWN_HOLD_ALL_GEOMETRIES_RETAINED',
        'WHOLE_LMDB_SHA_NOT_ORIGINALLY_AVAILABLE_NOT_CLAIMED':True,'new_QM_UFF_calls':0,'D5_jointly_frozen':False}


def worker(work):
    global OBJECTS
    task,declared,out,control=work;I.worker_check(control)
    if OBJECTS is None:OBJECTS=G.originals(initialize=True)
    check=lambda:I.worker_check(control)
    try:value=molecule(task,declared,check,OBJECTS)
    except Exception as exc:
        value={'molecule_id':task['molecule_id'],'logical_ordinal':task['logical_ordinal'],'bases':[],'orders':[],'atom_counts':[],'audit_identity':[],
            'status':'UNKNOWN_HOLD_SOURCE_VALIDATION_EXCEPTION','errors':[{'type':type(exc).__name__,'error':str(exc),'traceback':traceback.format_exc()}],
            'actual_descriptor':task,'original_DATA_retained':True,'new_QM_UFF_calls':0}
    raw=encode(value);I.worker_check(control,len(raw));path=pathlib.Path(out)/('molecule_%08d.lossless.json'%task['logical_ordinal'])
    with path.open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
    return {'reference':I.actual_ref(path),'logical_ordinal':task['logical_ordinal'],'held':value['status']!='COMPLETE_BASE_AND_ORIGINAL_ORDERS','pid':os.getpid()}


def run(plan,range_meta,out,budget):
    descriptors=I.jsonl(range_meta['descriptor_reference'],plan['data_references'],budget.check)
    workers=out/'workers';workers.mkdir();reports=[]
    tasks=((task,plan['data_references'],str(workers),budget.control) for task in descriptors)
    for report in I.R.ordered_map(worker,tasks,budget):reports.append(report)
    lo,hi=plan['logical_range'];C.need([r['logical_ordinal'] for r in reports]==list(range(lo,hi)),'EVERY_FROZEN_MOLECULE_ORDINAL_COMPLETED_OR_HELD')
    declared=[r['reference'] for r in reports];schemas0=schemas();held=sum(r['held'] for r in reports)
    def values(kind):
        for report in reports:
            v=decode(I.body(report['reference'],declared,budget.check,I.ROW_CAP))
            if kind=='roster':yield {'logical_ordinal':v['logical_ordinal'],'molecule_id':v['molecule_id'],
                'PM7_N':sum(r['geometry_source']=='pm7' for r in v['bases']),'UFF_N':sum(r['geometry_source']=='uff_sprime' for r in v['bases']),'child_count':0}
            else:yield from v['bases' if kind=='geometries' else kind]
    tables={k:I.parquet_rows(out/(k+'.parquet'),values(k),schema,budget) for k,schema in schemas0.items()}
    return {'table_references':tables,'logical_range':[lo,hi],'molecules':hi-lo,'held_molecules':held,
        'table_domain':'BASE_ONLY','worker_packet_references':declared,'effective_worker_pids':sorted({r['pid'] for r in reports}),
        'all_actual_children_closed':False,'WHOLE_LMDB_SHA_NOT_ORIGINALLY_AVAILABLE_NOT_CLAIMED':True,
        'full_typed_source_order_identity_parity':False}
