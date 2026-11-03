"""Small actual-authority adapter; large feature verification only inside Guard."""
from pathlib import Path
from ..alpha_runtime_v1 import common as Q
from ..pubchem_generic_recovery_overlay_v1.reader import validate_header
from ..pubchem_generic_recovery_overlay_v1.runtime import VERSION,actual_parent

BASELINE_REVIEW_SHA='5217385cfa77f2702e181aa8d97be579b6289ce2a51e60334930ff9f7ae04f69'
COMMON_REVIEW_SHA='30201799f051916d5117a4782479778a82fbf072ee59238a8472edf1973dceb9'


def read(ref):
    Q.need(ref['bytes']<=2<<20,'Only small actual authority metadata here')
    return Q.load(Q.verify(ref))


def baseline(receipt_ref,review_ref):
    Q.need(review_ref['bytes']==1918 and review_ref['sha256']==BASELINE_REVIEW_SHA,'Actual corrected183 Root authority required')
    review=read(review_ref);q=read(receipt_ref)
    Q.need(review['schema']=='ROOT_ACTUAL_ALPHA_CORRECTED_BASELINE1M_V1'
        and review['status']=='ACCEPTED_COMPLETE_CORRECTED_PREDECON_FIXED_1M'
        and review['producer_receipt_reference']==receipt_ref,'Exact current baseline Root receipt binding')
    parent=actual_parent(review)
    Q.need(parent['JobIDRaw']=='1885183'and q['actual_parent']['job_id']=='1885183'
        and q['actual_parent']['uid']==1264 and q['actual_parent']['endpoint']=='218.192.171.238:22',
        'Actual profile.job_id is required, never legacy SlurmJobID')
    pool=validate_header(read(q['source_pool_receipt']))
    Q.need(q['schema']=='EXPANSION_PUBCHEM_PREDECON_BASELINE_V1'and q['status']=='COMPLETE'
        and q['population_version']==pool['population_version']==review['population_version']==VERSION
        and q['sample_seed']==review['seed']==20261025 and q['sample_hash_domain']==review['domain']=='PubChem-baseline-uniform'
        and q['sample_molecules']==review['sample_molecules']==1000000 and q['source_pool_molecules']==109875599
        and q['source_pool_receipt']==review['source_pool_reference']==q['internal_deduplicated_pool_reference']
        and q['sample_ordinal_start']==0 and q['projection_order']=='sample_ordinal_ASC'
        and q['changed_membership']==review['changed_membership']==dict(old_keys_removed=31,new_full_keys_added=31,representative_CIDs_changed=0)
        and q['sample_selection']=='fixed_predecon_minCID_fullkey_unique'
        and q['all_source_internal_fullkey_dedup_before_v1_or_downstream_decontamination']is True
        and q['exact_incremental_method']=='INSERT_ONLY_TOPK_FROM_PROVEN_FROZEN_OLD_TOPK_PLUS_ALL_NEW_FULLKEYS',
        'Explicit actual corrected population/unchanged sampling/history, not old-baseline relabel')
    old=read(q['previous_baseline_receipt_reference']);old_actual=read(q['previous_baseline_actual_reference'])
    Q.need(old['source_pool_receipt']==pool['base_pool_receipt_reference']and old_actual['receipt_reference']==q['previous_baseline_receipt_reference']
        and old['sample_seed']==q['sample_seed']and old['sample_hash_domain']==q['sample_hash_domain'], 'Exact preserved old baseline history required')
    return q


def common(review_ref):
    Q.need(review_ref['bytes']==3514 and review_ref['sha256']==COMMON_REVIEW_SHA,'Actual closed178 Root authority required')
    review=read(review_ref);parent=actual_parent(review)
    Q.need(review['schema']=='ROOT_ALPHA_FULL_COMMON_POPULATION_STATISTICS_ACTUAL_ACCEPTANCE_V1'
        and review['status']=='ACCEPTED_COMPLETE_FULL_COMMON_WITH_HISTORICAL_BASELINE'
        and parent['JobIDRaw']=='1885178'and review['populations']==dict(pubchem_1m=1000000,v1_common=1196122)
        and review['complete_Common_not_subset']is True,'Closed whole Common statistics required')
    producer=read(review['producer_receipt_reference']);original=read(review['original_population_tables_receipt_reference'])
    Q.need(producer['profile_admission']['job_id']=='1885178'and original['endpoint_execution']['job_id']=='1885178',
        'Actual original profile job identity required')
    return review,original


def population(plan,path):
    q=baseline(plan['corrected_baseline_receipt_reference'],plan['corrected_baseline_actual_reference'])
    # Called only by the admitted wrapper, not metadata plan preparation.
    for key in('sample_membership','features','projection'):Q.verify(q[key])
    artifact=lambda r:{**r,'format':'parquet'}
    body=dict(schema='EXPANSION_DISTRIBUTION_POPULATION_V1',status='COMPLETE',population='pubchem_1m',
        population_version=VERSION,population_scope='FULL_DECLARED_POPULATION',expected_molecules=1000000,
        authority_reference=plan['corrected_baseline_receipt_reference'],authority_count_pointer='/sample_molecules',
        authority_kind='FROZEN_PREDECON_UNIFORM_BASELINE',is_sample=True,
        sampling=dict(uniform=True,seed=q['sample_seed'],source_status='X_SCREENED_INTERNAL_FULLKEY_DEDUPLICATED'),
        baseline_pool_phase='BEFORE_V1_DOWNSTREAM_DECONTAMINATION_AND_NOVELTY',
        raw_chemical_screen_reference=q['raw_chemical_screen_reference'],internal_deduplicated_pool_reference=q['source_pool_receipt'],
        source_pool_receipt=q['source_pool_receipt'],membership=dict(identity_column='full_key',artifacts=[artifact(q['sample_membership'])]),
        features=dict(identity_column='full_key',artifacts=[artifact(q['features'])]),allow_additive_descriptor_completion=False,
        original_sample_projection_reference=q['projection'],sample_order_preserved=q['projection_order'],
        source_endpoint=q['source_endpoint'],source_uid=q['source_uid'],sample_reselected_or_chemistry_recomputed=False,
        corrected_baseline_actual_reference=plan['corrected_baseline_actual_reference'],
        previous_baseline_receipt_reference=q['previous_baseline_receipt_reference'],
        previous_baseline_actual_reference=q['previous_baseline_actual_reference'],changed_membership=q['changed_membership'])
    if Path(path).exists():Q.need(Q.load(path)==body,'Same current baseline binding required on resume')
    else:Q.write(path,body)
    return Q.reference(path)
