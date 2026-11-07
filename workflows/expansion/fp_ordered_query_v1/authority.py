"""Small actual receipts only; no invented future fullfilter pins or acceptance."""
from ..alpha_runtime_v1 import common as Q
from ..pubchem_generic_recovery_overlay_v1.runtime import VERSION,actual_parent
from ..pubchem_generic_recovery_overlay_v1.reader import validate_header
from .core import population_scope


def read(ref):
    Q.need(0<ref['bytes']<=2<<20,'Small exact authority metadata required')
    Q.need(Q.frame(ref['path'])[2]==ref['bytes'],'Authority must be actual same-size small metadata before hashing')
    return Q.load(Q.verify(ref))


def validate(inputs):
    Q.need(inputs['schema']=='PUBCHEM_FP_ORDERED_QUERY_INPUTS_V1'
      and inputs['status']=='ACTUAL_INPUTS_COLLECTED_NOT_DATA_VERIFIED','Actual collector inputs required')
    fref=inputs['filtered_pool_receipt_reference'];f=read(fref)
    review=read(inputs['filtered_pool_actual_review_reference']);parent=actual_parent(review)
    pool=validate_header(read(f['source_pool_receipt']));population_scope(f,pool)
    Q.need(review['schema']=='ROOT_ALPHA_FULL_FILTERED_POOL_ACTUAL_ACCEPTANCE_V1'
      and review['status']=='APPROVED_COMPLETE_CORRECTED_ALL11_FILTERED_POOL' and review['reviewer']=='root'
      and review['producer_receipt_reference']==fref and review['population_version']==f['population_version']==VERSION
      and str(parent['JobIDRaw'])==str(f['actual_parent']['job_id']) and f['actual_parent']['uid']==1264
      and f['actual_parent']['endpoint']=='218.192.171.238:22'
      and review['source_pool_reference']==f['source_pool_receipt']
      and review['index_receipt_reference']==f['exclusion_index_receipt']
      and review['regression_reference']==f['regression_reference']
      and review['eligible_molecules']==f['counts']['eligible_molecules']
      and review['all_sources_all_splits_verified'] is f['all_sources_all_splits_verified'] is True,
      'Actual fullfilter C0/Root source acceptance, never the earlier52k partial')
    index_review=read(f['root_index_acceptance_reference']);ip=actual_parent(index_review)
    Q.need(index_review['schema']=='PUBCHEM_ALL11_EXCLUSION_INDEX_ACTUAL_ACCEPTANCE_V1'
      and index_review['status']=='APPROVED_COMPLETE_ALL11_INDEX' and index_review['reviewer']=='root'
      and index_review['index_receipt']==f['exclusion_index_receipt'] and str(ip['JobIDRaw'])=='1885205'
      and index_review['all_sources_all_splits_verified'] is True and index_review['original_graph_unknowns_retained'] is True,
      'Actual all11 amended205 index and original UNKNOWN/source scope required')
    regression=read(f['regression_reference']);rr=read(regression['root_review']);rp=actual_parent(rr)
    Q.need(regression['schema']=='pubchem_v1_complete_input_common_bound_regression_v1'
      and regression['status']=='PASS' and regression['full_v1_selection_regression_passed'] is True
      and regression['common_population_scope_bound'] is True and regression['agreement']>=.999
      and regression['unexplained_mismatches']==0 and regression['actual_all_original_records']==15879477
      and rr['schema']=='ROOT_COMMON_SELECTION_REGRESSION_BIND_ACTUAL_ACCEPTANCE_V1'
      and rr['status']=='APPROVED_ACTUAL_FULL_COMMON_SELECTION_REGRESSION' and rr['reviewer']=='root'
      and rr['producer_receipt']==regression['actual_binding_producer'] and str(rp['JobIDRaw'])=='1885195',
      'Original actual full-input X195 regression remains mandatory')
    return f,pool,review
