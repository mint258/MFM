"""Root-only small draft/finalize; never inspect catalog DATA or raw archives."""
from __future__ import annotations
import argparse,copy,pathlib
from . import contract as C
Q=C.Q


def source_files():
    paths=[*(C.HERE/name for name in C.FILES),C.ARCHIVE,C.ARCHIVE5,C.ARCHIVE.with_name('wp5_acceptance_catalog_v3.py')]
    paths += list((C.REPO/'workflows/data_v1_final/execution/cpu_auto_memory_queue_v2').glob('*.py'))
    paths += list((C.REPO/'workflows/data_v1_final/execution/queue_v1').glob('*.py'))
    paths += [C.OBSERVER/name for name in ('support.py','resource_runtime.py')]
    C.need(all(p.exists() for p in paths),'ALL_NEW_AND_REUSED_SOURCES_INSTALLED')
    return paths


def draft(request_path,out):
    v=Q.load(request_path)
    C.need(v['schema']=='ROOT_REQUESTED_NATIVE_RAW_AVAILABILITY_V1' and v['status']=='REQUESTED_FOR_REVIEW'
        and v['requested_by']=='root','ROOT_REQUEST_ONLY_NOT_APPROVAL')
    mode=v['mode'];params=C.parameters(mode);inputs=v['input_authority_references']
    C.need(set(inputs)==C.INPUT_KEYS,'EXACT_SMALL_INPUT_AUTHORITIES')
    for ref in inputs.values():C.meta(ref)
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.contract import validate_authority
    validate_authority(v['resource_authority_reference'],read_small=Q.read_small)
    cost=C.meta(v['cost_decision_reference'])
    C.need(cost['status']=='USER_AUTHORIZED' and cost['on_overrun']=='REPORT_AND_CONTINUE'
        and cost['scientific_quality_thresholds_unchanged'] is True,'CURRENT_COST_AND_QUALITY_AUTHORITY')
    parent_refs=v.get('parent_evidence_references',[])
    C.need(type(parent_refs) is list and bool(parent_refs),'EXISTING_CLOSED_PARENT_METADATA_REQUIRED')
    for ref in parent_refs:C.need(Q.pin(ref['path'])==C.triple(ref),'ACTUAL_SMALL_PARENT_PIN')
    if mode=='prepare':
        C.need(not v.get('preparation_closure_references'),'NO_FUTURE_PREPARATION_CLOSURE')
        data=C.prepare_data(inputs);closures=None
    else:
        closures=v['preparation_closure_references'];prepared,extra=C.closed_preparation(closures)
        C.need(inputs==prepared['input_authority_references'],'UNCHANGED_ORIGINAL_PREPARATION_AUTHORITIES')
        data=C.expected_probe_data(prepared);parent_refs=C.unique([*parent_refs,*extra])
    out=pathlib.Path(out);output=pathlib.Path(v['output_directory'])
    allowed=C.ROOT/'artifacts/labels/source_status_v1/native_availability_v1'
    C.need(out.is_absolute() and C.ROOT/'control' in out.parents and not out.exists()
        and allowed in output.parents and '..' not in output.parts and not output.exists(),'FRESH_METADATA_AND_SCOPED_OUTPUT')
    refs=C.unique([*(Q.pin(p) for p in source_files()),*inputs.values(),*parent_refs,Q.pin(request_path),
        v['resource_authority_reference'],v['cost_decision_reference']])
    C.need(not {r['path'] for r in refs}&{r['path'] for r in data},'SOURCE_DATA_DISJOINT_NO_BODY_ON_LOGIN')
    for r in refs:C.need(Q.pin(r['path'])==r,'ACTUAL_SMALL_SOURCE_PIN')
    out.mkdir(parents=True,exist_ok=False,mode=0o700)
    plan={'schema':'NATIVE_RAW_AVAILABILITY_PLAN_V1','mode':mode,'scope_parameters':params,
        'wall_seconds':C.WALL,'output_cap_bytes':C.CAP,'output_directory':str(output),
        'input_authority_references':inputs,'data_references':data,'source_references':refs,
        'resource_authority_reference':v['resource_authority_reference'],'cost_decision_reference':v['cost_decision_reference']}
    if closures:plan['preparation_closure_references']=closures
    plan_ref=Q.write_new(out/'plan.json',plan);refs=C.unique([*refs,plan_ref])
    fields={'kind':'analysis','scope_key':C.scope(mode),'scope_parameters':params,'pilot':False,
        'wall_seconds':C.WALL,'estimated_peak_output_bytes':C.CAP,
        'source_status_stage':'NATIVE_RAW_METADATA_ONLY_'+mode.upper(),
        'execution_argv':[C.PY,'-B','-m',C.MODULE,'--plan',str(out/'plan.json'),'--startup-proof','__ROOT_STARTUP_PROOF__']}
    review={'schema':'EXACT_CPU_AUTO_MEMORY_SCOPE_ROOT_REVIEW_V1','status':'PENDING_ROOT_REVIEW','reviewer':None,
        **copy.deepcopy(fields),'resource_authority_reference':v['resource_authority_reference'],
        'scope_mode':'BOUNDED_METADATA_PREPARATION','stage_output_cap_bytes':C.CAP,
        'parent_evidence_references':parent_refs,'approved_source_references':refs,'data_references':data,
        'raw_frame_or_staged_BLOB_fetch_allowed':False,'input_body_state':'HASH_ONLY_NOT_SAVED',
        'native_frame_and_tokens':'PENDING','new_QM_calls':0,'new_UFF_calls':0}
    rr=Q.write_new(out/'root_review.template.json',review)
    return Q.write_new(out/'draft_receipt.json',{'schema':'NATIVE_RAW_METADATA_DRAFT_V1','status':'PENDING_INDEPENDENT_ROOT_REVIEW',
        'mode':mode,'plan_reference':plan_ref,'review_template_reference':rr,'stage_fields':fields,
        'source_references':refs,'data_references':data,'resource_authority_reference':v['resource_authority_reference'],
        'scientific_DATA_opened_statted_or_hashed_on_login':False,'raw_archive_opened':False,'Root_approval_or_submission_created':False})


