"""Actual full CPP execution and immutable original rank source bindings."""
import hashlib
from pathlib import Path
from ..alpha_runtime_v1 import common as Q
from ..pubchem_generic_recovery_overlay_v1.runtime import VERSION,actual_parent
from . import budget


def ref(path):
    Q.need(Q.frame(path)[2]<=2<<20,'Only small actual metadata/source files in collector')
    return Q.reference(path)


def read(value):
    Q.need(0<value['bytes']<=2<<20 and Q.frame(value['path'])[2]==value['bytes'],'Same-size small authority metadata required')
    return Q.load(Q.verify(value))


def execution_shapes(wrapper,native,query,review):
    Q.need(wrapper['schema']=='ALPHA_COMPILED_FULL_POOL_EXECUTION_METADATA_V1'
      and wrapper['status']=='FULL_POOL_EXECUTION_COMPLETE_PENDING_ROOT_ACTUAL_C0_REVIEW'
      and wrapper['original_run_code_object_preserved']is True and wrapper['only_injected_global']=='exact_batches'
      and wrapper['RDKit_nearest_engine_used']is False and wrapper['no_automatic_scientific_retry']is True,
      'Explicit completed CPP wrapper required, never original-RDKit execution impersonation')
    Q.need(native['schema']=='expansion_exact_novelty_v1'and native['status']=='COMPLETE'
      and native['nearest_similarity_exact']is True and native['downstream_features_used']is False
      and query['schema']=='EXPANSION_TYPED_DECONTAMINATED_QUERY_PROJECTION_V1'and query['status']=='COMPLETE'
      and query['producer_schema']=='PUBCHEM_FULL_FP_ORDERED_TYPED_QUERY_V1'
      and query['projection_order']=='ecfp4_2048_hex_ASC_full_key_ASC_cid_ASC'and query['population_version']==VERSION
      and native['fingerprint_recipe']==query['fingerprint_recipe']=='ECFP4_2048_radius2_chiralityFalse_rdkit2025.09.5'
      and query['targets_present']is False and query['downstream_features_present']is False
      and type(native['queries'])is int and native['queries']>=10000000
      and native['queries']==native['projection']['rows']==query['projection']['rows']==review['queries']
      and native['reference_molecules']==1196122,'Actual same complete FP-ordered full eligible population/reference, never64/1M/prefix')
    Q.need(review['schema']=='ROOT_ALPHA_COMPILED_FULL_POOL_ACTUAL_ACCEPTANCE_V1'
      and review['status']=='APPROVED_COMPLETE_COMPILED_COMMON_EXACT_FULL_POOL'and review['reviewer']=='root',
      'Independent actual full-pool Root review required')


