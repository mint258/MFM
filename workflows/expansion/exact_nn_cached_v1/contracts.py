"""Representation-specific source gates; original scientific rules unchanged."""
from ..common import load,require
from ..portable_sources_v1.transport import verify
from .engine import RECIPE


def complete_source(pool):
    if pool.get('schema')=='PUBCHEM_EXACT_MINCID_OVERLAY_POOL_V1':
        from ..pubchem_generic_recovery_overlay_v1.reader import validate_header
        return validate_header(pool)
    require(pool.get('schema')=='PUBCHEM_EXACT_MINCID_CANDIDATE_POOL_V2'
        and pool.get('status')=='MATERIALIZED_UNFILTERED_NO_RELEASE'
        and pool.get('source_rows')==124857440 and pool.get('original_SQL_minimum_CID_semantics') is True
        and pool.get('all_original_Arrow_fields_and_F64_preserved') is True,'Complete original minCID pool required')
    projection=load(verify(pool['scope']['source_projection']))
    require(projection.get('schema')=='PUBCHEM_ALL_CLOSED_PROJECTIONS_V2'
        and projection.get('source_rows')==124857440,'True full original row scope, never accepted-prefix materialization')
    if projection.get('producer_schema')=='PUBCHEM_ALPHA_ORIGINAL502_TYPED_COVERAGE_V1':
        require(projection.get('source_endpoint')=='218.192.171.238:22' and projection.get('source_uid')==1264
            and projection.get('logical_descriptor_count')==500 and projection.get('fragment_count')==502
            and projection.get('counts')=={'accepted':110046364,'chemReject':14764875,'technicalUnresolved':46201}
            and projection.get('chemistry_recomputed') is False and projection.get('source_journals_replayed_again') is False
            and projection.get('source_typed_bodies_full_SHA_verified') is True,'Honest Alpha full502 original typed scope required')
        coverage=load(verify(projection['coverage_reference']));frozen=load(verify(projection['frozen_manifest_reference']))
        require(coverage.get('schema')=='ROOT_PUBCHEM_ORIGINAL_FINITE500_ROW_COVERAGE_V1'
            and frozen.get('schema')=='ALPHA_PUBCHEM_EXCLUSIVE_ORDINAL_MANIFEST_V1','Actual original Alpha500 ordinal/source closure required')
    else:
        require(projection.get('producer_schema')=='PUBCHEM_FULL_RAW_RECONSTRUCTION_COVERAGE_V1'
            and projection.get('fragment_count')==500 and projection.get('full_raw_scope_reconstructed') is True,
            'True all500 Main RAW scope required; Alpha is never relabeled as Main recomputation')
    return projection


def typed_filtered(filtered):
    require(filtered.get('schema')=='expansion_filtered_columnar_pool_v1' and filtered.get('status')=='COMPLETE'
        and filtered.get('all_sources_all_splits_verified') is True,'Complete all11 all-split typed filtered pool required')
    source=load(verify(filtered['source_pool_receipt']));complete_source(source)
    if source.get('schema')=='PUBCHEM_EXACT_MINCID_OVERLAY_POOL_V1':
        require(filtered.get('population_version')==source['population_version'],'Corrected filter population version must match sealed source')
    regression=load(verify(filtered['regression_reference']))
    require(regression.get('status')=='PASS' and regression.get('agreement',0)>=.999
        and regression.get('unexplained_mismatches')==0 and regression.get('full_v1_selection_regression_passed') is True,
        'Original full-input selection regression gate unchanged')
    index=load(verify(filtered['exclusion_index_receipt']))
    from ..decontamination import REQUIRED
    require(index.get('schema')=='expansion_exclusion_index_with_constraints_v3' and index.get('status')=='COMPLETE'
        and set(index.get('sources',{}))==set(REQUIRED) and index.get('all_physical_source_rows_covered') is True
        and index.get('original_graph_unknowns_retained') is True
        and index.get('constraint_source_datasets')==['coconut','moleculenet'],'All11 physical source/UNKNOWN/constraint gates required')
    acceptance=load(verify(filtered['root_index_acceptance_reference']))
    parent=acceptance.get('actual_parent',{})
    require(acceptance.get('schema')=='PUBCHEM_ALL11_EXCLUSION_INDEX_ACTUAL_ACCEPTANCE_V1'
        and acceptance.get('status')=='APPROVED_COMPLETE_ALL11_INDEX' and acceptance.get('reviewer')=='root'
        and acceptance.get('index_receipt')==filtered['exclusion_index_receipt']
        and acceptance.get('all_sources_all_splits_verified') is True and acceptance.get('original_graph_unknowns_retained') is True
        and parent.get('State')=='COMPLETED' and parent.get('ExitCode')=='0:0'
        and str(index['producer_parent_binding']['job_id'])==str(parent['JobIDRaw']),
        'Actual independent Root all11 acceptance and producer parent required')
    account=load(verify(acceptance['actual_accounting_reference']))
    require(parent in account['actual_parents'],'Real complete index parent must occur in actual accounting')
    verify(index['source_manifest_reference'])
    require(filtered['counts']['input_unique_molecules']==source['unique_full_keys']
        and filtered['counts']['eligible_molecules']+filtered['counts']['excluded_molecules']==source['unique_full_keys'],
        'Exact complete-source filtered census required')
    return filtered


