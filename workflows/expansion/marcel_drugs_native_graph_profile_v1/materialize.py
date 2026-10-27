"""Root small metadata draft/finalize; no body reads, approval signature or queue."""
import argparse,copy
from pathlib import Path
from . import contract as C
Q=C.Q


def draft(request_path,out):
    v=Q.load(request_path);Q.need(v['schema']=='ROOT_REQUESTED_MARCEL_DRUGS_NATIVE_GRAPH_PROFILE_V1' and v['status']=='REQUESTED_FOR_REVIEW'
        and v['requested_by']=='root','ROOT_REQUEST_NOT_APPROVAL')
    plan={'schema':'MARCEL_DRUGS_NATIVE_GRAPH_PROFILE_PLAN_V1','mode':'profile','scope_parameters':C.PARAMETERS,'wall_seconds':7200,'output_cap_bytes':C.CAP,
        **{k:v[k] for k in ('accepted_source_key_profile_receipt_reference','accepted_source_key_profile_accounting_reference','cost_decision_reference','output_directory')}}
    _,_,_,data,parents=C.inputs(plan);plan['data_references']=data
    out=Path(out);output=Path(v['output_directory']);Q.need(out.is_absolute() and output.is_absolute() and '..' not in out.parts and '..' not in output.parts
        and Q.ROOT/'control' in out.parents and not out.exists() and Q.ROOT/'artifacts' in output.parents and not output.exists()
        and not any(p.is_symlink() for p in (out,*out.parents,output,*output.parents)),'FRESH_CONTROL_AND_PROFILE_OUTPUT')
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.contract import validate_authority
    validate_authority(v['resource_authority_reference'],read_small=Q.read_small)
    cost=C.meta(v['cost_decision_reference']);Q.need(cost['status']=='USER_AUTHORIZED' and cost['on_overrun']=='REPORT_AND_CONTINUE' and cost['scientific_quality_thresholds_unchanged'] is True,'CURRENT_COST_AND_QUALITY_AUTHORITY')
    sources=C.unique([*(Q.pin(C.HERE/n) for n in C.FILES),*(Q.pin(p) for p in C.OLD),
        *(Q.pin(p) for p in (Q.REPO/'workflows/data_v1_final/execution/cpu_auto_memory_queue_v2').glob('*.py')),
        *parents,Q.pin(request_path),v['resource_authority_reference'],v['cost_decision_reference']])
    for r in sources:Q.need(r['path'] not in {d['path'] for d in data} and Q.pin(r['path'])==r,'SMALL_METADATA_ONLY_NO_SOURCE_JOURNAL_OR_ZIP_BODY')
    out.mkdir(parents=True,exist_ok=False,mode=0o700);pr=Q.write_new(out/'plan.json',plan);sources=C.unique([*sources,pr])
    fields={'kind':'analysis','scope_key':C.KEY,'scope_parameters':C.PARAMETERS,'pilot':True,'wall_seconds':7200,'estimated_peak_output_bytes':C.CAP,
        'source_status_stage':C.STAGE,'execution_argv':[Q.PY,'-B','-m',C.MODULE,'--plan',str(out/'plan.json'),'--startup-proof','__ROOT_STARTUP_PROOF__']}
    review={**copy.deepcopy(fields),'schema':'EXACT_CPU_AUTO_MEMORY_SCOPE_ROOT_REVIEW_V1','status':'PENDING_ROOT_REVIEW','reviewer':None,
        'resource_authority_reference':v['resource_authority_reference'],'scope_mode':'BOUNDED_PERFORMANCE_BATCH','stage_output_cap_bytes':C.CAP,
        'parent_evidence_references':parents,'approved_source_references':sources,'data_references':data,'bounded_batch_limits_reviewed':True,
        'author_native_SDF_reader_and_all_observed_union_reviewed':True,'full_or_pool_release':False}
    rr=Q.write_new(out/'root_review.template.json',review)
    return Q.write_new(out/'draft_receipt.json',{'schema':'MARCEL_DRUGS_NATIVE_GRAPH_PROFILE_DRAFT_V1','status':'PENDING_INDEPENDENT_ROOT_REVIEW','plan_reference':pr,
        'review_template_reference':rr,'stage_fields':fields,'source_references':sources,'data_references':data,'resource_authority_reference':v['resource_authority_reference'],
        'scientific_data_opened_or_hashed':False,'Root_approval_or_job_created':False})


def finalize(draft_path,review_path):
    d=Q.load(draft_path);Q.need(d['schema']=='MARCEL_DRUGS_NATIVE_GRAPH_PROFILE_DRAFT_V1' and d['status']=='PENDING_INDEPENDENT_ROOT_REVIEW','EXACT_PENDING_DRAFT')
    rr=Q.pin(review_path);r=C.meta(rr);t=C.meta(d['review_template_reference']);Q.need(rr!=d['review_template_reference'] and r['status']=='APPROVED_FOR_EXACT_STAGE' and r['reviewer']=='root','INDEPENDENT_ROOT_APPROVAL')
    for key,value in t.items():
        if key not in ('status','reviewer'):Q.need(r[key]==value,'EXACT_REVIEW_FIELD:'+key)
    for source in d['source_references']:Q.need(Q.pin(source['path'])==source,'ALL_SOURCE_PINS_UNCHANGED')
    plan=C.meta(d['plan_reference']);_,_,_,data,_=C.inputs(plan);Q.need(d['data_references']==data,'EXACT_FOUR_PRODUCER_PINNED_BODY_LOCATORS')
    spec={'schema':'ROOT_REVIEWED_CPU_AUTO_MEMORY_STAGE_SPEC_V1',**d['stage_fields'],'cpus':16,'memory_policy':'SLURM_DEFAULT_UNSPECIFIED','stage_output_cap_bytes':C.CAP,
        'source_references':d['source_references'],'data_references':data,'scope':{'mode':'BOUNDED_PERFORMANCE_BATCH','parent_profile':plan['accepted_source_key_profile_receipt_reference'],'review':rr}}
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.contract import validate_scope_spec
    validate_scope_spec(spec,d['resource_authority_reference'],read_small=Q.read_small);return Q.write_new(Path(draft_path).parent/'stage_spec.json',spec)


def main():
    Q.on_login();p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='action',required=True)
    a=s.add_parser('draft');a.add_argument('--request',type=Path,required=True);a.add_argument('--output',type=Path,required=True)
    a=s.add_parser('finalize');a.add_argument('--draft',type=Path,required=True);a.add_argument('--root-review',type=Path,required=True)
    a=p.parse_args();print(draft(a.request,a.output) if a.action=='draft' else finalize(a.draft,a.root_review))


if __name__=='__main__':main()
