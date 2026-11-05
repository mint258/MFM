"""Stdlib login metadata draft/finalize; DATA is never opened or hashed here."""
import argparse,copy
from pathlib import Path
from . import contract as C
Q=C.Q
FIELDS=('common_manifest_reference','common_entry_reference','common_accounting_reference',
        'formal_writer_order_review_reference','graph_policy_reference','quota_reuse_reference','cost_decision_reference')

def draft(request_path,out):
    v=Q.load(request_path);Q.need(v['schema']=='ROOT_REQUESTED_COMMON_MOLECULAR_FP_DAY_BRIDGE_V1'
        and v['requested_by']=='root' and v['status']=='REQUESTED_FOR_REVIEW','ROOT_ACTUAL_REQUEST_NOT_APPROVAL')
    missing=[k for k in (*FIELDS,'resource_authority_reference') if v.get(k) is None]
    if v.get('mode')=='full':missing.extend(k for k in ('accepted_profile_receipt_reference','accepted_profile_accounting_reference','profile_root_review_reference') if v.get(k) is None)
    if missing:
        out=Path(out);Q.need(Q.ROOT/'control' in out.parents and not out.exists() and '..' not in out.parts,'FRESH_PENDING_CONTROL');out.mkdir(parents=True,mode=0o700)
        return Q.write_new(out/'pending.json',{'schema':'COMMON_FP_DAY_BRIDGE_PENDING_V1','status':'NONEXECUTABLE_PENDING_ACTUAL_PARENTS','missing':missing,'stage_spec_generated':False,'DATA_opened':False})
    mode=v['mode'];params=C.parameters(mode,v['output_cap_bytes']);wall=v['wall_seconds']
    Q.need(type(wall)is int and wall%60==0 and 600<=wall<=86400,'EXPLICIT_FINITE_WHOLE_MINUTE_WALL')
    plan={'schema':'COMMON_MOLECULAR_FP_DAY_BRIDGE_PLAN_V1','mode':mode,'scope_parameters':params,'wall_seconds':wall,
          'output_cap_bytes':v['output_cap_bytes'],'output_directory':v['output_directory'],**{k:v[k] for k in FIELDS}}
    if mode=='full':
        for name in ('accepted_profile_receipt_reference','accepted_profile_accounting_reference','profile_root_review_reference'):plan[name]=v[name]
    *_,data,parents=C.inputs(plan)
    cost=C.meta(v['cost_decision_reference']);Q.need(cost['status']=='USER_AUTHORIZED' and cost['on_overrun']=='REPORT_AND_CONTINUE'
        and cost['scientific_quality_thresholds_unchanged'] is True,'COST_AND_QUALITY_AUTHORITY')
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.contract import validate_authority
    validate_authority(v['resource_authority_reference'],read_small=Q.read_small)
    out=Path(out);output=Path(v['output_directory']);Q.need(Q.ROOT/'control' in out.parents and Q.ROOT/'artifacts' in output.parents
        and '..' not in out.parts and '..' not in output.parts and not out.exists() and not output.exists(),'FRESH_METADATA_AND_SCIENCE_PATHS')
    sources=C.unique([*(Q.pin(p) for p in C.source_paths()),*parents,Q.pin(request_path),v['resource_authority_reference'],v['cost_decision_reference']])
    for r in sources:Q.need(r['path'] not in {d['path'] for d in data} and Q.pin(r['path'])==r,'SMALL_SOURCE_ONLY_NO_DATA_HASH')
    out.mkdir(parents=True,exist_ok=False,mode=0o700);pr=Q.write_new(out/'plan.json',plan);sources=C.unique([*sources,pr])
    fields={'kind':'analysis','scope_key':C.key(mode),'scope_parameters':params,'pilot':mode=='profile','wall_seconds':wall,
        'estimated_peak_output_bytes':v['output_cap_bytes'],'source_status_stage':C.STAGE,
        'execution_argv':[Q.PY,'-B','-m',C.MODULE,'--plan',str(out/'plan.json'),'--startup-proof','__ROOT_STARTUP_PROOF__']}
    review={**copy.deepcopy(fields),'schema':'EXACT_CPU_AUTO_MEMORY_SCOPE_ROOT_REVIEW_V1','status':'PENDING_ROOT_REVIEW','reviewer':None,
        'resource_authority_reference':v['resource_authority_reference'],'scope_mode':'BOUNDED_PERFORMANCE_BATCH' if mode=='profile' else 'FULL_SOURCE_AFTER_PROFILE',
        'stage_output_cap_bytes':v['output_cap_bytes'],'parent_evidence_references':parents,'approved_source_references':sources,'data_references':data,
        'original_graph_and_accepted_difference_semantics_reviewed':True,'Root_final_graph_review_required_before_consumer_manifest':True,
        'NN_1M_pool_training_release':False}
    if mode=='profile':review['bounded_batch_limits_reviewed']=True
    else:review.update(profile_reviewed=True,approved_profile_reference=plan['accepted_profile_receipt_reference'])
    rr=Q.write_new(out/'root_review.template.json',review)
    return Q.write_new(out/'draft_receipt.json',{'schema':'COMMON_MOLECULAR_FP_DAY_BRIDGE_DRAFT_V1','status':'PENDING_INDEPENDENT_ROOT_REVIEW',
        'plan_reference':pr,'review_template_reference':rr,'stage_fields':fields,'source_references':sources,'data_references':data,
        'resource_authority_reference':v['resource_authority_reference'],'DATA_opened_or_hashed':False,'Root_approval_or_job_created':False})

