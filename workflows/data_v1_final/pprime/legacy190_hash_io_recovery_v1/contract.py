"""I/O-only recovery of job4525190's exact50k; original physical once scope."""
from workflows.data_v1_final.pprime.formal_packed_day_v1.contract import *
from workflows.data_v1_final.pprime.formal_packed_day_v1 import contract as Old

HERE=Q.REPO/'workflows/data_v1_final/pprime/legacy190_hash_io_recovery_v1'
MODULE='workflows.data_v1_final.pprime.legacy190_hash_io_recovery_v1.run'
FILES=('__init__.py','contract.py','prepare.py','run.py','metadata.py','README.md')
# Keep the original scope, output role budget and global once namespace.
REQUIRED=(*Old.REQUIRED,'generation_partition_QA_reference','generation_partition_root_review_reference')

def parameters(node,mode='ORIGINAL_WP5'):
    return dict(Old.parameters(node,mode),input_hash_storage='APPEND_ONLY_RID_HASHES_JOIN_V1',
      exact_legacy190_MIDs_required=50000)

def bootstrap(p):
    b=Old.bootstrap(p);qa=meta(p['generation_partition_QA_reference']);rr=meta(p['generation_partition_root_review_reference'])
    need(qa['schema']=='PPRIME_READY_MID_PARTITION_QA_V1'
      and qa['status']=='CPU_CLOSED_PARTITION_REQUIRES_ROOT_REVIEW' and qa['actual_planner_job_id']=='4525197'
      and qa['main190_excluded_MIDs']==50000 and qa['pairwise_disjoint'] is True
      and qa['union_covers_original_ready_MID_universe'] is True,'ACTUAL197_CLOSED_EXACT_LEGACY_DOMAIN')
    need(rr['schema']=='PPRIME_DISJOINT_READY_MID_PARTITION_ROOT_REVIEW_V1'
      and rr['status']=='APPROVED_EXACT_CPU_CLOSED_DISJOINT_MID_PARTITION' and rr['reviewer']=='root'
      and rr['partition_QA_reference']==p['generation_partition_QA_reference']
      and rr['main190_exclusion_header_reference']==qa['main190_exclusion_header_reference'],
      'ROOT_EXISTING197_DOMAIN_ACCEPTANCE')
    href=qa['main190_exclusion_header_reference'];h=meta(href)
    need(h['schema']=='PPRIME_LIVE_PARENT_MID_DOMAIN_EXCLUSION_HEADER_V1'
      and h['status']=='EXACT_FROZEN_READY_PREFIX_RECONSTRUCTED_WITH_BASELINE_ONCE'
      and h['exact_live_assignment_reconstructed'] is True and h['molecules']==50000
      and h['actual_planner_job_id']=='4525197' and h['target_uid']==1278
      and h['target_endpoint']=='202.38.247.57:22'
      and h['original_protocol_reference']==b['pilot_plan']['original_protocol_reference']
      and h['pilot_execution_plan_reference']==p['pilot_execution_plan_reference'],
      'EXACT_LEGACY190_50K_NOT_CONSERVATIVE_OR_NEW_PARTITION')
    oldplan=meta(h['main190_registration']['plan'])
    need(oldplan['schema']=='PPRIME_FORMAL_PACKED_DAY_PLAN_V1'
      and oldplan['maximum_new_records']==Old.MAX_RECORDS
      and oldplan['original_protocol_reference']==h['original_protocol_reference']
      and oldplan['pilot_execution_plan_reference']==p['pilot_execution_plan_reference'],
      'ORIGINAL190_PLAN_AND_PROTOCOL_BINDING')
    population=unique([*b['population'],b['val'],*b['sprime']])
    need(sorted(h['population_data_references'],key=lambda x:x['path'])==sorted(population,key=lambda x:x['path']),
      'SAME_ORIGINAL_FROZEN_POPULATION_LOCATORS')
    b=dict(b,legacy190_header=h,legacy190_header_reference=href)
    b['data']=unique([*b['data'],P.triple(h['record_reference'])])
    b['refs']=unique([*b['refs'],p['generation_partition_QA_reference'],p['generation_partition_root_review_reference'],
      href,h['main190_registration']['plan']])
    return b

def sources(p):
    return unique([*Old.sources(p),*[Q.pin(HERE/n) for n in FILES]])
