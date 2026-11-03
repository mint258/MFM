"""Representation-specific source gates; original scientific rules unchanged."""
from ..common import load,require
from ..portable_sources_v1.transport import verify
from .engine import RECIPE


def complete_source(pool):
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


def baseline_query(q):
    require(q.get('schema')=='EXPANSION_PUBCHEM_PREDECON_BASELINE_V1' and q.get('status')=='COMPLETE'
        and q.get('fingerprint_recipe')==RECIPE and q.get('targets_present') is False
        and q.get('downstream_features_present') is False and q.get('sample_seed')==20261025
        and q.get('sample_selection')=='fixed_predecon_minCID_fullkey_unique'
        and q.get('sample_ordinal_start')==0 and q.get('projection_order')=='sample_ordinal_ASC'
        and q.get('all_source_internal_fullkey_dedup_before_v1_or_downstream_decontamination') is True
        and q['projection']['rows']==1000000,'Actual scientific fixed1M PRE-decon baseline required')
    complete_source(load(verify(q['source_pool_receipt'])))
    verify(q['sample_membership']);return verify(q['projection'])
