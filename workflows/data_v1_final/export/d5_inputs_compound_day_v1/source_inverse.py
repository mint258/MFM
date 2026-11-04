"""Executed once inside the actual allocation, before scientific DATA."""
import ast,inspect
from workflows.data_v1_final.export.d5_inputs_builder_v1 import build as OB,reader as OR,verify as OV,prepare as OP,children as OH,contract as OC,geometry as G
from workflows.data_v1_final.export.d5_materialize_cpu_v1 import produce as Produce,readback as Readback
from . import contract as C,core,reader,verify,prepare,executor,resources,canonical_children


def text(f):return inspect.getsource(f).replace('\r\n','\n').strip()


def same(actual,original,name):
    C.need(actual==original,'FULL_INVERSE_SOURCE_BYTES:'+name)
    C.need(ast.dump(ast.parse(actual),include_attributes=False)==ast.dump(ast.parse(original),include_attributes=False),'FULL_INVERSE_AST:'+name)
    return {'name':name,'complete_function_bytes_equal':True,'complete_function_AST_equal':True}


def proof():
    evidence=[]
    v=text(core.molecule).replace('def molecule(task,declared,check,objects,reader):','def molecule(task,declared,check,objects):')
    v=v.replace('reader.','R.').replace('R.physical_row(physical,declared,check,atomic_numbers=numbers.tolist())','R.physical_row(physical,declared,check)')
    evidence.append(same(v,text(OB.molecule),'ordinary_molecule_explicit_reader_and_verified_native_Z_only'))
    v=text(reader.physical_row).replace('def physical_row(row,declared,check,*,atomic_numbers):','def physical_row(row,declared,check):')
    v=v.replace(",'SPRIME_HISTORICAL_ATTEMPT_IMPORTED_V3')",')')
    extra="""    result=verified_atom_view(result,row,atomic_numbers)
    if row.get('once_ledger_path') is not None and value['schema']=='SPRIME_HISTORICAL_ATTEMPT_IMPORTED_V3':
        from workflows.data_v1_final.conformers.formal_cpu_auto_v3.contract import KERNEL_SHA
        C.need(value['science_result_observed'] is True and value['execution_resolution']=='DURABLE_PACKAGE_VALIDATED'
            and value['seed']==row['seed'] and value['kernel_sha256']==KERNEL_SHA
            and C.reference(value['package_reference'])==ref and value['new_scientific_attempt'] is False and value['new_seed'] is False,
            'HISTORICAL_IMPORTED_REAL_PACKAGE_KERNEL_SEED_NOT_A_NEW_ATTEMPT')
"""
    C.need(v.count(extra)==1,'EXACT_ONLY_NEW_READER_PREDICATES');v=v.replace(extra,'')
    evidence.append(same(v,text(OR.physical_row),'strict_import_schema_and_native_Z_IO_view'))
    v=text(verify.run).replace('def run(plan,parent,common,out,budget,executor,io_context=I):\n    I=io_context','def run(plan,parent,common,out,budget):')
    v=v.replace('executor.map(source_order,work())','I.R.ordered_map(source_order,work(),budget)')
    evidence.append(same(v,text(OV.run),'complete_original_every_row_source_order_readback_explicit_pool_IO'))
    v=text(core.observed_call).replace('def observed_call(row,base,declared,check,objects,protocol,evidence):','def observed_call(row,base,declared,check,objects,protocol):')
    v=v.replace("for candidate in evidence.pair_rows(row['pairs_reference'],rid,declared,check):","for candidate in I.jsonl(row['pairs_reference'],declared,check):")
    new="""        for candidate in evidence.staging_rows(row['staging_reference'],rid,declared,check,pprime):
            if candidate['record_id']==rid:
                C.need(record is None,'ONE_ACTUAL_PPRIME_STAGING_RECORD');record=candidate
"""
    original=text(OH.observed_call);start=original.index("        with I.held(row['staging_reference']");end=original.index('        C.need(record is not None',start)
    C.need(v.count(new)==1,'EXACT_INDEXED_STAGING_IO_BLOCK');v=v.replace(new,original[start:end])
    evidence.append(same(v,original,'complete_actual_child_call_renderer_binding_math_only_indexed_IO'))
    v=text(prepare.run)
    pilot="""        if plan['purpose']=='pilot512':
            C.need(db.execute('SELECT count(*) FROM roster').fetchone()[0]>=512,'REAL512_WHOLE_COMMON_PILOT_NOT_REDUCED_COUNT')
            db.execute('DELETE FROM roster WHERE logical_ordinal>=512')
"""
    C.need(v.count(pilot)==1,'ONLY_EXPLICIT_PILOT512_ROSTER_BOUND');v=v.replace(pilot,'')
    start=v.index("                evidence=C.meta(plan['native_source_frame_review_reference'])");end=v.index('    source_files=',start)
    expected="""                evidence=C.meta(plan['native_source_frame_review_reference'])
                C.need(evidence['canonical_reference']==formal and evidence['prior_CPU13_validation_reference']==review['canonical_node13_source_validation_reference']
                    and (frame[1],frame[2],frame[3],frame[5])==(prior['inode'],formal['bytes'],prior['mtime_ns'],prior['uid'])
                    and evidence['whole_CPU_SHA_and_stable_current_device_required'] is True,
                    'ACTUAL_CPU_WHOLE_SHA_SAME_INODE_SIZE_MTIME_UID_LOCAL_DEVICE_NOT_FAKED_CPU13')
"""
    C.need(v[start:end]==expected,'EXACT_SHARED_SOURCE_FRAME_IO_SEAM')
    original=text(OP.run);oldstart=original.index('                C.need((frame[0]');oldend=original.index('    source_files=',oldstart)
    v=v[:start]+original[oldstart:oldend]+v[end:]
    evidence.append(same(v,original,'original_global_locator_preparation_only_node_frame_and_pilot_bound'))
    v=text(C.common_body).replace('def common_body(plan):','def common(plan):').replace('Bridge.common_parent','D.common_parent')
    evidence.append(same(v,text(OC.common),'original_ordinary_N_HOF_N1_policy_with_truthful_Common_day_parent_reader'))
    C.need(core.schemas is OB.schemas and core.encode is OB.encode and core.decode is OB.decode
        and reader.native_record is OR.native_record and reader.source_fd is OR.source_fd
        and reader.SOURCE_FRAMES is OR.SOURCE_FRAMES and reader.NATIVE_FRAMES is OR.NATIVE_FRAMES
        and verify.source_order is OV.source_order and verify.merge is OV.merge
        and executor.V.merge is OV.merge and executor.G.order_rows is G.order_rows,'ACTUAL_ORIGINAL_READER_ORDER_CODEC_VERIFY_OBJECTS')
    from workflows.data_v1_final.labels.normalization_compact_runtime_v2 import runtime as Clock
    from workflows.data_v1_final.execution.cpu_analysis_day_v1 import quota_provider as Provider
    C.need(resources.wall_clock is Clock.wall_clock and resources.remaining_wall is Clock.remaining_wall
        and resources.Provider.Client is Provider.Client,'NO_NEW_CLOCK_OR_QUOTA_PARSER')
    M,_,_,_,_=Produce.originals();C.need(Produce.run.__globals__['originals'] is Produce.originals
        and Readback.run.__globals__['check_semantics'] is Readback.check_semantics
        and M.selection.__code__.co_filename.endswith('/pipeline_v1/materialize.py'),'ORIGINAL_GUIDE_COUNTS_SELECTION_ANTI_JOIN_AND_READBACK')
    objects=OH.sources();pins=OC.source_check()
    C.need(objects[0].render_inputs.__code__.co_filename==pins['native_renderer']['path']
        and objects[0].perturb_seed.__code__.co_filename==pins['native_renderer']['path']
        and canonical_children.H.O.input_binding is OH.O.input_binding,'ORIGINAL_WP5_RENDER_SEED_AND_EXACT_BYTE_BINDING_OBJECTS')
    return {'status':'EXACT_COMPOUND_SOURCE_INVERSE_AND_ORIGINAL_OBJECTS','all_mechanical_inverses_bytes_AST_equal':True,
        'inverses':evidence,'new_IO_and_new_resource_code_not_claimed_byte_identical':True,
        'canonical_full_child_projection_uses_original_actual_hashes_renderer_seed_and_bundle':True,
        'original_selection_COUNTS_anti_join_and_projection_objects':True,'new_QM_UFF_calls':0,
        'one_actual_parent_no_internal_C0':True,'scientific_DATA_read_for_this_proof':False}
