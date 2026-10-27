"""Source-only catalogue or real-parent Root draft/finalize;never invent R/N."""
import argparse,copy,pathlib
from . import contract as C
Q=C.Q
COMMON=('ranking_receipt_reference','graph_source_review_reference','kernel_catalog_reference','quota_reuse_reference','resource_authority_reference','cost_decision_reference','output_directory')
OPTIONAL=('source_preparation_receipt_reference','source_preparation_accounting_reference','accepted_previous_receipt_reference','accepted_previous_accounting_reference',
    'previous_stage_root_review_reference','reuse_snapshot_reference','reuse_accounting_reference','prior_runs_reference','resume_selection_mode','quality_reference_review_reference')
def catalog(out):
    out=pathlib.Path(out);Q.need(out.is_absolute() and Q.ROOT/'control' in out.parents and not out.exists() and '..' not in out.parts,'FRESH_SMALL_CONTROL_CATALOGUE')
    recipe=C.meta(Q.pin(C.RECIPE));value={'schema':'NO_PM7_UFF_D_ORIGINAL_KERNEL_CATALOG_V1','references':{k:Q.pin(p) for k,p in C.catalog_paths().items()},
        'recipe_reference':Q.pin(C.RECIPE),'science_source_pins':recipe['science_source_pins'],'source_only':True,'new_UFF_QM_calls':0}
    Q.need(value['references']['wire']['sha256']=='ce9bbdf15459e647fc21592941c99664141b7d7a4442619f433c88a3536d99a1'
        and value['recipe_reference']['sha256']==C.RECIPE_SHA256,'EXACT_ORIGINAL_CORRECTED_BASE_AND_RECIPE_SOURCE')
    for r in value['science_source_pins']:Q.need(Q.pin(r['path'])==r,'ACTUAL_ORIGINAL_SPRIME_SOURCES')
    out.mkdir(parents=True,exist_ok=False);return Q.write_new(out/'kernel_catalog.json',value)
def missing_fields(request):
    need=list(COMMON);mode=request['mode']
    if mode!='source':need+=['source_preparation_receipt_reference','source_preparation_accounting_reference']
    if mode in ('profile','full'):need+=['accepted_previous_receipt_reference','accepted_previous_accounting_reference','previous_stage_root_review_reference','reuse_snapshot_reference','reuse_accounting_reference']
    if mode=='resume':need+=['prior_runs_reference','resume_selection_mode']
    if mode=='coverage':need+=['reuse_snapshot_reference','reuse_accounting_reference']
    return [k for k in need if request.get(k) is None]
