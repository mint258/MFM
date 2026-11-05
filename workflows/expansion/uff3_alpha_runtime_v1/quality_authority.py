"""Consume independently accepted full Common TRAIN calibration, never refit R/N."""
from ..alpha_runtime_v1 import common as Q


def read(ref):return Q.load(Q.verify(ref))


def completed(review):
    parent=review['actual_parent'];account=read(review['actual_accounting_reference'])
    Q.need(parent['State']=='COMPLETED'and parent['ExitCode']=='0:0'
        and parent['endpoint']==Q.ENDPOINT and int(parent['UID'])==Q.UID
        and account['endpoint']==Q.ENDPOINT and account['uid']==Q.UID
        and parent in account['actual_parents'],'Real Alpha C0 and same independent Root accounting required')
    Q.verify(account['raw_sacct_reference'])
    return parent


def accepted(ref):
    review=read(ref)
    Q.need(review['schema']=='ROOT_NO_PM7_UFF_D_MATCHED_TRAIN_REFERENCE_V1'
        and review['status']=='APPROVED_REFERENCE_APPLICATION_ONLY'and review['reviewer']=='root'
        and review['R_N_fit_as_TRAIN']is False
        and review['same_D_function_units_and_family_field_map_reviewed']is True
        and review['UFF_D3_vs_original_TRAIN_domain_difference_reviewed']is True,
        'Actual reviewed original-functions fullTRAIN reference application required')
    completed(review);read(review['producer_receipt_reference'])
    cal=read(review['TRAIN_calibration_reference']);domain=read(review['TRAIN_reference_domain_reference'])
    Q.need(cal['schema']=='PUBCHEM_FULL_COMMON_TRAIN_D27_CALIBRATION_V1'
        and domain['schema']=='PUBCHEM_FULL_COMMON_TRAIN_D27_REFERENCE_DOMAIN_V1'
        and cal['fit_role']==domain['fit_role']=='TRAIN_ONLY'
        and domain['calibration_reference']==review['TRAIN_calibration_reference']
        and cal['coverage_fingerprint']==domain['coverage_fingerprint']
        and domain['actual_source_and_role_census_closed']is True
        and domain['full_Common_census_closed']is True
        and cal['provisional_scope_not_final_Common']is False
        and cal['R_N_used_for_fit']is False and domain['new_R_N_TRAIN_fit']is False
        and domain['robust_z_review_only_no_automatic_mask']is True
        and set(cal['fields'])=={str(i)for i in range(27)}
        and review['fit_records']==domain['fit_records']==10953084
        and review['Common_TRAIN_native_records_before_D5_exclusion']==10973084
        and review['D5_PM7_held_native_records_excluded']==20000,
        'Exact complete Common TRAIN minus original held D5; provisional50k is not this authority')
    Q.need(all(cal['fields'][str(i)]['TRAIN_n']==(580397586 if i==24 else 10953084)
        for i in range(27)),'All27 real accepted canonical-record/atom-leaf reference populations required')
    return review,cal,domain