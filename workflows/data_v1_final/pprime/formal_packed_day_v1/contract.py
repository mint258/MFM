"""User-released generation candidates, not final Common or training admission."""
import hashlib,json,pathlib
from workflows.data_v1_final.pprime.pilot2000_execution_day_v1 import contract as Original
Q=Original.Q;P=Original.P;O=Original.O;M=Original.M
need=Original.need;meta=Original.meta;unique=Original.unique
KEY='pprime_formal_packed_day_v1';MODULE='workflows.data_v1_final.pprime.formal_packed_day_v1.run'
HERE=Q.REPO/'workflows/data_v1_final/pprime/formal_packed_day_v1'
FILES=('contract.py','io.py','prepare.py','worker.py','run.py','metadata.py','test_v1.py','source_origin.json','README.md')
BASE=Q.ROOT/'artifacts/pprime_formal_packed_day_v1'
CAP=64<<30;WALL=86400;WORKER_CAP=Original.WORKER_CAP;RAW_CAP=Original.RAW_CAP;RESULT_CAP=Original.RESULT_CAP;PARENT_CAP=12<<30
NODES=tuple('compute-0-'+str(i) for i in range(11,20));MAX_RECORDS=100000
record_once_key=Original.record_once_key;ledger=Original.ledger
RESOURCE=('resource_authority_reference','cost_decision_reference','quota_provider_review_reference','quota_provider_identity_reference','root_carveout_review_reference')
REQUIRED=('pilot_execution_plan_reference','pilot_closure_reference','user_release_reference','generation_release_reference',*RESOURCE)

def parameters(node,mode='ORIGINAL_WP5'):
    need(node in NODES and mode=='ORIGINAL_WP5','ORIGINAL_WP5_ONLY_CURRENT_CPU_NODE')
    return {'generation_domain':'CURRENT_COMPLETE_OLD_SPRIME_CANDIDATES_NOT_FINAL_COMMON','maximum_new_records':MAX_RECORDS,
      'maximum_native_calls':MAX_RECORDS*12,'fixed_first2_seed':20261025,'tasks':list(O.TASKS),'timeout_seconds':900,
      'workers':16,'maximum_pending_records':16,'internal_export_batch_records':128,'wall_seconds':WALL,'node':node,
      'output_cap_bytes':CAP,'minimum_all12_success_fraction':.9945,'automatic_native_retry':False,
      'parent_preparation_export_metadata_reserve_bytes':PARENT_CAP,
      'reuse_original2000_including_scientific_failures':True,'N1_and_unavailable':'PENDING_NOT_EXCLUDED',
      'new_QA_calls':0,'precision_mode':'ORIGINAL_WP5','final_Common_or_training_admission':False,'source_methods':3}

def fraction_ok(successful,total):
    need(type(successful)is int and type(total)is int and 0<=successful<=total and total>0,'EXACT_SUCCESS_COUNT_DENOMINATOR')
    return successful*2000>=1989*total

def authority(p):
    u=meta(p['user_release_reference']);r=meta(p['generation_release_reference'])
    need(u['schema']=='USER_AUTHORIZED_PPRIME_FORMAL_GENERATION_RELEASE_V1'
      and u['status']=='USER_AUTHORIZED_START_FORMAL_GENERATION' and u['minimum_all12_success_fraction']==.9945
      and u['formal_generation_authorized'] is True and u['all_other_scientific_quality_thresholds_unchanged'] is True
      and u['original_WP5_versions_keywords_precision_seeds_and_timeout_unchanged'] is True
      and u['existing_original_pilot_once_outcomes_preserved_without_reinvocation'] is True
      and u['additional_QM_diagnostics_authorized'] is False,'EXACT_USER9945_GENERATION_NOT_DIAGNOSTIC_PRECISION')
    need(r['schema']=='ROOT_APPLIED_USER_PPRIME_9945_GENERATION_RELEASE_V1'
      and r['status']=='APPROVED_START_FORMAL_GENERATION' and r['reviewer']=='root'
      and r['user_authority_reference']==p['user_release_reference']
      and r['actual_original2000_formal_closure_reference']==p['pilot_closure_reference']
      and r['minimum_ratio_numerator']==1989 and r['minimum_ratio_denominator']==2000
      and r['other_original_pilot_gates_pass'] is True,'ACTUAL_ROOT_APPLIED_GENERATION_RELEASE')
    actual=u['actual_original_pilot']
    need(actual['job_id']=='4525179' and actual['requested_conformers']==actual['terminal_conformers']==2000
      and actual['all12_successful_conformers']==1989 and actual['parent_state']=='COMPLETED'
      and actual['parent_exit_code']=='0:0' and fraction_ok(1989,2000),'EXACT_EXISTING_PILOT_1989_OF2000')
    need(u['user_confirmation_required_above_comparable_pilot_estimate_multiple']==2
      and u['comparable_pilot_execution_estimate_core_seconds_per_conformer']==9.328
      and u['separate_pilot_preparation_and_Source_estimate_core_seconds_per_conformer']==2.144,'EXACT_COMPARABLE_COST_RULE')
    return u,r

