"""One exact generic16 draft/finalize; absent real parents -> NONEXECUTABLE."""
import argparse,copy,pathlib
from . import contract as C
def fresh(path,root):
    p=pathlib.Path(path);C.need(p.is_absolute() and root in p.parents and '..' not in p.parts and not p.exists()
      and not any(x.is_symlink() for x in (p,*p.parents)),'FRESH_LITERAL_METADATA_OR_PILOT_OUTPUT');return p
def proposal(output):
    out=fresh(output,C.ROOT/'control');out.mkdir(parents=True,mode=0o700)
    from . import configuration as G
    C.Q.write_new(out/'configuration_build_review.DRAFT.json',{
      'schema':G.SCHEMA,'status':'ROOT_REVIEW_REQUIRED','reviewer':None,'pilot_acceptance_reference':None,
      'D1_design_policy_reference':None,'D1_five_layer_reference':None,'base_registry_reference':None,
      'definition_authority_reference':None,'task_protocol_reference':None,
      'configuration_builder_source_references':[],'source_references':[],
      'no_future_output_hash':True,'scientific_grouping_and_original_masks_unchanged':True,'not_final_Common_or_Model_ACK':True})
    C.Q.write_new(out/'bounded_native_definitions.DRAFT.json',{
      'schema':'ROOT_BOUNDED_NATIVE_FIELD_DEFINITION_AUTHORITY_V1','status':'ROOT_REVIEW_REQUIRED','reviewer':None,
      'is_D1_design_only':False,'scientific_value_or_MID_arrays_present':False,'evidence_references':[],
      'fields':{},'source_rules':[],'size_rules_by_field':{},'condition_rule':'ORIGINAL_TASK_NAME',
      'charge_rule':'ACTUAL_ORIGINAL_PROTOCOL_EXPLICIT_CHARGE_NO_SMILES','condition_by_task':{},'actual_task_charge_by_task':{},
      'not_actual_approval_or_physics_or_joint_ACK':True})
    return C.Q.write_new(out/'request.NONEXECUTABLE.json',{'schema':'ROOT_REQUESTED_BOUNDED_PILOT_FAMILY_D3_DAY_V1','status':'NONEXECUTABLE_MISSING_ACTUAL55K_C0_AND_ROOT_INPUT_REVIEW',
      'requested_by':None,'node':None,'output_directory':None,'whole_output_cap_bytes':None,'order_capability':C.FULL_MODE,
      'native_fixed_random_early_delivery_mode':C.NATIVE_MODE,**{k:None for k in C.REQUIRED},'Source_or_fixture_is_actual_D3':False})
