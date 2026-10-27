"""Login metadata-only draft/finalize; no DATA hash/read, submission or signature."""
import argparse,copy,pathlib
from . import contract as C

def draft(path):
    r=C.Q.load(path);C.need(r['schema']=='ROOT_REQUESTED_PPRIME_PHYSICAL_CLOSURE_DAY_V1' and r['status']=='REQUESTED_FOR_REVIEW'
        and r['requested_by']=='root' and r['node'] in ('compute-0-14','compute-0-18') and r['cpus']==16,'EXACT_ROOT_REQUEST_NOT_AUTHORED_APPROVAL')
    out=pathlib.Path(r['metadata_output_directory']);C.need(C.ROOT/'control' in out.parents and '..' not in out.parts and not out.exists()
        and not any(p.is_symlink() for p in (out,*out.parents)),'FRESH_PRODUCER_METADATA_DIRECTORY')
    cap=r['output_cap_bytes'];params=C.parameters(cap);a,data,parents,_,_=C.derive(r)
    producer_out=pathlib.Path(r['output_directory']);C.need(C.BASE in producer_out.parents and '..' not in producer_out.parts
        and not producer_out.exists() and not any(p.is_symlink() for p in (producer_out,*producer_out.parents)),'FRESH_SHARED_DATA_OUTPUT')
    own=C.unique([C.Q.pin(p) for p in C.sources()],source=True)
    resource_keys=('resource_authority_reference','cost_decision_reference','quota_provider_review_reference','quota_provider_identity_reference','root_carveout_review_reference')
    resource=[C.P.triple(r[k]) for k in resource_keys]
    for ref in resource:C.need(C.Q.pin(ref['path'])==ref,'ACTUAL_RESOURCE_SMALL_REFERENCE')
    sources=C.unique([*own,*parents,*resource,C.Q.pin(path)],source=True)
    C.need(not {v['path'] for v in sources}&{v['path'] for v in data},'DISJOINT_SOURCE_METADATA_AND_DATA')
    plan={k:copy.deepcopy(r[k]) for k in ('aggregate_reference','native_summary_review_reference','old72_stage_receipt_reference',
        'old72_accounting_reference','official_source_catalog_reference',*resource_keys)}
    plan.update(schema='PPRIME_PHYSICAL_CLOSURE_DAY_PLAN_V1',scope_key=C.KEY,scope_parameters=params,cpus=16,node=r['node'],
        module=C.MODULE,wall_seconds=C.WALL,output_cap_bytes=cap,output_directory=str(producer_out),authority=a,
        source_references=sources,data_references=data,performance_statistics=False,new_QM_UFF_calls=0,scientific_PASS=False,full_or2000_release='HOLD')
    out.mkdir(parents=True,mode=0o700);pr=C.Q.write_new(out/'plan.candidate.json',plan)
    template={'schema':'ROOT_EXACT_PPRIME_PHYSICAL_CLOSURE_DAY_REVIEW_V1','status':'PENDING_ROOT_REVIEW','reviewer':None,
        'candidate_plan_reference':pr,'review_scope':'ONE_EXISTING_OUTPUT_ANALYSIS_PARENT_NOT_NEW_QM_OR_PRODUCTION_PRECISION_PERMISSION',
        'scope_key':C.KEY,'scope_parameters':params,'source_DATA_and_actual_failed_parent_preserved':True}
    tr=C.Q.write_new(out/'root_review.template.json',template)
    result={'schema':'PPRIME_PHYSICAL_CLOSURE_DAY_DRAFT_V1','status':'DRAFT_NOT_EXECUTABLE_OR_APPROVED','request_reference':C.Q.pin(path),
        'candidate_plan_reference':pr,'review_template_reference':tr,'node':r['node'],'job_name':r['job_name'],
        'final_plan_path':str(out/'plan.json'),'analysis_root_request_path':str(out/'analysis_day_root_request.json')}
    return C.Q.write_new(out/'draft.json',result)

def finalize(path,review_path):
    d=C.Q.load(path);need=C.need;need(d['schema']=='PPRIME_PHYSICAL_CLOSURE_DAY_DRAFT_V1','EXACT_THIS_PRODUCER_DRAFT')
    rr=C.Q.pin(review_path);review=C.meta(rr);template=C.meta(d['review_template_reference'])
    expected={**template,'status':'APPROVED','reviewer':'root'};need(review==expected,'ROOT_INDEPENDENT_EXACT_PRODUCER_REVIEW')
    plan=C.meta(d['candidate_plan_reference']);a,data,parents,_,_=C.derive(plan)
    need(a==plan['authority'] and data==plan['data_references'],'UNCHANGED_ACTUAL_PARENT_DERIVATION')
    for ref in plan['source_references']:need(C.Q.pin(ref['path'])==ref,'SOURCE_AND_SMALL_PARENTS_STILL_EXACT')
    final={**plan,'producer_root_review_reference':rr,'candidate_plan_reference':d['candidate_plan_reference']}
    p=C.Q.write_new(pathlib.Path(d['final_plan_path']),final)
    sources=C.unique([*plan['source_references'],rr,d['candidate_plan_reference'],p,C.Q.pin(path)],source=True)
    request={'schema':'ROOT_REQUESTED_ANALYSIS_DAY_V1','status':'REQUESTED_FOR_REVIEW','requested_by':'root',
        'job_name':d['job_name'],'cpus':16,'node':d['node'],'scope_key':C.KEY,'scope_parameters':plan['scope_parameters'],
        'producer_plan_reference':p,'estimated_peak_output_bytes':plan['output_cap_bytes'],'source_references':sources,'data_references':data}
    for key in ('resource_authority_reference','quota_provider_review_reference','quota_provider_identity_reference','root_carveout_review_reference'):request[key]=plan[key]
    q=C.Q.write_new(pathlib.Path(d['analysis_root_request_path']),request)
    return {'plan_reference':p,'analysis_day_root_request_reference':q,'submission_performed':False,'new_QM_calls':0}

def main():
    p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='command',required=True)
    a=s.add_parser('draft');a.add_argument('--request',type=pathlib.Path,required=True)
    b=s.add_parser('finalize');b.add_argument('--draft',type=pathlib.Path,required=True);b.add_argument('--root-review',type=pathlib.Path,required=True)
    a=p.parse_args();print(draft(a.request) if a.command=='draft' else finalize(a.draft,a.root_review))
if __name__=='__main__':main()
