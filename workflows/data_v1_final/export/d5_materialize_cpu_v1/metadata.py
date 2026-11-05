"""Login small metadata: missing parents never produce a runnable stage."""
from __future__ import annotations
import argparse,copy
from pathlib import Path
from . import contract as C
Q=C.Q


def fresh(path,base):
    p=Path(path);C.need(p.is_absolute() and base in p.parents and '..' not in p.parts and not p.exists()
        and not any(s.is_symlink() for s in (p,*p.parents)),'FRESH_LITERAL_OWNED_OUTPUT')
    return p


def draft(request_path,output):
    request=Q.load(request_path)
    C.need(request['schema']=='ROOT_REQUESTED_ORDINARY_D5_CPU_V1' and request['status']=='REQUESTED_FOR_REVIEW'
        and request['requested_by']=='root','ACTUAL_REQUEST_NOT_APPROVAL')
    mode=request['mode'];C.need(mode in C.WALL,'EXACT_D5_MODE')
    out=fresh(output,C.ROOT/'control');out.mkdir(mode=0o700,parents=True)
    blocked=C.pending(request)
    if blocked['missing_parents']:
        blocked['request_reference']=Q.pin(request_path)
        return Q.write_new(out/'pending.json',blocked)
    parameters=C.parameters(mode,request['seed'])
    plan={k:copy.deepcopy(request[k]) for k in ('mode','seed','parent_references','final_input_release_reference',
        'quota_reuse_reference','resource_authority_reference','cost_decision_reference','output_directory')}
    plan.update(schema='D5_ORDINARY_CPU_PLAN_V1',scope_parameters=parameters,wall_seconds=C.WALL[mode],output_cap_bytes=C.CAP[mode])
    if mode=='readback':plan['materialize_closure_references']=request['materialize_closure_references']
    _,_,_,data,parents,_=C.inputs(plan)
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.contract import validate_authority
    validate_authority(plan['resource_authority_reference'],read_small=Q.read_small)
    cost=C.meta(plan['cost_decision_reference']);C.need(cost['status']=='USER_AUTHORIZED'
        and cost['on_overrun']=='REPORT_AND_CONTINUE' and cost['scientific_quality_thresholds_unchanged'] is True,'UNCHANGED_QUALITY_AND_COST_REPORT_CONTINUE')
    fresh(plan['output_directory'],C.ROOT/'artifacts/labels/source_status_v1/d5_materialize_cpu_v1')
    C.original_source_check()
    refs=C.unique([*(Q.pin(p) for p in C.source_paths()),*parents,Q.pin(request_path),plan['resource_authority_reference'],plan['cost_decision_reference']])
    C.need(not {r['path'] for r in refs}&{r['path'] for r in data},'SMALL_SOURCE_AND_LARGE_DATA_DISJOINT')
    plan.update(data_references=data,source_references=refs)
    pr=Q.write_new(out/'plan.json',plan);refs=C.unique([*refs,pr])
    fields={'kind':'analysis','scope_key':'d5_ordinary_'+mode+'_cpu_v1','scope_parameters':parameters,'pilot':False,
        'wall_seconds':C.WALL[mode],'estimated_peak_output_bytes':C.CAP[mode],'source_status_stage':'ORDINARY_D5_'+mode.upper(),
        'execution_argv':[C.PY,'-B','-m',C.MODULE,'--plan',pr['path'],'--startup-proof','__ROOT_STARTUP_PROOF__']}
    template={'schema':'EXACT_CPU_AUTO_MEMORY_SCOPE_ROOT_REVIEW_V1','status':'PENDING_ROOT_REVIEW','reviewer':None,**copy.deepcopy(fields),
        'resource_authority_reference':plan['resource_authority_reference'],'scope_mode':'BOUNDED_PERFORMANCE_BATCH',
        'stage_output_cap_bytes':C.CAP[mode],'parent_evidence_references':parents,'approved_source_references':refs,
        'data_references':data,'bounded_batch_limits_reviewed':True,'new_QM_UFF_calls':0,'D5_jointly_frozen':False,
        'original_ordinary_source_ids_counts_and_selection_unchanged':True,'actual_CPU13_finite_quota_lease_and_space_reviewed':False}
    rr=Q.write_new(out/'root_review.template.json',template)
    return Q.write_new(out/'draft_receipt.json',{'schema':'D5_ORDINARY_CPU_DRAFT_V1','status':'PENDING_INDEPENDENT_ROOT_REVIEW',
        'plan_reference':pr,'review_template_reference':rr,'stage_fields':fields,'source_references':refs,'data_references':data,
        'resource_authority_reference':plan['resource_authority_reference'],'DATA_opened_statted_or_hashed':False,'stage_submitted':False})


