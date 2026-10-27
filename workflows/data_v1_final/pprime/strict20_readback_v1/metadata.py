"""Login small metadata only: Root review, exact stage, actual C0 and 20 closures."""
from __future__ import annotations
import argparse,copy,pathlib
from . import contract as C,io as I
Q=C.Q

def draft(request_path,out_path):
    r=Q.load(request_path);C.need(r['schema']=='ROOT_REQUESTED_STRICT20_READBACK_V1' and r['status']=='REQUESTED_FOR_REVIEW'
        and r['requested_by']=='root','ACTUAL_ROOT_REQUEST_NOT_APPROVAL')
    plan={k:copy.deepcopy(r[k]) for k in ('actual_root_review_reference','mode','output_directory','resource_authority_reference','cost_decision_reference','quota_reuse_reference')}
    plan['group_index']=r.get('group_index');plan['inventory_closure_reference']=r.get('inventory_closure_reference')
    mode=plan['mode'];params=C.parameters(mode,plan['group_index']);plan.update(schema='STRICT20_READBACK_PLAN_V1',scope_parameters=params,wall_seconds=C.WALL,output_cap_bytes=C.cap(mode))
    _,ep,data,parents,_,_=C.parents(plan)
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.contract import validate_authority
    validate_authority(plan['resource_authority_reference'],read_small=Q.read_small)
    cost=C.meta(plan['cost_decision_reference']);C.need(cost['status']=='USER_AUTHORIZED' and cost['on_overrun']=='REPORT_AND_CONTINUE'
        and cost['scientific_quality_thresholds_unchanged'] is True,'QUALITY_AND_COST_REPORT_CONTINUE_UNCHANGED')
    quota=C.meta(plan['quota_reuse_reference']);C.F.Provider.load_review(quota['provider_review_reference'])
    C.need(quota['status']=='APPROVED_RESOURCE_FACT_REUSE_ONLY' and quota['compute_node']=='compute-0-13','FINITE_ACTUAL_NODE13_PROVIDER_REVIEW')
    out=I.fresh(out_path,C.ROOT/'control');I.fresh(plan['output_directory'],C.BASE)
    refs=C.unique([*(Q.pin(p) for p in C.sources()),*parents,Q.pin(request_path),plan['resource_authority_reference'],plan['cost_decision_reference'],
        plan['quota_reuse_reference'],*C.F.Provider.references(quota['provider_review_reference'])],source=True)
    C.need(not {r['path'] for r in refs}&{r['path'] for r in data},'SOURCE_SMALL_METADATA_AND_SCIENTIFIC_DATA_DISJOINT')
    for ref in refs:C.need(Q.pin(ref['path'])==ref,'ALL_EXACT_SOURCE_SMALL_METADATA_PINS')
    out.mkdir(parents=True,mode=0o700);plan.update(source_references=refs,data_references=data);pr=Q.write_new(out/'plan.json',plan);refs=C.unique([*refs,pr],source=True)
    fields={'kind':'analysis','scope_key':C.scope(mode),'scope_parameters':params,'pilot':False,'wall_seconds':C.WALL,
        'estimated_peak_output_bytes':C.cap(mode),'source_status_stage':'STRICT20_INDEPENDENT_READONLY_'+mode.upper(),
        'execution_argv':[C.PY,'-B','-m',C.MODULE,'--plan',pr['path'],'--startup-proof','__ROOT_STARTUP_PROOF__']}
    review={'schema':'EXACT_CPU_AUTO_MEMORY_SCOPE_ROOT_REVIEW_V1','status':'PENDING_ROOT_REVIEW','reviewer':None,**copy.deepcopy(fields),
        'resource_authority_reference':plan['resource_authority_reference'],'scope_mode':'BOUNDED_PERFORMANCE_BATCH','stage_output_cap_bytes':C.cap(mode),
        'parent_evidence_references':parents,'approved_source_references':refs,'data_references':data,'bounded_batch_limits_reviewed':True,
        'strict_transitive_inventory_authority':{'allowed':mode=='inventory','actual_output_root':str(C.ACTUAL),
            'actual_prepared_reference':ep['prepared20_reference'],'actual_once_root_readonly':str(C.E.LEDGER),
            'only1200_actual_receipt_and_prepared_task_descendants':True,'positive_nonbool_triples_and_regular_single_link_UID1278_whole_SHA_currentFD':True},
        'all21_unique_stage_caps_total_bytes':896<<20,'technical_metadata_reserve_bytes':128<<20,'whole_new_output_ceiling_bytes':C.CAP,
        'native_initialize_or_invoke_or_retry':False,'native_inline_processing_independently_replayed':False,'scientific_or_full_release':False}
    rr=Q.write_new(out/'root_review.template.json',review)
    return Q.write_new(out/'draft_receipt.json',{'schema':'STRICT20_READBACK_DRAFT_V1','status':'PENDING_INDEPENDENT_ROOT_REVIEW','mode':mode,
        'plan_reference':pr,'review_template_reference':rr,'stage_fields':fields,'source_references':refs,'data_references':data,
        'resource_authority_reference':plan['resource_authority_reference'],'scientific_DATA_opened_statted_or_hashed_on_login':False})

