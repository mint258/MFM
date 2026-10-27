"""Actual small metadata only; independent Root review is not synthesized."""
import argparse,copy
from pathlib import Path
from . import contract as C
Q=C.Q


def draft(request_path,out):
    v=Q.load(request_path);Q.need(v['schema']=='ROOT_REQUESTED_TDC_ZIP44_IDENTITY_V1' and v['requested_by']=='root'
        and v['status']=='REQUESTED_FOR_REVIEW','ACTUAL_ROOT_REQUEST_NOT_APPROVAL')
    b=C.meta(v['accepted_header_receipt_reference']);plan={'schema':'TDC_ZIP44_IDENTITY_PLAN_V1','scope_parameters':C.PARAMETERS,
        'accepted_header_receipt_reference':v['accepted_header_receipt_reference'],'accepted_header_accounting_reference':v['accepted_header_accounting_reference'],
        'archive_reference':b['input_reference'],'cost_decision_reference':v['cost_decision_reference'],'wall_seconds':v['wall_seconds'],'output_directory':v['output_directory']}
    _,data,_,_,parents=C.inputs(plan);Q.need(type(v['wall_seconds']) is int and 600<=v['wall_seconds']<=7200 and v['wall_seconds']%60==0,'FINITE_EXPLICIT_WALL')
    out=Path(out);output=Path(v['output_directory']);Q.need(Q.ROOT/'control' in out.parents and not out.exists()
        and Q.ROOT/'artifacts' in output.parents and not output.exists(),'FRESH_CONTROL_AND_OUTPUT')
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.contract import validate_authority
    validate_authority(v['resource_authority_reference'],read_small=Q.read_small)
    cost=C.meta(v['cost_decision_reference']);Q.need(cost['status']=='USER_AUTHORIZED' and cost['on_overrun']=='REPORT_AND_CONTINUE'
        and cost['scientific_quality_thresholds_unchanged'] is True,'CURRENT_COST_QUALITY_AUTHORITY')
    out.mkdir(parents=True,exist_ok=False,mode=0o700);pr=Q.write_new(out/'plan.json',plan)
    sources=[*(Q.pin(C.HERE/n) for n in C.FILES),*(Q.pin(Q.REPO/n) for n in C.OLD),*parents,
        Q.pin(request_path),pr,v['resource_authority_reference'],v['cost_decision_reference']];by={}
    for r in sources:
        Q.need(r['path']!=data['path'] and Q.pin(r['path'])==r and (r['path'] not in by or by[r['path']]==r),'SMALL_SOURCE_ONLY_NEVER_ZIP_BODY');by[r['path']]=r
    sources=[by[k] for k in sorted(by)]
    fields={'kind':'analysis','scope_key':C.KEY,'scope_parameters':C.PARAMETERS,'pilot':False,'wall_seconds':v['wall_seconds'],
        'estimated_peak_output_bytes':C.CAP,'source_status_stage':C.STAGE,
        'execution_argv':[Q.PY,'-B','-m',C.MODULE,'--plan',str(out/'plan.json'),'--startup-proof','__ROOT_STARTUP_PROOF__']}
    review={**copy.deepcopy(fields),'schema':'EXACT_CPU_AUTO_MEMORY_SCOPE_ROOT_REVIEW_V1','status':'PENDING_ROOT_REVIEW','reviewer':None,
        'resource_authority_reference':v['resource_authority_reference'],'scope_mode':'BOUNDED_METADATA_PREPARATION','stage_output_cap_bytes':C.CAP,
        'parent_evidence_references':parents,'approved_source_references':sources,'data_references':[data],
        'all44_original_splits_identity_only_full_projection_authorized':True,'global_decontamination_pool_training_release':False}
    rr=Q.write_new(out/'root_review.template.json',review)
    return Q.write_new(out/'draft_receipt.json',{'schema':'TDC_ZIP44_IDENTITY_DRAFT_V1','status':'PENDING_INDEPENDENT_ROOT_REVIEW',
        'plan_reference':pr,'review_template_reference':rr,'stage_fields':fields,'source_references':sources,'data_references':[data],
        'resource_authority_reference':v['resource_authority_reference'],'scientific_ZIP_body_opened_or_hashed':False,'Root_approval_or_job_created':False})


def finalize(draft_path,review_path):
    d=Q.load(draft_path);Q.need(d['schema']=='TDC_ZIP44_IDENTITY_DRAFT_V1' and d['status']=='PENDING_INDEPENDENT_ROOT_REVIEW','PENDING_EXACT_DRAFT')
    rr=Q.pin(review_path);r=C.meta(rr);t=C.meta(d['review_template_reference'])
    Q.need(rr!=d['review_template_reference'] and r['status']=='APPROVED_FOR_EXACT_STAGE' and r['reviewer']=='root','INDEPENDENT_ROOT_APPROVED_EXACT_STAGE')
    for k,v in t.items():
        if k not in ('status','reviewer'):Q.need(r[k]==v,'EXACT_REVIEW_FIELD:'+k)
    for source in d['source_references']:Q.need(Q.pin(source['path'])==source,'ALL_SMALL_SOURCES_UNCHANGED')
    _,data,_,_,_=C.inputs(C.meta(d['plan_reference']));Q.need(d['data_references']==[data],'EXACT_ONE_MAIN_COPY_DATA_REF')
    spec={'schema':'ROOT_REVIEWED_CPU_AUTO_MEMORY_STAGE_SPEC_V1',**d['stage_fields'],'cpus':16,'memory_policy':'SLURM_DEFAULT_UNSPECIFIED',
        'stage_output_cap_bytes':C.CAP,'source_references':d['source_references'],'data_references':[data],
        'scope':{'mode':'BOUNDED_METADATA_PREPARATION','parent_profile':None,'review':rr}}
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.contract import validate_scope_spec
    validate_scope_spec(spec,d['resource_authority_reference'],read_small=Q.read_small)
    return Q.write_new(Path(draft_path).parent/'stage_spec.json',spec)


def main():
    Q.on_login();p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='action',required=True)
    a=s.add_parser('draft');a.add_argument('--request',type=Path,required=True);a.add_argument('--output',type=Path,required=True)
    a=s.add_parser('finalize');a.add_argument('--draft',type=Path,required=True);a.add_argument('--root-review',type=Path,required=True)
    a=p.parse_args();print(draft(a.request,a.output) if a.action=='draft' else finalize(a.draft,a.root_review))


if __name__=='__main__':main()
