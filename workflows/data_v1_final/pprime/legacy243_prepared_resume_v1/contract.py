"""Exact failed Parent provenance; a closed preparation is not a C0 Parent."""
import csv,io,pathlib
from workflows.data_v1_final.pprime.legacy190_hash_io_recovery_v1.contract import *
from workflows.data_v1_final.pprime.legacy190_hash_io_recovery_v1 import contract as Before
from workflows.data_v1_final.pprime.formal_packed_sharded_day_v3 import root_metadata as Small

HERE=Q.REPO/'workflows/data_v1_final/pprime/legacy243_prepared_resume_v1'
MODULE='workflows.data_v1_final.pprime.legacy243_prepared_resume_v1.run'
FILES=('__init__.py','contract.py','adopt.py','io.py','run.py','metadata.py','README.md')
REQUIRED=(*Before.REQUIRED,'prepared_resume_authority_reference')
OLD_OUTPUT=BASE/'legacy190_append_hash_io_cpu14_20261030_v1'
HEADER={'path':str(OLD_OUTPUT/'prepare/prepared_generation_header.json'),'bytes':2065,
        'sha256':'f5f1a40784c9c7dce50c8f3971a067ccc35f2021aa6e90e594bdfd0c0d37a5b0'}
PARENT_KEYS=('receipt_reference','plan_reference','execution_plan_reference','proof_reference',
             'request_reference','submission_reference','accounting_reference','raw_sacct_reference')

def parameters(node,mode='ORIGINAL_WP5'):
    return dict(Before.parameters(node,mode),prepared_input_adoption='ACTUAL_FAILED_4525243_CLOSED_HEADER_V1',
      preparation_reexecuted=False,prior_consumed_records=16,prior_UNKNOWN_records_no_retry=6,
      software_working_budget_bytes=64<<30,RSS_limit_bytes=56<<30,
      MemAvailable_minimum_bytes=4<<30,MemAvailable_minimum_node_fraction=.15,
      resource_version='PPRIME_PRIVATE_RSS56_V3')