def inputs(wrapper_ref,review_ref):
    w=read(wrapper_ref);r=read(review_ref);parent=actual_parent(r);nref=w['original_scientific_receipt_reference'];n=read(nref)
    q=read(n['query_manifest']);execution_shapes(w,n,q,r)
    Q.need(r['compiled_execution_wrapper_reference']==wrapper_ref and r['original_scientific_receipt_reference']==nref
      and r['query_manifest_reference']==n['query_manifest']and r['reference_manifest_reference']==n['reference']
      and str(parent['JobIDRaw'])==str(w['actual_parent']['job_id'])and w['actual_parent']['uid']==1264
      and w['actual_parent']['endpoint']==Q.ENDPOINT and n['resource_plan']==w['plan_reference'],
      'Actual full CPP C0/wrapper/original receipt/query/reference/plan must all bind')
    plan=read(w['plan_reference']);proof=read(w['startup_proof_reference'])
    Q.need(str(proof['job_id'])==str(parent['JobIDRaw'])and proof['uid']==1264 and proof['endpoint']==Q.ENDPOINT
      and proof['request']['producer_plan_reference']==w['plan_reference']and plan['query_manifest']==n['query_manifest']
      and plan['reference_manifest']==n['reference']and plan['schema']=='PUBCHEM_EXACT_CACHED_NN_PLAN_V1'
      and 'max_queries'not in plan,'Actual allocated full CPP startup, never source207 fixture C0')
    adoption=read(w['backend_adoption_reference']);actual_parent(adoption)
    Q.need(w['backend_adoption_reference']['bytes']==9317
      and w['backend_adoption_reference']['sha256']=='9fb210c91522beedc1ac33f6d73ad9cf401be2d4f53f06788b5dd9e4b7cae516'
      and adoption['reviewer']=='root'and adoption['schema']=='ROOT_ALPHA_COMPILED_EXACT_POPCOUNT_ACTUAL_ACCEPTANCE_V1'
      and adoption['status']=='APPROVED_COMPILED_INTEGER_BACKEND_FOR_FUTURE_COMMON_EXACT_NN'
      and str(adoption['actual_parent']['JobIDRaw'])=='1885206'
      and adoption['reference_manifest_reference']==n['reference']and adoption['reference_molecules']==1196122
      and adoption['mathematical_algorithm']==n['algorithm']and adoption['fingerprint_recipe']==n['fingerprint_recipe']
      and adoption['build_manifest_reference']==w['build_manifest_reference']and adoption['binary_reference']==w['binary_reference']
      and adoption['existing_cache_reuse_authorized']is False,'Actual206 same196 reference/build/binary adoption required')
    integration=read(w['worker_entry_actual_review_reference']);actual_parent(integration)
    Q.need(integration['reviewer']=='root'and integration['schema']=='ROOT_ALPHA_POPCOUNT_WORKER_ENTRY_ACTUAL_ACCEPTANCE_V1'
      and integration['status']=='APPROVED_NATIVE_WORKERS_AND_METADATA_ENTRY_FOR_FUTURE_FULL_POOL'
      and integration['backend_adoption_reference']==w['backend_adoption_reference'],'Actual worker/entry integration, not kernel-only approval')
    integrated=read(integration['producer_receipt_reference'])
    Q.need(integrated['schema']=='ALPHA_POPCOUNT_WORKER_ENTRY_INTEGRATION_VALIDATION_V1'
      and integrated['status']=='WORKER_ENTRY_VALIDATED_PENDING_ROOT_ACTUAL_C0_REVIEW'
      and str(integrated['actual_parent']['job_id'])==str(integration['actual_parent']['JobIDRaw'])
      and integrated['all_worker_fields_and_F64_equal_original_and_206']is True
      and integrated['reference_manifest_reference']==n['reference']and integrated['binary_reference']==w['binary_reference']
      and integrated['build_manifest_reference']==w['build_manifest_reference'],'Actual integrated worker/oracle/binary/source equality')
    marker=read(w['cache_namespace_manifest_reference']);binding=marker['binding']
    Q.need(marker['old_or_seeded_cache_used']is False and marker['namespace_identity']==plan['cache_namespace']==
      'cpp206-'+hashlib.sha256(Q.canonical(binding)).hexdigest()
      and binding['query_manifest']==n['query_manifest']and binding['reference_manifest']==n['reference']
      and binding['filtered_pool_receipt']==n['filtered_pool_receipt']==q['filtered_pool_receipt']
      and binding['population_version']==q['population_version']
      and binding['backend_adoption_reference']==w['backend_adoption_reference']
      and binding['build_manifest_reference']==w['build_manifest_reference']and binding['binary_reference']==w['binary_reference']
      and binding['original_source_bindings']==adoption['source_bindings']and binding['prototype_sources']==adoption['validated_source_references']
      and {x['path']:x for x in binding['production_sources']}=={x['path']:x for x in integrated['production_source_references']}
      and w['native_worker_source_reference']in binding['production_sources'],'Own exact CPP namespace and validated source closure required')
    for value in binding['production_sources']:Q.verify(value)
    proofq=read(q['all_row_equivalence_and_order_reference'])
    Q.need(proofq['status']=='COMPLETE'and proofq['projection_reference']==q['projection']
      and proofq['full_multiset_proof']['all_source_rows_proved']is True,'Actual full sorted query equivalence proof required')
    return w,n,q


def deployed(deployment):
    bindings=deployment['original_rank_source_bindings'];Q.need(set(bindings)=={'typed_rank.py','external_sort.py'},'Exactly two original source-body bindings')
    executed={}
    for name,row in bindings.items():
        origin=row['origin_reference'];execution=row['execution_reference']
        Q.need(origin['bytes']==execution['bytes']and origin['sha256']==execution['sha256'],'Original rank/queue bodies must be byte-identical copies')
        Q.verify(origin);Q.verify(execution)
        Q.need(execution in deployment['code_references'],'Both physical original-body copies must be startup source pins')
        executed[name]=execution
    rank=Path(executed['typed_rank.py']['path']);sort=Path(executed['external_sort.py']['path'])
    Q.need(rank.name=='typed_rank.py'and rank.parent.name=='exact_nn_cached_v1'
      and rank.parents[1]/'external_sort.py'==sort and sort.is_file()and not sort.is_symlink(),
      'Real independent capsule must satisfy original relative receipt-source path before large ranking')
    namespace=read(deployment['rank_namespace_manifest_reference'])
    Q.need(namespace['capsule_exact_nn_cached_v1_path']==str(rank.parent)
      and str(rank.parent)in namespace['exact_nn_cached_v1_search_paths']
      and any('/code/exact_Common_'in p for p in namespace['exact_nn_cached_v1_search_paths'])
      and namespace['namespace_source_reference']in deployment['code_references'],'Explicit new capsule plus original exact_Common package namespace required')
    Q.verify(namespace['namespace_source_reference']);return executed


def partition(review_ref,key):
    review=read(review_ref);global_budget=read(review['global_budget_reference']);chosen=budget.choose(review,global_budget,key)
    read(review['closed_legacy_scope_census_reference'])
    for value in review['closed_legacy_actual_accounting_references']:read(value)
    for row in review['partitions']:
        if row['allocated_bytes_credit']:read(row['physical_census_reference'])
    return chosen
