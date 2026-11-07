"""SOURCE/operational metadata only; separate Root budget and exact scope reviews."""
from __future__ import annotations
import argparse,copy
from pathlib import Path
from . import contract as C
Q=C.Q


def requested(path):
    v=Q.load(path)
    Q.need(v['schema']=='ROOT_REQUESTED_MARCEL_DRUGS_NATIVE_GRAPH_FULL_V1' and v['status']=='REQUESTED_FOR_REVIEW'
        and v['requested_by']=='root','ACTUAL_ROOT_REQUEST_ONLY_NOT_REVIEW')
    keys=('accepted_native_profile_receipt_reference','accepted_native_profile_accounting_reference',
        'accepted_source_key_full_receipt_reference','accepted_source_key_full_accounting_reference',
        'cost_decision_reference','output_directory')
    p={'schema':'MARCEL_DRUGS_NATIVE_GRAPH_FULL_PLAN_V1','mode':'full','scope_parameters':C.parameters(),
        'wall_seconds':C.WALL,'output_cap_bytes':C.CAP,**{k:v[k] for k in keys}}
    if v.get('profile_budget_root_review_reference'):p['profile_budget_root_review_reference']=v['profile_budget_root_review_reference']
    return v,p


def budget_template(request_path,output):
    v,p=requested(request_path);native,full,_,data,parents=C.inputs(p,require_review=False)
    review={'schema':'ROOT_DRUGS_NATIVE_FULL_COST_STORAGE_REVIEW_V1','status':'PENDING_INDEPENDENT_ROOT_COST_STORAGE_REVIEW','reviewer':None,
        **{k:p[k] for k in ('accepted_native_profile_receipt_reference','accepted_native_profile_accounting_reference',
            'accepted_source_key_full_receipt_reference','accepted_source_key_full_accounting_reference')},
        'actual_profile_cost_unknowns_and_source_mismatches_reviewed':True,
        'all558002_native_graphs_1000_adopted557002_new_authorized':True,
        'all75099_names_all633101_context_rows_and290_variant_groups_retained':True,
        'projection':C.project(native),'wall_seconds':C.WALL,'output_cap_bytes':C.CAP,
        'shared_output_cap_bytes':C.SHARED_CAP,'node_local_SDF_reserved_bytes':C.NODE_SDF_RESERVE,'storage_and_200GB_reserve_reviewed':True,
        'unknown_or_graph_mismatch_is_chemical_exclusion':False,'pool_or_global_decontamination_release_authorized':False,
        'actual_native_profile_allocated_core_seconds':C.meta(p['accepted_native_profile_accounting_reference'])['allocated_core_seconds'],
        'actual_source_key_full_allocated_core_seconds':C.meta(p['accepted_source_key_full_accounting_reference'])['allocated_core_seconds'],
        'exact_DATA_references':data,'parent_evidence_references':parents,
        'template_is_not_signed_Root_approval':True,'profile_does_not_bound_worst_case_storage_or_runtime':True}
    output=Path(output);Q.need(output.is_absolute() and Q.ROOT/'control' in output.parents and not output.exists()
        and '..' not in output.parts and not any(p.is_symlink() for p in (output,*output.parents)),'FRESH_ROOT_CONTROL_BUDGET_TEMPLATE')
    return Q.write_new(output,review)