def typed_release(filtered,novelty):
    typed_filtered(filtered)
    require(novelty.get('schema')=='expansion_exact_novelty_v1' and novelty.get('status')=='COMPLETE'
        and novelty.get('nearest_similarity_exact') is True and novelty.get('downstream_features_used') is False
        and novelty.get('fingerprint_recipe')==RECIPE,'Complete original exact novelty gate unchanged')


def corrected_baseline(q,source,actual_review_reference,receipt_reference):
    from ..pubchem_generic_recovery_overlay_v1.runtime import VERSION,actual_parent
    require(q.get('population_version')==source['population_version']==VERSION
        and q.get('sample_hash_domain')=='PubChem-baseline-uniform'
        and q.get('source_pool_molecules')==source['unique_full_keys']
        and q.get('internal_deduplicated_pool_reference')==q['source_pool_receipt']
        and q.get('scope',{}).get('population_version')==VERSION
        and q.get('scope',{}).get('source_pool_receipt')==q['source_pool_receipt'],
        'Explicit corrected baseline/source population version required; never old1M relabel')
    require(all(isinstance(q.get(k),dict)for k in('previous_baseline_receipt_reference','previous_baseline_actual_reference'))
        and q.get('exact_incremental_method')=='INSERT_ONLY_TOPK_FROM_PROVEN_FROZEN_OLD_TOPK_PLUS_ALL_NEW_FULLKEYS',
        'Corrected baseline must retain the exact old history and unchanged sampling proof')
    require(isinstance(actual_review_reference,dict)and isinstance(receipt_reference,dict)
        and actual_review_reference['bytes']==1918
        and actual_review_reference['sha256']=='5217385cfa77f2702e181aa8d97be579b6289ce2a51e60334930ff9f7ae04f69',
        'Actual corrected183 Root baseline review/receipt references are required')
    review=load(verify(actual_review_reference))
    require(review.get('schema')=='ROOT_ACTUAL_ALPHA_CORRECTED_BASELINE1M_V1'
        and review.get('status')=='ACCEPTED_COMPLETE_CORRECTED_PREDECON_FIXED_1M'
        and review.get('producer_receipt_reference')==receipt_reference
        and review.get('population_version')==VERSION and review.get('source_pool_reference')==q['source_pool_receipt']
        and review.get('sample_molecules')==1000000 and review.get('seed')==20261025
        and review.get('domain')=='PubChem-baseline-uniform','Exact current Root review binding required')
    parent=actual_parent(review)
    require(parent['JobIDRaw']==q['actual_parent']['job_id']=='1885183'
        and q['actual_parent']['uid']==1264 and q['actual_parent']['endpoint']=='218.192.171.238:22',
        'Actual corrected baseline profile job_id, never historical SlurmJobID')
    old=load(verify(q['previous_baseline_receipt_reference']));history=load(verify(q['previous_baseline_actual_reference']))
    require(old['source_pool_receipt']==source['base_pool_receipt_reference']
        and history['receipt_reference']==q['previous_baseline_receipt_reference']
        and old['sample_seed']==q['sample_seed']and old['sample_hash_domain']==q['sample_hash_domain'],
        'Exact preserved historical baseline source/seed/domain required')

def baseline_query(q, *, actual_review_reference=None, receipt_reference=None):
    require(q.get('schema')=='EXPANSION_PUBCHEM_PREDECON_BASELINE_V1' and q.get('status')=='COMPLETE'
        and q.get('fingerprint_recipe')==RECIPE and q.get('targets_present') is False
        and q.get('downstream_features_present') is False and q.get('sample_seed')==20261025
        and q.get('sample_selection')=='fixed_predecon_minCID_fullkey_unique'
        and q.get('sample_ordinal_start')==0 and q.get('projection_order')=='sample_ordinal_ASC'
        and q.get('all_source_internal_fullkey_dedup_before_v1_or_downstream_decontamination') is True
        and q['projection']['rows']==1000000,'Actual scientific fixed1M PRE-decon baseline required')
    source=load(verify(q['source_pool_receipt']));complete_source(source)
    if source.get('schema')=='PUBCHEM_EXACT_MINCID_OVERLAY_POOL_V1':
        corrected_baseline(q,source,actual_review_reference,receipt_reference)
    verify(q['sample_membership']);return verify(q['projection'])
