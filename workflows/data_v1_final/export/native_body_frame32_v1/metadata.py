"""Root smallmetadata draft/finalize; no DATA stat, hash, parser or submit."""
from __future__ import annotations
import argparse,copy,pathlib
from . import contract as C
Q=C.Q


def draft(request_path,out):
    v=Q.load(request_path)
    C.need(v['schema']=='ROOT_REQUESTED_NATIVE_BODY_FRAME32_V1' and v['status']=='REQUESTED_FOR_REVIEW'
        and v['requested_by']=='root','EXPLICIT_ROOT_REQUEST_NOT_APPROVAL')
    mode=v['mode'];params=C.parameters(mode)
    plan={'schema':'NATIVE_BODY_FRAME32_PLAN_V1','mode':mode,'scope_parameters':params,
        'input_authority_references':v['input_authority_references'],'wall_seconds':C.WALLS[mode],
        'output_cap_bytes':C.CAPS[mode],'output_directory':v['output_directory'],
        'resource_authority_reference':v['resource_authority_reference'],'cost_decision_reference':v['cost_decision_reference']}
    if mode=='body':plan['locator_preparation_closure_references']=v['locator_preparation_closure_references']
    else:C.need(not v.get('locator_preparation_closure_references'),'NO_FUTURE_BODY_LOCATOR_CLOSURE')
    prepared,probe,prior,data,parents=C.derivation(plan)
    protocolref,recipe_refs=C.recipe_sources(prepared);plan['protocol_reference']=protocolref
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.contract import validate_authority
    validate_authority(v['resource_authority_reference'],read_small=Q.read_small)
    cost=C.meta(v['cost_decision_reference'])
    C.need(cost['status']=='USER_AUTHORIZED' and cost['on_overrun']=='REPORT_AND_CONTINUE'
        and cost['scientific_quality_thresholds_unchanged'] is True,'UNCHANGED_QUALITY_REPORT_CONTINUE_AUTHORITY')
    evidence=v.get('parent_evidence_references',[])
    C.need(type(evidence) is list,'PARENT_METADATA_LIST')
    refs=C.unique([*(Q.pin(p) for p in C.source_paths()),*parents,*recipe_refs,*evidence,
        *prepared['input_authority_references'].values(),Q.pin(request_path),v['resource_authority_reference'],v['cost_decision_reference']])
    C.need(not {r['path'] for r in refs}&{r['path'] for r in data},'SOURCE_DATA_DISJOINT')
    for ref in refs:C.need(Q.pin(ref['path'])==ref,'ACTUAL_SMALL_SOURCE_PIN')
    out=pathlib.Path(out);output=pathlib.Path(plan['output_directory']);allowed=C.ROOT/'artifacts/labels/source_status_v1/native_body_frame32_v1'
    C.need(out.is_absolute() and C.ROOT/'control' in out.parents and not out.exists()
        and output.is_absolute() and allowed in output.parents and '..' not in output.parts and not output.exists(),
        'FRESH_SCOPED_METADATA_AND_EVIDENCE')
    out.mkdir(parents=True,exist_ok=False,mode=0o700)
    plan.update(data_references=data,source_references=refs)
    planref=Q.write_new(out/'plan.json',plan);refs=C.unique([*refs,planref])
    fields={'kind':'analysis','scope_key':C.scope(mode),'scope_parameters':params,'pilot':False,
        'wall_seconds':C.WALLS[mode],'estimated_peak_output_bytes':C.CAPS[mode],
        'source_status_stage':'NATIVE_BODY_FRAME32_'+mode.upper(),
        'execution_argv':[C.PY,'-B','-m',C.MODULE,'--plan',planref['path'],'--startup-proof','__ROOT_STARTUP_PROOF__']}
    review={'schema':'EXACT_CPU_AUTO_MEMORY_SCOPE_ROOT_REVIEW_V1','status':'PENDING_ROOT_REVIEW','reviewer':None,
        **copy.deepcopy(fields),'resource_authority_reference':v['resource_authority_reference'],
        'scope_mode':C.resource_mode(mode),'stage_output_cap_bytes':C.CAPS[mode],
        'bounded_batch_limits_reviewed':mode=='body',
        'parent_evidence_references':parents,'approved_source_references':refs,'data_references':data,
        'raw_body_and_original_geometry_allowed':mode=='body','new_QM_calls':0,'new_UFF_calls':0,
        'joint_D1_approval':False,'labels_masks_or_original_DATA_modified':False}
    rr=Q.write_new(out/'root_review.template.json',review)
    return Q.write_new(out/'draft_receipt.json',{'schema':'NATIVE_BODY_FRAME32_DRAFT_V1','status':'PENDING_INDEPENDENT_ROOT_REVIEW',
        'mode':mode,'plan_reference':planref,'review_template_reference':rr,'stage_fields':fields,
        'source_references':refs,'data_references':data,'resource_authority_reference':v['resource_authority_reference'],
        'scientific_DATA_opened_statted_or_hashed_on_login':False,'Root_approval_or_submission_created':False})


def finalize(draft_path,review_path):
    d=Q.load(draft_path);C.need(d['schema']=='NATIVE_BODY_FRAME32_DRAFT_V1'
        and d['status']=='PENDING_INDEPENDENT_ROOT_REVIEW','EXACT_PENDING_DRAFT')
    rr=Q.pin(review_path);review=C.meta(rr);template=C.meta(d['review_template_reference'])
    C.need(rr!=d['review_template_reference'] and review['status']=='APPROVED_FOR_EXACT_STAGE'
        and review['reviewer']=='root','INDEPENDENT_ROOT_REVIEW')
    for k,v in template.items():
        if k not in ('status','reviewer'):C.need(review[k]==v,'ROOT_REVIEW_EXACT_FIELD:'+k)
    for ref in d['source_references']:C.need(Q.pin(ref['path'])==ref,'FROZEN_SOURCE_PIN_CHANGED')
    plan=C.meta(d['plan_reference']);_,_,_,data,_=C.derivation(plan)
    C.need(data==plan['data_references']==d['data_references'],'EXACT_ACTUAL_DATA_LINEAGE')
    spec={'schema':'ROOT_REVIEWED_CPU_AUTO_MEMORY_STAGE_SPEC_V1',**d['stage_fields'],'cpus':16,
        'memory_policy':'SLURM_DEFAULT_UNSPECIFIED','stage_output_cap_bytes':C.CAPS[d['mode']],
        'source_references':d['source_references'],'data_references':data,
        'scope':{'mode':C.resource_mode(d['mode']),'parent_profile':None,'review':rr}}
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.contract import validate_scope_spec
    validate_scope_spec(spec,d['resource_authority_reference'],read_small=Q.read_small)
    return Q.write_new(pathlib.Path(draft_path).parent/'stage_spec.json',spec)


def main():
    Q.on_login();p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='action',required=True)
    d=sub.add_parser('draft');d.add_argument('--request',type=pathlib.Path,required=True);d.add_argument('--output',type=pathlib.Path,required=True)
    f=sub.add_parser('finalize');f.add_argument('--draft',type=pathlib.Path,required=True);f.add_argument('--root-review',type=pathlib.Path,required=True)
    a=p.parse_args();print(draft(a.request,a.output) if a.action=='draft' else finalize(a.draft,a.root_review))
if __name__=='__main__':main()
