"""Scoped source admission, original9945 science, no old-ready namespace spoof."""
from workflows.data_v1_final.pprime.formal_packed_sharded_day_v3.contract import *
from workflows.data_v1_final.pprime.formal_packed_sharded_day_v3 import contract as Before
from workflows.data_v1_final.pprime.formal_packed_day_v1 import contract as Base
from workflows.data_v1_final.pprime.formal_packed_sharded_day_v2 import contract as V2
HERE=Q.REPO/'workflows/data_v1_final/pprime/fill_current_scope_v1'
MODULE='workflows.data_v1_final.pprime.fill_current_scope_v1.run'
FILES=('__init__.py','contract.py','scope.py','source_io.py','prepare.py','component.py','metadata.py','run.py')
BASE=Q.ROOT/'artifacts/pprime_fill_current_scope_v1'
MODES={'SHARED_PREPARE':'pprime_fill_current_scope_prepare_v1','EXECUTE':'pprime_fill_current_scope_execute_v1'}
REQUIRED=(*Base.REQUIRED,'shared_pool_root_review_reference','fill_source_authority_reference',
 'closed_common_manifest_reference','closed_common_accounting_reference','original_config_reference',
 'original_ready_partition_reference','physical_reader_config_reference','original_closed_pilot_reuse_reference')


def parameters(p):
    need(p['mode']in MODES and p['node']in(*NODES,'compute-0-2','compute-0-8'),'EXACT_MAIN_CURRENT_FILL_MODE_NODE')
    need(p['mode']!='EXECUTE' or p['node']in NODES,'ORIGINAL_QM_CPU_NODES')
    need(p['output_cap_bytes']==32<<30 if p['mode']=='SHARED_PREPARE' else 2<<30<=p['output_cap_bytes']<=8<<30,'ORIGINAL_SHARED_RESOURCE_CAP')
    return dict(mode=p['mode'],node=p['node'],workers=16,wall_seconds=WALL,output_cap_bytes=p['output_cap_bytes'],
      generation_domain='CLOSED5659_FILL_SUCCESS_ANTI_ORIGINAL1110751_READY',fill_source_authority_reference=p['fill_source_authority_reference'],
      tasks=list(O.TASKS),timeout_seconds=900,fixed_first2_seed=20261025,minimum_all12_success_fraction=.9945,
      original_WP5_precision_only=True,maximum_new_records_per_component=MAX_RECORDS,maximum_pending_records=16,
      physical_once_namespace_unchanged=True,source_methods=3,new_QA_calls=0,final_Common_or_training_admission=False)


def bootstrap(p):
    from . import scope,component
    parameters(p);authority(p);b=Base.bootstrap(p)
    source=meta(p['fill_source_authority_reference'])
    need(source['schema']=='PPRIME_CURRENT_CLOSED_FILL_SOURCE_AUTHORITY_V1' and source['closed_common_manifest_reference']==p['closed_common_manifest_reference']
      and source['original_ready_partition_reference']==p['original_ready_partition_reference'] and source['new_UFF_QM_calls']==0,
      'EXPLICIT_CURRENT_FILL_SOURCE_NOT_FINAL_COMMON_PROMOTION')
    common,qa,hrefs,ready,data=scope.references(p)
    need(common['config']==p['original_config_reference'] and common['random_order_seed']==20261025 and common['random_identity_basis']=='canonical_sprime_conf_idx','UNCHANGED_CLOSED_PHYSICAL_RANDOM_IDENTITY')
    need(Q.pin(Q.REPO/'workflows/data_v1_final/conformers/selection.py')==common['random_order_algorithm'],'SAME_ORIGINAL_STABLE_RANDOM_FUNCTION')
    b['data']=unique([*b['data'],*data]);b['refs']=unique([*b['refs'],*[p[k]for k in REQUIRED],*hrefs,common['outcome_status_counts'],meta(p['closed_common_accounting_reference'])['raw_sacct_reference']])
    if p['mode']=='EXECUTE':
        h,refs,data=component.metadata_bind(p);b['prepared']=h;b['refs']=unique([*b['refs'],*refs]);b['data']=unique([*b['data'],*data])
    return b


def sources(p):
    refs=[*Before.sources(p),*[Q.pin(HERE/n)for n in FILES]]
    from workflows.data_v1_final.pprime.current_prepared_component_parentstate_v3 import contract as Current
    refs.extend(Q.pin(Current.HERE/n)for n in Current.FILES)
    root=Q.REPO/'workflows/data_v1_final'
    for path in [root/'pprime/formal_common_v1/prepare_v1.py',root/'pprime/formal_common_v1/common_v1.py',
      root/'pprime/current_prepared_component_parentstate_v3/authority.py',root/'pprime/current_prepared_component_parentstate_v3/run.py',
      root/'conformers/ordinary_postprocess_resume_v1/reuse.py',root/'conformers/formal_cpu_auto_v3/identity.py',root/'conformers/selection.py']:
        refs.append(Q.pin(path))
    return unique(refs)