def parents(p,b):
    a=Small.small(p['prepared_resume_authority_reference'])
    need(a['schema']=='ROOT_ACTUAL_PPRIME_CLOSED_PREPARATION_RESUME_AUTHORITY_V1'
      and a['status']=='APPROVED_READONLY_PREPARED_REUSE_FAILED_PARENT_NO_RETRY'
      and a['reviewer']=='root' and a['uid']==1278 and a['endpoint']=='202.38.247.57:22',
      'ROOT_EXACT_FAILED_PARENT_PREPARATION_ADOPTION_NOT_C0')
    e=a['original_parent'];need(set(e)==set(PARENT_KEYS),'EXACT_FAILED_PARENT_EIGHT_REFERENCES')
    values={k:Small.small(e[k]) for k in PARENT_KEYS if k!='raw_sacct_reference'}
    r,old,runtime,proof,req,sub,account=(values[k] for k in PARENT_KEYS[:-1])
    rows=list(csv.DictReader(io.StringIO(Small.small(e['raw_sacct_reference'],False).decode()),delimiter='|'))
    actual=[v for v in rows if v.get('JobIDRaw')=='4525243'];need(len(actual)==1,'ONE_REAL_PARENT_SACCT_ROW')
    actual=actual[0]
    need(actual['State']=='FAILED' and actual['ExitCode']=='3:0' and int(actual['AllocCPUS'])==16 and actual['UID']=='1278'
      and actual['NodeList']==req['node']=='compute-0-14'
      and Small.contains(account,e['raw_sacct_reference']),'REAL_4525243_FAILED3_RETAINED_NEVER_FAKE_C0')
    need(str(proof['job_id'])==str(sub['job_id'])==str(r['job_id'])=='4525243'
      and proof['uid']==sub['uid']==r['uid']==1278 and proof['execution_admission_granted'] is True
      and sub['sbatch_returncode']==0 and proof['request']==sub['request']==req
      and proof['request_reference']==sub['request_reference']==e['request_reference']
      and req['scope_key']==KEY and req['cpus']==16 and req['kind']=='qm' and req['wall_seconds']==WALL
      and req['memory_policy']=='SLURM_DEFAULT_UNSPECIFIED' and req['pilot'] is False
      and req['execution_argv']==[Q.PY,'-B','-m',Before.MODULE,'--plan',e['plan_reference']['path'],
                                '--startup-proof',e['proof_reference']['path']]
      and e['plan_reference'] in req['source_references']
      and old['scope_parameters']==Before.parameters(req['node'])==req['scope_parameters']
      and r['plan_reference']==e['plan_reference'] and r['startup_proof_reference']==e['proof_reference'],
      'ORIGINAL_REAL_PLAN_REQUEST_PROOF_SUBMISSION_RECEIPT_CHAIN')
    need(old['schema']==runtime['schema']=='PPRIME_FORMAL_PACKED_DAY_PLAN_V1'
      and runtime['output_directory']==old['output_directory']==str(OLD_OUTPUT)
      and all(runtime[k]==v for k,v in old.items())
      and runtime['plan_path']==e['plan_reference']['path'] and runtime['proof_path']==e['proof_reference']['path']
      and runtime['prepared2000_reference']==a['prepared_header_reference']==HEADER
      and runtime['actual_ready_records']==100000,'EXACT_ACTUAL_READY_PLAN_HEADER_NOT_NEW_DOMAIN')
    for k in (*Before.REQUIRED,'source_context_reference','original_protocol_reference','candidate_protocol_reference',
              'retention_policy_reference','original_sprime_recipe_reference'):
        expected=p.get(k,b['pilot_plan'].get(k))
        # New resource/cost authorities belong to the new Parent; scientific and
        # population authorities remain exactly the failed Parent's inputs.
        if k not in RESOURCE:need(old[k]==expected,'UNCHANGED_ORIGINAL_SCIENTIFIC_AUTHORITY:'+k)
    h=Small.small(HEADER)
    need(h['schema']=='PPRIME_FORMAL_READY_PREFIX_INPUT_HEADER_V1' and h['records']==100000 and h['MIDs']==50000
      and h['all_first2_original_seed']==20261025 and h['native_invokes']==0 and h['final_Common'] is False
      and h['source_index_input_refs']==b['population'],'ACTUAL_CLOSED50K100K_ORIGINAL_FIRST2_INPUT_HEADER')
    need(r['schema']=='PPRIME_FORMAL_PACKED_DAY_RECEIPT_V1' and r['prepared_header_reference']==HEADER
      and r['requested_ready_records']==100000 and r['dispatched_records']==16 and r['completed_records']==10
      and r['observed_native_returns']==120 and len(r['failures'])==6
      and len({v['record_id'] for v in r['failures']})==6
      and all(v['status']=='UNKNOWN_CONSUMED_NO_RETRY' for v in r['failures']) and r['scientific_PASS'] is False
      and r['final_Common_or_training_admission'] is False,'ACTUAL16_CONSUMED10_CLOSED6_UNKNOWN_NOT_SUCCESS_UPGRADE')
    index=a['closed_record_index_reference']
    need(index==r['closed_record_index_reference'] and index['path']==str(OLD_OUTPUT/'closed_record_index.DATA.jsonl')
      and a['global_physical_once_root']==str(ledger(old)/'physical_records_v1')
      and e['receipt_reference']['path']==str(OLD_OUTPUT/'receipt.json')
      and e['execution_plan_reference']['path']==str(OLD_OUTPUT/'actual_ready_execution_plan.json'),
      'EXACT_PRIOR_INDEX_OUTPUT_AND_ORIGINAL_GLOBAL_ONCE_ROOT')
    audit=Small.small(h['audit_membership_reference']);reuse=Small.small(h['pilot_reuse_reference'])
    need(audit['schema']=='WP5_STRATIFIED_RECORD_AUDIT_V1' and audit['status']=='AUDIT_MEMBERSHIP_CLOSED'
      and audit['audit_policy']==old['retention_policy_reference'],'ORIGINAL_CLOSED_STABLE_AUDIT_POLICY')
    need(reuse['schema']=='PPRIME_FORMAL_ORIGINAL2000_REUSE_CPU_QA_V1' and reuse['records']==2000
      and reuse['successful']==1989 and reuse['scientific_failures_consumed']==11
      and reuse['all_physical_claims_revalidated'] is True and reuse['reinvocations']==0
      and reuse['result_reference']==b['pilot_result'],'ORIGINAL2000_REUSE_INCLUDING11_FAILURES')
    data=unique([h['index_reference'],h['source_audit_reference'],P.triple(audit['selected_records']),index])
    refs=unique([p['prepared_resume_authority_reference'],*e.values(),HEADER,
                 h['audit_membership_reference'],h['pilot_reuse_reference']])
    return dict(authority=a,old=old,receipt=r,header=h,audit=audit,reuse=reuse,data=data,refs=refs,actual=actual)

def bootstrap(p):
    b=Before.bootstrap(p);adoption=parents(p,b)
    return dict(b,adoption=adoption,data=unique([*b['data'],*adoption['data']]),refs=unique([*b['refs'],*adoption['refs']]))

def sources(p):
    extra=[Q.pin(HERE/n) for n in FILES]
    parent=HERE.parent
    for rel in ('formal_packed_sharded_day_v3/resource.py','formal_packed_sharded_day_v3/contract.py',
                'formal_packed_sharded_day_v3/root_metadata.py','formal_packed_sharded_day_v2/contract.py'):
        extra.append(Q.pin(parent/rel))
    return unique([*Before.sources(p),*extra])
