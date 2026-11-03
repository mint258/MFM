"""Small operational parents only; every numeric/selector artifact stays DATA."""
import pathlib,sys
from workflows.data_v1_final.export.family_export_day_v1 import contract as F
from workflows.data_v1_final.labels.existing_sprime_pilot_day_v1 import contract as B
Q=F.Q;ROOT=F.ROOT;REPO=F.REPO;PY=F.PY;need=F.need;meta=F.meta;reference=F.reference;unique=F.unique
KEY='pilot_family_D3_fast55k_v1';MODULE='workflows.data_v1_final.export.'+KEY+'.run';HERE=REPO/'workflows/data_v1_final/export'/KEY
FILES=('__init__.py','contract.py','metadata.py','io.py','domain.py','wire.py','source.py','writer.py','verify.py','run.py','test_v1.py','configuration.py','projection.py','frame_mapping.py','source_revision2_origin.json','README.md')
OUTPUT=ROOT/'artifacts/labels/source_status_v1'/KEY
COUNTS={'TRAIN':50000,'VAL':5000}
ANALYSIS_NODES=('compute-0-2','compute-0-8','compute-0-9','compute-0-10','compute-0-11','compute-0-12','compute-0-13','compute-0-14','compute-0-15','compute-0-16','compute-0-17','compute-0-18','compute-0-19')
RESOURCE=('resource_authority_reference','cost_decision_reference','quota_provider_review_reference','quota_provider_identity_reference','root_carveout_review_reference')
REQUIRED=('pilot_acceptance_reference','bounded_export_review_reference','D1_design_policy_reference','D1_five_layer_reference',*RESOURCE)
COMPONENTS=('population_reference','geometry_reference','coverage_reference','eligibility_reference','typed_reader_config_reference','numeric_repetitions','r674_report_reference')
NATIVE_KEY='existing_sprime_fast55k_pilot_day_v1'
NATIVE_MODULE='workflows.data_v1_final.labels.'+NATIVE_KEY+'.run'
NATIVE_MODE='NATIVE55K_FIXED_RANDOM_ONLY'
FULL_MODE='FULL_THREE_ORDER'
def native_mode(p):
    mode=p.get('order_capability',FULL_MODE);need(mode in (FULL_MODE,NATIVE_MODE),'ONLY_EXACT_LEGACY_THREE_OR_NATIVE_FIXED_RANDOM_SCOPE')
    return mode==NATIVE_MODE
def order_domain(p,scope):
    native=native_mode(p)
    need(native and scope==NATIVE_KEY,'ONLY_EXACT_NATIVE_RESUME_V2_PRODUCER_AND_FIXED_RANDOM_SCOPE_NO_ALIAS')
    return native
def capabilities(p):
    return {'release_version':'v1-pilot-provisional','available_orders':['fixed_random'],'unavailable_orders':['energy','diversity'],
      'full_three_order':False,'D7':False,'lowest_energy_rank0_available':False,
      'consumer_requiring_three_orders_released':False} if native_mode(p) else {}
def parameters(p):
    value={'domain':'TEMPORARY_COMPLETE_OLD_SPRIME_PILOT_NOT_FINAL_COMMON','TRAIN_MIDs':50000,'ROUTINE_VAL_MIDs':5000,
      'seed':20261025,'orders':['fixed_random','energy','diversity'],'source_roundtrip_records':10000,'workers':16,'pending':32,
      'wall_seconds':86400,'whole_output_cap_bytes':p['whole_output_cap_bytes'],'source_methods':3,'new_QM_UFF_calls':0,
      'permanent_authority':'SOURCE_FLOAT64_AND_PERMANENT_F64_SIDECAR','training_cast':'ORIGINAL_CODEC_ONCE_FLOAT32',
      'r73':'SOURCE_ORDERED_RECORDS_V1_BOTH_ENDPOINT_CHANNELS_ONSITE_DIRECTION_DUPLICATES_ORDINAL',
      'r674':'FULL6_ORIGINAL_MASKS_COMPLETE6_SEPARATE_LOSS_ELIGIBILITY','missing_scale':'LOSS_DISABLED_SCALE_UNBOUND_OR_DEGENERATE',
      'actual_QM_charge_not_SMILES_formal_charge':True,'full_Common_D6_or_Model_ACK':False}
    if native_mode(p):value.update(orders=['fixed_random'],order_capability=NATIVE_MODE,**capabilities(p))
    return value
def walkrefs(value):
    if isinstance(value,dict):
        if set(('path','bytes','sha256'))<=set(value):yield reference(value)
        else:
            for v in value.values():yield from walkrefs(v)
    elif isinstance(value,list):
        for v in value:yield from walkrefs(v)
