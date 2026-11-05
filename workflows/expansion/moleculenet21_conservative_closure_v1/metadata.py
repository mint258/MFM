"""Small metadata only: exact existing generic16 stage, no scientific body pins."""
import argparse,copy
from pathlib import Path
from . import closure as R
Q=R.Q;need=R.need;meta=R.meta

def draft(path,out):
    Q.on_login();request=Q.load(path);need(request['schema']=='ROOT_REQUESTED_MOLNET21_CONSERVATIVE_CLOSURE_V1'
      and request['status']=='REQUESTED_FOR_REVIEW' and request['requested_by']=='root' and request['node'] in R.NODES,'EXACT_ROOT_REQUEST_NOT_APPROVAL')
    plan={k:request[k] for k in ('policy_reference','actual_input_locators_reference','diagnostic_receipt_reference','candidate_domain_authority',
      'resource_authority_reference','cost_decision_reference','quota_provider_review_reference','quota_provider_identity_reference','root_carveout_review_reference')}
    _,_,data,refs,_=R.inputs(plan);R.M.validate_authority(plan['resource_authority_reference'],read_small=Q.read_small)
    cost=meta(plan['cost_decision_reference']);need(cost['status']=='USER_AUTHORIZED' and cost['on_overrun']=='REPORT_AND_CONTINUE'
      and cost['scientific_quality_thresholds_unchanged'] is True,'ORIGINAL_COST_AND_QUALITY_POLICY')
    resources=[plan[k] for k in ('resource_authority_reference','cost_decision_reference','quota_provider_review_reference','quota_provider_identity_reference','root_carveout_review_reference')]
    for ref in resources:meta(ref)
    R.M.carveout(meta(plan['root_carveout_review_reference']),{'scope_key':R.KEY,'node':request['node'],'resource_authority_reference':plan['resource_authority_reference'],'estimated_peak_output_bytes':R.CAP})
    plan.update(schema='MOLNET21_CONSERVATIVE_CLOSURE_PLAN_V1',node=request['node'],scope_parameters=R.parameters(request['node']),output_cap_bytes=R.CAP,wall_seconds=R.WALL,
      output_directory=str(R.M.fresh(request['output_directory'],'artifacts')),data_references=data)
    parent_refs=R.C.unique([*refs,*resources,Q.pin(path)]);plan['source_references']=R.C.unique([*R.sources(plan),*parent_refs])
    out=R.M.fresh(out);out.mkdir(parents=True,mode=0o700);pr=Q.write_new(out/'plan.json',plan);src=R.C.unique([*plan['source_references'],pr])
    fields={'kind':'analysis','scope_key':R.KEY,'scope_parameters':plan['scope_parameters'],'pilot':False,'wall_seconds':R.WALL,'estimated_peak_output_bytes':R.CAP,
      'source_status_stage':'MOLNET21_CONSERVATIVE_CLOSURE_SAME_PARENT_VALIDATION','execution_argv':[Q.PY,'-B','-m',R.MODULE,'--plan',str(out/'plan.json'),'--startup-proof','__ROOT_STARTUP_PROOF__']}
    template={'schema':'EXACT_CPU_AUTO_MEMORY_SCOPE_ROOT_REVIEW_V1','status':'PENDING_ROOT_REVIEW','reviewer':None,**copy.deepcopy(fields),
      'scope_mode':'BOUNDED_METADATA_PREPARATION','resource_authority_reference':plan['resource_authority_reference'],'stage_output_cap_bytes':R.CAP,
      'parent_evidence_references':parent_refs,'approved_source_references':src,'data_references':data,
      'exact21_conservative_evidence_validation_authorized':True,'maximum_new_HTTPS_calls':8,'new_full_keys_QM_UFF_or_READY_release_authorized':False}
    tr=Q.write_new(out/'root_review.template.json',template)
    return Q.write_new(out/'draft_receipt.json',{'schema':'MOLNET21_CONSERVATIVE_CLOSURE_DRAFT_V1','plan_reference':pr,'template_reference':tr,
      'stage_fields':fields,'source_references':src,'data_references':data,'resource_authority_reference':plan['resource_authority_reference'],'scientific_DATA_or_network_on_login':False})

def finalize(path,review):
    Q.on_login();d=Q.load(path);need(d['schema']=='MOLNET21_CONSERVATIVE_CLOSURE_DRAFT_V1','EXACT_CLOSURE_DRAFT');rr=R.M.approved(d['template_reference'],review)
    plan=meta(d['plan_reference']);_,_,data,_,_=R.inputs(plan);need(data==d['data_references']==plan['data_references'],'ACTUAL_UNCHANGED_SOURCE_DATA_LOCATORS')
    for ref in d['source_references']:need(Q.pin(ref['path'])==ref,'SOURCE_AND_SMALL_PARENT_CURRENT_BYTES')
    spec={'schema':'ROOT_REVIEWED_CPU_AUTO_MEMORY_STAGE_SPEC_V1',**d['stage_fields'],'cpus':16,'memory_policy':'SLURM_DEFAULT_UNSPECIFIED','stage_output_cap_bytes':R.CAP,
      'source_references':d['source_references'],'data_references':data,'scope':{'mode':'BOUNDED_METADATA_PREPARATION','parent_profile':None,'review':rr}}
    R.M.validate_scope_spec(spec,d['resource_authority_reference'],read_small=Q.read_small);return Q.write_new(Path(path).parent/'stage_spec.json',spec)

def main():
    p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='action',required=True);a=s.add_parser('draft');a.add_argument('--request',required=True);a.add_argument('--output',required=True)
    a=s.add_parser('finalize');a.add_argument('--draft',required=True);a.add_argument('--root-review',required=True);a=p.parse_args()
    print(draft(a.request,a.output) if a.action=='draft' else finalize(a.draft,a.root_review))
if __name__=='__main__':main()
