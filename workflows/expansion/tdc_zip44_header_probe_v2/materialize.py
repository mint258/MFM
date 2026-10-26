"""Main login metadata-only draft/finalize for existing centralCPU; never signs Root."""
import argparse,copy,csv,io
from pathlib import Path
from . import contract as C
Q=C.Q


def merge(*groups):
    rows={}
    for group in groups:
        for r in group:
            Q.need(r['path'] not in rows or rows[r['path']]==r,'CONFLICTING_SMALL_SOURCE_PIN');rows[r['path']]=r
    return [rows[k] for k in sorted(rows)]


def failed_parent(request):
    a=C.meta(request['parent_get_accounting_reference']);p=a['actual_parent'];local=request['parent_raw_sacct_copy_reference'];origin=a['raw_sacct_reference']
    Q.need(a['schema']=='SECONDARY_CPU_ACTUAL_ACCOUNTING_EVIDENCE_V1' and a['endpoint']=='218.192.171.238:22' and a['uid']==1264
        and a['query_returncode']==0 and p['JobIDRaw']=='1884799' and p['UID']=='1264' and p['State']=='FAILED'
        and p['ExitCode']!='0:0' and p['AllocCPUS']=='16' and a['allocated_core_seconds_observed']==int(p['ElapsedRaw'])*16,
        'WHOLE_FAILED1884799_COST_RETAINED_NOT_C0')
    Q.need(all(local[k]==origin[k] for k in ('bytes','sha256')) and Q.pin(local['path'])==local,'ACTUAL_UNCHANGED_MAIN_SMALL_RAW_ACCOUNT_COPY')
    rows=[r for r in csv.DictReader(io.StringIO(Q.read_small(local['path']).decode()),delimiter='|') if r.get('JobIDRaw')=='1884799']
    Q.need(len(rows)==1 and all(rows[0][k]==p[k] for k in ('UID','State','ExitCode','ElapsedRaw','AllocCPUS','NodeList','Partition')),'ACTUAL_FAILED_PARENT_RAW_BINDING')


def draft(request_path,out):
    request=Q.load(request_path);Q.need(request['schema']=='ROOT_REQUESTED_TDC_ZIP44_HEADER_PROBE_V1' and request['requested_by']=='root'
        and request['status']=='REQUESTED_FOR_REVIEW' and request['wall_seconds'] in (300,600),'EXPLICIT_ROOT_SMALL_PROBE_REQUEST')
    obs,target,entries=C.inputs(request['observation_reference'],request['relocation_reference']);failed_parent(request)
    out=Path(out);output=Path(request['output_directory'])
    Q.need(Q.ROOT/'control' in out.parents and not out.exists() and Q.ROOT/'artifacts' in output.parents and not output.exists(),'NEW_METADATA_AND_SCIENCE_LEAVES')
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.contract import validate_authority
    validate_authority(request['resource_authority_reference'],read_small=Q.read_small)
    cost=C.meta(request['cost_decision_reference']);Q.need(cost['status']=='USER_AUTHORIZED' and cost['on_overrun']=='REPORT_AND_CONTINUE'
        and cost['scientific_quality_thresholds_unchanged'] is True,'ACTUAL_COST_AUTHORITY_NO_SCIENCE_THRESHOLD_CHANGE')
    plan={'schema':'TDC_ZIP44_HEADER_PROBE_PLAN_V1','scope_key':C.KEY,'scope_parameters':C.PARAMETERS,'wall_seconds':request['wall_seconds'],
        'output_directory':str(output),'observation_reference':request['observation_reference'],'relocation_reference':request['relocation_reference'],
        'parent_get_accounting_reference':request['parent_get_accounting_reference'],'parent_raw_sacct_copy_reference':request['parent_raw_sacct_copy_reference'],
        'original_formats_reference':Q.pin(C.OLD/'formats.py'),'cost_decision_reference':request['cost_decision_reference'],
        'source_get_parent_was_C0':False,'identity_or_population_or_pool_release':False}
    out.mkdir(parents=True,exist_ok=False,mode=0o700);plan_ref=Q.write_new(out/'plan.json',plan)
    sources=merge([Q.pin(C.HERE/name) for name in C.FILES],[Q.pin(C.OLD/'formats.py'),Q.pin(C.OLD/'__init__.py')],
        [request[k] for k in ('observation_reference','relocation_reference','parent_get_accounting_reference','parent_raw_sacct_copy_reference','resource_authority_reference','cost_decision_reference')],
        [Q.pin(request_path),plan_ref])
    Q.need(target['path'] not in {r['path'] for r in sources},'ZIP_IS_DATA_NOT_PRE_FIXTURE_SMALL_SOURCE')
    for r in sources:Q.need(Q.pin(r['path'])==r,'CURRENT_SMALL_SOURCE_METADATA_ONLY')
    argv=[Q.PY,'-B','-m',C.MODULE,'--plan',str(out/'plan.json'),'--startup-proof','__ROOT_STARTUP_PROOF__']
    parents=[request[k] for k in ('observation_reference','relocation_reference','parent_get_accounting_reference','parent_raw_sacct_copy_reference')]
    fields={'kind':'analysis','scope_key':C.KEY,'scope_parameters':C.PARAMETERS,'pilot':False,'wall_seconds':request['wall_seconds'],
        'estimated_peak_output_bytes':64<<20,'execution_argv':argv,'source_status_stage':C.STAGE}
    review={**copy.deepcopy(fields),'schema':'EXACT_CPU_AUTO_MEMORY_SCOPE_ROOT_REVIEW_V1','status':'PENDING_ROOT_REVIEW','reviewer':None,
        'resource_authority_reference':request['resource_authority_reference'],'scope_mode':'BOUNDED_METADATA_PREPARATION',
        'stage_output_cap_bytes':64<<20,'parent_evidence_references':parents,'approved_source_references':sources,
        'data_references': [target],'accept_only_closed_TDC_payload_from_failed1884799':True,'identity_or_full_or_pool_release':False}
    template=Q.write_new(out/'root_review.template.json',review)
    Q.write_new(out/'draft_receipt.json',{'schema':'TDC_ZIP44_CENTRAL_DRAFT_V1','status':'PENDING_INDEPENDENT_ROOT_REVIEW',
        'plan_reference':plan_ref,'review_template_reference':template,'source_references':sources,'data_references':[target],
        'resource_authority_reference':request['resource_authority_reference'],'stage_fields':fields,'parent_evidence_references':parents,
        'ZIP_body_opened_hashed_parsed':False,'new_Root_approval_or_request_or_job_created':False})
    return Q.pin(out/'draft_receipt.json')