def draft(request_path,output):
    C.Q.on_login();r=C.Q.load(request_path);C.need(r['schema']=='ROOT_REQUESTED_BOUNDED_PILOT_FAMILY_D3_DAY_V1' and r['status']=='REQUESTED_FOR_REVIEW' and r['requested_by']=='root','ACTUAL_ROOT_REQUEST')
    out=fresh(output,C.ROOT/'control');out.mkdir(parents=True,mode=0o700);missing=[k for k in C.REQUIRED if not isinstance(r.get(k),dict)]
    if missing:return C.Q.write_new(out/'NONEXECUTABLE.json',{'status':'NONEXECUTABLE','missing':missing,'DATA_opened_or_hashed':False,'stage_created':False})
    p={k:copy.deepcopy(v) for k,v in r.items() if k not in ('schema','status','requested_by')}
    bounded=C.meta(p['bounded_export_review_reference'])
    if bounded.get('configuration_mode')=='CPU_MATERIALIZED_FROM_ACTUAL_D4_LIMITED_COMPONENTS':
        ref=bounded.get('configuration_build_review_reference')
        if not isinstance(ref,dict):missing.append('actual_configuration_build_review_reference')
        else:
            build=C.meta(ref)
            missing.extend('configuration_build.'+k for k in ('base_registry_reference','definition_authority_reference','task_protocol_reference') if not isinstance(build.get(k),dict))
            if build.get('status')!='APPROVED_EXACT_CPU_BOUNDED_CONFIGURATION_CONSTRUCTION' or build.get('reviewer')!='root':missing.append('actual_Root_configuration_build_review')
        if missing:return C.Q.write_new(out/'NONEXECUTABLE.json',{'status':'NONEXECUTABLE','missing':missing,'DATA_opened_or_hashed':False,'stage_created':False})
    C.need(p['node'] in C.ANALYSIS_NODES and type(p['whole_output_cap_bytes']) is int and 32<<30<=p['whole_output_cap_bytes']<=1<<40,'EXPLICIT_FINITE_CPU16_OUTPUT_CEILING_NOT_SIZE_FORECAST')
    fresh(p['output_directory'],C.OUTPUT);p.update(schema='BOUNDED_PILOT_FAMILY_D3_PLAN_V1',wall_seconds=86400)
    p['scope_parameters']=C.parameters(p);a,receipt,proof,old,review,data,parents=C.parents(p)
    if C.native_mode(p) and old.get('historical_D1_design_document_references'):
        historical=C.unique(old['historical_D1_design_document_references'])
        C.need(all(r['path']==str(C.REPO/'docs/interfaces/training_format_v3.md') for r in historical),
          'ONLY_EXACT_NONEXECUTED_D1_DESIGN_DOCUMENT_HISTORY_NOT_EXECUTABLE_OR_DATA_PIN_EXEMPTION')
        p['historical_D1_design_document_references']=historical
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.contract import validate_authority
    validate_authority(p['resource_authority_reference'],read_small=C.Q.read_small)
    cost=C.meta(p['cost_decision_reference']);C.need(cost['status']=='USER_AUTHORIZED' and cost['on_overrun']=='REPORT_AND_CONTINUE' and cost['scientific_quality_thresholds_unchanged'] is True,'COST_POLICY_NOT_QC_WAIVER')
    carve=C.meta(p['root_carveout_review_reference']);C.need(carve['parent_output_cap_bytes']==p['whole_output_cap_bytes'] and carve['parent_included_exactly_once'] is True,'CURRENT_QUOTA_ALL_FUTURE_PARENT_ONCE')
    refs=C.unique([*C.sources(),*parents,C.Q.pin(request_path)]);C.need(not {r['path'] for r in refs}&{r['path'] for r in data},'NO_SCIENTIFIC_BODY_IN_SMALL_SOURCE_LIST')
    p.update(source_references=refs,data_references=data,pilot_parent_manifest_reference=a['actual_parent']['manifest'],actual_geometry_manifest_reference=a['component_references']['geometry_reference'])
    export=C.REPO/'workflows/data_v1_final/export';p['codec_source_references']=[C.Q.pin(export/n) for n in ('wire_v1/codec.py','wire_v1/mapping.py','wire_v1/store.py','pipeline_v1/source.py','pipeline_v1/masks.py','pipeline_v1/granular_store.py')]
    pr=C.Q.write_new(out/'plan.json',p);refs=C.unique([*refs,pr]);fields={'kind':'analysis','scope_key':C.KEY,'scope_parameters':p['scope_parameters'],'pilot':False,
      'wall_seconds':86400,'estimated_peak_output_bytes':p['whole_output_cap_bytes'],'source_status_stage':'BOUNDED55K_FAMILY_D3_SOURCE_ROUNDTRIP',
      'execution_argv':[C.PY,'-B','-m',C.MODULE,'--plan',pr['path'],'--startup-proof','__ROOT_STARTUP_PROOF__']}
    template={'schema':'EXACT_CPU_AUTO_MEMORY_SCOPE_ROOT_REVIEW_V1','status':'PENDING_ROOT_REVIEW','reviewer':None,**fields,
      'scope_mode':'BOUNDED_PERFORMANCE_BATCH','resource_authority_reference':p['resource_authority_reference'],'stage_output_cap_bytes':p['whole_output_cap_bytes'],
      'parent_evidence_references':parents,'approved_source_references':refs,'data_references':data,'bounded_batch_limits_reviewed':True,
      'bounded_old_complete55k_only_not_Common':True,'source_methods_are_not_actual_D3_or_Model_ACK':True,'resource_current_context_reviewed':False}
    tr=C.Q.write_new(out/'root_review.template.json',template)
    return C.Q.write_new(out/'draft.json',{'schema':'BOUNDED_PILOT_FAMILY_D3_DRAFT_V1','plan_reference':pr,'template_reference':tr,'stage_fields':fields,
      'source_references':refs,'data_references':data,'resource_authority_reference':p['resource_authority_reference'],'DATA_opened_or_hashed':False})
def finalize(path,review_path):
    C.Q.on_login();d=C.Q.load(path);C.need(d['schema']=='BOUNDED_PILOT_FAMILY_D3_DRAFT_V1','EXACT_DRAFT');rr=C.Q.pin(review_path);review=C.meta(rr);template=C.meta(d['template_reference'])
    C.need(rr!=d['template_reference'] and review['status']=='APPROVED_FOR_EXACT_STAGE' and review['reviewer']=='root' and review['resource_current_context_reviewed'] is True,'SEPARATE_ACTUAL_ROOT_EXACT_STAGE_REVIEW')
    for k,v in template.items():
        if k not in ('status','reviewer','resource_current_context_reviewed'):C.need(review[k]==v,'EXACT_REVIEW_FIELD:'+k)
    p=C.meta(d['plan_reference']);C.need(C.parents(p)[5]==d['data_references']==p['data_references'],'UNCHANGED_DATA_DECLARATIONS')
    for ref in d['source_references']:C.need(C.Q.pin(ref['path'])==ref,'EXACT_INSTALLED_SOURCE_AND_SMALL_PARENT_BYTES')
    spec={'schema':'ROOT_REVIEWED_CPU_AUTO_MEMORY_STAGE_SPEC_V1',**d['stage_fields'],'cpus':16,'memory_policy':'SLURM_DEFAULT_UNSPECIFIED',
      'stage_output_cap_bytes':p['whole_output_cap_bytes'],'source_references':d['source_references'],'data_references':d['data_references'],
      'scope':{'mode':'BOUNDED_PERFORMANCE_BATCH','parent_profile':None,'review':rr}}
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.contract import validate_scope_spec
    validate_scope_spec(spec,d['resource_authority_reference'],read_small=C.Q.read_small)
    return C.Q.write_new(pathlib.Path(path).parent/'stage_spec.json',spec)
def main():
    p=argparse.ArgumentParser();s=p.add_subparsers(dest='action',required=True);x=s.add_parser('proposal');x.add_argument('--output',required=True)
    x=s.add_parser('draft');x.add_argument('--request',required=True);x.add_argument('--output',required=True)
    x=s.add_parser('finalize');x.add_argument('--draft',required=True);x.add_argument('--root-review',required=True);a=p.parse_args()
    print(proposal(a.output) if a.action=='proposal' else draft(a.request,a.output) if a.action=='draft' else finalize(a.draft,a.root_review))
if __name__=='__main__':main()