def draft(request_path,out):
    v,p=requested(request_path);native,full,_,data,parents=C.inputs(p)
    Q.need(p['profile_budget_root_review_reference'] in parents,'ACTUAL_SEPARATE_ROOT_BUDGET_REVIEW')
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.contract import validate_authority
    validate_authority(v['resource_authority_reference'],read_small=Q.read_small)
    cost=C.meta(p['cost_decision_reference'])
    Q.need(cost['status']=='USER_AUTHORIZED' and cost['on_overrun']=='REPORT_AND_CONTINUE'
        and cost['scientific_quality_thresholds_unchanged'] is True,'UNCHANGED_QUALITY_REPORT_CONTINUE_COST_AUTHORITY')
    sources=C.unique([*(Q.pin(s) for s in C.source_paths()),*parents,Q.pin(request_path),
        v['resource_authority_reference'],v['cost_decision_reference']])
    Q.need(not {r['path'] for r in sources}&{r['path'] for r in data},'SOURCE_DATA_DISJOINT')
    for r in sources:Q.need(Q.pin(r['path'])==r,'EXACT_SMALL_SOURCE_OR_OPERATIONAL_METADATA')
    out=Path(out);output=Path(p['output_directory']);allowed=Q.ROOT/'artifacts/expansion/marcel_drugs_native_graph_full_v1'
    Q.need(out.is_absolute() and Q.ROOT/'control' in out.parents and not out.exists() and '..' not in out.parts
        and output.is_absolute() and allowed in output.parents and not output.exists() and '..' not in output.parts
        and not any(s.is_symlink() for s in (out,*out.parents,output,*output.parents)),'FRESH_FULL_NATIVE_CONTROL_AND_OUTPUT')
    out.mkdir(parents=True,exist_ok=False,mode=0o700);p['data_references']=data;pr=Q.write_new(out/'plan.json',p);sources=C.unique([*sources,pr])
    fields={'kind':'analysis','scope_key':C.KEY,'scope_parameters':C.parameters(),'pilot':False,'wall_seconds':C.WALL,
        'estimated_peak_output_bytes':C.CAP,'source_status_stage':C.STAGE,
        'execution_argv':[Q.PY,'-B','-m',C.MODULE,'--plan',str(out/'plan.json'),'--startup-proof','__ROOT_STARTUP_PROOF__']}
    review={'schema':'EXACT_CPU_AUTO_MEMORY_SCOPE_ROOT_REVIEW_V1','status':'PENDING_ROOT_REVIEW','reviewer':None,
        **copy.deepcopy(fields),'resource_authority_reference':v['resource_authority_reference'],
        'scope_mode':'FULL_SOURCE_AFTER_PROFILE','stage_output_cap_bytes':C.CAP,'parent_evidence_references':parents,
        'approved_source_references':sources,'data_references':data,'profile_reviewed':True,
        'approved_profile_reference':p['accepted_native_profile_receipt_reference'],
        'closed1000_adoption_and557002_new_only_reviewed':True,'candidate_pool_or_global_decontamination_release':False}
    rr=Q.write_new(out/'root_review.template.json',review)
    return Q.write_new(out/'draft_receipt.json',{'schema':'MARCEL_DRUGS_NATIVE_GRAPH_FULL_DRAFT_V1','status':'PENDING_INDEPENDENT_ROOT_REVIEW',
        'plan_reference':pr,'review_template_reference':rr,'stage_fields':fields,'source_references':sources,'data_references':data,
        'resource_authority_reference':v['resource_authority_reference'],'scientific_DATA_opened_statted_or_hashed':False,
        'Root_scope_signature_or_submission_created':False})


def finalize(draft_path,review_path):
    d=Q.load(draft_path);Q.need(d['schema']=='MARCEL_DRUGS_NATIVE_GRAPH_FULL_DRAFT_V1'
        and d['status']=='PENDING_INDEPENDENT_ROOT_REVIEW','EXACT_PENDING_FULL_NATIVE_DRAFT')
    rr=Q.pin(review_path);r=C.meta(rr);template=C.meta(d['review_template_reference'])
    Q.need(rr!=d['review_template_reference'] and r['status']=='APPROVED_FOR_EXACT_STAGE' and r['reviewer']=='root','INDEPENDENT_EXACT_ROOT_SCOPE_REVIEW')
    for k,v in template.items():
        if k not in ('status','reviewer'):Q.need(r[k]==v,'EXACT_SCOPE_REVIEW_FIELD:'+k)
    for ref in d['source_references']:Q.need(Q.pin(ref['path'])==ref,'ORIGINAL_AND_NEW_SOURCE_PINS_CHANGED')
    p=C.meta(d['plan_reference']);_,_,_,data,_=C.inputs(p);Q.need(data==p['data_references']==d['data_references'],'EXACT6_ACTUAL_DATA_DECLARATIONS')
    spec={'schema':'ROOT_REVIEWED_CPU_AUTO_MEMORY_STAGE_SPEC_V1',**d['stage_fields'],'cpus':16,'memory_policy':'SLURM_DEFAULT_UNSPECIFIED',
        'stage_output_cap_bytes':C.CAP,'source_references':d['source_references'],'data_references':data,
        'scope':{'mode':'FULL_SOURCE_AFTER_PROFILE','parent_profile':p['accepted_native_profile_receipt_reference'],'review':rr}}
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.contract import validate_scope_spec
    validate_scope_spec(spec,d['resource_authority_reference'],read_small=Q.read_small)
    return Q.write_new(Path(draft_path).parent/'stage_spec.json',spec)


def main():
    Q.on_login();p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='action',required=True)
    b=s.add_parser('budget-template');b.add_argument('--request',type=Path,required=True);b.add_argument('--output',type=Path,required=True)
    d=s.add_parser('draft');d.add_argument('--request',type=Path,required=True);d.add_argument('--output',type=Path,required=True)
    f=s.add_parser('finalize');f.add_argument('--draft',type=Path,required=True);f.add_argument('--root-review',type=Path,required=True)
    a=p.parse_args();print(finalize(a.draft,a.root_review) if a.action=='finalize' else draft(a.request,a.output) if a.action=='draft' else budget_template(a.request,a.output))
if __name__=='__main__':main()
