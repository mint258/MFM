"""Only original defined vector gates and WP5 states; other semantics UNKNOWN."""
from . import contract as C
PAIRS=(('B1','B2'),('B1','R1'),('B1','P1'),('P1','P2'),('B1','P2'))
FIELDS={'pm7_B':{'pm7_dipole_Debye','pm7_gradient_kcal_mol_A'},'xtb_singlepoint':{'xtb_dipole_Debye'},
    'xtb_perturbed_gradient':{'xtb_dipole_Debye','xtb_gradient_Eh_bohr'}}
def measurement(record,config):
    from evaluate_v1 import measurement as original
    return original(record,config)
def own(record,config):
    expected=FIELDS.get(record['condition'],set());parsed=record.get('parsed_wp5_result',{})
    checks={'native_return_observed':record.get('native_invoke_function_return_observed') is True,
        'original_WP5_scope_SUCCESS':parsed.get('scope_status')=='SUCCESS','original_atomic_array_QC':parsed.get('atomic_array_validation')==[],
        'actual_input_matches':bool(record.get('actual_postcall_input_references')) and all(v.get('matches_prepared_bytes') is True for v in record.get('actual_postcall_input_references',[])),
        'closed_whole_SHA_and_bounded_raw_readback':bool(record.get('closed_raw_container_reference')) and record.get('raw_readback_source')=='CLOSED_SQLITE_GZIP_EOF_CRC_WHOLE_AND_MEMBER_SHA_ORIGINAL_UNBUNDLE',
        'no_wrapper_or_close_errors':not any(record.get(k) for k in ('error','raw_close_error','engine_close_error'))}
    unknown=['UNTESTED_BASIS_TENSOR_OR_OTHER_PROPERTY_AXIS_SEMANTICS_UNKNOWN']
    measured=None
    if expected:
        measured=measurement(record,config);checks['original_defined_vectors_present']=expected<=set(measured['vectors'])
        checks['original_available_stored_raw_fields_match']=bool(measured['stored_raw_checks']) and all(v['pass'] for v in measured['stored_raw_checks'].values())
        if record['condition'] in ('pm7_B','xtb_perturbed_gradient'):
            checks['own_output_coordinates_and_atom_order']=measured['coordinates']['supports_input_axes'] and measured['coordinates'].get('atom_order_matches') is True
        else:unknown.append('XTB_SINGLEPOINT_NO_INDEPENDENT_OUTPUT_COORDINATE_BLOCK_DO_NOT_CLAIM_AXIS_PASS')
        if record['condition']=='xtb_perturbed_gradient':checks['original_force_relation']=measured.get('force_relation',{}).get('pass') is True
    else:unknown.append('NO_NEW_VECTOR_OR_TENSOR_TOLERANCE_DEFINED_FOR_THIS_TASK')
    return {'qa_id':record['qa_id'],'molecule_id':record['molecule_id'],'condition':record['condition'],'arm':record['arm'],
        'checks':checks,'defined_QC_pass':all(checks.values()),'interpretation_UNKNOWN':unknown,
        'SCF_converged_original_metadata':parsed.get('provenance',{}).get('converged'),'SCF_UNKNOWN_not_backfilled_from_SUCCESS':True},measured
def pair(left,right,config):
    import numpy as np
    from math_v1 import covariance
    C.Q.need(left['molecule_id']==right['molecule_id'] and left['condition']==right['condition'],'PAIR_SAME_MID_AND_TASK')
    a,ma=own(left,config);b,mb=own(right,config);fields=FIELDS.get(left['condition'],set());checks={}
    if fields and ma and mb:
        rotation=np.eye(3).tolist() if (left['arm'],right['arm']) in {('B1','B2'),('P1','P2')} else right['rotation_matrix']
        for name in sorted(fields & set(ma['vectors']) & set(mb['vectors'])):
            x,y=ma['vectors'][name],mb['vectors'][name]
            checks[name]=covariance(x['values'],y['values'],x['rounding_halfwidth'],y['rounding_halfwidth'],config['vector_tolerances'][name],rotation)
    passed=a['defined_QC_pass'] and b['defined_QC_pass'] and (not fields or set(checks)==fields and all(v['pass'] for v in checks.values()))
    return {'molecule_id':left['molecule_id'],'condition':left['condition'],'arms':[left['arm'],right['arm']],
        'defined_vector_checks':checks,'defined_QC_pass':passed,'unsupported_axes_basis_tensors_certified':False}
def completed_group(records,config):
    by={r['arm']:r for r in records};C.Q.need(len(by)==len(records),'UNIQUE_ARM_PER_MID_TASK')
    return [pair(by[a],by[b],config) for a,b in PAIRS if a in by and b in by]