def finalize(draft_path,review_path):
    d=Q.load(draft_path);C.need(d['schema']=='STRICT20_READBACK_DRAFT_V1','EXACT_PENDING_READBACK_DRAFT')
    rr=Q.pin(review_path);review=C.meta(rr);template=C.meta(d['review_template_reference'])
    C.need(rr!=d['review_template_reference'] and review['status']=='APPROVED_FOR_EXACT_STAGE' and review['reviewer']=='root','INDEPENDENT_ROOT_SCOPE_NOT_CHILD_SELF_SIGNATURE')
    for key,value in template.items():
        if key not in ('status','reviewer'):C.need(review[key]==value,'EXACT_APPROVED_READBACK_FIELD:'+key)
    for ref in d['source_references']:C.need(Q.pin(ref['path'])==ref,'SAME_FROZEN_SOURCE_SMALL_AUTHORITY')
    plan=C.meta(d['plan_reference']);C.need(C.parents(plan)[2]==plan['data_references']==d['data_references'],'ACTUAL_SAME_DATA_LOCATORS_ONLY')
    spec={'schema':'ROOT_REVIEWED_CPU_AUTO_MEMORY_STAGE_SPEC_V1',**d['stage_fields'],'cpus':16,'memory_policy':'SLURM_DEFAULT_UNSPECIFIED',
        'stage_output_cap_bytes':C.cap(plan['mode']),'source_references':d['source_references'],'data_references':d['data_references'],
        'scope':{'mode':'BOUNDED_PERFORMANCE_BATCH','parent_profile':None,'review':rr}}
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.contract import validate_scope_spec
    validate_scope_spec(spec,d['resource_authority_reference'],read_small=Q.read_small);return Q.write_new(pathlib.Path(draft_path).parent/'stage_spec.json',spec)

def close(refs,out_path):
    m,p,parents=C.actual(refs);C.need(C.parents(p)[2]==p['data_references'],'ACTUAL_CLOSURE_SAME_DATA_AUTHORITY')
    out=I.fresh(out_path,C.ROOT/'control')
    return Q.write_new(out,{'schema':'STRICT20_READBACK_ACTUAL_STAGE_C0_V1','status':'ACTUAL_READONLY_STAGE_C0_NOT_PHYSICAL_ACCEPTANCE','mode':m['mode'],
        'group_index':m.get('group_index'),'manifest_reference':refs['manifest'],'closure_references':refs,'actual_small_parent_references':parents,
        'scientific_PASS':False,'full_or2000_release':'HOLD','native_units_sign_basis_origin_axes_accepted':False,'SCF_cause':'UNKNOWN','new_QM_calls':0})

