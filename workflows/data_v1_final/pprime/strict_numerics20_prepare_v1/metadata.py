"""Small metadata only. Root independently approves the zero-invoke prepare stage."""
import argparse,copy,pathlib
from . import contract as C
from .proposal import proposal
Q=C.Q
FIELDS=('prior_strict15_root_review_reference','original_preparation_closure_reference','original_prepared_reference','source_context_reference',
    'original_protocol_reference','candidate_protocol_reference','original_sprime_recipe_reference','quota_reuse_reference',
    'resource_authority_reference','cost_decision_reference','output_directory')

def draft(request_path,out):
    value=Q.load(request_path);Q.need(value['schema']=='ROOT_REQUESTED_PPRIME_NEW20_ZERO_INVOKE_PREPARE_V1'
        and value['status']=='REQUESTED_FOR_REVIEW' and value['requested_by']=='root','ROOT_REQUEST_NOT_CHILD_OR_USER_QM_APPROVAL')
    plan={'schema':'PPRIME_NEW20_ALL12_ZERO_INVOKE_PREPARE_PLAN_V1',**{k:value[k] for k in FIELDS},'scope_parameters':C.PARAMETERS,
        'wall_seconds':7200,'output_cap_bytes':C.PREP_CAP,'user_decision_reference':None,'execute_authorized':False}
    old,new,diff,source,prepared,pair,sprime,data,parents=C.parents(plan);plan['data_references']=data
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.contract import validate_authority
    validate_authority(plan['resource_authority_reference'],read_small=Q.read_small)
    cost=C.meta(plan['cost_decision_reference']);Q.need(cost['status']=='USER_AUTHORIZED' and cost['on_overrun']=='REPORT_AND_CONTINUE'
        and cost['scientific_quality_thresholds_unchanged'] is True,'COST_IS_NOT_QM_NUMERICAL_AUTHORIZATION')
    out=pathlib.Path(out);output=pathlib.Path(plan['output_directory']);base=Q.ROOT/'artifacts/pprime_strict20_zero_invoke_prepare_v1'
    Q.need(out.is_absolute() and Q.ROOT/'control' in out.parents and '..' not in out.parts and not out.exists()
        and output.is_absolute() and base in output.parents and '..' not in output.parts and not output.exists()
        and not any(p.is_symlink() for p in (out,*out.parents,output,*output.parents)),'FRESH_PREPARE_METADATA_AND_INDEPENDENT_OUTPUT')
    sources=C.unique([*(Q.pin(p) for p in C.sources()),*parents,Q.pin(request_path),plan['resource_authority_reference'],plan['cost_decision_reference']])
    body_paths={r['path'] for r in data}
    for ref in sources:Q.need(ref['path'] not in body_paths and Q.pin(ref['path'])==ref,'SMALL_SOURCE_ONLY_NO_LOGIN_DATA_OPEN_HASH')
    out.mkdir(parents=True,exist_ok=False,mode=0o700);pr=Q.write_new(out/'plan.json',plan);sources=C.unique([*sources,pr])
    proposed=Q.write_new(out/'unapproved_NEW20_execution_proposal.json',proposal());sources=C.unique([*sources,proposed])
    fields={'kind':'analysis','scope_key':C.KEY,'scope_parameters':C.PARAMETERS,'pilot':False,'wall_seconds':7200,'estimated_peak_output_bytes':C.PREP_CAP,
        'source_status_stage':C.STAGE,'execution_argv':[Q.PY,'-B','-m',C.MODULE,'--plan',str(out/'plan.json'),'--startup-proof','__ROOT_STARTUP_PROOF__']}
    review={**copy.deepcopy(fields),'schema':'EXACT_CPU_AUTO_MEMORY_SCOPE_ROOT_REVIEW_V1','status':'PENDING_ROOT_REVIEW','reviewer':None,
        'resource_authority_reference':plan['resource_authority_reference'],'scope_mode':'BOUNDED_METADATA_PREPARATION','stage_output_cap_bytes':C.PREP_CAP,
        'parent_evidence_references':parents,'approved_source_references':sources,'data_references':data,'zero_invoke_readonly_preparation_only':True,
        'original_protocol_initialize_for_readers_allowed':True,'candidate_initialize_or_any_invoke_authorized':False,'original15FAIL_preserved':True,'full_or2000_release':'HOLD'}
    rr=Q.write_new(out/'root_review.template.json',review)
    return Q.write_new(out/'draft_receipt.json',{'schema':'PPRIME_NEW20_ZERO_INVOKE_PREPARE_DRAFT_V1','status':'PENDING_INDEPENDENT_ROOT_REVIEW_ZERO_INVOKE_ONLY',
        'plan_reference':pr,'proposal_reference':proposed,'root_review_template_reference':rr,'stage_fields':fields,'source_references':sources,'data_references':data,
        'resource_authority_reference':plan['resource_authority_reference'],'scientific_bodies_opened_or_hashed':False,'Root_approval_job_or_QM_created':False})

def finalize(draft_path,review_path):
    d=Q.load(draft_path);Q.need(d['schema']=='PPRIME_NEW20_ZERO_INVOKE_PREPARE_DRAFT_V1'
        and d['status']=='PENDING_INDEPENDENT_ROOT_REVIEW_ZERO_INVOKE_ONLY','EXACT_PREPARE_ONLY_DRAFT')
    rr=Q.pin(review_path);review=C.meta(rr);template=C.meta(d['root_review_template_reference'])
    Q.need(rr!=d['root_review_template_reference'] and review['status']=='APPROVED_FOR_EXACT_STAGE' and review['reviewer']=='root','INDEPENDENT_ROOT_APPROVAL_REQUIRED')
    for key,value in template.items():
        if key not in ('status','reviewer'):Q.need(review[key]==value,'EXACT_PREPARE_REVIEW_FIELD:'+key)
    for ref in d['source_references']:Q.need(Q.pin(ref['path'])==ref,'SOURCE_AND_SMALL_PARENTS_UNCHANGED')
    plan=C.meta(d['plan_reference']);*_,data,parents=C.parents(plan);Q.need(data==d['data_references'] and plan['execute_authorized'] is False,'EXACT_LOCATORS_NOT_QM_EXECUTION')
    spec={'schema':'ROOT_REVIEWED_CPU_AUTO_MEMORY_STAGE_SPEC_V1',**d['stage_fields'],'cpus':16,'memory_policy':'SLURM_DEFAULT_UNSPECIFIED',
        'stage_output_cap_bytes':C.PREP_CAP,'source_references':d['source_references'],'data_references':data,
        'scope':{'mode':'BOUNDED_METADATA_PREPARATION','parent_profile':None,'review':rr}}
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.contract import validate_scope_spec
    validate_scope_spec(spec,d['resource_authority_reference'],read_small=Q.read_small);return Q.write_new(pathlib.Path(draft_path).parent/'stage_spec.json',spec)

def main():
    Q.on_login();p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='action',required=True)
    a=s.add_parser('draft');a.add_argument('--request',type=pathlib.Path,required=True);a.add_argument('--output',type=pathlib.Path,required=True)
    a=s.add_parser('finalize');a.add_argument('--draft',type=pathlib.Path,required=True);a.add_argument('--root-review',type=pathlib.Path,required=True)
    a=p.parse_args();print(draft(a.request,a.output) if a.action=='draft' else finalize(a.draft,a.root_review))

if __name__=='__main__':main()
