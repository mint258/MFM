"""Original generic metadata draft/finalize, no scientific body at login."""
import argparse,copy,pathlib
from . import contract as C
Q=C.Q;M=C.M

def draft(path,out):
    Q.on_login();root=Q.load(path)
    C.need(root['schema']=='ROOT_REQUESTED_PPRIME_FORMAL_PACKED_DAY_V1' and root['status']=='REQUESTED_FOR_REVIEW'
      and root['requested_by']=='root','ACTUAL_ROOT_FORMAL_DAY_REQUEST')
    out=M.fresh(out);out.mkdir(parents=True,mode=0o700)
    missing=[k for k in C.REQUIRED if not root.get(k)]
    if missing:return Q.write_new(out/'NONEXECUTABLE.json',{'status':'NONEXECUTABLE_MISSING_ACTUAL_PARENTS','missing':missing,'SCI_DATA_opened':False})
    p={k:root[k] for k in C.REQUIRED};b=C.bootstrap(p);pilot=b['pilot_plan']
    C.need(root['node'] in C.NODES and root['output_cap_bytes']==C.CAP and root['maximum_new_records']==C.MAX_RECORDS,'EXACT64GIB100K_BOUND_NOT_SUCCESS_PROMISE')
    for k in ('source_context_reference','original_protocol_reference','candidate_protocol_reference','retention_policy_reference','original_sprime_recipe_reference'):
        p[k]=pilot[k]
    p.update(schema='PPRIME_FORMAL_PACKED_DAY_PLAN_V1',node=root['node'],precision_mode='ORIGINAL_WP5',user_precision_decision_reference=None,
      wall_seconds=C.WALL,output_cap_bytes=C.CAP,maximum_new_records=C.MAX_RECORDS,output_directory=str(M.fresh(root['output_directory'],'artifacts')),
      scope_parameters=C.parameters(root['node']),data_references=b['data'])
    M.validate_authority(p['resource_authority_reference'],read_small=Q.read_small)
    M.carveout(C.meta(p['root_carveout_review_reference']),{'scope_key':C.KEY,'node':p['node'],'resource_authority_reference':p['resource_authority_reference'],'estimated_peak_output_bytes':C.CAP})
    cost=C.meta(p['cost_decision_reference'])
    C.need(cost['status']=='USER_AUTHORIZED' and cost['on_overrun']=='REPORT_AND_CONTINUE'
      and cost['scientific_quality_thresholds_unchanged'] is True,'ACTUAL_COST_POLICY_NOT_QC_WAIVER')
    fields={'kind':'qm','scope_key':C.KEY,'scope_parameters':p['scope_parameters'],'pilot':False,'wall_seconds':C.WALL,
      'estimated_peak_output_bytes':C.CAP,'source_status_stage':'PPRIME_USER_RELEASED_COMPLETE_SPRIME_FORMAL_DAY',
      'execution_argv':[Q.PY,'-B','-m',C.MODULE,'--plan',str(out/'plan.json'),'--startup-proof','__ROOT_STARTUP_PROOF__']}
    review={'schema':'EXACT_CPU_AUTO_MEMORY_SCOPE_ROOT_REVIEW_V1','status':'PENDING_ROOT_REVIEW','reviewer':None,**copy.deepcopy(fields),
      'scope_mode':'BOUNDED_PERFORMANCE_BATCH','bounded_batch_limits_reviewed':True,'resource_authority_reference':p['resource_authority_reference'],
      'stage_output_cap_bytes':C.CAP,'formal_generation_authorized':True,'user_release_reference':p['user_release_reference'],
      'generation_release_reference':p['generation_release_reference'],'original_WP5_precision_only':True,
      'minimum_record_success_rate':.9945,'maximum_native_invocations':C.MAX_RECORDS*12,
      'current_ready_prefix_not_final_Common':True,'original2000_once_including_failures_reused':True}
    C.precision(p,review)
    p['source_references']=C.unique([*C.sources(p),*b['refs'],*[p[k] for k in C.REQUIRED],Q.pin(path)])
    pr=Q.write_new(out/'plan.json',p);sources=C.unique([*p['source_references'],pr])
    review.update(parent_evidence_references=b['refs'],approved_source_references=sources,data_references=p['data_references'])
    tr=Q.write_new(out/'root_review.template.json',review)
    return Q.write_new(out/'draft_receipt.json',{'schema':'PPRIME_FORMAL_PACKED_DAY_DRAFT_V1','plan_reference':pr,'template_reference':tr,
      'stage_fields':fields,'source_references':sources,'data_references':p['data_references'],'resource_authority_reference':p['resource_authority_reference'],'SCI_DATA_opened_on_login':False})

def finalize(path,review):
    Q.on_login();d=Q.load(path);C.need(d['schema']=='PPRIME_FORMAL_PACKED_DAY_DRAFT_V1','EXACT_FORMAL_DRAFT')
    rr=M.approved(d['template_reference'],review);p=C.meta(d['plan_reference']);C.precision(p,C.meta(rr));b=C.bootstrap(p)
    C.need(b['data']==p['data_references']==d['data_references'],'UNCHANGED_EXACT_PRODUCER_DATA_LOCATORS')
    for r in d['source_references']:C.need(Q.pin(r['path'])==r,'FROZEN_SOURCE_OR_OPERATIONAL_AUTHORITY')
    return Q.write_new(M.fresh(pathlib.Path(path).parent/'stage_spec.json'),{'schema':'ROOT_REVIEWED_CPU_AUTO_MEMORY_STAGE_SPEC_V1',**d['stage_fields'],
      'cpus':16,'memory_policy':'SLURM_DEFAULT_UNSPECIFIED','stage_output_cap_bytes':C.CAP,'source_references':d['source_references'],
      'data_references':d['data_references'],'scope':{'mode':'BOUNDED_PERFORMANCE_BATCH','parent_profile':None,'review':rr}})

def main():
    p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='action',required=True)
    d=s.add_parser('draft');d.add_argument('--request',required=True);d.add_argument('--output',required=True)
    d=s.add_parser('finalize');d.add_argument('--draft',required=True);d.add_argument('--root-review',required=True)
    a=p.parse_args();print(draft(a.request,a.output) if a.action=='draft' else finalize(a.draft,a.root_review))
if __name__=='__main__':main()