def bootstrap(p):
    authority(p);oldplan=meta(p['pilot_execution_plan_reference']);closed=meta(p['pilot_closure_reference'])
    need(closed['schema']=='PPRIME2000_ACTUAL_TERMINAL_PILOT_CLOSURE_V1'
      and closed['plan_reference']==p['pilot_execution_plan_reference'] and closed['actual_parent']['JobIDRaw']=='4525179'
      and closed['actual_parent']['State']=='COMPLETED' and closed['actual_parent']['ExitCode']=='0:0'
      and closed['requested_record_denominator']==2000 and closed['WP5_record_cost_gate_pass'] is True
      and closed['one_percent_quality_mask_gate_waived'] is False,'REAL_PILOT_C0_OTHER_GATES_NOT_REWRITTEN')
    need(oldplan['precision_mode']=='ORIGINAL_WP5','NO_DIAGNOSTIC_TIGHT_PRECISION_PROMOTION')
    gates=closed['all_original_pilot_gate_results_including_WP5_record_cost']
    need(set(gates)=={'parent_completed_zero','complete_2000_conformer_pilot','compute_closed_without_errors',
      'sixteen_workers_closed_and_joined','record_success_at_least_99_5_percent','allocated_seconds_within_1_5x_wp5'}
      and all(v is True for k,v in gates.items() if k!='record_success_at_least_99_5_percent'),
      'ONLY_EXACT_USER_SUCCESS_FLOOR_OVERRIDE_OTHER_ORIGINAL_GATES_PASS')
    old,new,diff,context,pilot,header,pairs,data,parents=Original.inputs(oldplan)
    pp=meta(header['plan_reference'])
    _,_,_,_,_,_,_,sprime,population,val,olddata,parents0=P.parents(pp)
    refs=unique([*parents,*parents0,*[p[k] for k in REQUIRED],p['pilot_execution_plan_reference'],
      closed['accounting_reference'],closed['raw_sacct_reference'],closed['startup_proof_reference']])
    # This is a producer locator only. The result and terminal index remain DATA.
    result=P.triple(closed['result_reference']);data=unique([*data,*olddata,result])
    for name in ('record_index',):
        matches=[x for x in pilot['large_authority_pins']+pilot['small_authority_pins'] if x['path']==pilot[name]]
        need(len(matches)==1,'ORIGINAL_FULL_CANONICAL_LOCATOR:'+name);data=unique([*data,P.triple(matches[0])])
    return {'pilot_plan':oldplan,'old':old,'context':context,'pilot':pilot,'header':header,'pilot_pairs':pairs,
      'sprime':sprime,'population':population,'val':val,'data':data,'refs':refs,'pilot_result':result}

def precision(plan,review):
    authority(plan)
    need(plan['precision_mode']=='ORIGINAL_WP5' and review['formal_generation_authorized'] is True
      and review['user_release_reference']==plan['user_release_reference']
      and review['generation_release_reference']==plan['generation_release_reference']
      and review['original_WP5_precision_only'] is True and review['minimum_record_success_rate']==.9945
      and review['maximum_native_invocations']==MAX_RECORDS*12,'EXACT_FORMAL_ROOT_SCOPE_NOT_PILOT_OR_QA_PERMISSION')
    need(plan.get('user_precision_decision_reference') is None,'NO_NEW_PRECISION_ALLOWED')
    return plan['original_protocol_reference']

def sources(p):
    b=bootstrap(p);refs=[*Original.sources(b['pilot_plan']),*[Q.pin(HERE/n) for n in FILES]]
    origin=meta(Q.pin(HERE/'source_origin.json'))
    for r in origin['sources']:need(Q.pin(r['path'])==r,'ACTUAL_FROZEN_ORIGINAL_PILOT_SOURCE_BYTES');refs.append(r)
    r=origin['coordinate_source'];need(Q.pin(r['path'])==r,'ORIGINAL_COORDINATE_SHA_SOURCE');refs.append(r)
    return unique(refs)
