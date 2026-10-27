"""Main login: exact prior metadata -> unsigned plan, independent review, stage spec."""
import argparse,copy,pathlib
from . import contract as C
Q=C.Q


def draft(request_path,out):
    v=Q.load(request_path);Q.need(v['schema']=='ROOT_REQUESTED_PPRIME15_READONLY_RECOVERY_V1' and v['status']=='REQUESTED_FOR_REVIEW'
        and v['requested_by']=='root','EXPLICIT_ROOT_REQUEST_NOT_APPROVAL')
    plan={'schema':'PPRIME_CAUSAL15_READONLY_RECOVERY_PLAN_V1',
        **{k:v[k] for k in ('execution_receipt_reference','execution_accounting_reference','source_lstat_reference','quota_reuse_review_reference',
            'resource_authority_reference','cost_decision_reference','wall_seconds','output_directory')}}
    receipt,prepared,source,_,obs,locations,parents=C.parents(plan)
    from workflows.data_v1_final.pprime.causal15_main_v1.metadata_v3 import resource_refs
    resources=resource_refs(pathlib.Path(v['quota_reuse_review_reference']['path']))
    reuse=C.meta(v['quota_reuse_review_reference']);Q.need(reuse['additional_Pprime_readonly_recovery_cap_bytes']==C.CAP
        and reuse['whole_wave_output_reserve_bytes']>=reuse['preserved_previous_reserve_bytes']+C.CAP,'ACTUAL_SIGNED_ADDITIONAL_RECOVERY_RESERVE')
    Q.need(type(v['wall_seconds']) is int and 600<=v['wall_seconds']<=3600 and v['wall_seconds']%60==0,'FINITE_ROOT_WALL')
    cost=C.meta(v['cost_decision_reference']);Q.need(cost['status']=='USER_AUTHORIZED' and cost['on_overrun']=='REPORT_AND_CONTINUE'
        and cost['scientific_quality_thresholds_unchanged'] is True,'UNCHANGED_SCIENCE_AND_COST_AUTHORITY')
    sources=[*(Q.pin(C.HERE/n) for n in C.FILES),*source['source_references'],*parents,*resources,
        v['resource_authority_reference'],v['cost_decision_reference'],Q.pin(request_path)]
    claims={C.meta(r)['qa_id']:r for r in receipt['claims']};cases={};data=list(receipt['results'])
    for row in prepared['tasks']:
        qa=row['qa_id'];start=Q.pin(C.BASE/qa/'worker_start.json');intent=Q.pin(C.BASE/qa/'invoke_intent.json')
        cases[qa]={'claim_reference':claims[qa],'worker_start_reference':start,'invoke_intent_reference':intent}
        sources.extend([claims[qa],start,intent]);finished=C.BASE/qa/'finished.json'
        if finished.exists():sources.append(Q.pin(finished))
        data.extend([row['task_reference'],row['original_evidence_reference'],*row['target_input_references']])
        if qa!='qa-08':
            data.extend({'path':str(C.BASE/qa/'actual_postcall_inputs'/pathlib.Path(r['path']).name),'bytes':r['bytes'],'sha256':r['sha256']}
                for r in row['target_input_references'])
    plan['case_metadata']=cases;plan['data_references']=C.unique(data);plan['scope_parameters']=C.PARAMETERS
    out=pathlib.Path(out);output=pathlib.Path(v['output_directory']);Q.need(Q.ROOT/'control' in out.parents and not out.exists()
        and Q.ROOT/'artifacts' in output.parents and not output.exists(),'FRESH_RECOVERY_METADATA_AND_OUTPUT')
    out.mkdir(parents=True,exist_ok=False,mode=0o700)
    plan['source_references']=C.unique(sources);pr=Q.write_new(out/'plan.json',plan);sources=C.unique([*sources,pr])
    data_paths={r['path'] for r in plan['data_references']}
    for r in sources:Q.need(r['path'] not in data_paths and Q.pin(r['path'])==r,'SMALL_SOURCE_ONLY_NO_SCIENTIFIC_BODY_ON_LOGIN')
    fields={'kind':'analysis','scope_key':C.KEY,'scope_parameters':C.PARAMETERS,'pilot':False,'wall_seconds':v['wall_seconds'],
        'estimated_peak_output_bytes':C.CAP,'source_status_stage':C.STAGE,
        'execution_argv':[Q.PY,'-B','-m',C.MODULE,'--plan',str(out/'plan.json'),'--startup-proof','__ROOT_STARTUP_PROOF__']}
    review={**copy.deepcopy(fields),'schema':'EXACT_CPU_AUTO_MEMORY_SCOPE_ROOT_REVIEW_V1','status':'PENDING_ROOT_REVIEW','reviewer':None,
        'resource_authority_reference':v['resource_authority_reference'],'scope_mode':'BOUNDED_METADATA_PREPARATION','stage_output_cap_bytes':C.CAP,
        'parent_evidence_references':parents,'approved_source_references':sources,'data_references':plan['data_references'],
        'deferred_authority_references':locations,'zero_native_calls_no_once_writes_first_SHA_only_after_fixtures':True,
        'original15FAIL_preserved':True,'scientific_PASS':False,'full_or2000_release':'HOLD'}
    rr=Q.write_new(out/'root_review.template.json',review)
    return Q.write_new(out/'draft_receipt.json',{'schema':'PPRIME15_READONLY_RECOVERY_DRAFT_V1','status':'PENDING_INDEPENDENT_ROOT_REVIEW',
        'plan_reference':pr,'review_template_reference':rr,'stage_fields':fields,'source_references':sources,'data_references':plan['data_references'],
        'deferred_authority_references':locations,'resource_authority_reference':v['resource_authority_reference'],'scientific_bodies_read_or_hashed':False,
        'Root_approval_or_job_created':False})