def finalize(draft_path,review_path):
    d=Q.load(draft_path);Q.need(d['schema']=='COMMON_MOLECULAR_FP_DAY_BRIDGE_DRAFT_V1' and d['status']=='PENDING_INDEPENDENT_ROOT_REVIEW','EXACT_DRAFT')
    rr=Q.pin(review_path);r=C.meta(rr);t=C.meta(d['review_template_reference'])
    Q.need(rr!=d['review_template_reference'] and r['reviewer']=='root' and r['status']=='APPROVED_FOR_EXACT_STAGE','INDEPENDENT_ACTUAL_ROOT_REVIEW')
    for k,v in t.items():
        if k not in ('status','reviewer'):Q.need(r[k]==v,'EXACT_REVIEW_FIELD:'+k)
    for source in d['source_references']:Q.need(Q.pin(source['path'])==source,'ALL_SOURCE_PINS_UNCHANGED')
    plan=C.meta(d['plan_reference']);*_,data,parents=C.inputs(plan);Q.need(data==d['data_references'],'EXACT33_BODY_LOCATORS')
    spec={'schema':'ROOT_REVIEWED_CPU_AUTO_MEMORY_STAGE_SPEC_V1',**d['stage_fields'],'cpus':16,'memory_policy':'SLURM_DEFAULT_UNSPECIFIED',
        'stage_output_cap_bytes':plan['output_cap_bytes'],'source_references':d['source_references'],'data_references':data,
        'scope':{'mode':t['scope_mode'],'parent_profile':plan.get('accepted_profile_receipt_reference'),'review':rr}}
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.contract import validate_scope_spec
    validate_scope_spec(spec,d['resource_authority_reference'],read_small=Q.read_small)
    return Q.write_new(Path(draft_path).parent/'stage_spec.json',spec)

def main():
    Q.on_login();p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='action',required=True)
    a=s.add_parser('draft');a.add_argument('--request',type=Path,required=True);a.add_argument('--output',type=Path,required=True)
    a=s.add_parser('finalize');a.add_argument('--draft',type=Path,required=True);a.add_argument('--root-review',type=Path,required=True)
    a=s.add_parser('publish-projection');a.add_argument('--receipt',type=Path,required=True);a.add_argument('--accounting',type=Path,required=True);a.add_argument('--graph-review',type=Path,required=True);a.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    if a.action=='draft':result=draft(a.request,a.output)
    elif a.action=='finalize':result=finalize(a.draft,a.root_review)
    else:
        from .finalize import finalize as publish
        result=publish(Q.pin(a.receipt),Q.pin(a.accounting),Q.pin(a.graph_review),a.output)
    print(result)
if __name__=='__main__':main()
