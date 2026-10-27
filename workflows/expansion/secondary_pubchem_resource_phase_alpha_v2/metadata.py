"""Unsigned Alpha-login metadata candidates; no queue, DATA or ordinal claims."""
import argparse,copy,json
from pathlib import Path
from secondary_cpu_queue_v1 import common as Q
from secondary_pubchem_screening_alpha_v1 import contracts as C
from . import phase as A


def merge(values):
    out={}
    for r in values:
        Q.normalized(r);Q.need(r['path'] not in out or out[r['path']]==r,'NO_CONFLICTING_METADATA_PINS');out[r['path']]=r
    return list(out.values())


def pin_metadata(path,receipt=False):
    path=Q.literal(path);Q.need(path.suffix=='.json' and path.stat().st_size<=2<<20
        and ((Q.ROOT/'control' in path.parents) or (receipt and Q.ROOT/'artifacts' in path.parents and path.name=='receipt.json')),
        'NAMED_SMALL_CONTROL_METADATA_OR_QA_RECEIPT_ONLY_NO_DATA_BODY')
    return Q.ref(path)


def main():
    Q.login();p=argparse.ArgumentParser(description=__doc__);p.add_argument('--phase',choices=('QA0','FULL_SHARD'),required=True)
    for name in ('original-plan','failed51-accounting','qa0-receipt','qa0-accounting','claim-absence-review','stage-output','startup-proof','plan-path','scope-review','output'):
        p.add_argument('--'+name,type=Path,required=name in ('original-plan','failed51-accounting','stage-output','startup-proof','plan-path','output'))
    p.add_argument('--node',required=True);p.add_argument('--wall-seconds',type=int);a=p.parse_args()
    out=Q.literal(a.output);Q.need(Q.ROOT/'control' in out.parents and not out.exists(),'NEW_SMALL_CONTROL_OUTPUT_ONLY');out.mkdir(parents=True,mode=0o700)
    Q.need(Q.literal(a.original_plan)==Q.ROOT/'control/readonly_specs/pubchem_C_shard_0051_v1/plan.json','EXACT_REAL_ORIGINAL51_PLAN_LOCATOR')
    original_ref=pin_metadata(a.original_plan);old=Q.load_ref(original_ref);plan=copy.deepcopy(old)
    Q.need(old['mode']=='full_shard' and old['schema']==C.MODES['full_shard']['plan'] and old['shard_index']==51
        and old['first_part']==old['last_part']==51 and old['first_ordinal']==12750001 and old['last_ordinal']==13000000,
        'EXACT_ORIGINAL51_SMALL_PLAN_METADATA_ONLY')
    prior_review=Q.load_ref(old['root_review_reference'])
    Q.need(prior_review['schema']=='EXACT_SECONDARY_BOUNDED_READONLY_ROOT_REVIEW_V1'
        and prior_review['status']=='APPROVED_FOR_EXACT_STAGE' and prior_review['reviewer']=='root'
        and prior_review['actual_profile_equivalence_and_cost_reviewed'] is True
        and prior_review['scope_parameters']==old['scope_parameters'] and prior_review['execution_argv']==old['execution_argv'],
        'ACTUAL_PREVIOUS_ROOT_REVIEWED51_METADATA_NOT_A_NEW_SCIENCE_AUTHORITY')
    body_paths={r['path'] for r in old['data_references']}
    Q.need(str(a.original_plan) not in body_paths,'NO_DATA_AS_METADATA_INPUT');sources=list(old['source_references'])+A.sources()+[original_ref]
    failed_ref=pin_metadata(a.failed51_accounting);failed=Q.load_ref(failed_ref);parents=merge([*old['parent_evidence_references'],failed_ref,failed['raw_sacct_reference']])
    A.terminal(failed_ref,'1884853',parents,False)
    phase=a.phase;spec=A.spec(phase);wall=a.wall_seconds if a.wall_seconds is not None else (600 if phase=='QA0' else old['wall_seconds'])
    cap=(2<<30) if phase=='QA0' else old['output_cap_bytes'];output=Q.literal(a.stage_output);startup=Q.literal(a.startup_proof)
    Q.need(Q.ROOT/'artifacts' in output.parents and not output.exists() and not startup.exists() and a.node in Q.NODES,'FRESH_REGISTERABLE_OUTPUT_PROOF_ACTUAL_ALLOWED_NODE')
    plan.update(schema=spec['plan'],producer_key=spec['key'],scope_key=spec['key'],stage=spec['stage'],scope_mode=spec['scope_mode'],
        performance_profile=False,pilot=False,kind='analysis',resource_phase=phase,node=a.node,cpus=16,memory_policy=Q.POLICY,
        wall_seconds=wall,output_cap_bytes=cap,output_directory=str(output),startup_proof_path=str(startup),
        data_references=[] if phase=='QA0' else old['data_references'],historical_original51_plan_reference=original_ref)
    plan['scope_parameters']=A.parameters(plan);plan_path=Q.literal(a.plan_path)
    Q.need(Q.ROOT/'control' in plan_path.parents and not plan_path.exists(),'SAME_EXACT_NEW_PLAN_LOCATOR_ACROSS_CANDIDATE_AND_FINALIZE')
    plan.pop('root_review_reference',None)
    plan['execution_argv']=[plan['python'],'-B','-m',A.module(phase),'--plan',str(plan_path),'--startup-proof',str(startup)]
    change={'schema':'ROOT_PUBCHEM_FIXTURE_ORDER_ONLY_CHANGE_V2','approved':False,'resource_phase':phase,
        'historical_failure_exact_cause':'UNKNOWN_NOT_PERSISTED','scientific_code_or_threshold_or_once_changed':False,
        'original_runtime_unchanged':True,'fixtures_before_Budget':True,'failed51_accounting_reference':failed_ref,
        'qa0_receipt_reference':None,'qa0_accounting_reference':None,'claim_absence_review_reference':None}
    if phase=='FULL_SHARD':
        Q.need(a.qa0_receipt and a.qa0_accounting and a.claim_absence_review,'NO_FUTURE_QA_OR_CLAIM_ABSENCE_REFS')
        qr=pin_metadata(a.qa0_receipt,receipt=True);qa=Q.load_ref(qr);ar=pin_metadata(a.qa0_accounting);account=Q.load_ref(ar);absence=pin_metadata(a.claim_absence_review)
        parents=merge([*parents,qr,ar,account['raw_sacct_reference'],absence,qa['startup_proof_reference'],qa['plan_reference']]);A.terminal(ar,qa['job_id'],parents,True)
        change.update(qa0_receipt_reference=qr,qa0_accounting_reference=ar,claim_absence_review_reference=absence)
    sources=merge([*sources,*parents]);Q.need(not body_paths.intersection(r['path'] for r in sources),'ALL_SCIENTIFIC_DATA_REMAIN_LOCATORS_ONLY')
    plan['source_references']=sources;plan['parent_evidence_references']=parents
    review={k:plan[k] for k in ('scope_key','scope_parameters','stage','endpoint','uid','run_root','node','cpus','memory_policy','kind','pilot',
        'wall_seconds','output_cap_bytes','execution_argv','data_references','parent_evidence_references','scope_mode','performance_profile')}
    review.update(schema='EXACT_SECONDARY_BOUNDED_READONLY_ROOT_REVIEW_V1',status='ROOT_REVIEW_REQUIRED',reviewer='UNSIGNED',
        proposed_runtime_status='APPROVED_FOR_EXACT_STAGE',approved_source_references=sources,actual_profile_equivalence_and_cost_reviewed=True,
        root_review_reason=None,resource_phase_change=change)
    if not a.scope_review:
        Q.write_new(out/'root_review_candidate.json',review);Q.write_new(out/'plan_candidate.json',plan)
        Q.write_new(out/'candidate_notice.json',{'plan_is_not_executable':True,'root_review_reference_not_fabricated':True,
            'Root_must_approve_exact_review_and_resource_phase_change':True,'final_plan_locator':str(plan_path),
            'finalize_command':'repeat exact arguments and --plan-path, add --scope-review ACTUAL, use another new --output directory'})
        return
    scope_ref=pin_metadata(a.scope_review);approved=Q.load_ref(scope_ref);Q.need(approved['status']=='APPROVED_FOR_EXACT_STAGE' and approved['reviewer']=='root'
        and approved['resource_phase_change']==dict(change,approved=True),'INDEPENDENT_ROOT_SCOPE_AND_RESOURCE_CHANGE_APPROVAL')
    for key,value in review.items():
        if key not in ('status','reviewer','proposed_runtime_status','root_review_reason','resource_phase_change'):
            Q.need(approved[key]==value,'EXACT_NEW_RESOURCE_PHASE_ROOT_REVIEW_FIELD:'+key)
    plan['root_review_reference']=scope_ref;plan_path.parent.mkdir(parents=True,exist_ok=True);Q.write_new(plan_path,plan)
    print(json.dumps({'plan_reference':Q.ref(plan_path),'root_review_reference':Q.ref(a.scope_review),'submitted':False,'scientific_DATA_read':False}))


if __name__=='__main__':main()
