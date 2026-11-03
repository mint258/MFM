"""Metadata-only contract; the old claim/FAILED Parent and every old row survive."""
import os,re
from pathlib import Path
from secondary_cpu_queue_v1 import common as Q
from secondary_pubchem_screening_alpha_v1 import contracts as OLD
from secondary_pubchem_packed_day_alpha_v1 import contracts as DAY

NAME='pubchem_consumed_partial_tail_alpha_v2'
HERE=Q.ROOT/'code'/NAME
MODULE=NAME+'.run'
PROOF='ALPHA_CONSUMED_PARTIAL_TAIL_STARTUP_V1'
FILES=('__init__.py','contract.py','metadata.py','resource.py','gate.py','runtime.py','run.py','README.md')
KEYS=('accepted','chemReject','technicalUnresolved')
TAILS=(
 {'index':363,'parent':'1885075','node':'compute-0-1','first':90750001,'last_prefix':90866289,'last':91000000,
  'prefix_rows':116289,'tail_rows':133711,'counts':{'accepted':103364,'chemReject':12912,'technicalUnresolved':13},
  'checkpoint_reference':{'path':str(Q.ROOT/'artifacts/pubchem_packed_day32_alpha_v1/parent_a_day01/chunk_000363/checkpoint.json'),
   'bytes':2836,'sha256':'5bb970f67adb0f7bae0e41b9e1940bbf640de74a0712f0f606d6041c978de567'}},
 {'index':412,'parent':'1885076','node':'compute-0-6','first':103000001,'last_prefix':103233073,'last':103250000,
  'prefix_rows':233073,'tail_rows':16927,'counts':{'accepted':225838,'chemReject':7233,'technicalUnresolved':2},
  'checkpoint_reference':{'path':str(Q.ROOT/'artifacts/pubchem_packed_day32_alpha_v1/parent_b_day01/chunk_000412/checkpoint.json'),
   'bytes':2834,'sha256':'6d9b0710a0fa477fd6d7d137e75ef32889d0c1f05cf9e076786872af1fa99b3d'}})
INTENT=Q.ROOT/'control'/'pubchem_consumed_partial_tail_alpha_v1'/'original363_412_unread_tail_intent.json'

def sources():return [Q.ref(HERE/name) for name in FILES]
def merge(*groups):
    result={}
    for group in groups:
        for ref in group:
            if ref['path'] in result:Q.need(result[ref['path']]==ref,'CONFLICTING_SOURCE_REFERENCE')
            result[ref['path']]=ref
    return [result[k] for k in sorted(result)]
def locator(ref):
    Q.need(set(ref)=={'path','bytes','sha256'} and type(ref['bytes'])is int and ref['bytes']>0
      and re.fullmatch('[0-9a-f]{64}',ref['sha256']) and Path(ref['path']).is_relative_to(Q.ROOT/'artifacts'),'STRICT_DATA_LOCATOR_NO_LOGIN_BODY')
    Q.literal(ref['path']);return ref
