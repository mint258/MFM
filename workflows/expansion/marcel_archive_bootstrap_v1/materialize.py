"""Explicit Root metadata draft/finalize for a first-hash opaque archive stage."""
import argparse,copy
from pathlib import Path
from . import contract as C
Q=C.Q


def draft(request_path,out):
    v=Q.load(request_path);Q.need(v['schema']=='ROOT_REQUESTED_MARCEL_ARCHIVE_BOOTSTRAP_V1' and v['requested_by']=='root'
        and v['status']=='REQUESTED_FOR_REVIEW' and type(v['wall_seconds']) is int and 300<=v['wall_seconds']<=7200 and v['wall_seconds']%60==0,'EXPLICIT_FINITE_ROOT_BOOTSTRAP_REQUEST')
    transport,locator=C.transport(v['transport_receipt_reference'],v.get('relocation_reference'));params=C.parameters(transport,v['expanded_byte_cap'])
    out=Path(out);output=Path(v['output_directory']);Q.need(Q.ROOT/'control' in out.parents and not out.exists()
        and Q.ROOT/'artifacts' in output.parents and not output.exists(),'NEW_METADATA_AND_OUTPUT_PATHS')
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.contract import validate_authority
    validate_authority(v['resource_authority_reference'],read_small=Q.read_small)
    cost=C.meta(v['cost_decision_reference']);Q.need(cost['status']=='USER_AUTHORIZED' and cost['on_overrun']=='REPORT_AND_CONTINUE'
        and cost['scientific_quality_thresholds_unchanged'] is True,'UNCHANGED_COST_QUALITY_AUTHORITY')
    plan={'schema':'MARCEL_OFFICIAL_ARCHIVE_BOOTSTRAP_PLAN_V1','scope_parameters':params,'transport_receipt_reference':v['transport_receipt_reference'],
        'relocation_reference':v.get('relocation_reference'),
        'wall_seconds':v['wall_seconds'],'expanded_byte_cap':v['expanded_byte_cap'],'output_directory':str(output),
        'cost_decision_reference':v['cost_decision_reference'],'expected_archive_SHA_before_CPU':None}
    out.mkdir(parents=True,exist_ok=False,mode=0o700);pr=Q.write_new(out/'plan.json',plan)
    sources=[Q.pin(C.HERE/name) for name in C.FILES]+[Q.pin(request_path),pr,v['transport_receipt_reference'],v['resource_authority_reference'],v['cost_decision_reference']]
    parents=[v['transport_receipt_reference']]
    if v.get('relocation_reference') is not None:sources.append(v['relocation_reference']);parents.append(v['relocation_reference'])
    bypath={}
    for r in sources:
        Q.need(r['path']!=locator['path'] and Q.pin(r['path'])==r and (r['path'] not in bypath or bypath[r['path']]==r),'OPAQUE_ARCHIVE_NEVER_READ_AS_SMALL_SOURCE');bypath[r['path']]=r
    sources=[bypath[k] for k in sorted(bypath)]
    fields={'kind':'analysis','scope_key':C.KEY,'scope_parameters':params,'pilot':False,'wall_seconds':v['wall_seconds'],
        'estimated_peak_output_bytes':64<<20,'execution_argv':[Q.PY,'-B','-m',C.MODULE,'--plan',str(out/'plan.json'),'--startup-proof','__ROOT_STARTUP_PROOF__'],
        'source_status_stage':C.STAGE}
    review={**copy.deepcopy(fields),'schema':'EXACT_CPU_AUTO_MEMORY_SCOPE_ROOT_REVIEW_V1','status':'PENDING_ROOT_REVIEW','reviewer':None,
        'resource_authority_reference':v['resource_authority_reference'],'scope_mode':'BOUNDED_METADATA_PREPARATION','stage_output_cap_bytes':64<<20,
        'parent_evidence_references':parents,'approved_source_references':sources,'data_references':[],
        'deferred_authority_references':[locator],'first_unknown_archive_SHA_CPU_bootstrap_authorized':True,
        'prior_archive_CRC_or_identity_population_acceptance':False,'pool_or_identity_release':False}
    rr=Q.write_new(out/'root_review.template.json',review)
    return Q.write_new(out/'draft_receipt.json',{'schema':'MARCEL_ARCHIVE_BOOTSTRAP_DRAFT_V1','status':'PENDING_INDEPENDENT_ROOT_REVIEW',
        'review_template_reference':rr,'plan_reference':pr,'stage_fields':fields,'source_references':sources,
        'data_references':[],'deferred_authority_references':[locator],'resource_authority_reference':v['resource_authority_reference'],
        'opaque_file_stat_or_open_or_hash_or_ZIP_read':False,'new_Root_approval_or_job_created':False})


def finalize(draft_path,review_path):
    d=Q.load(draft_path);Q.need(d['schema']=='MARCEL_ARCHIVE_BOOTSTRAP_DRAFT_V1' and d['status']=='PENDING_INDEPENDENT_ROOT_REVIEW','EXACT_PENDING_DRAFT')
    rr=Q.pin(review_path);r=C.meta(rr);template=C.meta(d['review_template_reference'])
    Q.need(rr!=d['review_template_reference'] and r['status']=='APPROVED_FOR_EXACT_STAGE' and r['reviewer']=='root','INDEPENDENT_ACTUAL_ROOT_APPROVAL_REQUIRED')
    for k,v in template.items():
        if k not in ('status','reviewer'):Q.need(r[k]==v,'ROOT_EXACT_FIELD_DIFFERS:'+k)
    for source in d['source_references']:Q.need(Q.pin(source['path'])==source,'ACTUAL_SMALL_SOURCES_UNCHANGED')
    plan=C.meta(d['plan_reference']);_,locator=C.transport(plan['transport_receipt_reference'],plan.get('relocation_reference'));Q.need(d['deferred_authority_references']==[locator],'ACTUAL_ONE_UNHASHED_TRANSPORT_AUTHORITY')
    spec={'schema':'ROOT_REVIEWED_CPU_AUTO_MEMORY_STAGE_SPEC_V1',**d['stage_fields'],'cpus':16,'memory_policy':'SLURM_DEFAULT_UNSPECIFIED',
        'stage_output_cap_bytes':64<<20,'source_references':d['source_references'],'data_references':[],'deferred_authority_references':[locator],
        'scope':{'mode':'BOUNDED_METADATA_PREPARATION','parent_profile':None,'review':rr}}
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.contract import validate_scope_spec
    validate_scope_spec(spec,d['resource_authority_reference'],read_small=Q.read_small)
    return Q.write_new(Path(draft_path).parent/'stage_spec.json',spec)


def main():
    Q.on_login();p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='action',required=True)
    a=sub.add_parser('draft');a.add_argument('--request',type=Path,required=True);a.add_argument('--output',type=Path,required=True)
    a=sub.add_parser('finalize');a.add_argument('--draft',type=Path,required=True);a.add_argument('--root-review',type=Path,required=True)
    a=p.parse_args();print(draft(a.request,a.output) if a.action=='draft' else finalize(a.draft,a.root_review))


if __name__=='__main__':main()
