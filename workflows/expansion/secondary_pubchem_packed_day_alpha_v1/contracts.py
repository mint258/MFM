"""One fixed Alpha32 day protocol; current actual Root cutover is mandatory."""
import hashlib,json,os,re,time
from pathlib import Path
from secondary_cpu_queue_v1 import common as Q
from secondary_pubchem_screening_alpha_v1 import contracts as OLD,materialize_shards as M
ROOT=Q.ROOT;HERE=ROOT/'code/secondary_pubchem_packed_day_alpha_v1';MODULE='secondary_pubchem_packed_day_alpha_v1.run'
KEY='pubchem_packed_day32_alpha_v1';SCHEMA='ALPHA_PUBCHEM_PACKED_DAY32_PLAN_V1';PROOF='ALPHA_ACTUAL_PACKED_DAY32_EXECUTION_PROOF_V1'
BASE=ROOT/'control/pubchem_packed_day32_alpha_v1';CPUS=32;WALL=86400;DRAIN=900
FILES=('__init__.py','contracts.py','runtime.py','resource.py','gate.py','probe.py','metadata.py','run.py','test_v1.py','source_inverse.py','README.md')

def data_ref(r):
    Q.need(isinstance(r,dict) and set(r)=={'path','bytes','sha256'} and type(r['bytes'])is int and r['bytes']>0
      and type(r['sha256'])is str and re.fullmatch('[0-9a-f]{64}',r['sha256']),'LARGE_DATA_POSITIVE_NONBOOL64HEX_NOT_SMALL_SOURCE')
    Q.literal(r['path']);return r

def merge(*groups):
    out={}
    for group in groups:
        for r in group:
            Q.normalized(r);Q.need(r['path'] not in out or out[r['path']]==r,'CONFLICTING_SOURCE_OR_SMALL_META_PIN');out[r['path']]=r
    return list(out.values())

def selection(unclaimed,assignments):
    Q.need(type(unclaimed)is list and unclaimed==sorted(set(unclaimed)) and all(type(i)is int and 0<=i<500 for i in unclaimed),'EXACT_OBSERVED_UNCLAIMED500_INDEX_SET')
    Q.need(type(assignments)is dict and len(assignments)==2,'TWO_EXPLICIT_PARENT_ASSIGNMENTS');seen=[]
    for token,row in assignments.items():
        Q.need(type(token)is str and re.fullmatch('[A-Za-z0-9_]+',token) and row['node'] in ('compute-0-1','compute-0-6')
          and row['cpus']==32 and type(row['cpus'])is int and type(row['indices'])is list
          and row['indices']==sorted(set(row['indices'])) and all(type(i)is int for i in row['indices']) and row['indices'],'FINITE_REAL_NODE32_NONEMPTY_ORIGINAL_DESCRIPTOR_LIST')
        seen.extend(row['indices'])
    Q.need(sorted(seen)==unclaimed and len(seen)==len(set(seen)),'NO_OVERLAP_EXTRA_OR_OMISSION_BETWEEN_TWO_DAY_PARENTS')
    return assignments

def cutover(ref):
    r=Q.load_ref(ref);Q.need(r['schema']=='ROOT_PUBCHEM_TWO_PACKED_DAY32_ACTUAL_CUTOVER_V1' and r['status']=='ROOT_APPROVED_ACTUAL_CUTOVER_NO_AUTO_RENEW'
      and r['reviewer']=='root' and r['endpoint']==Q.ENDPOINT and r['uid']==1264 and r['run_root']==str(ROOT), 'REAL_ROOT_ALPHA_CUTOVER_NOT_FUTURE_OR_OLD16_PROOF')
    original=Q.load_ref(r['original_grant_reference']);Q.need(original['schema']=='ROOT_APPROVED_PUBCHEM_C_CONTINUATION52_499_V3'
      and original['status']=='ROOT_APPROVED' and r['old_deadline_unix_seconds']==original['deadline_unix_seconds']
      and r['actual_cutover_unix_seconds']>=r['old_deadline_unix_seconds'] and r['old_source_grant_deadline_claims_or_results_modified'] is False
      and r['automatic_new_epoch_or_retry'] is False,'OLD_FINITE_GRANT_AND_DEADLINE_HISTORY_UNCHANGED')
    for key in ('predecessor_actual_ended_reference','fence_actual_ended_reference','actual_registry_and_claim_inventory_reference','new_actual_alpha32_day_authority_reference'):
        Q.load_ref(r[key])
    authority=Q.load_ref(r['new_actual_alpha32_day_authority_reference']);Q.need(authority['schema']=='ROOT_ACTUAL_USER_DAY_PACKING_ALPHA32_RESOURCE_REVIEW_V1'
      and authority['status']=='ROOT_APPROVED_FROM_ACTUAL_USER_DAY_INSTRUCTION' and authority['reviewer']=='root' and authority['endpoint']==Q.ENDPOINT
      and authority['uid']==1264 and authority['cpus']==32 and type(authority['cpus'])is int and authority['wall_seconds']==86400
      and authority['no_memory_or_exclusive_or_GPU'] is True and authority['old16_is_history_not32_proof'] is True
      and authority['science_or_finite500_or_once_or_quality_changed'] is False,'EXPLICIT_NEW32_USER_DAY_RESOURCE_INTERPRETATION_NOT_OLD16')
    Q.authority(authority['original_alpha16_authority_reference']['path'])
    original_user=authority['actual_Main_user_day_decision_origin_reference'];target=authority['actual_Alpha_user_day_decision_copy_reference'];Q.verify(target)
    Q.need(all(original_user[k]==target[k] for k in ('bytes','sha256')),'ACTUAL_MAIN_TO_ALPHA_USER_DAY_BYTES_EQUAL')
    decision=Q.load_ref(target);Q.need(decision['schema']=='USER_AUTHORIZED_DAY_PACKED_DATA_JOBS_V1' and decision['status']=='USER_AUTHORIZED'
      and decision['target_job_wall_seconds']==86400 and decision['minimum_allocated_cpus']==16 and decision['scientific_data_scope_or_recipe_or_quality_changed'] is False,
      'ACTUAL_USER_DAY_PACKING_DECISION_COPY_NOT_SELF_SIGNATURE')
    selection(r['actual_unclaimed_indices'],r['assignments']);return r

