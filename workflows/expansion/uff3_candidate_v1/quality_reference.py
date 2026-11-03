"""Metadata-only projection of existing closed D4 TRAIN medians/MADs; no fit."""
import argparse
import hashlib
import json
from pathlib import Path
from . import core as C,store as S


def prepare(publication_path,mask_config_path,field_map_path,output):
    """Prepare concrete references for independent Root domain review.

    Reads existing small JSON metadata only. Never reads source label Parquet,
    invents a role census, generates geometry, or computes a new statistic.
    """
    from workflows.expansion.common import verify
    publication_ref=S.reference(publication_path);pub=S.read_json(publication_path)
    if (pub['schema']!='DATA_V1_PILOT_D4_FORMAL_NORMALIZATION_DELIVERY_V1'
            or pub['status']!='DELIVERED_PROVISIONAL_SCOPE_NOT_FINAL_COMMON'
            or pub['fit_role']!='TRAIN' or pub['fit_pilot_molecules']!=50000
            or pub['VAL_used_for_fitting'] is not False or pub['guide_required_checks_passed'] is not True
            or pub['full_second_statistics_pass_performed'] is not False
            or pub['independent_numeric_replay_equal'] is not None):
        raise RuntimeError('ACTUAL_PUBLISHED_SINGLE_PASS_50K_TRAIN_D4_REQUIRED')
    for name in ('actual_D4_receipt_reference','actual_current_source6_reference','actual_local_exit_reference',
            'actual_local_launch_reference','actual_local_process_proof_reference','population_reference',
            'geometry_reference','statistics_reference'):
        verify(pub[name])
    receipt=S.read_json(pub['actual_D4_receipt_reference']['path'])
    exit_record=S.read_json(pub['actual_local_exit_reference']['path'])
    source6=S.read_json(pub['actual_current_source6_reference']['path'])
    if (exit_record['schema']!='ACTUAL_MAIN_HEAD_D4_PROCESS_EXIT_V1' or exit_record['exit_code']!=0
            or exit_record['execution_kind']!='LOCAL_HEADNODE' or exit_record['Slurm_job_id'] is not None
            or source6['errors']!=0 or source6['failures']!=0):
        raise RuntimeError('ACTUAL_MAIN_LOCAL_EXIT_ZERO_AND_ORIGINAL_SOURCE6_REQUIRED')
    # Keep the real exit schema/field names as evidence; don't pretend a Slurm
    # job or manufacture a second replay from a first-pass reference.
    if receipt['pilot_counts']!={'TRAIN':50000,'VAL':5000}:
        raise RuntimeError('EXACT_ORIGINAL_CHOSEN_ROSTER_REQUIRED')
    statistics=S.read_json(pub['statistics_reference']['path'])
    fields=S.read_json(field_map_path);cfg=S.read_json(mask_config_path)
    field_ref=S.reference(field_map_path);cfg_ref=S.reference(mask_config_path)
    header=S.read_json(verify(receipt['schema_only_header_reference']))
    original_map=header['actual_input_references']['field_map'];verify(original_map)
    if (original_map['bytes'],original_map['sha256'])!=(field_ref['bytes'],field_ref['sha256']):
        raise RuntimeError('ACTUAL_D4_FIELD_MAP_BYTES_MUST_MATCH')
    if cfg['sources']['registry']!=header['actual_input_references']['registry']:
        raise RuntimeError('ACTUAL_D4_ORIGINAL_REGISTRY_MUST_MATCH')
    if not cfg.get('adapter_source_pins'):raise RuntimeError('ORIGINAL_MASK_SOURCE_PINS_REQUIRED')
    for pin in cfg['adapter_source_pins']:verify(pin)
    selected=[f for f in fields if f['task'] in ('D20','D3')]
    if len(selected)!=27 or {f['field_id'] for f in selected}!=set(range(27)):
        raise RuntimeError('EXACT_ORIGINAL_D20_PLUS7_FIELD_MAP_REQUIRED')
    original=statistics['diagnostic_median_MAD']
    projected={str(f['field_id']):original[str(f['field_id'])] for f in selected}
    for fid,item in projected.items():
        if not {'median','MAD','TRAIN_n','MAD_n'}<=set(item) or item['TRAIN_n']!=item['MAD_n'] or item['TRAIN_n']<1:
            raise RuntimeError('ACTUAL_COMPLETE_TRAIN_MEDIAN_MAD_FIELD_REQUIRED:'+fid)
    domain_inputs={'publication_reference':publication_ref,'statistics_reference':pub['statistics_reference'],
        'population_reference':pub['population_reference'],'geometry_reference':pub['geometry_reference'],
        'field_map_reference':field_ref,'scope':'v1-pilot-provisional chosen50000 TRAIN; fixed_random available old-complete S-prime mother'}
    coverage=hashlib.sha256(C.canonical(domain_inputs)).hexdigest()
    out=Path(output);out.mkdir(parents=True,exist_ok=False)
    calibration={'schema':'PUBCHEM_EXISTING_D4_TRAIN_REFERENCE_PROJECTION_V1','fit_role':'TRAIN_ONLY',
        'coverage_fingerprint':coverage,'fields':projected,'original_statistics_reference':pub['statistics_reference'],
        'original_json_path':'diagnostic_median_MAD','projection_only_no_statistical_fit':True,
        'all27_original_median_MAD_values_preserved_binary64':True,'provisional_scope_not_final_Common':True,
        'actual_numeric_passes':1,'full_second_statistics_pass_performed':False,'independent_numeric_replay_equal':None}
    S.write_new(out/'calibration.json',calibration);calibration_ref=S.reference(out/'calibration.json')
    # Round-trip check applies only to existing JSON numbers, not source DATA.
    again=S.read_json(out/'calibration.json')
    import struct
    for fid,item in projected.items():
        for name in ('median','MAD'):
            if struct.pack('<d',item[name])!=struct.pack('<d',again['fields'][fid][name]):
                raise RuntimeError('ORIGINAL_BINARY64_REFERENCE_PROJECTION_CHANGED')
    domain={'schema':'PUBCHEM_EXISTING_D4_TRAIN_REFERENCE_DOMAIN_V1','fit_role':'TRAIN_ONLY',
        'coverage_fingerprint':coverage,'calibration_reference':calibration_ref,**domain_inputs,
        'actual_source_and_role_census_closed':True,'closed_census_scope':'chosen50000 TRAIN and5000 ROUTINE VAL; VAL not fitted',
        'full_Common_census_closed':False,'original_receipt_reference':pub['actual_D4_receipt_reference'],
        'original_local_exit_reference':pub['actual_local_exit_reference'],'actual_exit_record':exit_record,
        'D20_historical_precision_may_be_F32_promoted_new_outputs_are_F64':True,
        'D3_original_label_geometry_vs_new_UFF_domain_difference_requires_review':True,
        'robust_z_review_only_no_automatic_mask':True,'new_R_N_TRAIN_fit':False}
    S.write_new(out/'domain.json',domain)
    review={'schema':'ROOT_NO_PM7_UFF_D_MATCHED_TRAIN_REFERENCE_V1','status':'PROPOSED_PENDING_INDEPENDENT_ROOT_DOMAIN_REVIEW',
        'reviewer':None,'R_N_fit_as_TRAIN':False,'same_D_function_units_and_family_field_map_reviewed':False,
        'UFF_D3_vs_original_TRAIN_domain_difference_reviewed':False,'field_map_reference':field_ref,
        'original_mask_config_reference':cfg_ref,'TRAIN_calibration_reference':calibration_ref,
        'TRAIN_reference_domain_reference':S.reference(out/'domain.json'),'original_D4_publication_reference':publication_ref,
        'scope_label':'Original chosen50000 TRAIN provisional calibration; not final full Common normalization',
        'Root_action':'Review original descriptor units/field IDs/precision and UFF-vs-original geometry domain; approve application only, never fit R/N'}
    S.write_new(out/'review.proposed.json',review)
    return review


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('publication','mask-config','field-map','output'):parser.add_argument('--'+name,required=True,type=Path)
    args=parser.parse_args();prepare(args.publication,args.mask_config,args.field_map,args.output)


if __name__=='__main__':main()
