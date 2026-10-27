"""Root small metadata→exact scope→actual C0 technical closure. No DATA IO."""
from __future__ import annotations
import argparse,copy
from pathlib import Path
from . import contract as C
Q=C.Q


def draft(request_path,output):
    v=Q.load(request_path);C.need(v['schema']=='ROOT_REQUESTED_NATIVE_PRECISION384_V1' and v['status']=='REQUESTED_FOR_REVIEW'
        and v['requested_by']=='root','ACTUAL_ROOT_REQUEST_NOT_APPROVAL')
    plan={k:copy.deepcopy(v[k]) for k in ('summary_closure_references','official_callchain_acquisition_reference',
        'output_directory','resource_authority_reference','cost_decision_reference')}
    plan.update(schema='NATIVE_PRECISION384_PLAN_V1',mode='precision',scope_parameters=C.parameters(),wall_seconds=C.WALL,output_cap_bytes=C.CAP)
    _,_,_,data,parents=C.derive(plan)
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.contract import validate_authority
    validate_authority(v['resource_authority_reference'],read_small=Q.read_small)
    cost=C.meta(v['cost_decision_reference']);C.need(cost['status']=='USER_AUTHORIZED' and cost['on_overrun']=='REPORT_AND_CONTINUE'
        and cost['scientific_quality_thresholds_unchanged'] is True,'UNCHANGED_QUALITY_AND_COST_REPORT_CONTINUE')
    out=Path(output);target=Path(v['output_directory']);allowed=C.ROOT/'artifacts/labels/source_status_v1/native_precision384_v1'
    C.need(out.is_absolute() and C.ROOT/'control' in out.parents and not out.exists() and '..' not in out.parts
        and target.is_absolute() and allowed in target.parents and not target.exists() and '..' not in target.parts
        and not any(p.is_symlink() for p in (out,*out.parents,target,*target.parents)),'FRESH_LITERAL_METADATA_AND_DATA_OUTPUT')
    refs=C.unique([*(Q.pin(p) for p in C.source_paths()),*parents,Q.pin(request_path),v['resource_authority_reference'],v['cost_decision_reference']])
    for r in refs:C.need(Q.pin(r['path'])==r,'ALL_ACTUAL_SOURCE_SMALL_PARENT_BYTES')
    C.need(not {r['path'] for r in refs}&{r['path'] for r in data},'SOURCE_AND_DATA_DISJOINT')
    out.mkdir(mode=0o700,parents=True);plan.update(source_references=refs,data_references=data)
    pr=Q.write_new(out/'plan.json',plan);refs=C.unique([*refs,pr])
    fields={'kind':'analysis','scope_key':C.SCOPE,'scope_parameters':C.parameters(),'pilot':False,
        'wall_seconds':C.WALL,'estimated_peak_output_bytes':C.CAP,'source_status_stage':'NATIVE_PRECISION384_READONLY',
        'execution_argv':[C.PY,'-B','-m',C.MODULE,'--plan',pr['path'],'--startup-proof','__ROOT_STARTUP_PROOF__']}
    template={'schema':'EXACT_CPU_AUTO_MEMORY_SCOPE_ROOT_REVIEW_V1','status':'PENDING_ROOT_REVIEW','reviewer':None,**copy.deepcopy(fields),
        'resource_authority_reference':v['resource_authority_reference'],'scope_mode':'BOUNDED_PERFORMANCE_BATCH','stage_output_cap_bytes':C.CAP,
        'parent_evidence_references':parents,'approved_source_references':refs,'data_references':data,'bounded_batch_limits_reviewed':True,
        'new_QM_UFF_calls':0,'printing_theoretical_bound_is_QC':False,'native_physics_or_joint_acceptance':False}
    rr=Q.write_new(out/'root_review.template.json',template)
    return Q.write_new(out/'draft_receipt.json',{'schema':'NATIVE_PRECISION384_DRAFT_V1','status':'PENDING_INDEPENDENT_ROOT_REVIEW',
        'plan_reference':pr,'review_template_reference':rr,'stage_fields':fields,'source_references':refs,'data_references':data,
        'resource_authority_reference':v['resource_authority_reference'],'scientific_DATA_opened_statted_or_hashed_on_login':False})


