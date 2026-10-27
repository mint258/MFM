"""Small metadata only; a real input-locator C0 must precede summary DATA use."""
from __future__ import annotations
import argparse,copy,pathlib
from . import contract as C
Q=C.Q


def resource_mode(mode):return 'BOUNDED_METADATA_PREPARATION' if mode=='prepare' else 'BOUNDED_PERFORMANCE_BATCH'


def draft(request_path,out):
    v=Q.load(request_path);C.need(v['schema']=='ROOT_REQUESTED_NATIVE_FRAME_SUMMARY32_V1'
        and v['status']=='REQUESTED_FOR_REVIEW' and v['requested_by']=='root','EXACT_ROOT_REQUEST_NOT_APPROVAL')
    mode=v['mode'];params=C.parameters(mode)
    p={'schema':'NATIVE_FRAME_SUMMARY32_PLAN_V1','mode':mode,'scope_parameters':params,'wall_seconds':C.WALL[mode],
        'output_cap_bytes':C.CAP[mode],'body_closure_references':v['body_closure_references'],
        'output_directory':v['output_directory'],'resource_authority_reference':v['resource_authority_reference'],
        'cost_decision_reference':v['cost_decision_reference'],'official_context_references':v.get('official_context_references',[])}
    if mode=='summary':p['input_locator_closure_references']=v['input_locator_closure_references']
    else:C.need(not v.get('input_locator_closure_references'),'NO_FUTURE_INPUT_LOCATOR_CLOSURE')
    _,_,_,_,data,parents=C.derive(p)
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.contract import validate_authority
    validate_authority(v['resource_authority_reference'],read_small=Q.read_small)
    cost=C.meta(v['cost_decision_reference']);C.need(cost['status']=='USER_AUTHORIZED' and cost['on_overrun']=='REPORT_AND_CONTINUE'
        and cost['scientific_quality_thresholds_unchanged'] is True,'UNCHANGED_QUALITY_REPORT_CONTINUE_COST')
    official=p['official_context_references'];C.need(type(official) is list and len(official)<=8,'BOUNDED_ACTUAL_OFFICIAL_SOURCE_CONTEXT')
    for r in official:C.need(Q.pin(r['path'])==C.B.A.triple(r),'ACTUAL_OFFICIAL_SOURCE_BYTES_NO_FUTURE_SHA')
    refs=C.unique([*(Q.pin(s) for s in C.source_paths()),*parents,*official,Q.pin(request_path),
        v['resource_authority_reference'],v['cost_decision_reference']])
    for r in refs:C.need(Q.pin(r['path'])==r,'ALL_ACTUAL_SMALL_SOURCE_AND_METADATA_PINS')
    C.need(not {r['path'] for r in refs}&{r['path'] for r in data},'SOURCE_DATA_DISJOINT')
    out=pathlib.Path(out);target=pathlib.Path(v['output_directory']);allowed=C.ROOT/'artifacts/labels/source_status_v1/native_frame_summary32_v1'
    C.need(out.is_absolute() and C.ROOT/'control' in out.parents and not out.exists() and '..' not in out.parts
        and target.is_absolute() and allowed in target.parents and not target.exists() and '..' not in target.parts
        and not any(s.is_symlink() for s in (out,*out.parents,target,*target.parents)),'FRESH_SCOPED_METADATA_AND_SUMMARY_OUTPUT')
    out.mkdir(parents=True,mode=0o700,exist_ok=False);p.update(data_references=data,source_references=refs)
    pr=Q.write_new(out/'plan.json',p);refs=C.unique([*refs,pr])
    fields={'kind':'analysis','scope_key':C.scope(mode),'scope_parameters':params,'pilot':False,'wall_seconds':C.WALL[mode],
        'estimated_peak_output_bytes':C.CAP[mode],'source_status_stage':'NATIVE_FRAME_SUMMARY32_'+mode.upper(),
        'execution_argv':[C.PY,'-B','-m',C.MODULE,'--plan',pr['path'],'--startup-proof','__ROOT_STARTUP_PROOF__']}
    review={'schema':'EXACT_CPU_AUTO_MEMORY_SCOPE_ROOT_REVIEW_V1','status':'PENDING_ROOT_REVIEW','reviewer':None,**copy.deepcopy(fields),
        'resource_authority_reference':v['resource_authority_reference'],'scope_mode':resource_mode(mode),'stage_output_cap_bytes':C.CAP[mode],
        'parent_evidence_references':parents,'approved_source_references':refs,'data_references':data,
        'bounded_batch_limits_reviewed':mode=='summary','scientific_summary_only_no_new_tolerance_or_D1_acceptance':True,
        'original_QM_UFF_calls':0,'native_unit_sign_axes_acceptance':False}
    rr=Q.write_new(out/'root_review.template.json',review)
    return Q.write_new(out/'draft_receipt.json',{'schema':'NATIVE_FRAME_SUMMARY32_DRAFT_V1','status':'PENDING_INDEPENDENT_ROOT_REVIEW',
        'mode':mode,'plan_reference':pr,'review_template_reference':rr,'stage_fields':fields,'source_references':refs,
        'data_references':data,'resource_authority_reference':v['resource_authority_reference'],
        'scientific_DATA_opened_statted_or_hashed_on_login':False,'Root_signature_or_submission_created':False})


def finalize(draft_path,review_path):
    d=Q.load(draft_path);C.need(d['schema']=='NATIVE_FRAME_SUMMARY32_DRAFT_V1'
        and d['status']=='PENDING_INDEPENDENT_ROOT_REVIEW','EXACT_PENDING_SUMMARY_DRAFT')
    rr=Q.pin(review_path);r=C.meta(rr);template=C.meta(d['review_template_reference'])
    C.need(rr!=d['review_template_reference'] and r['status']=='APPROVED_FOR_EXACT_STAGE' and r['reviewer']=='root','INDEPENDENT_ROOT_SCOPE_REVIEW')
    for k,v in template.items():
        if k not in ('status','reviewer'):C.need(r[k]==v,'EXACT_ROOT_REVIEW_FIELD:'+k)
    for ref in d['source_references']:C.need(Q.pin(ref['path'])==ref,'FROZEN_SOURCE_OR_METADATA_CHANGED')
    p=C.meta(d['plan_reference']);_,_,_,_,data,_=C.derive(p)
    C.need(data==p['data_references']==d['data_references'],'ONLY_ACTUAL_CLOSED_DECLARED_INPUTS')
    spec={'schema':'ROOT_REVIEWED_CPU_AUTO_MEMORY_STAGE_SPEC_V1',**d['stage_fields'],'cpus':16,
        'memory_policy':'SLURM_DEFAULT_UNSPECIFIED','stage_output_cap_bytes':C.CAP[d['mode']],
        'source_references':d['source_references'],'data_references':data,
        'scope':{'mode':resource_mode(d['mode']),'parent_profile':None,'review':rr}}
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.contract import validate_scope_spec
    validate_scope_spec(spec,d['resource_authority_reference'],read_small=Q.read_small)
    return Q.write_new(pathlib.Path(draft_path).parent/'stage_spec.json',spec)


def main():
    Q.on_login();p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='action',required=True)
    d=s.add_parser('draft');d.add_argument('--request',type=pathlib.Path,required=True);d.add_argument('--output',type=pathlib.Path,required=True)
    f=s.add_parser('finalize');f.add_argument('--draft',type=pathlib.Path,required=True);f.add_argument('--root-review',type=pathlib.Path,required=True)
    a=p.parse_args();print(draft(a.request,a.output) if a.action=='draft' else finalize(a.draft,a.root_review))
if __name__=='__main__':main()
