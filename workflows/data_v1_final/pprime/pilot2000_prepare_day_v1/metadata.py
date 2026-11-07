"""Existing generic16 metadata only; no scientific body or native initialization."""
import argparse,copy,pathlib
from . import contract as C
Q=C.Q;M=C.ResourceOrigin
KEYS=('original_prepared_reference','original_preparation_closure_reference','source_context_reference','original_protocol_reference',
 'candidate_protocol_reference','retention_policy_reference','original_sprime_recipe_reference','resource_authority_reference',
 'cost_decision_reference','quota_provider_review_reference','quota_provider_identity_reference','root_carveout_review_reference')
def draft(path,out):
    Q.on_login();root=Q.load(path);C.need(root['schema']=='ROOT_REQUESTED_PPRIME_ORIGINAL2000_ZERO_INVOKE_PREPARATION_V1'
      and root['status']=='REQUESTED_FOR_REVIEW' and root['requested_by']=='root','ACTUAL_ROOT_REQUEST_NOT_USER_PRECISION_PERMISSION')
    params=C.parameters(root['node']);plan={k:root[k] for k in KEYS};parent_values=C.parents(plan);*_,data,parents=parent_values;C.software_original_specs(parent_values[3])
    M.validate_authority(plan['resource_authority_reference'],read_small=Q.read_small)
    resources=[plan[k] for k in KEYS[-5:]]
    for ref in resources:C.meta(ref)
    cost=C.meta(plan['cost_decision_reference']);C.need(cost['status']=='USER_AUTHORIZED' and cost['on_overrun']=='REPORT_AND_CONTINUE'
      and cost['scientific_quality_thresholds_unchanged'] is True,'ACTUAL_UNCHANGED_COST_QUALITY_POLICY')
    M.carveout(C.meta(plan['root_carveout_review_reference']),{'scope_key':C.KEY,'node':root['node'],'resource_authority_reference':plan['resource_authority_reference'],'estimated_peak_output_bytes':C.CAP})
    plan.update(schema='PPRIME_ORIGINAL2000_ZERO_INVOKE_PLAN_V1',node=root['node'],scope_parameters=params,wall_seconds=C.WALL,output_cap_bytes=C.CAP,
      output_directory=str(M.fresh(root['output_directory'],'artifacts')),data_references=data)
    plan['source_references']=C.unique([*C.sources(plan),*parents,*resources,Q.pin(path)])
    out=M.fresh(out);out.mkdir(parents=True,mode=0o700);pr=Q.write_new(out/'plan.json',plan);src=C.unique([*plan['source_references'],pr])
    fields={'kind':'analysis','scope_key':C.KEY,'scope_parameters':params,'pilot':False,'wall_seconds':C.WALL,'estimated_peak_output_bytes':C.CAP,
      'source_status_stage':'PPRIME_ORIGINAL2000_INPUTS_CPU_REVALIDATION_NO_INVOKE','execution_argv':[Q.PY,'-B','-m',C.MODULE,'--plan',str(out/'plan.json'),'--startup-proof','__ROOT_STARTUP_PROOF__']}
    template={'schema':'EXACT_CPU_AUTO_MEMORY_SCOPE_ROOT_REVIEW_V1','status':'PENDING_ROOT_REVIEW','reviewer':None,**copy.deepcopy(fields),
      'scope_mode':'BOUNDED_METADATA_PREPARATION','resource_authority_reference':plan['resource_authority_reference'],'stage_output_cap_bytes':C.CAP,
      'parent_evidence_references':C.unique([*parents,*resources,Q.pin(path)]),'approved_source_references':src,'data_references':data,
      'original2000_readonly_prepare_authorized':True,'native_invoke_or_new_QM_authorized':False,'production_precision_permission_created':False}
    tr=Q.write_new(out/'root_review.template.json',template)
    return Q.write_new(out/'draft_receipt.json',{'schema':'PPRIME_ORIGINAL2000_ZERO_INVOKE_DRAFT_V1','plan_reference':pr,'template_reference':tr,
      'stage_fields':fields,'source_references':src,'data_references':data,'resource_authority_reference':plan['resource_authority_reference'],'DATA_on_login':False})
def finalize(path,review):
    Q.on_login();d=Q.load(path);C.need(d['schema']=='PPRIME_ORIGINAL2000_ZERO_INVOKE_DRAFT_V1','EXACT_ZERO_INVOKE_DRAFT');rr=M.approved(d['template_reference'],review)
    plan=C.meta(d['plan_reference']);*_,data,parents=C.parents(plan);C.need(data==plan['data_references']==d['data_references'],'SAME_FROZEN_DATA_LOCATORS')
    for ref in d['source_references']:C.need(Q.pin(ref['path'])==ref,'ALL_SOURCE_AND_SMALL_AUTHORITY_PINS_CURRENT')
    spec={'schema':'ROOT_REVIEWED_CPU_AUTO_MEMORY_STAGE_SPEC_V1',**d['stage_fields'],'cpus':16,'memory_policy':'SLURM_DEFAULT_UNSPECIFIED','stage_output_cap_bytes':C.CAP,
      'source_references':d['source_references'],'data_references':data,'scope':{'mode':'BOUNDED_METADATA_PREPARATION','parent_profile':None,'review':rr}}
    M.validate_scope_spec(spec,d['resource_authority_reference'],read_small=Q.read_small);return Q.write_new(pathlib.Path(path).parent/'stage_spec.json',spec)
def main():
    p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='action',required=True);a=s.add_parser('draft');a.add_argument('--request',required=True);a.add_argument('--output',required=True)
    a=s.add_parser('finalize');a.add_argument('--draft',required=True);a.add_argument('--root-review',required=True);a=p.parse_args();print(draft(a.request,a.output) if a.action=='draft' else finalize(a.draft,a.root_review))
if __name__=='__main__':main()