def finalize(draft_path,review_path):
    d=Q.load(draft_path);C.need(d['schema']=='NATIVE_RAW_METADATA_DRAFT_V1'
        and d['status']=='PENDING_INDEPENDENT_ROOT_REVIEW','EXACT_PENDING_NATIVE_METADATA_DRAFT')
    rr=Q.pin(review_path);r=C.meta(rr);t=C.meta(d['review_template_reference'])
    C.need(rr!=d['review_template_reference'] and r['status']=='APPROVED_FOR_EXACT_STAGE' and r['reviewer']=='root','INDEPENDENT_ACTUAL_ROOT_REVIEW')
    for key,value in t.items():
        if key not in ('status','reviewer'):C.need(r[key]==value,'ROOT_EXACT_REVIEW_FIELD:'+key)
    for ref in d['source_references']:C.need(Q.pin(ref['path'])==ref,'FROZEN_SMALL_SOURCE_CHANGED')
    plan=C.meta(d['plan_reference'])
    if d['mode']=='prepare':expected=C.prepare_data(plan['input_authority_references'])
    else:
        prior,_=C.closed_preparation(plan['preparation_closure_references']);expected=C.expected_probe_data(prior)
    C.need(expected==d['data_references']==plan['data_references'],'EXACT_DECLARED_DATA_NO_DYNAMIC_ARCHIVE_OPEN')
    spec={'schema':'ROOT_REVIEWED_CPU_AUTO_MEMORY_STAGE_SPEC_V1',**d['stage_fields'],
        'cpus':16,'memory_policy':'SLURM_DEFAULT_UNSPECIFIED','stage_output_cap_bytes':C.CAP,
        'source_references':d['source_references'],'data_references':d['data_references'],
        'scope':{'mode':'BOUNDED_METADATA_PREPARATION','parent_profile':None,'review':rr}}
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.contract import validate_scope_spec
    validate_scope_spec(spec,d['resource_authority_reference'],read_small=Q.read_small)
    return Q.write_new(pathlib.Path(draft_path).parent/'stage_spec.json',spec)


def main():
    Q.on_login();p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='action',required=True)
    a=sub.add_parser('draft');a.add_argument('--request',type=pathlib.Path,required=True);a.add_argument('--output',type=pathlib.Path,required=True)
    a=sub.add_parser('finalize');a.add_argument('--draft',type=pathlib.Path,required=True);a.add_argument('--root-review',type=pathlib.Path,required=True)
    a=p.parse_args();print(draft(a.request,a.output) if a.action=='draft' else finalize(a.draft,a.root_review))
if __name__=='__main__':main()