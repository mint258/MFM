"""Existing generic draft/finalize; never opens MID/pair/scientific bodies."""
import argparse,copy,pathlib
from . import contract as C
Q=C.Q;M=C.M

def draft(path,out):
    Q.on_login();root=Q.load(path)
    C.need(root['schema']=='ROOT_REQUESTED_PPRIME_FORMAL_SHARDED_DAY_V2' and root['status']=='REQUESTED_FOR_REVIEW'
      and root['requested_by']=='root','ACTUAL_ROOT_SHARDED_DAY_REQUEST')
    out=M.fresh(out);out.mkdir(parents=True,mode=0o700)
    required=[*C.REQUIRED,'generation_shard_header_references']
    if root['mode']=='EXECUTE':required+=['prepared_shard_header_reference','shared_preparation_root_acceptance_reference']
    if root['mode']=='RECOVER_PUBLISH':required+=['recovery_locator_reference','recovery_root_review_reference']
    missing=[k for k in required if not root.get(k)]
    if missing:return Q.write_new(out/'NONEXECUTABLE.json',{'status':'NONEXECUTABLE_MISSING_ACTUAL_PARENTS','missing':missing,'SCI_DATA_opened':False})
    p={k:root[k] for k in required};p.update(mode=root['mode'],node=root['node'],output_cap_bytes=root['output_cap_bytes'])
    pilot=C.meta(p['pilot_execution_plan_reference'])
    for k in ('source_context_reference','original_protocol_reference','candidate_protocol_reference','retention_policy_reference','original_sprime_recipe_reference'):p[k]=pilot[k]
    p.update(schema='PPRIME_FORMAL_SHARDED_DAY_PLAN_V2',precision_mode='ORIGINAL_WP5',user_precision_decision_reference=None,
      wall_seconds=C.WALL,output_directory=str(M.fresh(root['output_directory'],'artifacts')))
    b=C.bootstrap(p);p['data_references']=b['data'];p['scope_parameters']=C.parameters(p)
    p['maximum_assigned_records']=sum(h['conformer_records'] for _,h in b['headers']) if p['mode']=='SHARED_PREPARE' else b.get('prepared',{}).get('records',1)
    M.validate_authority(p['resource_authority_reference'],read_small=Q.read_small)
    M.carveout(C.meta(p['root_carveout_review_reference']),{'scope_key':C.MODES[p['mode']],'node':p['node'],
      'resource_authority_reference':p['resource_authority_reference'],'estimated_peak_output_bytes':p['output_cap_bytes']})
    cost=C.meta(p['cost_decision_reference']);C.need(cost['status']=='USER_AUTHORIZED' and cost['on_overrun']=='REPORT_AND_CONTINUE'
      and cost['scientific_quality_thresholds_unchanged'] is True,'REAL_COST_AUTHORITY_NOT_SCIENCE_WAIVER')
    kind='qm' if p['mode']=='EXECUTE' else 'analysis'
    fields={'kind':kind,'scope_key':C.MODES[p['mode']],'scope_parameters':p['scope_parameters'],'pilot':False,'wall_seconds':C.WALL,
      'estimated_peak_output_bytes':p['output_cap_bytes'],'source_status_stage':'PPRIME_DISJOINT_SHARED_PREPARATION_OR_ASSIGNED_ORIGINAL_EXECUTION',
      'execution_argv':[Q.PY,'-B','-m',C.MODULE,'--plan',str(out/'plan.json'),'--startup-proof','__ROOT_STARTUP_PROOF__']}
    review={'schema':'EXACT_CPU_AUTO_MEMORY_SCOPE_ROOT_REVIEW_V1','status':'PENDING_ROOT_REVIEW','reviewer':None,**copy.deepcopy(fields),
      'scope_mode':'BOUNDED_PERFORMANCE_BATCH','bounded_batch_limits_reviewed':True,'resource_authority_reference':p['resource_authority_reference'],
      'stage_output_cap_bytes':p['output_cap_bytes'],'formal_generation_authorized':True,'mode':p['mode'],
      'user_release_reference':p['user_release_reference'],'generation_release_reference':p['generation_release_reference'],
      'original_WP5_precision_only':True,'minimum_record_success_rate':.9945,'maximum_native_invocations':p['maximum_assigned_records']*12 if kind=='qm' else 0,
      'shared_pool_root_review_reference':p['shared_pool_root_review_reference'],'shared_pools_counted_once_not_once_per_Parent':True,
      'local_tmp_closed_unpublished_preserved_without_native_retry':True,'original2000_including_failures_never_reinvoked':True,
      'final_Common_or_training_admission':False}
    C.precision(p,review)
    p['source_references']=C.unique([*C.sources(p),*b['refs'],*[p[k] for k in C.REQUIRED],Q.pin(path)])
    pr=Q.write_new(out/'plan.json',p);sources=C.unique([*p['source_references'],pr])
    review.update(parent_evidence_references=b['refs'],approved_source_references=sources,data_references=p['data_references'])
    tr=Q.write_new(out/'root_review.template.json',review)
    return Q.write_new(out/'draft_receipt.json',{'schema':'PPRIME_FORMAL_SHARDED_DAY_DRAFT_V2','plan_reference':pr,'template_reference':tr,
      'stage_fields':fields,'source_references':sources,'data_references':p['data_references'],'resource_authority_reference':p['resource_authority_reference'],'SCI_DATA_opened_on_login':False})

def finalize(path,review):
    Q.on_login();d=Q.load(path);C.need(d['schema']=='PPRIME_FORMAL_SHARDED_DAY_DRAFT_V2','EXACT_SHARDED_DRAFT')
    rr=M.approved(d['template_reference'],review);p=C.meta(d['plan_reference']);C.precision(p,C.meta(rr));b=C.bootstrap(p)
    C.need(b['data']==p['data_references']==d['data_references'],'UNCHANGED_PRODUCER_DATA_LOCATORS')
    for r in d['source_references']:C.need(Q.pin(r['path'])==r,'FROZEN_SOURCES_AND_OPERATIONAL_AUTHORITY')
    return Q.write_new(M.fresh(pathlib.Path(path).parent/'stage_spec.json'),{'schema':'ROOT_REVIEWED_CPU_AUTO_MEMORY_STAGE_SPEC_V1',**d['stage_fields'],
      'cpus':16,'memory_policy':'SLURM_DEFAULT_UNSPECIFIED','stage_output_cap_bytes':p['output_cap_bytes'],'source_references':d['source_references'],
      'data_references':d['data_references'],'scope':{'mode':'BOUNDED_PERFORMANCE_BATCH','parent_profile':None,'review':rr}})

def main():
    p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='action',required=True)
    d=s.add_parser('draft');d.add_argument('--request',required=True);d.add_argument('--output',required=True)
    d=s.add_parser('finalize');d.add_argument('--draft',required=True);d.add_argument('--root-review',required=True)
    a=p.parse_args();print(draft(a.request,a.output) if a.action=='draft' else finalize(a.draft,a.root_review))
if __name__=='__main__':main()