def parameters(plan):
    return {'original_full_shard_manifest_reference':plan['science']['full_shard_manifest_reference'],'assignment_token':plan['assignment_token'],
      'original_descriptor_indices':plan['descriptor_indices'],'requested_cpus':32,'wall_seconds':86400,'natural_drain_seconds':900,
      'whole_output_cap_bytes':plan['output_cap_bytes'],'pending_chemical_records':32,'same_original_kernel_funnel_typed_journal':True,
      'same_original_finite500_and_global_claim_namespace':True,'single_true_parent_no_child_Slurm_C0':True,'pool_release':False,'new_UFF_QM_training_calls':0}

def validate(plan):
    Q.need(plan['schema']==SCHEMA and plan['scope_key']==KEY and plan['endpoint']==Q.ENDPOINT and plan['uid']==1264
      and plan['run_root']==str(ROOT) and type(plan['cpus'])is int and plan['cpus']==32 and plan['node'] in ('compute-0-1','compute-0-6')
      and plan['wall_seconds']==86400 and plan['memory_policy']==Q.POLICY and plan['mode']=='full_shard'
      and type(plan['output_cap_bytes'])is int and (2<<30)<=plan['output_cap_bytes']<=(1<<40),'EXACT_ONE32_CPU_DAY_ALPHA_NEW_SCOPE')
    Q.need(plan['scope_parameters']==parameters(plan) and plan['source_or_science_or_claim_history_modified'] is False
      and plan['automatic_epoch_retry_or_submission'] is False and plan['full_source_pool_release_authorized'] is False,'ROOT_EXACT_SCOPE_AND_NO_RELEASE_OR_AUTOMATIC_RETRY')
    root=cutover(plan['cutover_review_reference']);a=root['assignments'][plan['assignment_token']]
    Q.need(plan['descriptor_indices']==a['indices'] and plan['node']==a['node'],'ONLY_ACTUAL_REVIEWED_DISJOINT_INDEX_ASSIGNMENT')
    manifest=M.validate(Q.load_ref(plan['science']['full_shard_manifest_reference']));Q.need(manifest['status']=='ROOT_FROZEN_EXCLUSIVE_SUBMISSION_MANIFEST'
      and manifest['profile_receipt_reference']==plan['science']['accepted_profile_receipt_reference']
      and manifest['profile_output_budget_reference']==plan['science']['profile_output_budget_reference'],'ORIGINAL_FROZEN500_AND_ORIGINAL_PROFILE_BUDGET')
    for r in plan['source_references']:Q.verify(r)
    for r in plan['data_references']:data_ref(r)
    Q.need(not {r['path'] for r in plan['data_references']}&{r['path'] for r in plan['source_references']},'SCIENTIFIC_BODY_NOT_SMALL_SOURCE')
    return plan

def sources():return [*(Q.ref(HERE/n) for n in FILES),Q.ref(Q.PACKAGE/'common.py'),Q.ref(Q.PACKAGE/'probe.py')]

def parent_review(plan):
    r=Q.load_ref(plan['root_parent_review_reference']);candidate_ref=plan['candidate_plan_reference'];candidate=Q.load_ref(candidate_ref)
    Q.need(r['schema']=='ROOT_EXACT_ALPHA_PUBCHEM_DAY32_PARENT_REVIEW_V1' and r['status']=='APPROVED' and r['reviewer']=='root'
      and r['candidate_plan_reference']==candidate_ref and r['exact_scope']==plan['scope_parameters'],'INDEPENDENT_EXACT_ROOT_DAY32_PARENT_APPROVAL')
    stripped={k:v for k,v in plan.items() if k not in ('root_parent_review_reference','candidate_plan_reference')}
    stripped['source_references']=candidate['source_references'];Q.need(stripped==candidate
      and plan['source_references']==merge(candidate['source_references'],[plan['root_parent_review_reference'],candidate_ref]),'ONLY_EXACT_REVIEW_BINDINGS_ADDED_TO_FROZEN_PLAN')
    return r
