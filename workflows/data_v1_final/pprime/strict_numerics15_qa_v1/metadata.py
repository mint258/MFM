"""Small metadata only: preapproval draft or real-decision independent review."""
import argparse,copy,pathlib
from . import contract as C
Q=C.Q


def draft(request_path,out):
    v=Q.load(request_path);Q.need(v['schema']=='ROOT_REQUESTED_PPRIME_STRICT_NUMERICS15_QA_V1' and v['status']=='REQUESTED_FOR_REVIEW' and v['requested_by']=='root','ROOT_REQUEST_IS_NOT_USER_APPROVAL')
    plan={'schema':'PPRIME_STRICT_NUMERICS15_QA_PLAN_V1','scope_parameters':C.PARAMETERS,'output_cap_bytes':C.CAP,'wall_seconds':7200,
        **{k:v[k] for k in ('native_control_receipt_reference','native_control_accounting_reference','original_protocol_reference','candidate_protocol_reference',
            'resource_authority_reference','cost_decision_reference','output_directory')},'user_decision_reference':v.get('user_decision_reference')}
    _,_,diff,_,_,prepared_ref,cases,data,parents,prior=C.parents(plan)
    plan.update(original_prepared_reference=prepared_ref,case_sources=cases,data_references=data)
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.contract import validate_authority
    validate_authority(v['resource_authority_reference'],read_small=Q.read_small)
    cost=C.meta(v['cost_decision_reference']);Q.need(cost['status']=='USER_AUTHORIZED' and cost['on_overrun']=='REPORT_AND_CONTINUE' and cost['scientific_quality_thresholds_unchanged'] is True,'CURRENT_COST_AUTHORITY_NOT_NUMERICAL_APPROVAL')
    out=pathlib.Path(out);output=pathlib.Path(v['output_directory']);Q.need(out.is_absolute() and output.is_absolute() and '..' not in out.parts and '..' not in output.parts
        and Q.ROOT/'control' in out.parents and not out.exists() and C.BASE in output.parents and C.LEDGER not in output.parents and output!=C.LEDGER and not output.exists()
        and not any(p.is_symlink() for p in (out,*out.parents,output,*output.parents)),'FRESH_CONTROL_AND_NEW_QA_OUTPUT')
    authorized=plan['user_decision_reference'] is not None
    if authorized:C.require_user(plan)
    sources=C.unique([*(Q.pin(C.HERE/n) for n in C.FILES),*(Q.pin(C.P.HERE/n) for n in C.P.FILES),*prior,*parents,Q.pin(request_path),
        v['resource_authority_reference'],v['cost_decision_reference'],*([plan['user_decision_reference']] if authorized else [])])
    for ref in sources:Q.need(ref['path'] not in {d['path'] for d in data} and Q.pin(ref['path'])==ref,'SMALL_SOURCE_ONLY_NO_SCIENTIFIC_BODY_ON_LOGIN')
    out.mkdir(parents=True,exist_ok=False,mode=0o700);pr=Q.write_new(out/'plan.json',plan);sources=C.unique([*sources,pr])
    fields={'kind':'qm','scope_key':C.KEY,'scope_parameters':C.PARAMETERS,'pilot':False,'wall_seconds':7200,'estimated_peak_output_bytes':C.CAP,
        'source_status_stage':C.STAGE,'execution_argv':[Q.PY,'-B','-m',C.MODULE,'--plan',str(out/'plan.json'),'--startup-proof','__ROOT_STARTUP_PROOF__']}
    if not authorized:
        return Q.write_new(out/'draft_receipt.json',{'schema':'PPRIME_STRICT_NUMERICS15_QA_DRAFT_V1','status':'USER_APPROVAL_PENDING_NO_RUNNABLE_SPEC',
            'plan_reference':pr,'protocol_diff':diff,'maximum_new_QM_calls':15,'stage_fields_for_review_only':fields,'source_references':sources,'data_references':data,
            'resource_authority_reference':v['resource_authority_reference'],'user_decision_reference':None,'root_review_template_reference':None,
            'fresh_request_required_after_actual_user_approval':True,'scientific_bodies_opened_or_hashed':False,'Root_approval_or_job_created':False,'full_or2000_release':'HOLD'})
    review={**copy.deepcopy(fields),'schema':'EXACT_CPU_AUTO_MEMORY_SCOPE_ROOT_REVIEW_V1','status':'PENDING_ROOT_REVIEW','reviewer':None,
        'resource_authority_reference':v['resource_authority_reference'],'scope_mode':'BOUNDED_METADATA_PREPARATION','stage_output_cap_bytes':C.CAP,
        'parent_evidence_references':parents,'approved_source_references':sources,'data_references':data,'user_limited15_numerical_QA_only':True,
        'user_decision_reference':plan['user_decision_reference'],'original15FAIL_preserved':True,'scientific_PASS':False,'full_or2000_release':'HOLD'}
    rr=Q.write_new(out/'root_review.template.json',review)
    return Q.write_new(out/'draft_receipt.json',{'schema':'PPRIME_STRICT_NUMERICS15_QA_DRAFT_V1','status':'PENDING_INDEPENDENT_ROOT_REVIEW_AFTER_REAL_USER_DECISION',
        'plan_reference':pr,'root_review_template_reference':rr,'stage_fields':fields,'source_references':sources,'data_references':data,
        'resource_authority_reference':v['resource_authority_reference'],'user_decision_reference':plan['user_decision_reference'],
        'scientific_bodies_opened_or_hashed':False,'Root_approval_or_job_created':False})


