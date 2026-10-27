"""CPU B: original raw reader, pure renderer/SCF/array gates and 500 comparisons.

No lifecycle initializer, native invocation, copied chemistry formula, or changed
parser global is used. Inline-only native enrichment is explicitly not replayed.
"""
from __future__ import annotations
import copy,hashlib,importlib,importlib.util,pathlib,sqlite3,sys
from urllib.parse import quote
from workflows.data_v1_final.pprime.causal15_main_v1 import render as T
from workflows.data_v1_final.pprime.causal15_main_v1.prepare import raw_reader
from workflows.data_v1_final.pprime.strict_numerics15_qa_v1.prepare import targets
from workflows.data_v1_final.pprime.strict_numerics20_qa_v1 import analysis as A,io as W
from . import contract as C,io as I,checks as K
WP5=C.ROOT.parent/'phase1_wp5_20261011/scripts'

def originals():
    for path in (WP5,C.REPO/'workflows/data_v1_final/pprime/vector_audit'):
        if str(path) not in sys.path:sys.path.insert(0,str(path))
    engine=importlib.import_module('wp5_engine_v3');wire=importlib.import_module('wp5_parquet_v2')
    parse=importlib.import_module('read_outputs_v1').parse_outputs
    C.need(pathlib.Path(engine.__file__)==WP5/'wp5_engine_v3.py' and engine.CONFIG is None and engine.NATIVE is None
        and engine.WORK is None,'IMPORT_ONLY_NO_ENGINE_INITIALIZATION_OR_NATIVE')
    C.need(pathlib.Path(wire.__file__)==WP5/'wp5_parquet_v2.py' and pathlib.Path(sys.modules[parse.__module__].__file__)
        ==C.REPO/'workflows/data_v1_final/pprime/vector_audit/read_outputs_v1.py','EXACT_ORIGINAL_READER_CODEC_MODULES')
    Parent=raw_reader()
    class Immutable(Parent):
        """Storage constructor only. Original get/close objects are inherited."""
        def __init__(self,path,archive,max_raw,max_meta):
            self.path=pathlib.Path(path);self.archive=archive;self.max_raw_bytes=max_raw;self.max_metadata_bytes=max_meta;self.max_frame_bytes=max_raw+(1<<20)
            self.db=sqlite3.connect('file:'+quote(str(self.path),safe='/')+'?mode=ro&immutable=1',uri=True)
            self.db.execute('PRAGMA query_only=ON');self.db.execute('BEGIN')
    C.need(Immutable.get is Parent.get and Immutable.close is Parent.close,'ORIGINAL_BOUNDED_READER_METHOD_OBJECTS')
    return engine,wire,parse,Immutable

def digest(value):
    # Storage digest only. Exact scientific comparisons use the frozen codec.
    from workflows.data_v1_final.pprime.common import staging_bytes
    return hashlib.sha256(staging_bytes(value)).hexdigest()