def finalize(draft_path,review_path):
    d=Q.load(draft_path);C.need(d['schema']=='NATIVE_PRECISION384_DRAFT_V1','EXACT_PENDING_DRAFT')
    rr=Q.pin(review_path);r=C.meta(rr);template=C.meta(d['review_template_reference'])
    C.need(rr!=d['review_template_reference'] and r['status']=='APPROVED_FOR_EXACT_STAGE' and r['reviewer']=='root','INDEPENDENT_ROOT_EXACT_SCOPE')
    for k,v in template.items():
        if k not in ('status','reviewer'):C.need(r[k]==v,'EXACT_ROOT_SCOPE_FIELD:'+k)
    for ref in d['source_references']:C.need(Q.pin(ref['path'])==ref,'FROZEN_SOURCE_OR_SMALL_PARENT_CHANGED')
    p=C.meta(d['plan_reference']);C.need(C.derive(p)[3]==p['data_references']==d['data_references'],'ONLY_SAME1152_ACTUAL_LOCATORS')
    spec={'schema':'ROOT_REVIEWED_CPU_AUTO_MEMORY_STAGE_SPEC_V1',**d['stage_fields'],'cpus':16,'memory_policy':'SLURM_DEFAULT_UNSPECIFIED',
        'stage_output_cap_bytes':C.CAP,'source_references':d['source_references'],'data_references':d['data_references'],
        'scope':{'mode':'BOUNDED_PERFORMANCE_BATCH','parent_profile':None,'review':rr}}
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.contract import validate_scope_spec
    validate_scope_spec(spec,d['resource_authority_reference'],read_small=Q.read_small)
    return Q.write_new(Path(draft_path).parent/'stage_spec.json',spec)


def close(manifest,proof,account,raw_account,output):
    refs={k:Q.pin(v) for k,v in {'manifest':manifest,'startup_proof':proof,'accounting':account,'raw_accounting':raw_account}.items()}
    m,p,parents=C.S.B.actual_closure(refs,'precision','NATIVE_PRECISION384_OBSERVATIONS_V1',
        'COMPLETE384_DIRECT_PRECISION_CONTROL_OBSERVATIONS_PHYSICAL_REVIEW_PENDING',C.MODULE,C.SCOPE,C.parameters())
    C.need(m['completed_keys']==384 and m['held_keys']==0 and m['native_physical_acceptance'] is False
        and m['D1_jointly_frozen'] is False and m['theoretical_printing_envelope_is_authorized_QC'] is False
        and m['full20k_completed'] is False and m['new_QM_UFF_calls']==0,'ACTUAL384_CLOSED_NOT_PHYSICAL_ACCEPTANCE')
    C.need(C.derive(p)[3]==p['data_references'],'ACTUAL_CLOSURE_EXACT_SAME1152_PARENT_DATA')
    for ref in p['source_references']:C.need(Q.pin(ref['path'])==ref,'ACTUAL_CLOSURE_ORIGINAL_SOURCE_SMALL_PARENT_STILL_EXACT')
    out=Path(output);C.need(out.is_absolute() and C.ROOT/'control' in out.parents and not out.exists()
        and '..' not in out.parts and not any(p.is_symlink() for p in (out,*out.parents)),'NEW_TECHNICAL_CLOSURE')
    return Q.write_new(out,{'schema':'NATIVE_PRECISION384_ACTUAL_C0_TECHNICAL_CLOSURE_V1',
        'status':'ACTUAL_BOUNDED_READONLY_PRECISION_EVIDENCE_CLOSED_NOT_QC_OR_JOINT',
        'closure_references':refs,'actual_small_parent_references':parents,'original_summary_closure_references':p['summary_closure_references'],
        'native_units_sign_origin_axes_accepted':False,'theoretical_printing_bound_is_QC':False,'full20k_completed':False,'D1_jointly_frozen':False})


def main():
    Q.on_login();p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='action',required=True)
    d=s.add_parser('draft');d.add_argument('--request',type=Path,required=True);d.add_argument('--output',type=Path,required=True)
    f=s.add_parser('finalize');f.add_argument('--draft',type=Path,required=True);f.add_argument('--root-review',type=Path,required=True)
    c=s.add_parser('close')
    for key in ('manifest','proof','account','raw-account','output'):c.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args()
    if a.action=='draft':result=draft(a.request,a.output)
    elif a.action=='finalize':result=finalize(a.draft,a.root_review)
    else:result=close(a.manifest,a.proof,a.account,a.raw_account,a.output)
    print(result)
if __name__=='__main__':main()
