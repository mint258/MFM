"""Source proof only, no fixture/SCI/environment initialization."""
import ast,pathlib
from . import contract as C


def proof():
    from workflows.data_v1_final.conformers.n1_pprime2_source_full_v1 import core
    from . import science_port as port
    here=pathlib.Path(__file__).parent;actual=C.ref(port.__file__)
    C.need((actual['bytes'],actual['sha256'])==C.N1_PORT,'EXACT_EXISTING_SCIENCE_PORT_FULL_FILE')
    original=C.ref(core.__file__);C.need((original['bytes'],original['sha256'])==C.N1_CORE,'EXACT_ORIGINAL_N1_CORE')
    old=pathlib.Path(core.__file__).read_text();new=pathlib.Path(port.__file__).read_text()
    old=old[old.index('def process_task(task):'):].rstrip();new=new[new.index('def process_task(task):'):].rstrip()
    needle="'original_sprime_conf_idx':task.get('baseline_physical_idx',old['sprime_conf_idx'])"
    C.need(new.count(needle)==1 and new.replace(needle,"'original_sprime_conf_idx':0")==old,'FULL_ORIGINAL_NUMERICAL_BODY_INVERSE')
    C.need(port._embedding is core._embedding and port._add_conformer is core._add_conformer and port._raw_number is core._raw_number
        and C.select_real_second is C.O.select_real_second and C.expanded_orders is C.O.expanded_orders
        and C.validate_task is C.O.validate_task,'DIRECT_ORIGINAL_HELPER_AND_SELECTION_OBJECTS')
    return {'original_core_reference':original,'exact_science_port_reference':actual,'full_body_inverse':True,
        'original_function_objects':True,'new_UFF_QM_calls':0,'fixtures_or_software_controls_run':0}


def existing_environment(review,legacy_reference):
    legacy=C.load(legacy_reference);rows=legacy['science_sources']
    C.need(len(rows)==7 and {r['basename'] for r in rows}==set(C.SCIENCE7),'EXACT_EXISTING_SEVEN_SOURCE_SET')
    for row in rows:
        old,new=row['origin_reference'],row['target_locator'];C.need((old['bytes'],old['sha256'])==(new['bytes'],new['sha256'])==C.SCIENCE7[row['basename']],'UNCHANGED_SEVEN_ORIGINAL_SOURCE_BYTES');C.verify(new,2<<20)
    C.need(review['reviewer']=='root' and review['status']=='APPROVED_EXISTING_CONTROL16_F64_COMPATIBILITY_FOR_REMAINING'
        and review['original_seven_source_bytes_identical']is True and review['all16_scientific_sha_exact']is True
        and review['torch_build_identical_claimed']is False,'EXPLICIT_DIFFERENT_BUILD_ACCEPTANCE_NOT_A_NEW_N1_SOFTWARE_CONTROL')
    refs=review['existing_control16_by_endpoint']['alpha'];receipt=C.load(refs['receipt']);readback=C.load(refs['readback'])
    C.need(receipt['job_id']=='1884766' and receipt['uid']==1264 and not receipt['errors'] and len(receipt['executions'])==16
        and all(r['main_golden_exact_match']is True for r in receipt['executions']) and receipt['deployment_map_reference']==legacy_reference
        and receipt['actual_target_scientific_sources_verified_byte_identical']is True,'ACTUAL_EXISTING_CONTROL16_NOT_REPLAYED')
    C.need(readback['readback_uid']==1264 and readback['controls']==16 and len(readback['verified_controls'])==16
        and readback['quality_gates_changed_or_waived']is False,'EXISTING_INDEPENDENT_F64_READBACK')
    return legacy,{'existing_control16_receipt_reference':refs['receipt'],'existing_readback_reference':refs['readback'],
        'new_controls_run':0,'N1_cross_build_numerical_control_claimed':False,'same_original_N1_Source_proof_is_separate':True}