def checkpoint(spec):
    ref=spec['checkpoint_reference'];value=Q.load_ref(ref)
    r=value['result'];member=value['original_descriptor']
    Q.need(value['schema']=='ALPHA_PACKED_DAY32_ORIGINAL_DESCRIPTOR_CHECKPOINT_V1'
      and value['status']=='PARTIAL_ORIGINAL_DESCRIPTOR_HOLD_NO_AUTO_RETRY'
      and value['actual_parent_job_id']==spec['parent'] and member=={'shard_index':spec['index'],'first_part':spec['index'],
      'last_part':spec['index'],'first_ordinal':spec['first'],'last_ordinal':spec['last']}
      and value['expected_rows']==250000 and value['unread_rows']==spec['tail_rows']
      and value['source_row_conservation'] is False and value['technical_unknown_is_chemical_exclusion'] is False
      and r['completed_rows']==r['dispatched_rows']==r['actual_input_rows_dispatched']==spec['prefix_rows']
      and r['last_completed_ordinal']==r['last_dispatched_ordinal']==spec['last_prefix']
      and r['counts']==spec['counts'] and r['journal_precedes_parquet'] is True
      and r['technical_unknown_is_chemical_exclusion'] is False,'EXACT_ORIGINAL_CLOSED_PREFIX_AND_UNREAD_TAIL')
    for k in ('features','full_dispatch_and_result_journal'):locator(r[k])
    claim=Q.load_ref(value['original_claim_reference'])
    Q.need(claim['job_id']==spec['parent'] and claim['uid']==1264 and claim['node']==spec['node']
      and claim['range']==member and claim['plan_reference']==value['actual_parent_plan_reference']
      and claim['automatic_retry_or_release'] is False,'ORIGINAL_CONSUMED_CLAIM_NOT_RECREATED')
    plan=DAY.validate(Q.load_ref(value['actual_parent_plan_reference']));DAY.parent_review(plan)
    Q.need(plan['node']==spec['node'] and spec['index'] in plan['descriptor_indices']
      and plan['science']['full_shard_manifest_reference']==claim['manifest_reference'],'OLD_PARENT_SCIENCE_PLAN')
    return value,plan

def validate(plan):
    Q.need(plan['schema']=='ALPHA_CONSUMED_PARTIAL_TAIL_PLAN_V1' and plan['status']=='READY'
      and plan['endpoint']==Q.ENDPOINT and plan['uid']==1264 and plan['mode']=='consumed_partial_tail'
      and plan['cpus'] in (16,32,64) and type(plan['cpus'])is int and plan['node'] in Q.NODES
      and 1800<=plan['wall_seconds']<=86400 and plan['wall_seconds']%60==0
      and 4<<30<=plan['output_cap_bytes']<=16<<30 and plan['software_budget_bytes']==64<<30
      and plan['rss_stop_bytes']==56<<30 and plan['intent_path']==str(INTENT)
      and plan['tail_specs']==list(TAILS) and plan['tail_rows']==150638
      and plan['pool_release'] is False and plan['old_results_modified'] is False
      and plan['python']==str(Q.ROOT/'chemprop_compatible_v2/bin/python'),'EXACT_TWO_CONSUMED_TAILS_RESOURCE_SCOPE')
    out=Q.literal(plan['output_directory'])
    Q.need(out.is_relative_to(Q.ROOT/'artifacts'/NAME) and out!=Q.ROOT/'artifacts'/NAME
      and re.fullmatch('[A-Za-z0-9_]{1,80}',plan['job_name'])
      and plan['execution_argv']==[plan['python'],'-B','-m',MODULE,'--plan',plan['plan_path'],'--startup-proof',plan['startup_proof_path']]
      and Path(plan['startup_proof_path']).parent==Path(plan['plan_path']).parent,'EXACT_FRESH_PRIMARY_AND_OUTPUT')
    Q.need(plan['new_source_references']==sources(),'EXACT_TRANSFERRED_EIGHT_NEW_SOURCE_FILES')
    for ref in plan['source_references']:Q.verify(ref)
    Q.verify(plan['old_accounting_reference']);Q.verify(plan['storage_scope_review_reference']);Q.verify(plan['cost_gate_reference']);return plan
def review(plan):
    r=Q.load_ref(plan['root_review_reference'])
    Q.need(r['schema']=='ROOT_REVIEWED_EXACT_PUBCHEM_TAIL_PLAN_V1' and r['status']=='APPROVED' and r['reviewer']=='root'
      and r['candidate_reference']==plan['candidate_reference']
      and r['old_claims_and_failures_unchanged'] is True and r['only_exact_unread_suffixes'] is True,'INDEPENDENT_ROOT_EXACT_TAIL_REVIEW')
    candidate=Q.load_ref(plan['candidate_reference']);expected=dict(candidate,status='READY',
      candidate_reference=plan['candidate_reference'],root_review_reference=plan['root_review_reference'])
    Q.need(plan==expected,'ONLY_REVIEW_BINDINGS_ADDED_TO_CANDIDATE')
    return r