def finalize(draft_path,review_path):
    d=Q.load(draft_path);Q.need(d['schema']=='PPRIME_STRICT_NUMERICS15_QA_DRAFT_V1' and d['status']=='PENDING_INDEPENDENT_ROOT_REVIEW_AFTER_REAL_USER_DECISION','GENUINE_USER_DECISION_MUST_PRECEDE_RUNNABLE_STAGE')
    plan=C.meta(d['plan_reference']);C.require_user(plan)
    rr=Q.pin(review_path);r=C.meta(rr);t=C.meta(d['root_review_template_reference']);Q.need(rr!=d['root_review_template_reference'] and r['status']=='APPROVED_FOR_EXACT_STAGE' and r['reviewer']=='root','INDEPENDENT_ROOT_REVIEW_NOT_CHILD_SIGNATURE')
    for k,value in t.items():
        if k not in ('status','reviewer'):Q.need(r[k]==value,'EXACT_REVIEW_FIELD:'+k)
    for ref in d['source_references']:Q.need(Q.pin(ref['path'])==ref,'CURRENT_SMALL_SOURCE_PINS_UNCHANGED')
    *_,data,parents,prior=C.parents(plan);Q.need(data==d['data_references'],'EXACT_EXISTING_SCIENTIFIC_INPUT_LOCATORS')
    spec={'schema':'ROOT_REVIEWED_CPU_AUTO_MEMORY_STAGE_SPEC_V1',**d['stage_fields'],'cpus':16,'memory_policy':'SLURM_DEFAULT_UNSPECIFIED',
        'stage_output_cap_bytes':C.CAP,'source_references':d['source_references'],'data_references':data,
        'scope':{'mode':'BOUNDED_METADATA_PREPARATION','parent_profile':None,'review':rr}}
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.contract import validate_scope_spec
    validate_scope_spec(spec,d['resource_authority_reference'],read_small=Q.read_small);return Q.write_new(pathlib.Path(draft_path).parent/'stage_spec.json',spec)


def main():
    Q.on_login();p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='action',required=True)
    a=s.add_parser('draft');a.add_argument('--request',type=pathlib.Path,required=True);a.add_argument('--output',type=pathlib.Path,required=True)
    a=s.add_parser('finalize');a.add_argument('--draft',type=pathlib.Path,required=True);a.add_argument('--root-review',type=pathlib.Path,required=True)
    a=p.parse_args();print(draft(a.request,a.output) if a.action=='draft' else finalize(a.draft,a.root_review))


if __name__=='__main__':main()
