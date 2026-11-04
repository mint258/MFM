"""Actual206 authority and future independent worker-entry adoption contracts."""
from pathlib import Path
import sys
import sysconfig
from ..alpha_runtime_v1 import common as Q
from ..exact_nn_cached_v1 import engine as original
from ..exact_nn_popcount_cpp_v1 import backend

ADOPTION_SHA='9fb210c91522beedc1ac33f6d73ad9cf401be2d4f53f06788b5dd9e4b7cae516'
N=1196122


def read(ref):
    Q.need(ref['bytes']<=2<<20,'Small exact authority metadata only')
    return Q.load(Q.verify(ref))


def closed(review,job=None):
    p=review['actual_parent'];account=read(review['actual_accounting_reference'])
    Q.need(review['reviewer']=='root'and p['State']=='COMPLETED'and p['ExitCode']=='0:0'
        and str(p['UID'])=='1264'and p['endpoint']==account['endpoint']==Q.ENDPOINT
        and p in account['actual_parents']and(job is None or str(p['JobIDRaw'])==job),'Actual independent Alpha C0/accounting required')
    Q.verify(account['raw_sacct_reference']);return p


def adopted(ref):
    Q.need(ref['bytes']==9317 and ref['sha256']==ADOPTION_SHA,'Actual206 compiled backend Root authority required')
    r=read(ref);closed(r,'1885206')
    Q.need(r['schema']=='ROOT_ALPHA_COMPILED_EXACT_POPCOUNT_ACTUAL_ACCEPTANCE_V1'
        and r['status']=='APPROVED_COMPILED_INTEGER_BACKEND_FOR_FUTURE_COMMON_EXACT_NN'
        and r['reference_molecules']==N and r['measured_queries']==64 and r['workers_each_loaded_both_full_references']==16
        and r['native_boundary_tests']==8 and r['original_math_tests']==9
        and r['all_eight_fields_including_unreduced_counts_groups_and_F64_bits_equal']is True
        and r['all_historical200_fields_and_query_identity_equal']is True
        and r['fingerprint_recipe']==original.RECIPE and r['mathematical_algorithm']==original.ALGORITHM
        and r['existing_cache_reuse_authorized']is False,'Scoped same196 Common implementation adoption, never whole-pipeline approval')
    producer=read(r['producer_receipt_reference'])
    Q.need(producer['status']=='BENCHMARK_PENDING_ROOT_ACTUAL_C0_REVIEW'
        and producer['actual_parent']['job_id']=='1885206'and producer['build_manifest_reference']==r['build_manifest_reference']
        and producer['measurements_reference']==r['measurements_reference'],'Actual206 producer/build/measurement binding')
    Q.verify(r['measurements_reference'])
    packed=read(r['reference_manifest_reference']);review196=read(r['reference_actual_review_reference']);closed(review196,'1885196')
    Q.need(review196['status']=='APPROVED_COMPLETE_COMMON_EXACT_REFERENCE_PACK'
        and review196['reference_manifest_reference']==r['reference_manifest_reference']
        and packed['schema']=='expansion_exact_ecfp4_reference_v1'and packed['status']=='COMPLETE'
        and packed['molecules']==N and packed['fingerprint_recipe']==original.RECIPE and packed['targets_present']is False,
        'Only actual196 full1196122 reference, no augmented/subset substitution')
    module,build=backend.load_kernel(r['build_manifest_reference'])
    Q.need(build['binary_reference']==r['binary_reference']and build['python']==r['python_ABI']
        and build['source_references']==r['validated_source_references']
        and module.build_info()['runtime_popcount_backend']==r['validated_runtime_popcount_backend']=='x86_runtime_popcnt',
        'Same206 actual binary/Core5/ABI and native CPU branch required')
    for name,binding in r['source_bindings'].items():
        if name=='engine.py':
            actual=Q.reference(original.__file__);expected=binding['execution_reference']
            Q.need(actual==expected,'Original oracle import must retain exact validated source')
    return r,packed


def integration(ref,adoption_ref):
    """Future Root review is mandatory;206 itself explicitly did not validate wiring."""
    r=read(ref)
    Q.need(r['schema']=='ROOT_ALPHA_POPCOUNT_WORKER_ENTRY_ACTUAL_ACCEPTANCE_V1'
        and r['status']=='APPROVED_NATIVE_WORKERS_AND_METADATA_ENTRY_FOR_FUTURE_FULL_POOL'
        and r['backend_adoption_reference']==adoption_ref,'Independent actual worker/metadata-entry integration approval required')
    parent=closed(r);p=read(r['producer_receipt_reference']);adoption,packed=adopted(adoption_ref)
    Q.need(p['schema']=='ALPHA_POPCOUNT_WORKER_ENTRY_INTEGRATION_VALIDATION_V1'
        and p['status']=='WORKER_ENTRY_VALIDATED_PENDING_ROOT_ACTUAL_C0_REVIEW'
        and p['actual_parent']['job_id']==str(parent['JobIDRaw'])
        and p['backend_adoption_reference']==adoption_ref and p['reference_molecules']==N
        and p['build_manifest_reference']==adoption['build_manifest_reference']
        and p['binary_reference']==adoption['binary_reference']
        and p['reference_manifest_reference']==adoption['reference_manifest_reference']
        and p['measured_queries']==64 and p['full_reference_worker_count']==16
        and p['all_worker_fields_and_F64_equal_original_and_206']is True
        and p['entry_code_object_preserved']is True and p['entry_global_changes']==['exact_batches']
        and p['full_pool_execution_claimed']is False,'Actual newworkers64/fullref/oracle proof, not kernel-only or full-pool pretence')
    sources={Path(x['path']).name:x for x in p['production_source_references']}
    actual={path.name:Q.reference(path)for path in Path(__file__).parent.glob('*.py')}
    Q.need(len(sources)==len(actual)and sources==actual,'Production wiring source changed since independently validated integration')
    Q.verify(p['measurements_reference']);return r,p