def finalize(draft_path,review_path):
    d=Q.load(draft_path);Q.need(d['schema']=='PPRIME15_READONLY_RECOVERY_DRAFT_V1' and d['status']=='PENDING_INDEPENDENT_ROOT_REVIEW','EXACT_PENDING_DRAFT')
    rr=Q.pin(review_path);review=C.meta(rr);template=C.meta(d['review_template_reference'])
    Q.need(rr!=d['review_template_reference'] and review['status']=='APPROVED_FOR_EXACT_STAGE' and review['reviewer']=='root','INDEPENDENT_ROOT_REVIEW')
    for k,value in template.items():
        if k not in ('status','reviewer'):Q.need(review[k]==value,'ROOT_EXACT_FIELD:'+k)
    for r in d['source_references']:Q.need(Q.pin(r['path'])==r,'ALL_SMALL_SOURCES_UNCHANGED')
    plan=C.meta(d['plan_reference']);*_,locations,parents=C.parents(plan)
    Q.need(locations==d['deferred_authority_references'],'EXACT_ROOT_LSTAT_FIRST_SHA_LOCATORS')
    spec={'schema':'ROOT_REVIEWED_CPU_AUTO_MEMORY_STAGE_SPEC_V1',**d['stage_fields'],'cpus':16,'memory_policy':'SLURM_DEFAULT_UNSPECIFIED',
        'stage_output_cap_bytes':C.CAP,'source_references':d['source_references'],'data_references':d['data_references'],
        'deferred_authority_references':locations,'scope':{'mode':'BOUNDED_METADATA_PREPARATION','parent_profile':None,'review':rr}}
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.contract import validate_scope_spec
    validate_scope_spec(spec,d['resource_authority_reference'],read_small=Q.read_small)
    return Q.write_new(pathlib.Path(draft_path).parent/'stage_spec.json',spec)


def main():
    Q.on_login();p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='action',required=True)
    a=s.add_parser('draft');a.add_argument('--request',type=pathlib.Path,required=True);a.add_argument('--output',type=pathlib.Path,required=True)
    a=s.add_parser('finalize');a.add_argument('--draft',type=pathlib.Path,required=True);a.add_argument('--root-review',type=pathlib.Path,required=True)
    a=p.parse_args();print(draft(a.request,a.output) if a.action=='draft' else finalize(a.draft,a.root_review))


if __name__=='__main__':main()