def draft(request_path,out):
    request=Q.load(request_path);Q.need(request['schema']=='ROOT_REQUESTED_NO_PM7_UFF_D_STAGE_V1' and request['status']=='REQUESTED_FOR_REVIEW'
        and request['requested_by']=='root','ROOT_REQUEST_NOT_CHILD_APPROVAL')
    mode=request['mode'];cap=request['output_cap_bytes'];lower=request.get('lower_inclusive',0);upper=request.get('upper_exclusive',0)
    params=C.parameters(mode,lower,upper,cap);wall=request['wall_seconds'];Q.need(type(wall)is int and 600<=wall<=86400 and wall%60==0,'FINITE_WALL_WITHOUT_AUTORENEW')
    out=pathlib.Path(out);Q.need(out.is_absolute() and Q.ROOT/'control' in out.parents and not out.exists() and '..' not in out.parts,'FRESH_REQUEST_DRAFT_DIRECTORY')
    absent=missing_fields(request)
    if absent:
        out.mkdir(parents=True);return Q.write_new(out/'NONEXECUTABLE.json',{'schema':'NO_PM7_UFF_D_NONEXECUTABLE_CANDIDATE_V1','status':'NONEXECUTABLE_MISSING_ACTUAL_FROZEN_RN_OR_PARENT_EVIDENCE',
            'mode':mode,'missing_actual_references':absent,'future_hashes_jobs_or_approval_created':False,'stage_spec_created':False,'new_UFF_QM_calls':0})
    plan={'schema':'NO_PM7_UFF_D_STAGE_PLAN_V1','mode':mode,'scope_parameters':params,'lower_inclusive':lower,'upper_exclusive':upper,'output_cap_bytes':cap,
        'wall_seconds':wall,**{k:request[k] for k in COMMON},**{k:request[k] for k in OPTIONAL if k in request}}
    manifest,kernel,graph,data,parents=C.input_parents(plan);plan['data_references']=data
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.contract import validate_authority
    validate_authority(plan['resource_authority_reference'],read_small=Q.read_small)
    cost=C.meta(plan['cost_decision_reference']);Q.need(cost['status']=='USER_AUTHORIZED' and cost['on_overrun']=='REPORT_AND_CONTINUE' and cost['scientific_quality_thresholds_unchanged'] is True,'COST_AUTHORITY_ONLY_STOP_RULE_CHANGED')
    output=pathlib.Path(plan['output_directory']);Q.need(C.BASE in output.parents and C.CACHE not in output.parents and output!=C.CACHE and not output.exists()
        and not any(p.is_symlink() for p in (output,*output.parents,out,*out.parents)),'FRESH_OUTPUT_NOT_OLD_CACHE_SOURCE_OR_LEDGER')
    recipe=C.meta(kernel['recipe_reference']);sources=C.unique([*(Q.pin(p) for p in C.sources()),*parents,*recipe['science_source_pins'],Q.pin(request_path),
        plan['resource_authority_reference'],plan['cost_decision_reference']])
    for r in sources:Q.need(r['path'] not in {p['path'] for p in data} and Q.pin(r['path'])==r,'ONLY_SMALL_SOURCE_METADATA_OPENED_OR_HASHED_ON_LOGIN')
    out.mkdir(parents=True,exist_ok=False);pr=Q.write_new(out/'plan.json',plan);sources=C.unique([*sources,pr])
    kind='conformer' if mode in ('compat','profile','full') else 'analysis';pilot=mode in ('compat','profile')
    fields={'kind':kind,'scope_key':C.key(mode),'scope_parameters':params,'pilot':pilot,'wall_seconds':wall,'estimated_peak_output_bytes':cap,
        'source_status_stage':'NEW_PUBCHEM_NO_PM7_UFF_D_'+mode.upper(),'execution_argv':[Q.PY,'-B','-m',C.MODULE,'--plan',str(out/'plan.json'),'--startup-proof','__ROOT_STARTUP_PROOF__']}
    scope_mode='BOUNDED_PERFORMANCE_BATCH' if pilot else 'FULL_SOURCE_AFTER_PROFILE' if mode=='full' else 'BOUNDED_METADATA_PREPARATION'
    review={**copy.deepcopy(fields),'schema':'EXACT_CPU_AUTO_MEMORY_SCOPE_ROOT_REVIEW_V1','status':'PENDING_ROOT_REVIEW','reviewer':None,
        'resource_authority_reference':plan['resource_authority_reference'],'scope_mode':scope_mode,'stage_output_cap_bytes':cap,
        'parent_evidence_references':parents,'approved_source_references':sources,'data_references':data,'bounded_batch_limits_reviewed':pilot,
        'new_graph_seam_no_PM7_fix_stereo_or_HOF':True,'technical_UNKNOWN_not_chemical_exclusion':True,'pool_or_training_release':False}
    if mode=='full':review.update(profile_reviewed=True,approved_profile_reference=plan['accepted_previous_receipt_reference'])
    rr=Q.write_new(out/'root_review.template.json',review)
    return Q.write_new(out/'draft_receipt.json',{'schema':'NO_PM7_UFF_D_EXACT_DRAFT_V1','status':'PENDING_INDEPENDENT_ROOT_SCOPE_REVIEW','mode':mode,'plan_reference':pr,
        'root_review_template_reference':rr,'stage_fields':fields,'scope_mode':scope_mode,'source_references':sources,'data_references':data,
        'resource_authority_reference':plan['resource_authority_reference'],'parent_profile':plan.get('accepted_previous_receipt_reference') if mode=='full' else None,
        'scientific_DATA_opened_or_hashed':False,'Root_approval_or_submission_created':False})
def finalize(draft_path,review_path):
    d=Q.load(draft_path);Q.need(d['schema']=='NO_PM7_UFF_D_EXACT_DRAFT_V1' and d['status']=='PENDING_INDEPENDENT_ROOT_SCOPE_REVIEW','REAL_PARENT_COMPLETE_DRAFT')
    template=C.meta(d['root_review_template_reference']);rr=Q.pin(review_path);review=C.meta(rr)
    Q.need(rr!=d['root_review_template_reference'] and review['status']=='APPROVED_FOR_EXACT_STAGE' and review['reviewer']=='root','INDEPENDENT_ROOT_SIGNATURE_NOT_CHILD')
    for k,v in template.items():
        if k not in ('status','reviewer'):Q.need(review[k]==v,'EXACT_SCOPE_FIELD:'+k)
    for r in d['source_references']:Q.need(Q.pin(r['path'])==r,'ALL_FROZEN_SOURCE_AND_SMALL_PARENT_PINS')
    plan=C.meta(d['plan_reference']);*_,data,parents=C.input_parents(plan);Q.need(data==d['data_references'],'UNCHANGED_REAL_DATA_LOCATORS')
    spec={'schema':'ROOT_REVIEWED_CPU_AUTO_MEMORY_STAGE_SPEC_V1',**d['stage_fields'],'cpus':16,'memory_policy':'SLURM_DEFAULT_UNSPECIFIED',
        'stage_output_cap_bytes':plan['output_cap_bytes'],'source_references':d['source_references'],'data_references':data,
        'scope':{'mode':d['scope_mode'],'parent_profile':d['parent_profile'],'review':rr}}
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.contract import validate_scope_spec
    validate_scope_spec(spec,d['resource_authority_reference'],read_small=Q.read_small);return Q.write_new(pathlib.Path(draft_path).parent/'stage_spec.json',spec)
def main():
    Q.on_login();p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='action',required=True)
    a=s.add_parser('catalog');a.add_argument('--output',type=pathlib.Path,required=True)
    a=s.add_parser('draft');a.add_argument('--request',type=pathlib.Path,required=True);a.add_argument('--output',type=pathlib.Path,required=True)
    a=s.add_parser('finalize');a.add_argument('--draft',type=pathlib.Path,required=True);a.add_argument('--root-review',type=pathlib.Path,required=True)
    a=p.parse_args();print(catalog(a.output) if a.action=='catalog' else draft(a.request,a.output) if a.action=='draft' else finalize(a.draft,a.root_review))
if __name__=='__main__':main()