def finalize(draft_path,review_path):
    d=Q.load(draft_path);Q.need(d['schema']=='TDC_ZIP44_CENTRAL_DRAFT_V1' and d['status']=='PENDING_INDEPENDENT_ROOT_REVIEW','EXACT_DRAFT_ONLY')
    review_ref=Q.pin(review_path);review=C.meta(review_ref);template=C.meta(d['review_template_reference'])
    Q.need(review_ref!=d['review_template_reference'] and review['status']=='APPROVED_FOR_EXACT_STAGE' and review['reviewer']=='root','ROOT_INDEPENDENT_APPROVAL_REQUIRED')
    for k,v in template.items():
        if k not in ('status','reviewer'):Q.need(review[k]==v,'ROOT_EXACT_FIELD_DIFFERS:'+k)
    for r in [*d['source_references'],*d['parent_evidence_references'],d['plan_reference']]:Q.need(Q.pin(r['path'])==r,'DRAFT_SOURCE_OR_PARENT_CHANGED')
    plan=C.meta(d['plan_reference']);C.inputs(plan['observation_reference'],plan['relocation_reference'])
    spec={'schema':'ROOT_REVIEWED_CPU_AUTO_MEMORY_STAGE_SPEC_V1',**d['stage_fields'],'cpus':16,'memory_policy':'SLURM_DEFAULT_UNSPECIFIED',
        'stage_output_cap_bytes':64<<20,'source_references':d['source_references'],'data_references':d['data_references'],
        'scope':{'mode':'BOUNDED_METADATA_PREPARATION','parent_profile':None,'review':review_ref}}
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.contract import validate_scope_spec
    validate_scope_spec(spec,d['resource_authority_reference'],read_small=Q.read_small)
    out=Path(draft_path).parent;return Q.write_new(out/'stage_spec.json',spec)


def main():
    Q.on_login();p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='action',required=True)
    a=s.add_parser('draft');a.add_argument('--request',type=Path,required=True);a.add_argument('--output',type=Path,required=True)
    a=s.add_parser('finalize');a.add_argument('--draft',type=Path,required=True);a.add_argument('--root-review',type=Path,required=True)
    a=p.parse_args();r=draft(a.request,a.output) if a.action=='draft' else finalize(a.draft,a.root_review)
    print({'actual_small_metadata_reference':r,'body_reads':0,'submissions':0})


if __name__=='__main__':main()