def finalize(draft_path,review_path):
    d=Q.load(draft_path);C.need(d['schema']=='D5_ORDINARY_CPU_DRAFT_V1' and d['status']=='PENDING_INDEPENDENT_ROOT_REVIEW','EXACT_PENDING_DRAFT')
    rr=Q.pin(review_path);review=C.meta(rr);template=C.meta(d['review_template_reference'])
    C.need(rr!=d['review_template_reference'] and review['status']=='APPROVED_FOR_EXACT_STAGE' and review['reviewer']=='root'
        and review['actual_CPU13_finite_quota_lease_and_space_reviewed'] is True,'INDEPENDENT_ROOT_FINITE_SPACE_AND_SCOPE_REVIEW')
    for k,v in template.items():
        if k not in ('status','reviewer','actual_CPU13_finite_quota_lease_and_space_reviewed'):C.need(review[k]==v,'EXACT_ROOT_SCOPE_FIELD:'+k)
    for ref in d['source_references']:C.need(Q.pin(ref['path'])==ref,'EXACT_SOURCE_OR_SMALL_PARENT_CHANGED')
    p=C.meta(d['plan_reference']);C.need(C.inputs(p)[3]==d['data_references']==p['data_references'],'EXACT_ACTUAL_DECLARED_INPUTS')
    spec={'schema':'ROOT_REVIEWED_CPU_AUTO_MEMORY_STAGE_SPEC_V1',**d['stage_fields'],'cpus':16,
        'memory_policy':'SLURM_DEFAULT_UNSPECIFIED','stage_output_cap_bytes':p['output_cap_bytes'],
        'source_references':d['source_references'],'data_references':d['data_references'],
        'scope':{'mode':'BOUNDED_PERFORMANCE_BATCH','parent_profile':None,'review':rr}}
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.contract import validate_scope_spec
    validate_scope_spec(spec,d['resource_authority_reference'],read_small=Q.read_small)
    return Q.write_new(Path(draft_path).parent/'stage_spec.json',spec)


def close(receipt,proof,accounting,output):
    chain={'receipt':Q.pin(receipt),'startup_proof':Q.pin(proof),'accounting':Q.pin(accounting)}
    r,plan,parents=C.materialize_parent(chain,'readback')
    old,oldplan,oldrefs=C.materialize_parent(plan['materialize_closure_references'])
    C.need(oldplan['final_input_release_reference']==plan['final_input_release_reference']
        and r['all_TRAIN_molecules_projected']==old['subset_counts']['train_all']
        and r['subset_counts']==old['subset_counts'],'COMPLETE_SAME_INPUT_MATERIALIZE_AND_READBACK')
    for key,n in (('train_120000',120000),('train_240000',240000),('train_600000',600000),('pilot_train',50000),('pilot_val',5000)):
        C.need(r['subset_counts'][key]==n,'ACTUAL_GUIDE_COUNTS_CLOSED')
    path=fresh(output,C.ROOT/'control')
    return Q.write_new(path,{'schema':'D5_ACTUAL_TWO_STAGE_TECHNICAL_CLOSURE_V1',
        'status':'ACTUAL_ORDINARY_D5_MATERIALIZE_AND_FULL_READBACK_C0_ROOT_PUBLICATION_PENDING',
        'readback_closure_references':chain,'materialize_closure_references':plan['materialize_closure_references'],
        'actual_small_parent_references':C.unique([*parents,*oldrefs]),'final_input_release_reference':plan['final_input_release_reference'],
        'subset_counts':r['subset_counts'],'diagnostic_TRAIN_molecules':20000,'full_TRAIN_projection_molecules':r['all_TRAIN_molecules_projected'],
        'D5_jointly_frozen':False,'D3_label_export_or_Model_VAL_accepted':False,'new_QM_UFF_calls':0,
        'scientific_DATA_opened_statted_or_hashed_on_login':False})


def main():
    Q.on_login();p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='action',required=True)
    d=s.add_parser('draft');d.add_argument('--request',type=Path,required=True);d.add_argument('--output',type=Path,required=True)
    f=s.add_parser('finalize');f.add_argument('--draft',type=Path,required=True);f.add_argument('--root-review',type=Path,required=True)
    c=s.add_parser('close');c.add_argument('--readback-receipt',type=Path,required=True);c.add_argument('--readback-proof',type=Path,required=True)
    c.add_argument('--readback-accounting',type=Path,required=True);c.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    if a.action=='draft':result=draft(a.request,a.output)
    elif a.action=='finalize':result=finalize(a.draft,a.root_review)
    else:result=close(a.readback_receipt,a.readback_proof,a.readback_accounting,a.output)
    print(result)
if __name__=='__main__':main()
