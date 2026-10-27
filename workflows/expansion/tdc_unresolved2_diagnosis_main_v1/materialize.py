"""Login small metadata only: unsigned draft and separately reviewed final spec."""
import argparse,copy
from pathlib import Path
from . import contract as C
Q=C.Q


def draft(request_path,out):
    v=Q.load(request_path);Q.need(v['schema']=='ROOT_REQUESTED_TDC_UNRESOLVED2_DIAGNOSIS_V1' and v['requested_by']=='root'
        and v['status']=='REQUESTED_FOR_REVIEW','REAL_ROOT_REQUEST_NOT_APPROVAL')
    b=C.T.meta(v['accepted_identity_receipt_reference']);data=[b['result']['journal_reference'],b['input_reference']]
    plan={'schema':'TDC_UNRESOLVED2_DIAGNOSIS_PLAN_V1','scope_parameters':C.PARAMETERS,
        'accepted_identity_receipt_reference':v['accepted_identity_receipt_reference'],
        'accepted_identity_accounting_reference':v['accepted_identity_accounting_reference'],'data_references':data,
        'cost_decision_reference':v['cost_decision_reference'],'wall_seconds':v['wall_seconds'],'output_cap_bytes':C.CAP,
        'output_directory':v['output_directory'],'original_stderr_reference':v.get('original_stderr_reference')}
    _,_,_,parents=C.inputs(plan)
    Q.need(type(v['wall_seconds']) is int and 600<=v['wall_seconds']<=3600 and v['wall_seconds']%60==0,'FINITE_WHOLE_MINUTE_SCOPE')
    out=Path(out);output=Path(v['output_directory']);Q.need(out.is_absolute() and '..' not in out.parts and Q.ROOT/'control' in out.parents and not out.exists()
        and output.is_absolute() and '..' not in output.parts and Q.ROOT/'artifacts' in output.parents and not output.exists(),'NEW_CONTROL_AND_OUTPUT')
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.contract import validate_authority
    validate_authority(v['resource_authority_reference'],read_small=Q.read_small)
    cost=C.T.meta(v['cost_decision_reference']);Q.need(cost['status']=='USER_AUTHORIZED' and cost['on_overrun']=='REPORT_AND_CONTINUE'
        and cost['scientific_quality_thresholds_unchanged'] is True,'EXACT_COST_QUALITY_AUTHORITY')
    out.mkdir(parents=True,mode=0o700);pr=Q.write_new(out/'plan.json',plan)
    sources=C.unique([*(Q.pin(C.HERE/n) for n in C.FILES),*(Q.pin(path) for path in C.OLD),
        *(Q.pin(path) for path in (Q.REPO/'workflows/data_v1_final/execution/cpu_auto_memory_queue_v2').glob('*.py')),
        *parents,Q.pin(request_path),pr,v['resource_authority_reference'],v['cost_decision_reference']])
    for r in sources:Q.need(r['path'] not in {d['path'] for d in data} and Q.pin(r['path'])==r,'NO_JOURNAL_OR_ZIP_LOGIN_HASH')
    fields={'kind':'analysis','scope_key':C.KEY,'scope_parameters':C.PARAMETERS,'pilot':False,'wall_seconds':v['wall_seconds'],
        'estimated_peak_output_bytes':C.CAP,'source_status_stage':C.STAGE,
        'execution_argv':[Q.PY,'-B','-m',C.MODULE,'--plan',str(out/'plan.json'),'--startup-proof','__ROOT_STARTUP_PROOF__']}
    review={**copy.deepcopy(fields),'schema':'EXACT_CPU_AUTO_MEMORY_SCOPE_ROOT_REVIEW_V1','status':'PENDING_ROOT_REVIEW','reviewer':None,
        'resource_authority_reference':v['resource_authority_reference'],'scope_mode':'BOUNDED_METADATA_PREPARATION','stage_output_cap_bytes':C.CAP,
        'parent_evidence_references':parents,'approved_source_references':sources,'data_references':data,
        'only_exact2_original_unknowns_ZIP_binding_authorized':True,'global_decontamination_pool_training_release':False}
    rr=Q.write_new(out/'root_review.template.json',review)
    return Q.write_new(out/'draft_receipt.json',{'schema':'TDC_UNRESOLVED2_DIAGNOSIS_DRAFT_V1','status':'PENDING_INDEPENDENT_ROOT_REVIEW',
        'plan_reference':pr,'review_template_reference':rr,'stage_fields':fields,'source_references':sources,'data_references':data,
        'resource_authority_reference':v['resource_authority_reference'],'journal_or_ZIP_opened_hashed_or_parsed':False,'Root_approval_or_job_created':False})


def finalize(draft_path,review_path):
    d=Q.load(draft_path);Q.need(d['schema']=='TDC_UNRESOLVED2_DIAGNOSIS_DRAFT_V1' and d['status']=='PENDING_INDEPENDENT_ROOT_REVIEW','EXACT_UNSIGNED_DRAFT')
    rr=Q.pin(review_path);r=C.T.meta(rr);template=C.T.meta(d['review_template_reference'])
    Q.need(rr!=d['review_template_reference'] and r['status']=='APPROVED_FOR_EXACT_STAGE' and r['reviewer']=='root','INDEPENDENT_ROOT_APPROVED_REVIEW')
    for k,value in template.items():
        if k not in ('status','reviewer'):Q.need(r[k]==value,'EXACT_REVIEW_FIELD:'+k)
    for source in d['source_references']:Q.need(Q.pin(source['path'])==source,'CURRENT_SMALL_SOURCE_PIN')
    plan=C.T.meta(d['plan_reference']);C.inputs(plan);Q.need(d['data_references']==plan['data_references'],'ONLY_ORIGINAL_JOURNAL_AND_ZIP_DATA')
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
