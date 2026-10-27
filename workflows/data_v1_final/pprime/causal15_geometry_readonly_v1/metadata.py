"""Actual small metadata only; independent Root review and existing central queue."""
import argparse,copy,pathlib
from . import contract as C
Q=C.Q


def draft(request_path,out):
    v=Q.load(request_path);Q.need(v['schema']=='ROOT_REQUESTED_PPRIME15_GEOMETRY_READONLY_V1' and v['status']=='REQUESTED_FOR_REVIEW'
        and v['requested_by']=='root','ROOT_REQUEST_NOT_APPROVAL')
    plan={'schema':'PPRIME_CAUSAL15_GEOMETRY_READONLY_PLAN_V1','scope_parameters':C.PARAMETERS,'output_cap_bytes':C.CAP,
        **{k:v[k] for k in ('recovery_summary_reference','recovery_plan_reference','recovery_startup_proof_reference','recovery_accounting_reference',
            'resource_authority_reference','cost_decision_reference','wall_seconds','output_directory')}}
    rp,source,_,cases,data,parents=C.parents(plan);plan['case_sources']=cases;plan['data_references']=data
    Q.need(type(v['wall_seconds']) is int and 300<=v['wall_seconds']<=1800 and v['wall_seconds']%60==0,'BOUNDED_WHOLE_MINUTE_WALL')
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.contract import validate_authority
    validate_authority(v['resource_authority_reference'],read_small=Q.read_small)
    cost=C.meta(v['cost_decision_reference']);Q.need(cost['status']=='USER_AUTHORIZED' and cost['on_overrun']=='REPORT_AND_CONTINUE'
        and cost['scientific_quality_thresholds_unchanged'] is True,'ACTUAL_COST_QUALITY_AUTHORITY')
    out=pathlib.Path(out);output=pathlib.Path(v['output_directory']);Q.need(out.is_absolute() and output.is_absolute() and '..' not in out.parts and '..' not in output.parts
        and Q.ROOT/'control' in out.parents and not out.exists() and Q.ROOT/'artifacts' in output.parents and not output.exists(),'FRESH_METADATA_AND_OUTPUT')
    sources=C.unique([*(Q.pin(C.HERE/n) for n in C.FILES),*(Q.pin(C.P.HERE/n) for n in C.P.FILES),
        *(Q.pin(C.D.HERE/n) for n in C.D.FILES),*(Q.pin(p) for p in C.D.OLD),
        *source['source_references'],*rp['source_references'],*parents,Q.pin(request_path),v['resource_authority_reference'],v['cost_decision_reference'],
        *(Q.pin(p) for p in (Q.REPO/'workflows/data_v1_final/execution/cpu_auto_memory_queue_v2').glob('*.py'))])
    for r in sources:Q.need(r['path'] not in {d['path'] for d in data} and Q.pin(r['path'])==r,'SOURCE_ONLY_NO_SCIENTIFIC_BODY_READ_ON_LOGIN')
    out.mkdir(parents=True,exist_ok=False,mode=0o700);pr=Q.write_new(out/'plan.json',plan);sources=C.unique([*sources,pr])
    fields={'kind':'analysis','scope_key':C.KEY,'scope_parameters':C.PARAMETERS,'pilot':False,'wall_seconds':v['wall_seconds'],
        'estimated_peak_output_bytes':C.CAP,'source_status_stage':C.STAGE,
        'execution_argv':[Q.PY,'-B','-m',C.MODULE,'--plan',str(out/'plan.json'),'--startup-proof','__ROOT_STARTUP_PROOF__']}
    review={**copy.deepcopy(fields),'schema':'EXACT_CPU_AUTO_MEMORY_SCOPE_ROOT_REVIEW_V1','status':'PENDING_ROOT_REVIEW','reviewer':None,
        'resource_authority_reference':v['resource_authority_reference'],'scope_mode':'BOUNDED_METADATA_PREPARATION','stage_output_cap_bytes':C.CAP,
        'parent_evidence_references':parents,'approved_source_references':sources,'data_references':data,
        'actual_input_geometry_and_JSON_selection_only_zero_QM':True,'original15FAIL_preserved':True,'scientific_PASS':False,'full_or2000_release':'HOLD'}
    rr=Q.write_new(out/'root_review.template.json',review)
    return Q.write_new(out/'draft_receipt.json',{'schema':'PPRIME15_GEOMETRY_READONLY_DRAFT_V1','status':'PENDING_INDEPENDENT_ROOT_REVIEW',
        'plan_reference':pr,'review_template_reference':rr,'stage_fields':fields,'source_references':sources,'data_references':data,
        'resource_authority_reference':v['resource_authority_reference'],'scientific_bodies_opened_or_hashed':False,'Root_approval_or_job_created':False})


def finalize(draft_path,review_path):
    d=Q.load(draft_path);Q.need(d['schema']=='PPRIME15_GEOMETRY_READONLY_DRAFT_V1' and d['status']=='PENDING_INDEPENDENT_ROOT_REVIEW','EXACT_PENDING_DRAFT')
    rr=Q.pin(review_path);r=C.meta(rr);t=C.meta(d['review_template_reference'])
    Q.need(rr!=d['review_template_reference'] and r['status']=='APPROVED_FOR_EXACT_STAGE' and r['reviewer']=='root','INDEPENDENT_ROOT_REVIEW')
    for key,value in t.items():
        if key not in ('status','reviewer'):Q.need(r[key]==value,'EXACT_REVIEW_FIELD:'+key)
    for ref in d['source_references']:Q.need(Q.pin(ref['path'])==ref,'ACTUAL_SMALL_SOURCES_UNCHANGED')
    *_,data,parents=C.parents(C.meta(d['plan_reference']));Q.need(data==d['data_references'],'EXACT_PRODUCED_SHARED_DATA_REFS')
    spec={'schema':'ROOT_REVIEWED_CPU_AUTO_MEMORY_STAGE_SPEC_V1',**d['stage_fields'],'cpus':16,'memory_policy':'SLURM_DEFAULT_UNSPECIFIED',
        'stage_output_cap_bytes':C.CAP,'source_references':d['source_references'],'data_references':data,
        'scope':{'mode':'BOUNDED_METADATA_PREPARATION','parent_profile':None,'review':rr}}
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.contract import validate_scope_spec
    validate_scope_spec(spec,d['resource_authority_reference'],read_small=Q.read_small)
    return Q.write_new(pathlib.Path(draft_path).parent/'stage_spec.json',spec)


def main():
    Q.on_login();p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='action',required=True)
    a=s.add_parser('draft');a.add_argument('--request',type=pathlib.Path,required=True);a.add_argument('--output',type=pathlib.Path,required=True)
    a=s.add_parser('finalize');a.add_argument('--draft',type=pathlib.Path,required=True);a.add_argument('--root-review',type=pathlib.Path,required=True)
    a=p.parse_args();print(draft(a.request,a.output) if a.action=='draft' else finalize(a.draft,a.root_review))


if __name__=='__main__':main()
