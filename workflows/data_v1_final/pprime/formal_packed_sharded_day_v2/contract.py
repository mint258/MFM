"""Exact Main-only disjoint generation; no final-Common/training admission."""
import pathlib
from workflows.data_v1_final.pprime.formal_packed_day_v1 import contract as Old
Q=Old.Q;P=Old.P;O=Old.O;M=Old.M;Original=Old.Original
need=Old.need;meta=Old.meta;unique=Old.unique;authority=Old.authority;record_once_key=Old.record_once_key;ledger=Old.ledger;fraction_ok=Old.fraction_ok
HERE=Q.REPO/'workflows/data_v1_final/pprime/formal_packed_sharded_day_v2'
MODULE='workflows.data_v1_final.pprime.formal_packed_sharded_day_v2.run'
FILES=('contract.py','io.py','prepare.py','worker.py','publication.py','run.py','metadata.py','test_v1.py','source_origin.json','README.md')
BASE=Q.ROOT/'artifacts/pprime_formal_packed_sharded_day_v2'
MODES={'SHARED_PREPARE':'pprime_formal_shared_pairs_prepare_v2','EXECUTE':'pprime_formal_assigned_pairs_execute_v2','RECOVER_PUBLISH':'pprime_formal_readonly_publish_recovery_v2'}
NODES=Old.NODES;WALL=86400;MAX_RECORDS=100000
RAW_CAP=Old.RAW_CAP;RESULT_CAP=Old.RESULT_CAP;WORKER_CAP=Old.WORKER_CAP
PARENT_CAP=12<<30;ADMIN_CAP=256<<20;LOCAL_CAP=64<<30
RESOURCE=Old.RESOURCE;REQUIRED=(*Old.REQUIRED,'generation_partition_QA_reference','generation_partition_root_review_reference','shared_pool_root_review_reference')

def shape(p):
    mode=p['mode'];need(mode in MODES,'EXACT_MAIN_ONLY_MODE')
    allowed=NODES if mode=='EXECUTE' else (*NODES,'compute-0-2','compute-0-8')
    need(p['node'] in allowed,'QM11_TO19_PREP_OR_SAME_ORIGIN_RECOVERY_ANALYSIS2_8_11_TO19')
    cap=p['output_cap_bytes'];need(type(cap)is int,'EXACT_INTEGER_OUTPUT_CAP')
    need(cap==32<<30 if mode=='SHARED_PREPARE' else 2<<30<=cap<=8<<30,'ROOT_CHOSEN_SHARED_CAP_NOT_COMPLETION_GUARANTEE')
    if mode=='SHARED_PREPARE':need(1<=len(p['generation_shard_header_references'])<=64,'BOUNDED_EXACT_SHARD_LIST')
    return cap

def parameters(p):
    cap=shape(p)
    return {'mode':p['mode'],'node':p['node'],'workers':16,'wall_seconds':WALL,'output_cap_bytes':cap,
      'original_WP5_precision_only':True,'tasks':list(O.TASKS),'timeout_seconds':900,'fixed_first2_seed':20261025,
      'maximum_new_records_per_assigned_MID_shard':MAX_RECORDS,'maximum_pending_records':16,
      'shared_preparation_is_counted_once':True,'local_record_partition_bytes':WORKER_CAP,
      'local_record_plus_closed_staging_soft_cap_bytes':LOCAL_CAP,'shared_active_record_1GiB_reservation':False,
      'shared_publish_requires_exact_closed_bytes_and_original_raw_F64_readback':True,
      'unpublished_native_outputs':'PRESERVE_NODE_SCRATCH_UNKNOWN_ONCE_CONSUMED_NO_NATIVE_RETRY',
      'minimum_all12_success_fraction':.9945,'new_QA_calls':0,'source_methods':3,
      'final_Common_or_training_admission':False,'Alpha_QM_portability_claimed':False}

def same_refs(a,b):return {r['path']:(r['bytes'],r['sha256']) for r in a}=={r['path']:(r['bytes'],r['sha256']) for r in b} and len({r['path'] for r in a})==len(a) and len({r['path'] for r in b})==len(b)

