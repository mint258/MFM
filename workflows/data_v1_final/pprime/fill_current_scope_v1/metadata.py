"""Small-plan builder using existing queue stage shape; no SCI bodies/submit."""
import argparse,pathlib
from . import contract as C
Q=C.Q;M=C.M


def draft(request_path,out):
    Q.on_login();root=Q.load(request_path);out=M.fresh(out);out.mkdir(parents=True)
    required=[*C.REQUIRED]
    if root['mode']=='EXECUTE':required+=['prepared_shard_header_reference','shared_preparation_root_acceptance_reference']
    missing=[k for k in required if not root.get(k)]
    if missing:return Q.write_new(out/'NONEXECUTABLE.json',dict(status='MISSING_ACTUAL_ROOT_RUNTIME_BINDINGS',missing=missing,SCI_DATA_opened=False))
    p={k:root[k]for k in required};pilot=C.meta(p['pilot_execution_plan_reference'])
    for k in ('source_context_reference','original_protocol_reference','candidate_protocol_reference','retention_policy_reference','original_sprime_recipe_reference'):p[k]=pilot[k]
    p.update(schema='PPRIME_FORMAL_SHARDED_DAY_PLAN_V2',mode=root['mode'],node=root['node'],output_cap_bytes=root['output_cap_bytes'],
      wall_seconds=C.WALL,precision_mode='ORIGINAL_WP5',user_precision_decision_reference=None,
      maximum_assigned_records=161480 if root['mode']=='SHARED_PREPARE' else C.meta(root['prepared_shard_header_reference'])['records'],
      output_directory=str(M.fresh(root['output_directory'],'artifacts')))
    b=C.bootstrap(p);p['data_references']=b['data'];p['scope_parameters']=C.parameters(p)
    p['source_references']=C.unique([*C.sources(p),*b['refs'],Q.pin(request_path)])
    pr=Q.write_new(out/'plan.json',p);sources=C.unique([*p['source_references'],pr]);kind='analysis' if p['mode']=='SHARED_PREPARE' else 'qm'
    fields=dict(kind=kind,scope_key=C.MODES[p['mode']],scope_parameters=p['scope_parameters'],pilot=False,
      wall_seconds=C.WALL,estimated_peak_output_bytes=p['output_cap_bytes'],source_status_stage='CLOSED_FILL_CURRENT_PHYSICAL_INPUT_BRIDGE',
      execution_argv=[Q.PY,'-B','-m',C.MODULE,'--plan',str(out/'plan.json'),'--startup-proof','__ROOT_STARTUP_PROOF__'])
    review=dict(schema='EXACT_CPU_AUTO_MEMORY_SCOPE_ROOT_REVIEW_V1',status='PENDING_ROOT_REVIEW',reviewer=None,**fields,
      scope_mode='BOUNDED_PERFORMANCE_BATCH',bounded_batch_limits_reviewed=True,resource_authority_reference=p['resource_authority_reference'],
      stage_output_cap_bytes=p['output_cap_bytes'],formal_generation_authorized=True,mode=p['mode'],
      user_release_reference=p['user_release_reference'],generation_release_reference=p['generation_release_reference'],original_WP5_precision_only=True,
      minimum_record_success_rate=.9945,maximum_native_invocations=0 if kind=='analysis' else 12*b['prepared']['records'],
      shared_pool_root_review_reference=p['shared_pool_root_review_reference'],shared_pools_counted_once_not_once_per_Parent=True,
      parent_evidence_references=b['refs'],approved_source_references=sources,data_references=b['data'],
      final_Common_or_training_admission=False)
    tr=Q.write_new(out/'root_review.template.json',review)
    return Q.write_new(out/'draft_receipt.json',dict(schema='PPRIME_CURRENT_FILL_DRAFT_V1',plan_reference=pr,template_reference=tr,
      stage_fields=fields,source_references=sources,data_references=b['data'],resource_authority_reference=p['resource_authority_reference'],SCI_DATA_opened_on_login=False))


def finalize(draft_path,review_path):
    Q.on_login();d=Q.load(draft_path);rr=M.approved(d['template_reference'],review_path);p=C.meta(d['plan_reference'])
    C.precision(p,C.meta(rr));b=C.bootstrap(p);C.need(b['data']==d['data_references']==p['data_references'],'SAME_ACTUAL_SOURCE_LOCATORS')
    for ref in d['source_references']:C.need(Q.pin(ref['path'])==ref,'FROZEN_PREP_SOURCE')
    return Q.write_new(pathlib.Path(draft_path).parent/'stage_spec.json',dict(schema='ROOT_REVIEWED_CPU_AUTO_MEMORY_STAGE_SPEC_V1',**d['stage_fields'],
      cpus=16,memory_policy='SLURM_DEFAULT_UNSPECIFIED',stage_output_cap_bytes=p['output_cap_bytes'],source_references=d['source_references'],
      data_references=d['data_references'],scope=dict(mode='BOUNDED_PERFORMANCE_BATCH',parent_profile=None,review=rr)))


def main():
    a=argparse.ArgumentParser(description=__doc__);s=a.add_subparsers(dest='action',required=True)
    p=s.add_parser('draft');p.add_argument('--request',required=True);p.add_argument('--output',required=True)
    p=s.add_parser('finalize');p.add_argument('--draft',required=True);p.add_argument('--root-review',required=True)
    v=a.parse_args();print(draft(v.request,v.output)if v.action=='draft'else finalize(v.draft,v.root_review))
if __name__=='__main__':main()