def one(entry,plan,ep,roots,declared,old,new,objects,check):
    engine,wire,parse,Reader=objects;check();row=entry['row'];qa=row['qa_id']
    with I.held(entry['task_reference'],roots,declared):task=W.task(entry['task_reference'],row,ep)
    record=I.value(entry['result_reference'],roots,declared);claim=I.value(entry['claim_reference'],roots,declared,1<<20)
    terminal=I.value(entry['terminal_reference'],roots,declared,1<<20);K.identity(row,task,record,claim,ep)
    C.need(terminal['qa_id']==qa and terminal['result_reference']==entry['result_reference'] and terminal['closed25M_role_eligible'] is True
        and terminal['call_technical_readback_complete'] is True and terminal['native_return_observed'] is True,'ORIGINAL_TERMINAL_STILL_EXACT')
    inputs={pathlib.Path(r['path']).name:I.body(r,roots,declared,C.E.O.INPUT_CAP) for r in task['target_input_references']}
    old_inputs={pathlib.Path(r['path']).name:I.body(r,roots,declared,C.E.O.INPUT_CAP) for r in task['original_target_input_references']}
    post={pathlib.Path(r['path']).name:I.body(r,roots,declared,C.E.O.INPUT_CAP) for r in record['actual_postcall_input_references']}
    K.exact(inputs,post,wire)
    native,seed,after,rendered=targets(task,old_inputs,old,new,engine)
    K.exact(after,task['candidate_task'],wire);K.exact(rendered,inputs,wire)
    K.exact(native['coords'].tolist(),task['native_coordinates_A'],wire);K.exact(seed,task['seed'],wire)
    case=copy.deepcopy(task['case']);case.update(native_coordinates_A=native['coords'].tolist(),actual_rendered_coordinates_A=T.arrays(inputs,task['case']['symbols']).tolist())
    K.exact(case,record['case'],wire);K.exact(record['rotation_matrix'],task['case']['rotation_matrix'],wire)
    hashes=[{'name':name,'sha256':hashlib.sha256(body).hexdigest()} for name,body in sorted(inputs.items())]
    members=[{'name':name,'data':body,'role':'input','sha256':hashlib.sha256(body).hexdigest(),'byte_count':len(body)} for name,body in sorted(inputs.items())]
    bundle_sha=hashlib.sha256(engine.OUTPUT_ARCHIVE.bundle(members)[0]).hexdigest()
    intent=I.value(record['invoke_intent_reference'],roots,declared,1<<20);start=I.value(record['worker_start_reference'],roots,declared,1<<20)
    C.need(intent['qa_id']==start['qa_id']==qa and intent['job_id']==start['job_id']==C.JOB and start['uid']==1278
        and intent['state']=='DURABLE_INTENT_NOT_NATIVE_RETURN' and intent['timeout_seconds']==900
        and intent['original_record_id']==task['case']['row']['record_id'] and intent['seed']==seed
        and start['claim_reference']==entry['claim_reference'] and start['task_reference']==entry['task_reference'],
        'EXACT_WORKER_START_INTENT_AND_SEED_NOT_POPEN_PROOF')
    C.need(start['boot_id']==claim['boot_id'] and claim['startup_proof_reference']==C.meta(plan['actual_root_review_reference'])['startup_proof_reference'],
        'WORKER_START_CLAIM_AND_REAL_ORIGINAL_PROOF_BOOT_PARITY')
    for key in ('candidate_protocol_reference','prepared20_reference','user_decision_reference'):K.exact(intent[key],ep[key],wire)
    K.exact(intent['input_file_sha256'],hashes,wire);K.exact(intent['input_bundle_sha256'],bundle_sha,wire)
    raw=record['raw_reference'];dbref=C.triple(record['closed_raw_container_reference']);db=pathlib.Path(dbref['path'])
    eid='strict-new20:'+ep['candidate_protocol_reference']['sha256']+':'+C.JOB+':'+qa
    C.need(raw['container_path']==str(db) and raw['record_id']==task['case']['row']['record_id']
        and raw['calc_type']==task['condition'] and raw['execution_id']==eid and raw['output_retained'] is True
        and raw['raw_call_durable'] is True and raw['input_bodies_saved'] is False
        and not any(pathlib.Path(str(db)+s).exists() for s in ('-wal','-shm','-journal')),'EXACT_RAW_CALL_KEY_AND_CLOSED_CONTAINER')
    with I.held(dbref,roots,declared) as (f,_):
        # SQLite opens the already-hashed inode through this live FD, rather
        # than resolving the external filename a second time.
        reader=Reader('/proc/self/fd/'+str(f.fileno()),engine.OUTPUT_ARCHIVE,C.E.O.RAW_CAP,C.E.O.RESULT_CAP)
        try:
            C.need(reader.db.execute('PRAGMA integrity_check').fetchall()==[('ok',)]
                and reader.db.execute('SELECT count(*) FROM raw').fetchone()==(1,),'EXACT_ONE_INTEGRAL_ORIGINAL_RAW_ROW')
            retained=reader.get(raw['record_id'],raw['calc_type'],raw['execution_id'],raw['raw_sha256'],raw['raw_bytes'])
        finally:reader.close()
    metadata=retained['metadata'];files=retained['output_files'];parsed=record['parsed_wp5_result'];native_observation=record['original_native_result_observation']
    C.need(metadata['record_id']==raw['record_id'] and metadata['molecule_id']==task['molecule_id']
        and metadata['calc_type']==task['condition'] and metadata['execution_id']==eid
        and metadata['source_payload_sha256']==task['case']['row']['record_payload_sha256']
        and metadata['software']['version']==new['expected_versions'][task['candidate_task']['family']]
        and metadata['input_bodies_saved'] is False,'ORIGINAL_RAW_SOURCE_RECORD_SOFTWARE_AND_EXECUTION_LINEAGE')
    K.exact(metadata['input_file_sha256'],hashes,wire);K.exact(metadata['input_bundle_sha256'],bundle_sha,wire)
    keywords=task['candidate_task'].get('keywords',task['candidate_task'].get('args'))
    if task['candidate_task']['family']=='mopac':keywords+=' THREADS=1'
    K.exact(metadata['keywords'],keywords,wire);K.exact(metadata['keywordSHA'],engine.stable_sha(keywords),wire)
    raw_view=parse(files,task['condition'],task['case']['symbols'])
    K.exact(raw_view,record['independent_raw_readback'],wire)
    K.exact(native_observation.get('values'),parsed.get('values'),wire)
    issues=engine.validate_atomic_arrays(native_observation,native['z']);K.exact(issues,parsed['atomic_array_validation'],wire)
    expected_status=engine.canonical_status('PROPERTY_FAILED' if issues and native_observation['status']=='SUCCESS' else native_observation['status'])
    K.exact(parsed['source_status'],native_observation['status'],wire);K.exact(parsed['status'],expected_status,wire);K.exact(parsed['scope_status'],expected_status,wire)
    scf=engine.extract_scf(task['condition'],files,parsed.get('values'),parsed['status'],parsed['source_status'])
    for field,source in (('scf_iterations','scf_iterations'),('converged','converged'),('scf_iteration_definition','iteration_definition'),('scf_missing_reason','missing_reason')):
        K.exact(parsed['provenance'][field],scf[source],wire)
    for key in ('source_status','scope_status'):K.exact(metadata[key],parsed[key],wire)
    for key in ('scf_iterations','converged','software_version_id','input_file_sha256','input_bundle_sha256'):
        K.exact(metadata[key],parsed['provenance'][key],wire)
    # Original analysis receives the independently reread raw view, never a new
    # native return state or invented inline parser/enrichment result.
    independent=copy.deepcopy(record);independent['independent_raw_readback']=raw_view
    return independent,{'qa_id':qa,'task_reference':entry['task_reference'],'result_reference':entry['result_reference'],
        'raw_reference':dbref,'input_and_raw_lineage_exact':True,'original_raw_parser_exact':True,'original_atomic_array_and_SCF_exact':True,
        'native_values_to_enriched_values_float64_exact':True,'native_values_typed_sha256':digest(native_observation.get('values')),
        'inline_native_shell_Mulliken_task_projection_and_return_processing':'PRESERVED_ORIGINAL_OBSERVATION_NOT_INDEPENDENTLY_REPLAYED',
        'r73_channel_onsite_list_order_preserved':True,'r674_six_components_not_projected_or_reordered':True,
        'independent_native_process_count_proved':False,'unit_sign_basis_axes_or_SCF_cause_accepted':False}

