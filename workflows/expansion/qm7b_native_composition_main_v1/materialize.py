"""Unsigned metadata plan; Root independently approves the set-only exact scope."""
import argparse,copy
from pathlib import Path
from . import contract as C
Q=C.Q


def draft(request_path,out):
    v=Q.load(request_path);Q.need(v['schema']=='ROOT_REQUESTED_QM7B_AUTHOR_NATIVE_COMPOSITION_V1' and v['status']=='REQUESTED_FOR_REVIEW'
        and v['requested_by']=='root','ACTUAL_ROOT_REQUEST_NOT_APPROVAL')
    b=C.T.meta(v['accepted_format_receipt_reference'])
    plan={'schema':'QM7B_AUTHOR_NATIVE_COMPOSITION_PLAN_V1','scope_parameters':C.PARAMETERS,'data_references':[b['original_reference']],
        'accepted_format_receipt_reference':v['accepted_format_receipt_reference'],'accepted_format_accounting_reference':v['accepted_format_accounting_reference'],
        'author_transport_reference':v['author_transport_reference'],'decontamination_policy_reference':v['decontamination_policy_reference'],
        'cost_decision_reference':v['cost_decision_reference'],'wall_seconds':v['wall_seconds'],'output_cap_bytes':C.CAP,'output_directory':v['output_directory']}
    _,parents=C.inputs(plan)
    Q.need(type(v['wall_seconds']) is int and 600<=v['wall_seconds']<=1800 and v['wall_seconds']%60==0,'FINITE_WHOLE_MINUTE_FULL7211_STAGE')
    out=Path(out);output=Path(v['output_directory']);Q.need(out.is_absolute() and '..' not in out.parts and Q.ROOT/'control' in out.parents and not out.exists()
        and output.is_absolute() and '..' not in output.parts and Q.ROOT/'artifacts' in output.parents and not output.exists(),'FRESH_METADATA_AND_JOB_OUTPUT')
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.contract import validate_authority
    validate_authority(v['resource_authority_reference'],read_small=Q.read_small)
    cost=C.T.meta(v['cost_decision_reference']);Q.need(cost['status']=='USER_AUTHORIZED' and cost['on_overrun']=='REPORT_AND_CONTINUE'
        and cost['scientific_quality_thresholds_unchanged'] is True,'ACTUAL_COST_QUALITY_AUTHORITY')
    out.mkdir(parents=True,mode=0o700);pr=Q.write_new(out/'plan.json',plan)
    sources=C.unique([*(Q.pin(C.HERE/name) for name in C.FILES),*(Q.pin(path) for path in C.OLD),
        *(Q.pin(path) for path in (Q.REPO/'workflows/data_v1_final/execution/cpu_auto_memory_queue_v2').glob('*.py')),
        *parents,Q.pin(request_path),pr,v['resource_authority_reference'],v['cost_decision_reference']])
    for r in sources:Q.need(r['path']!=plan['data_references'][0]['path'] and Q.pin(r['path'])==r,'SMALL_SOURCE_METADATA_ONLY_NEVER_HASH_OR_PARSE_XYZ_ON_LOGIN')
    fields={'kind':'analysis','scope_key':C.KEY,'scope_parameters':C.PARAMETERS,'pilot':False,'wall_seconds':v['wall_seconds'],
        'estimated_peak_output_bytes':C.CAP,'source_status_stage':C.STAGE,
        'execution_argv':[Q.PY,'-B','-m',C.MODULE,'--plan',str(out/'plan.json'),'--startup-proof','__ROOT_STARTUP_PROOF__']}
    review={**copy.deepcopy(fields),'schema':'EXACT_CPU_AUTO_MEMORY_SCOPE_ROOT_REVIEW_V1','status':'PENDING_ROOT_REVIEW','reviewer':None,
        'resource_authority_reference':v['resource_authority_reference'],'scope_mode':'BOUNDED_METADATA_PREPARATION','stage_output_cap_bytes':C.CAP,
        'parent_evidence_references':parents,'approved_source_references':sources,'data_references':plan['data_references'],
        'author_asserted_all7211_set_conservative_composition_only_authorized':True,'exact_MAT_ID_native_graph_or_pool_release_authorized':False}
    rr=Q.write_new(out/'root_review.template.json',review)
    return Q.write_new(out/'draft_receipt.json',{'schema':'QM7B_NATIVE_COMPOSITION_DRAFT_V1','status':'PENDING_INDEPENDENT_ROOT_REVIEW',
        'plan_reference':pr,'review_template_reference':rr,'stage_fields':fields,'source_references':sources,'data_references':plan['data_references'],
        'resource_authority_reference':v['resource_authority_reference'],'scientific_XYZ_or_format_DATA_journal_read_hashed_or_parsed':False,
        'Root_approval_or_job_created':False})


def finalize(draft_path,review_path):
    d=Q.load(draft_path);Q.need(d['schema']=='QM7B_NATIVE_COMPOSITION_DRAFT_V1' and d['status']=='PENDING_INDEPENDENT_ROOT_REVIEW','EXACT_PENDING_UNSIGNED_DRAFT')
    rr=Q.pin(review_path);r=C.T.meta(rr);template=C.T.meta(d['review_template_reference'])
    Q.need(rr!=d['review_template_reference'] and r['status']=='APPROVED_FOR_EXACT_STAGE' and r['reviewer']=='root','INDEPENDENT_ROOT_AUTHOR_SET_ONLY_APPROVAL')
    for key,value in template.items():
        if key not in ('status','reviewer'):Q.need(r[key]==value,'EXACT_REVIEW_FIELD:'+key)
    for source in d['source_references']:Q.need(Q.pin(source['path'])==source,'SOURCE_OR_SMALL_METADATA_CHANGED')
    plan=C.T.meta(d['plan_reference']);C.inputs(plan);Q.need(plan['data_references']==d['data_references'],'EXACT_ACTUAL_SINGLE_XYZ_DATA_REF')
    spec={'schema':'ROOT_REVIEWED_CPU_AUTO_MEMORY_STAGE_SPEC_V1',**d['stage_fields'],'cpus':16,'memory_policy':'SLURM_DEFAULT_UNSPECIFIED',
        'stage_output_cap_bytes':C.CAP,'source_references':d['source_references'],'data_references':d['data_references'],
        'scope':{'mode':'BOUNDED_METADATA_PREPARATION','parent_profile':None,'review':rr}}
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.contract import validate_scope_spec
    validate_scope_spec(spec,d['resource_authority_reference'],read_small=Q.read_small)
    return Q.write_new(Path(draft_path).parent/'stage_spec.json',spec)


def main():
    Q.on_login();p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='mode',required=True)
    a=s.add_parser('draft');a.add_argument('--request',type=Path,required=True);a.add_argument('--output',type=Path,required=True)
    a=s.add_parser('finalize');a.add_argument('--draft',type=Path,required=True);a.add_argument('--root-review',type=Path,required=True)
    args=p.parse_args();print(draft(args.request,args.output) if args.mode=='draft' else finalize(args.draft,args.root_review))


if __name__=='__main__':main()