def aggregate(request_path,out_path):
    r=Q.load(request_path);C.need(r['schema']=='ROOT_REQUESTED_STRICT20_READBACK_AGGREGATION_V1' and r['requested_by']=='root'
        and r['status']=='REQUESTED_FOR_REVIEW' and len(r['audit_closure_references'])==20,'ACTUAL20_UNIQUE_GROUP_CLOSURES')
    inventory=C.meta(r['inventory_closure_reference']);im,ip,_=C.actual(inventory['closure_references']);C.need(im['mode']=='inventory','ACTUAL_INVENTORY_C0')
    seen=set();matrix={t:{a:0 for a in C.E.P.ARMS} for t in C.E.P.TASKS};parents=[r['inventory_closure_reference']];vector=0;used=0
    for ref in r['audit_closure_references']:
        v=C.meta(ref);m,p,_=C.actual(v['closure_references']);i=m['group_index']
        C.need(m['mode']=='audit' and i not in seen and p['inventory_closure_reference']==r['inventory_closure_reference']
            and p['actual_root_review_reference']==ip['actual_root_review_reference'],'SAME_INVENTORY_ROOT_DISTINCT_ALL20_AUDITS')
        C.need(pathlib.Path(p['output_directory']).is_relative_to(C.BASE),'OWN_FINITE_GROUP_OUTPUT');seen.add(i);vector+=m['original_vector_exact_comparisons'];used+=m['completed_calls'];parents.append(ref)
        for cell in m['condition_arm_matrix']:
            C.need(cell['own_exact']==cell['pair_exact']==5 and set(cell['arms'])==set(C.E.P.ARMS),'COMPLETE12_BY5_MATRIX')
            for arm,n in cell['arms'].items():C.need(type(n)is int and n==1,'EXACT_ONE_CELL_PER_GROUP');matrix[cell['condition']][arm]+=n
    C.need(seen==set(range(20)) and used==1200 and vector==500 and all(n==20 for row in matrix.values() for n in row.values()),'ALL1200_AND500_EXACT_NO_PARTIAL_ACCEPTANCE')
    for ref in parents:C.need(Q.pin(ref['path'])==ref,'ACTUAL_AGGREGATE_PARENTS_STILL_EXACT')
    return Q.write_new(I.fresh(out_path,C.ROOT/'control'),{'schema':'STRICT20_READBACK_ALL1200_ACTUAL_TECHNICAL_CLOSURE_V1',
        'status':'ACTUAL_ALL1200_LINEAGE_RAW_AND500_ORIGINAL_COMPARISONS_EXACT_PHYSICS_UNKNOWN',
        'actual_closure_references':parents,'original_actual_root_review_reference':ip['actual_root_review_reference'],'condition_arm_matrix':matrix,
        'actual_readonly_calls':used,'original_vector_exact_comparisons':vector,'native_inline_processing_independently_replayed':False,
        'native_process_count_independently_proved':False,'native_units_sign_basis_origin_axes_accepted':False,'SCF_cause':'UNKNOWN',
        'all_original_DATA_masks_tolerances_unchanged':True,'old15FAIL_preserved':True,'scientific_PASS':False,'full_or2000_release':'HOLD','new_QM_UFF_calls':0})

def main():
    Q.on_login();p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='action',required=True)
    a=s.add_parser('draft');a.add_argument('--request',type=pathlib.Path,required=True);a.add_argument('--output',type=pathlib.Path,required=True)
    a=s.add_parser('finalize');a.add_argument('--draft',type=pathlib.Path,required=True);a.add_argument('--root-review',type=pathlib.Path,required=True)
    a=s.add_parser('close')
    for name in ('manifest','proof','account','raw-account','output'):a.add_argument('--'+name,type=pathlib.Path,required=True)
    a=s.add_parser('aggregate');a.add_argument('--request',type=pathlib.Path,required=True);a.add_argument('--output',type=pathlib.Path,required=True)
    a=p.parse_args()
    if a.action=='draft':result=draft(a.request,a.output)
    elif a.action=='finalize':result=finalize(a.draft,a.root_review)
    elif a.action=='aggregate':result=aggregate(a.request,a.output)
    else:result=close({k:Q.pin(v) for k,v in {'manifest':a.manifest,'startup_proof':a.proof,'accounting':a.account,'raw_accounting':a.raw_account}.items()},a.output)
    print(result)
if __name__=='__main__':main()
