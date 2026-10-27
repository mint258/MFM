"""Login stdlib metadata only; no source-log body and no automatic Root approval."""
import argparse,copy
from pathlib import Path
from . import contract as C
Q=C.Q


def draft(request_path,out):
    v=Q.load(request_path);Q.need(v['schema']=='ROOT_REQUESTED_MARCEL_DRUGS_KEYS_V1' and v['requested_by']=='root'
        and v['status']=='REQUESTED_FOR_REVIEW','ACTUAL_ROOT_REQUEST_NOT_APPROVAL')
    mode=v['mode'];cap=v['output_cap_bytes'];params=C.parameters(mode,cap)
    b=C.M.meta(v['accepted_probe_receipt_reference']);data=[r for r in b['output_references'] if Path(r['path']).name=='source_identity_rows.jsonl']
    Q.need(len(data)==1,'SOLE_PRODUCER_PINNED_IDENTITY_LOG')
    plan={'schema':'MARCEL_DRUGS_KEYS_PLAN_V1','mode':mode,'scope_parameters':params,'input_reference':data[0],
        'accepted_probe_receipt_reference':v['accepted_probe_receipt_reference'],'accepted_probe_accounting_reference':v['accepted_probe_accounting_reference'],
        'cost_decision_reference':v['cost_decision_reference'],'wall_seconds':v['wall_seconds'],'output_cap_bytes':cap,'output_directory':v['output_directory']}
    if mode=='full':
        for field in ('accepted_profile_receipt_reference','accepted_profile_accounting_reference','profile_root_review_reference'):plan[field]=v[field]
    _,parents=C.inputs(plan)
    Q.need(type(v['wall_seconds']) is int and 600<=v['wall_seconds']<=(7200 if mode=='profile' else 172800)
        and v['wall_seconds']%60==0,'EXPLICIT_WHOLE_MINUTE_WALL')
    out=Path(out);output=Path(v['output_directory']);Q.need(out.is_absolute() and output.is_absolute() and '..' not in out.parts and '..' not in output.parts
        and Q.ROOT/'control' in out.parents and not out.exists()
        and Q.ROOT/'artifacts' in output.parents and not output.exists(),'FRESH_CONTROL_AND_OUTPUT')
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.contract import validate_authority
    validate_authority(v['resource_authority_reference'],read_small=Q.read_small)
    cost=C.M.meta(v['cost_decision_reference']);Q.need(cost['status']=='USER_AUTHORIZED' and cost['on_overrun']=='REPORT_AND_CONTINUE'
        and cost['scientific_quality_thresholds_unchanged'] is True,'ACTUAL_COST_QUALITY_AUTHORITY')
    out.mkdir(parents=True,exist_ok=False,mode=0o700);pr=Q.write_new(out/'plan.json',plan)
    sources=C.unique([*(Q.pin(C.HERE/n) for n in C.FILES),*(Q.pin(path) for path in C.OLD),
        *(Q.pin(path) for path in (Q.REPO/'workflows/data_v1_final/execution/cpu_auto_memory_queue_v2').glob('*.py')),
        *parents,Q.pin(request_path),pr,v['resource_authority_reference'],v['cost_decision_reference']])
    for r in sources:Q.need(r['path']!=data[0]['path'] and Q.pin(r['path'])==r,'SMALL_SOURCE_ONLY_NOT_IDENTITY_LOG_BODY')
    fields={'kind':'analysis','scope_key':C.scope_key(mode),'scope_parameters':params,'pilot':mode=='profile',
        'wall_seconds':v['wall_seconds'],'estimated_peak_output_bytes':cap,'source_status_stage':C.STAGE,
        'execution_argv':[Q.PY,'-B','-m',C.MODULE,'--plan',str(out/'plan.json'),'--startup-proof','__ROOT_STARTUP_PROOF__']}
    scope_mode='BOUNDED_PERFORMANCE_BATCH' if mode=='profile' else 'FULL_SOURCE_AFTER_PROFILE'
    review={**copy.deepcopy(fields),'schema':'EXACT_CPU_AUTO_MEMORY_SCOPE_ROOT_REVIEW_V1','status':'PENDING_ROOT_REVIEW','reviewer':None,
        'resource_authority_reference':v['resource_authority_reference'],'scope_mode':scope_mode,'stage_output_cap_bytes':cap,
        'parent_evidence_references':parents,'approved_source_references':sources,'data_references':data,
        'all_native_conformers_variants_and_unknowns_retained':True,'global_decontamination_pool_training_release':False}
    if mode=='profile':review['bounded_batch_limits_reviewed']=True
    else:review.update(profile_reviewed=True,approved_profile_reference=plan['accepted_profile_receipt_reference'])
    rr=Q.write_new(out/'root_review.template.json',review)
    return Q.write_new(out/'draft_receipt.json',{'schema':'MARCEL_DRUGS_KEYS_DRAFT_V1','status':'PENDING_INDEPENDENT_ROOT_REVIEW',
        'plan_reference':pr,'review_template_reference':rr,'stage_fields':fields,'source_references':sources,'data_references':data,
        'resource_authority_reference':v['resource_authority_reference'],'scientific_identity_log_opened_or_hashed':False,'Root_approval_or_job_created':False})


def finalize(draft_path,review_path):
    d=Q.load(draft_path);Q.need(d['schema']=='MARCEL_DRUGS_KEYS_DRAFT_V1' and d['status']=='PENDING_INDEPENDENT_ROOT_REVIEW','EXACT_PENDING_DRAFT')
    rr=Q.pin(review_path);r=C.M.meta(rr);t=C.M.meta(d['review_template_reference'])
    Q.need(rr!=d['review_template_reference'] and r['status']=='APPROVED_FOR_EXACT_STAGE' and r['reviewer']=='root','INDEPENDENT_ROOT_APPROVED_STAGE')
    for key,value in t.items():
        if key not in ('status','reviewer'):Q.need(r[key]==value,'EXACT_REVIEW_FIELD:'+key)
    for source in d['source_references']:Q.need(Q.pin(source['path'])==source,'ALL_SMALL_SOURCE_PINS_UNCHANGED')
    plan=C.M.meta(d['plan_reference']);C.inputs(plan);Q.need(d['data_references']==[plan['input_reference']],'SOLE_EXACT_PRODUCER_LOG_DATA')
    spec={'schema':'ROOT_REVIEWED_CPU_AUTO_MEMORY_STAGE_SPEC_V1',**d['stage_fields'],'cpus':16,'memory_policy':'SLURM_DEFAULT_UNSPECIFIED',
        'stage_output_cap_bytes':plan['output_cap_bytes'],'source_references':d['source_references'],'data_references':d['data_references'],
        'scope':{'mode':t['scope_mode'],'parent_profile':plan.get('accepted_profile_receipt_reference'),'review':rr}}
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.contract import validate_scope_spec
    validate_scope_spec(spec,d['resource_authority_reference'],read_small=Q.read_small)
    return Q.write_new(Path(draft_path).parent/'stage_spec.json',spec)


def main():
    Q.on_login();p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='action',required=True)
    a=s.add_parser('draft');a.add_argument('--request',type=Path,required=True);a.add_argument('--output',type=Path,required=True)
    a=s.add_parser('finalize');a.add_argument('--draft',type=Path,required=True);a.add_argument('--root-review',type=Path,required=True)
    a=p.parse_args();print(draft(a.request,a.output) if a.action=='draft' else finalize(a.draft,a.root_review))


if __name__=='__main__':main()