def produce(plan,parent,out,store,check):
    review,ep,declared,_,prepare_root,g=parent;roots=[C.ACTUAL,prepare_root,C.E.LEDGER,pathlib.Path(g['descriptor_reference']['path']).parent,C.audit_ref()['path']]
    descriptor=I.value(g['descriptor_reference'],roots,declared)
    C.need(descriptor['schema']=='STRICT20_READBACK_GROUP_DESCRIPTOR_V1' and descriptor['group_index']==plan['group_index']
        and len(descriptor['rows'])==60 and all(K.qa_cell(r['qa_id'])[0]==plan['group_index'] for r in descriptor['rows']),
        'EXACT_FROZEN_GROUP_DESCRIPTOR')
    analysis=I.value(descriptor['original_analysis_reference'],roots,declared);old_own,old_pairs=K.index_analysis(analysis)
    config=I.value(C.audit_ref(),roots,declared,2<<20);objects=originals();engine,wire,_,_=objects
    K.exact(analysis['original_predeclared_tolerances'],{k:config[k] for k in ('coordinate_atol_A','vector_tolerances','rendered_coordinate_atol_A','same_geometry_dipole_atol_au')},wire)
    old,new,diff=C.E.P.S.protocol(ep);checks=[];own=[];pairs=[];errors=[];completed=0;cache={};threads=set()
    # Twelve independent task groups, each five arms. At most five full records
    # remain in the cache; immutable file reads and raw BLOBs are not shared.
    for entry in sorted(descriptor['rows'],key=lambda r:r['qa_id']):
        check()
        try:
            record,evidence=one(entry,plan,ep,roots,declared,old,new,objects,check)
            qa=record['qa_id'];value,_=A.own(record,config);K.exact(value,old_own[qa],wire)
            C.need(value['defined_QC_pass'] is True,'ORIGINAL_OWN_DEFINED_GATE_PASS_NOT_NEW_SEMANTICS')
            checks.append(evidence);own.append(value);completed+=1;cache[record['arm']]=record
            if len(cache)==5:
                group=A.completed_group(list(cache.values()),config)
                C.need(len(group)==5,'EXACT_ORIGINAL5_PAIRS_PER_CONDITION')
                for comparison in group:
                    K.exact(comparison,old_pairs[K.expected_key(comparison)],wire)
                    C.need(comparison['defined_QC_pass'] is True,'ORIGINAL_VECTOR_GATES_WITHOUT_NEW_TOLERANCES');pairs.append(comparison)
                cache.clear()
        except Exception as exc:
            import traceback
            failure=store.json(out/(entry['qa_id']+'.failure.DATA.json'),{'qa_id':entry['qa_id'],'locators':entry,'error_type':type(exc).__name__,
                'message':str(exc),'traceback':traceback.format_exc(),'state':'READBACK_HOLD_NOT_NEW_CHEMICAL_FAILURE'},failure=True)
            errors.append({'qa_id':entry['qa_id'],'failure_DATA_reference':failure});cache.clear()
    C.need(engine.CONFIG is None and engine.NATIVE is None and engine.WORK is None,'ENGINE_STILL_NEVER_INITIALIZED_OR_INVOKED')
    vectors=sum(len(r['defined_vector_checks']) for r in pairs)
    evidence=store.json(out/'exact_readback_checks.DATA.json',{'schema':'STRICT20_READBACK_EXACT_GROUP_EVIDENCE_V1','group_index':plan['group_index'],
        'calls':checks,'original_own_call_checks':own,'original_pair_checks':pairs,'protocol_three_diff':diff,
        'all_old_numeric_DATA_retained':True,'native_inline_processing_independently_replayed':False,'new_tolerances_or_masks':False})
    matrix=[]
    for condition in C.E.P.TASKS:
        selected=[r for r in own if r['condition']==condition];matrix.append({'condition':condition,'arms':{arm:sum(r['arm']==arm for r in selected) for arm in C.E.P.ARMS},
            'own_exact':len(selected),'pair_exact':sum(r['condition']==condition for r in pairs),
            'original_vector_comparisons_exact':sum(len(r['defined_vector_checks']) for r in pairs if r['condition']==condition)})
    return {'group_index':plan['group_index'],'completed_calls':completed,'held_calls':60-completed,'original_own_exact_checks':len(own),
        'original_pair_exact_checks':len(pairs),'original_vector_exact_comparisons':vectors,'condition_arm_matrix':matrix,
        'evidence_DATA_reference':evidence,'errors':errors,'all60_and25_exact':completed==60 and not errors and len(pairs)==60 and vectors==25,
        'inline_native_processing_independently_replayed':False,'native_initialize_or_invoke_calls':0}