def partition(p,b):
    qa=meta(p['generation_partition_QA_reference']);rr=meta(p['generation_partition_root_review_reference'])
    need(qa['schema']=='PPRIME_READY_MID_PARTITION_QA_V1' and qa['status']=='CPU_CLOSED_PARTITION_REQUIRES_ROOT_REVIEW'
      and all(qa[k] is True for k in ('pairwise_disjoint','union_covers_original_ready_MID_universe','roles_equal_original_frozen_authority','source_MID_ids_preserved'))
      and qa['physical_conformer_IDs_verified'] is False,'EXACT_CPU_MID_PARTITION_NOT_PHYSICAL_ID_PROOF')
    need(rr['schema']=='PPRIME_DISJOINT_READY_MID_PARTITION_ROOT_REVIEW_V1' and rr['status']=='APPROVED_EXACT_CPU_CLOSED_DISJOINT_MID_PARTITION'
      and rr['reviewer']=='root' and rr['partition_QA_reference']==p['generation_partition_QA_reference']
      and rr['shard_header_references']==qa['shard_header_references'],'ROOT_EXACT_CPU_PARTITION')
    refs=[];data=[];headers=[]
    for k in ('main190_exclusion_header_reference','legacy_pilot_exclusion_header_reference'):
        need(rr[k]==qa[k],'ROOT_PARTITION_EXCLUSION_BINDING');h=meta(qa[k]);refs.append(qa[k]);data.append(P.triple(h['record_reference']))
        if k.startswith('main190'):
            need(h['schema']=='PPRIME_LIVE_PARENT_MID_DOMAIN_EXCLUSION_HEADER_V1' and h['status'] in ('EXACT_FROZEN_READY_PREFIX_RECONSTRUCTED_WITH_BASELINE_ONCE','CONSERVATIVE_SUPERSET_EXCLUSION_OF_LIVE_PREFIX_NOT_EXACT_ASSIGNMENT'),'LIVE190_FROZEN_EXCLUSION_NOT_ACTIVE_DB_READ')
        else:need(h['schema']=='PPRIME_ORIGINAL1000_MID_EXCLUSION_HEADER_V1' and h['status']=='CPU_REVALIDATED_ORIGINAL2000_CONSUMED_NOT_REINVOKED','ORIGINAL1000_EXCLUSION')
    population=unique([*b['population'],b['val'],*b['sprime']])
    for ref in p['generation_shard_header_references']:
        need(ref in qa['shard_header_references'],'ONLY_ROOT_ASSIGNED_PARTITION_HEADER');h=meta(ref)
        need(h['schema']=='PPRIME_READY_MID_SHARD_HEADER_V1' and h['status']=='CPU_CLOSED_ASSIGNED_MID_SET_REQUIRES_ROOT_REVIEW'
          and h['target_endpoint']=='202.38.247.57:22' and h['target_uid']==1278
          and type(h['molecules'])is int and 0<h['molecules']<=50000 and h['conformer_records']==2*h['molecules']
          and h['maximum_native_calls']==12*h['conformer_records'] and same_refs(h['population_data_references'],population)
          and h['original_protocol_reference']==p['original_protocol_reference'] and h['pilot_execution_plan_reference']==p['pilot_execution_plan_reference'],
          'EXACT_ASSIGNED_MAIN_MID_HEADER_AND_FROZEN_POPULATION')
        for k in ('main190_exclusion_header_reference','legacy_pilot_exclusion_header_reference'):need(h[k]==qa[k],'SHARD_EXCLUSION_AUTHORITY')
        data.append(P.triple(h['record_reference']));headers.append((ref,h));refs.append(ref)
    need(len({h['shard_id'] for _,h in headers})==len(headers),'UNIQUE_ASSIGNED_SHARDS')
    return headers,unique(data),unique([*refs,p['generation_partition_QA_reference'],p['generation_partition_root_review_reference']])