def parents(p):
    need(not (REPO/'configs/data_v1/v1-pilot-provisional/D3_export.json').exists(),'D3_ALREADY_FORMALLY_DELIVERED_DO_NOT_SUBMIT_SECOND_EXPORT')
    accepted=meta(p['pilot_acceptance_reference']);need(accepted['schema']=='ROOT_ACCEPTED_EXISTING_SPRIME_FAST55K_PILOT_COMPONENTS_V1'
      and accepted['status']=='ACTUAL_C0_BOUNDED_COMPONENTS_ACCEPTED_NOT_FINAL_COMMON' and accepted['reviewer']=='root'
      and accepted['complete_55k_components'] is True and accepted['pilot_counts']==COUNTS
      and accepted['full_Common_D2_D3_D4_D5_D6_release'] is False,'ACTUAL_BOUNDED55K_NOT_FINAL_COMMON')
    chain=accepted['actual_parent'];need(set(chain)=={'manifest','proof','accounting','raw'},'EXACT_TRUE_PILOT_PARENT_CHAIN')
    r=meta(chain['manifest']);proof=meta(chain['proof']);old=meta(r['plan_reference']);req=proof['request']
    native=order_domain(p,req['scope_key']);components=COMPONENTS+('schema_only_header_reference',) if native else COMPONENTS
    need(accepted['schema']=='ROOT_ACCEPTED_EXISTING_SPRIME_FAST55K_PILOT_COMPONENTS_V1'
      and r['schema']=='EXISTING_SPRIME_FAST55K_PILOT_DAY_RECEIPT_V1'
      and r['status']=='PROVISIONAL55K_FAST_TYPED_NATIVE_RANDOM_AND_TRAIN_D4_COMPLETE_PENDING_ACTUAL_C0_ROOT_SEAL'
      and not r['held'] and r['errors']==[] and r['independent_numeric_replay_equal'] is True and r['pilot_counts']==COUNTS
      and r['new_QM_UFF_calls']==0 and r['temporary_complete_old_Sprime_domain_only'] is True
      and r['startup_proof_reference']==chain['proof'] and str(r['job_id'])==str(proof['job_id'])
      and req['cpus']==16
      and accepted['component_references']=={k:r[k] for k in components},'ACTUAL_PILOT_RECEIPT_PROOF_COMPONENTS')
    producers={NATIVE_KEY:NATIVE_MODULE}
    need(req['scope_key'] in producers and req['execution_argv']==[PY,'-B','-m',producers[req['scope_key']],
      '--plan',r['plan_reference']['path'],'--startup-proof',chain['proof']['path']]
      and r['plan_reference'] in req['source_references'] and meta(proof['request_reference'])==req,
      'EXACT_ORIGINAL_OR_GENERAL_D4_MODULE_SCOPE_PLAN_PROOF_NOT_ALIAS')
    header_refs=[]
    if native:
        from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.contract import PROOF_SCHEMA
        need(proof['schema']==PROOF_SCHEMA and proof['uid']==1278 and proof['node']==req['node'] and req['node'] in ANALYSIS_NODES
          and req['kind']=='analysis' and req['pilot'] is False and req['cpus']==16 and req['wall_seconds']==86400
          and req['memory_policy']=='SLURM_DEFAULT_UNSPECIFIED' and old['schema']=='EXISTING_SPRIME_FAST55K_PILOT_DAY_PLAN_V1'
          and old['scope_parameters']==req['scope_parameters'] and r['available_orders']==['fixed_random']
          and r['full_three_order'] is False and r['D7'] is False,'TRUE_NATIVE_GENERIC16_NO_MEM_ACTUAL_NODE_UID_FIXED_RANDOM_ONLY')
        for name in ('__init__.py','contract.py','metadata.py','run.py','geometry.py','source_inverse.py','test_boundaries.py','README.md','fast_coverage.py','reader_memo.py'):
            need(Q.pin(REPO/'workflows/data_v1_final/labels'/NATIVE_KEY/name) in req['source_references'],'ALL_EXACT_NATIVE8_PARENT_SOURCE_PINS')
        href=r['schema_only_header_reference'];header=meta(href)
        need(header['schema']=='ACTUAL_CPU146_FIELD_SCHEMA_ONLY_QA_V1'
          and header['status']=='ACTUAL_CPU_FIELD_SCHEMA_EXTRACTED_NOT_NATIVE_PRINTED_UNIT_VALIDATION'
          and header['uid']==1278 and header['actual_node']==req['node'] and str(header['actual_parent_job_id'])==str(proof['job_id'])
          and header['numerical_statistics_or_MID_or_coordinates_included'] is False and header['native_printed_units_verified'] is False
          and len(header['fields'])==146 and {f['field_id'] for f in header['fields']}==set(range(146))
          and header['actual_input_references']['field_map']==old['field_map_reference']
          and header['actual_input_references']['registry']==old['base_registry_reference'],
          'ACTUAL_PURE_SCHEMA_HEADER_SAME_PARENT_NOT_NUMERIC_OR_NATIVE_UNIT_ACCEPTANCE')
        header_refs=[href]
    from workflows.data_v1_final.export.common_day_parent_v1 import parent as A
    A.account(chain['accounting'],str(proof['job_id']),req['node'],16)
    need(meta(chain['accounting'])['raw_sacct_reference']==chain['raw'],'ACTUAL_RAW_ACCOUNTING_NOT_FAKE_CHILD_C0')
    review=meta(p['bounded_export_review_reference']);need(review['schema']=='ROOT_BOUNDED_PILOT_FAMILY_D3_INPUT_REVIEW_V1'
      and review['status']=='APPROVED_EXACT_OLD_COMPLETE55K_EXPORT_NOT_FULL_COMMON' and review['reviewer']=='root'
      and review['pilot_acceptance_reference']==p['pilot_acceptance_reference'] and review['pilot_counts']==COUNTS
      and review['all_original_masks_reasons_and_physical_identity_preserved'] is True
      and review['source_frame_policy']=='PRODUCER_SHA_PLUS_CURRENT_STABLE_FD_FOOTER_NOT_CLAIM_CURRENT_FULL_RAW_SHA'
      and review['Model_ACK_or_full_release_claimed'] is False,'ROOT_EXACT_PILOT_SOURCE_PROJECTION_NOT_FINAL_JOINT_POLICY')
    if native:
        need(review['order_capability']==NATIVE_MODE and review['available_orders']==['fixed_random']
          and review['full_three_order'] is False and review['D7'] is False
          and review['original_roles_and_actual_D5_anti_join_required'] is True
          and review['unavailable_energy_diversity_not_filled'] is True,'ROOT_EXPLICIT_PROVISIONAL_FIXED_RANDOM_SCOPE_NOT_GENERIC_DOWNGRADE')
    else:need(review['original_roles_three_orders_and_actual_D5_anti_join_required'] is True,'ORIGINAL_FULL_THREE_ORDER_REVIEW_UNCHANGED')
    design=meta(p['D1_design_policy_reference']);five=meta(p['D1_five_layer_reference'])
    need(design['schema']=='USER_FROZEN_D1_V3_DESIGN_POLICY_V1' and design['contract_version']=='v3.0'
      and five['schema']=='USER_FROZEN_D1_V3_FIVE_LAYER_MAPPING_SELECTIONS_V1' and five['contract_version']=='v3.0'
      and design['is_joint_release_authority'] is False,'ACTUAL_USER_DESIGN_NOT_INVENTED_MODEL_ACK')
    mode=review.get('configuration_mode','PREEXISTING_EXACT_CONFIGURATIONS')
    if mode=='CPU_MATERIALIZED_FROM_ACTUAL_D4_LIMITED_COMPONENTS':
        from . import configuration
        _,_,configuration_sources,configuration_data=configuration.review(p,review)
    else:
        need(mode=='PREEXISTING_EXACT_CONFIGURATIONS','EXPLICIT_EXISTING_OR_CPU_DERIVED_CONFIGURATION_AUTHORITY')
        configuration_sources=[];configuration_data=[review[k] for k in ('registry_reference','mapping_reference','projection_recipe_reference','target_policy_reference')]
    data=unique([*walkrefs({k:accepted['component_references'][k] for k in COMPONENTS}),*review['data_references'],*configuration_data])
    refs=unique([*(p[k] for k in REQUIRED),*chain.values(),r['plan_reference'],accepted['request_reference'],accepted['submission_reference'],accepted['registration_reference'],*old['source_references'],*review['source_references'],*configuration_sources,*header_refs])
    data=unique([*data,*old['data_references']])
    need(not {x['path'] for x in refs}&{x['path'] for x in data},'SMALL_NUMERIC_OR_SELECTOR_FILES_REMAIN_DATA')
    return accepted,r,proof,old,review,data,refs
def sources():
    from . import domain,wire,source,writer,verify,test_v1,configuration,projection,frame_mapping
    refs=[Q.pin(HERE/n) for n in FILES]+F.sources()
    refs.extend(configuration.ORIGINALS.proof()['source_references'])
    refs.extend(Q.pin(B.HERE/n) for n in B.FILES)
    from workflows.data_v1_final.labels.existing_sprime_pilot_general_cpu_day_v1 import contract as General
    refs.extend(Q.pin(General.HERE/n) for n in General.FILES)
    refs.extend(Q.pin(REPO/'workflows/data_v1_final/execution/cpu_analysis_general_nodes_v1'/n)
      for n in ('__init__.py','contract.py','quota_provider.py'))
    for name,m in list(sys.modules.items()):
        path=getattr(m,'__file__',None)
        if name.startswith('workflows.') and path and pathlib.Path(path).suffix=='.py':
            path=pathlib.Path(path).absolute();need(REPO in path.parents,'SOURCE_DEPENDENCIES_FROM_ACTUAL_REPOSITORY');refs.append(Q.pin(path))
    return unique(refs)