def bootstrap(p):
    shape(p)
    b=Old.bootstrap(p);headers,data,refs=partition(p,b);b=dict(b,headers=headers)
    b['data']=unique([*b['data'],*data]);b['refs']=unique([*b['refs'],*refs])
    if p['mode']=='EXECUTE':
        h=meta(p['prepared_shard_header_reference']);r=meta(p['shared_preparation_root_acceptance_reference'])
        need(h['schema']=='PPRIME_CPU_CLOSED_ASSIGNED_PAIRS_HEADER_V2' and h['native_invokes']==0 and type(h['records'])is int and 0<h['records']<=MAX_RECORDS and len(headers)==1
          and h['generation_shard_header_reference']==headers[0][0]
          and h['generation_partition_QA_reference']==p['generation_partition_QA_reference'],'ACTUAL_SHARED_PREPARATION_EXACT_ASSIGNED_SHARD')
        need(r['schema']=='ROOT_ACCEPTED_PPRIME_SHARED_PAIRS_PREPARATION_V2' and r['status']=='ACTUAL_C0_SHARED_PAIRS_ACCEPTED_FOR_ASSIGNED_GENERATION'
          and r['reviewer']=='root' and p['prepared_shard_header_reference'] in r['prepared_shard_header_references']
          and r['actual_parent']['State']=='COMPLETED' and r['actual_parent']['ExitCode']=='0:0'
          and r['plan_reference']==h['shared_prepare_plan_reference'] and r['startup_proof_reference']==h['shared_prepare_proof_reference'],
          'ROOT_ACTUAL_SHARED_PREPARATION_C0_NOT_FUTURE_PIN')
        prior=meta(r['plan_reference']);need(prior['mode']=='SHARED_PREPARE' and prior['original_protocol_reference']==p['original_protocol_reference'],'SAME_PREPARATION_PROTOCOL')
        need(h['original_protocol_reference']==p['original_protocol_reference'] and h['source_context_reference']==p['source_context_reference'],'SAME_PREPARED_ORIGINAL_PROTOCOL_AND_SOURCE_CONTEXT')
        for key in ('index_reference','source_audit_reference','audit_selected_reference'):b['data']=unique([*b['data'],P.triple(h[key])])
        b['refs']=unique([*b['refs'],p['prepared_shard_header_reference'],p['shared_preparation_root_acceptance_reference'],r['plan_reference'],r['startup_proof_reference'],r['accounting_reference'],r['raw_sacct_reference'],h['audit_membership_reference'],h['pilot_reuse_reference']]);b['prepared']=h
    if p['mode']=='RECOVER_PUBLISH':
        r=meta(p['recovery_root_review_reference']);h=meta(p['recovery_locator_reference'])
        need(r['schema']=='ROOT_APPROVED_PPRIME_CLOSED_LOCAL_PUBLICATION_RECOVERY_V2' and r['status']=='APPROVED_READONLY_ZERO_NATIVE_PUBLICATION'
          and r['reviewer']=='root' and r['recovery_locator_reference']==p['recovery_locator_reference']
          and r['actual_parent']['JobIDRaw']==h['job_id'] and r['actual_parent']['State'] in ('COMPLETED','FAILED','TIMEOUT','CANCELLED')
          and h['node']==p['node'] and h['uid']==1278,'EXACT_TERMINAL_LOCAL_ROOT_RECOVERY_NOT_NATIVE_RETRY')
        b['refs']=unique([*b['refs'],p['recovery_root_review_reference'],p['recovery_locator_reference'],r['accounting_reference'],r['raw_sacct_reference']]);b['recovery']=h
    return b

def precision(p,r):
    authority(p);need(p['precision_mode']=='ORIGINAL_WP5' and p.get('user_precision_decision_reference') is None
      and r['formal_generation_authorized'] is True and r['user_release_reference']==p['user_release_reference']
      and r['generation_release_reference']==p['generation_release_reference'] and r['original_WP5_precision_only'] is True
      and r['minimum_record_success_rate']==.9945 and r['mode']==p['mode'],'EXACT_USER_RELEASE_ORIGINAL_PRECISION_MODE')
    return p['original_protocol_reference']

def sources(p):
    refs=[*Old.sources(p),*[Q.pin(HERE/n) for n in FILES]];origin=meta(Q.pin(HERE/'source_origin.json'))
    for r in origin['sources']:
        ref={k:r[k] for k in ('path','bytes','sha256')};need(Q.pin(ref['path'])==ref,'FROZEN_LIVE190_FORMAL_R2_ORIGIN_NO_HOTPATCH');refs.append(ref)
    provider=meta(p['quota_provider_review_reference'])
    refs.extend(provider.get('provider_source_references',[]))
    namespace='cpu_packed_day_v1' if p['node']=='compute-0-13' else 'cpu_analysis_cpu19_v1' if p['node']=='compute-0-19' else 'cpu_analysis_day_v1' if p['node'] in ('compute-0-14','compute-0-18') else 'cpu_analysis_general_nodes_v1'
    names=('quota_provider.py','contract.py')
    if namespace in ('cpu_packed_day_v1','cpu_analysis_day_v1'):names+=('quota_origin.json',)
    for name in names:refs.append(Q.pin(Q.REPO/'workflows/data_v1_final/execution'/namespace/name))
    return unique(refs)
