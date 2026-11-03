"""Small operational parents only; every numeric/selector artifact stays DATA."""
import pathlib,sys
from workflows.data_v1_final.export.family_export_day_v1 import contract as F
from workflows.data_v1_final.labels.existing_sprime_pilot_day_v1 import contract as B
Q=F.Q;ROOT=F.ROOT;REPO=F.REPO;PY=F.PY;need=F.need;meta=F.meta;reference=F.reference;unique=F.unique
PRODUCER_NAMESPACE='pilot_family_D3_lustre_store_v1'
KEY=PRODUCER_NAMESPACE.lower();MODULE='workflows.data_v1_final.export.'+PRODUCER_NAMESPACE+'.run';HERE=REPO/'workflows/data_v1_final/export'/PRODUCER_NAMESPACE
FILES=('__init__.py','contract.py','metadata.py','io.py','domain.py','wire.py','source.py','writer.py','verify.py','run.py','test_v1.py','configuration.py','projection.py','frame_mapping.py','source_revision2_origin.json','lossless_io.py','local_parent.py','closed_domain_resume.py','pilot_finish.py','payload_io.py','runtime_budget.py','parallel_writer.py','delivery.py','queued_bootstrap.py','queued_runtime.py','queued_quota.py','unlimited_budget.py','README.md')
OUTPUT=pathlib.Path('/lfshome/zixiao/data_v1_20261025/D3_pilot_provisional_lustre_v1')
COUNTS={'TRAIN':50000,'VAL':5000}
ANALYSIS_NODES=('compute-0-2','compute-0-8','compute-0-9','compute-0-10','compute-0-11','compute-0-12','compute-0-13','compute-0-14','compute-0-15','compute-0-16','compute-0-17','compute-0-18','compute-0-19')
RESOURCE=('resource_authority_reference','cost_decision_reference','quota_provider_review_reference','quota_provider_identity_reference','root_carveout_review_reference')
REQUIRED=('pilot_acceptance_reference','bounded_export_review_reference','D1_design_policy_reference','D1_five_layer_reference',*RESOURCE)
COMPONENTS=('prefix_reference','population_reference','geometry_reference','coverage_reference','eligibility_reference','typed_reader_config_reference','numeric_repetitions','r674_report_reference')
NATIVE_KEY='existing_sprime_fast55k_resume_v4'
NATIVE_V5_KEY='existing_sprime_fast55k_resume_v5'
NATIVE_V6_KEY='existing_sprime_fast55k_resume_v6'
NATIVE_V7_KEY='existing_sprime_fast55k_resume_v7'
NATIVE_V8_KEY='existing_sprime_fast55k_resume_v8'
NATIVE_V9_KEY='existing_sprime_fast55k_resume_v9'
NATIVE_V10_KEY='existing_sprime_fast55k_resume_v10'
NATIVE_V11_KEY='existing_sprime_fast55k_resume_v11'
NATIVE_V12_KEY='existing_sprime_fast55k_resume_v12'
NATIVE_V13_KEY='existing_sprime_fast55k_resume_v13'
NATIVE_V2_KEY='existing_sprime_fast55k_resume_v2'
NATIVE_V1_KEY='existing_sprime_fast55k_resume_v1'
NATIVE_MODULE='workflows.data_v1_final.labels.'+NATIVE_KEY+'.run'
NATIVE_MODE='NATIVE55K_FIXED_RANDOM_ONLY'
FULL_MODE='FULL_THREE_ORDER'
def native_mode(p):
    mode=p.get('order_capability',FULL_MODE);need(mode in (FULL_MODE,NATIVE_MODE),'ONLY_EXACT_LEGACY_THREE_OR_NATIVE_FIXED_RANDOM_SCOPE')
    return mode==NATIVE_MODE
def order_domain(p,scope):
    native=native_mode(p)
    need(native and scope in (NATIVE_KEY,NATIVE_V5_KEY,NATIVE_V6_KEY,NATIVE_V7_KEY,NATIVE_V8_KEY,NATIVE_V9_KEY,NATIVE_V10_KEY,NATIVE_V11_KEY,NATIVE_V12_KEY,NATIVE_V13_KEY,NATIVE_V2_KEY,NATIVE_V1_KEY),'ONLY_EXACT_NATIVE_RESUME_V2_PRODUCER_AND_FIXED_RANDOM_SCOPE_NO_ALIAS')
    return native
def capabilities(p):
    return {'release_version':'v1-pilot-provisional','available_orders':['fixed_random'],'unavailable_orders':['energy','diversity'],
      'full_three_order':False,'D7':False,'lowest_energy_rank0_available':False,
      'consumer_requiring_three_orders_released':False} if native_mode(p) else {}
def parameters(p):
    value={'domain':'TEMPORARY_COMPLETE_OLD_SPRIME_PILOT_NOT_FINAL_COMMON','TRAIN_MIDs':50000,'ROUTINE_VAL_MIDs':5000,
      'seed':20261025,'orders':['fixed_random','energy','diversity'],'source_roundtrip_records':1000,'workers':16,'pending':32,
      'wall_seconds':86400,'worker_software_rss_cap_bytes':3<<30,'whole_output_cap_bytes':p['whole_output_cap_bytes'],'source_methods':0,'parallel_store_workers':8,'new_QM_UFF_calls':0,
      'permanent_authority':'SOURCE_FLOAT64_AND_PERMANENT_F64_SIDECAR','training_cast':'ORIGINAL_CODEC_ONCE_FLOAT32',
      'internal_domain_blob_codec':'CLOSED_D4_ROWS_AND_LOSSLESS_COMPRESSED_LABELS',
      'active_output_resource_credit':'EARLIER_QUOTA_COVERED_WHOLE_OWN_BLOCKS_ONCE_NO_MONOTONICITY',
      'r73':'SOURCE_ORDERED_RECORDS_V1_BOTH_ENDPOINT_CHANNELS_ONSITE_DIRECTION_DUPLICATES_ORDINAL',
      'r674':'FULL6_ORIGINAL_MASKS_COMPLETE6_SEPARATE_LOSS_ELIGIBILITY','missing_scale':'LOSS_DISABLED_SCALE_UNBOUND_OR_DEGENERATE',
      'actual_QM_charge_not_SMILES_formal_charge':True,'full_Common_D6_or_Model_ACK':False}
    if p.get('queue_startup_mode'):value['queue_startup_mode']=p['queue_startup_mode']
    if p.get('queue_startup_mode')=='USER_UNLIMITED_CPU21_D3_20261103':
        value.update(wall_seconds=None,worker_software_rss_cap_bytes=None,software_time_or_memory_stops=False,estimated_future_output_bytes=p['estimated_future_output_bytes'],whole_output_ceiling_is_physical_account_quota=True)
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
    accepted=meta(p['pilot_acceptance_reference'])
    if accepted['schema']=='ROOT_LOCAL_HEAD_D4_BOUNDED_COMPONENT_ACCEPTANCE_V1':
        from . import local_parent
        return local_parent.parents(p,accepted)
    need(accepted['schema']=='ROOT_FAST55K_RESUME_LIMITED_COMPONENT_ACCEPTANCE_V1'
      and accepted['status']=='ACTUAL_C0_BOUNDED_COMPONENTS_ACCEPTED_NOT_FINAL_COMMON' and accepted['reviewer']=='root'
      and accepted['complete_55k_components'] is True and accepted['pilot_counts']==COUNTS
      and accepted['full_Common_D2_D3_D4_D5_D6_release'] is False,'ACTUAL_BOUNDED55K_NOT_FINAL_COMMON')
    chain=accepted['actual_parent'];need(set(chain)=={'manifest','proof','accounting','raw'},'EXACT_TRUE_PILOT_PARENT_CHAIN')
    registration=meta(accepted['registration_reference']);need(all(registration[k]==chain[v]for k,v in (('receipt_reference','manifest'),('proof_reference','proof'),('accounting_reference','accounting'),('raw_reference','raw'))),'ROOT_ACCEPTED_COMPONENTS_MATCH_EXACT_ACTUAL_REGISTRATION')
    r=meta(chain['manifest']);proof=meta(chain['proof']);old=meta(r['plan_reference']);req=proof['request']
    submitted=meta(registration['submission_reference']);need(meta(registration['request_reference'])==req==submitted['request']
      and submitted['request_reference']==proof['request_reference']==registration['request_reference']
      and str(submitted['job_id'])==str(proof['job_id'])and submitted['uid']==1278 and submitted['sbatch_returncode']==0,'REAL_REGISTERED_NEW_RESUME_PARENT_NO_PARTIAL_C0_ALIAS')
    native=order_domain(p,req['scope_key']);components=COMPONENTS+('schema_only_header_reference',) if native else COMPONENTS
    need(accepted['schema']=='ROOT_FAST55K_RESUME_LIMITED_COMPONENT_ACCEPTANCE_V1'
      and r['schema']=='EXISTING_SPRIME_FAST55K_PILOT_DAY_RECEIPT_V1'
      and r['status']=='PROVISIONAL55K_FAST_TYPED_NATIVE_RANDOM_AND_TRAIN_D4_COMPLETE_PENDING_ACTUAL_C0_ROOT_SEAL'
      and not r['held'] and r['errors']==[] and r['independent_numeric_replay_equal'] is True and r['pilot_counts']==COUNTS
      and r['new_QM_UFF_calls']==0 and r['temporary_complete_old_Sprime_domain_only'] is True
      and r['startup_proof_reference']==chain['proof'] and str(r['job_id'])==str(proof['job_id'])
      and req['cpus']==16
      and accepted['component_references']=={k:r[k] for k in components},'ACTUAL_PILOT_RECEIPT_PROOF_COMPONENTS')
    producers={NATIVE_V13_KEY:'workflows.data_v1_final.labels.'+NATIVE_V13_KEY+'.run',NATIVE_V12_KEY:'workflows.data_v1_final.labels.'+NATIVE_V12_KEY+'.run',NATIVE_V11_KEY:'workflows.data_v1_final.labels.'+NATIVE_V11_KEY+'.run',NATIVE_V10_KEY:'workflows.data_v1_final.labels.'+NATIVE_V10_KEY+'.run',NATIVE_V9_KEY:'workflows.data_v1_final.labels.'+NATIVE_V9_KEY+'.run',NATIVE_V8_KEY:'workflows.data_v1_final.labels.'+NATIVE_V8_KEY+'.run',NATIVE_V7_KEY:'workflows.data_v1_final.labels.'+NATIVE_V7_KEY+'.run',NATIVE_V6_KEY:'workflows.data_v1_final.labels.'+NATIVE_V6_KEY+'.run',NATIVE_V5_KEY:'workflows.data_v1_final.labels.'+NATIVE_V5_KEY+'.run',NATIVE_KEY:NATIVE_MODULE,NATIVE_V2_KEY:'workflows.data_v1_final.labels.'+NATIVE_V2_KEY+'.run',NATIVE_V1_KEY:'workflows.data_v1_final.labels.'+NATIVE_V1_KEY+'.run'}
    need(req['scope_key'] in producers and req['execution_argv']==[PY,'-B','-m',producers[req['scope_key']],
      '--plan',r['plan_reference']['path'],'--startup-proof',chain['proof']['path']]
      and r['plan_reference'] in req['source_references'] and meta(proof['request_reference'])==req,
      'EXACT_ORIGINAL_OR_GENERAL_D4_MODULE_SCOPE_PLAN_PROOF_NOT_ALIAS')
    header_refs=[]
    if native:
        from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.contract import PROOF_SCHEMA
        need(proof['schema']==PROOF_SCHEMA and proof['uid']==1278 and proof['node']==req['node'] and req['node'] in ANALYSIS_NODES
          and req['kind']=='analysis' and req['pilot'] is False and req['cpus']==16 and req['wall_seconds']==86400
          and req['memory_policy']=='SLURM_DEFAULT_UNSPECIFIED' and old['schema']=='EXISTING_SPRIME_FAST55K_RESUME_PLAN_V1'
          and old['scope_parameters']==req['scope_parameters'] and r['available_orders']==['fixed_random']
          and r['full_three_order'] is False and r['D7'] is False,'TRUE_NATIVE_GENERIC16_NO_MEM_ACTUAL_NODE_UID_FIXED_RANDOM_ONLY')
        if req['scope_key']==NATIVE_V13_KEY:
            from workflows.data_v1_final.labels.existing_sprime_fast55k_resume_v13 import contract as Producer
        elif req['scope_key']==NATIVE_V12_KEY:
            from workflows.data_v1_final.labels.existing_sprime_fast55k_resume_v12 import contract as Producer
        elif req['scope_key']==NATIVE_V11_KEY:
            from workflows.data_v1_final.labels.existing_sprime_fast55k_resume_v11 import contract as Producer
        elif req['scope_key']==NATIVE_V10_KEY:
            from workflows.data_v1_final.labels.existing_sprime_fast55k_resume_v10 import contract as Producer
        elif req['scope_key']==NATIVE_V9_KEY:
            from workflows.data_v1_final.labels.existing_sprime_fast55k_resume_v9 import contract as Producer
        elif req['scope_key']==NATIVE_V8_KEY:
            from workflows.data_v1_final.labels.existing_sprime_fast55k_resume_v8 import contract as Producer
        elif req['scope_key']==NATIVE_V7_KEY:
            from workflows.data_v1_final.labels.existing_sprime_fast55k_resume_v7 import contract as Producer
        elif req['scope_key']==NATIVE_V6_KEY:
            from workflows.data_v1_final.labels.existing_sprime_fast55k_resume_v6 import contract as Producer
        elif req['scope_key']==NATIVE_V5_KEY:
            from workflows.data_v1_final.labels.existing_sprime_fast55k_resume_v5 import contract as Producer
        elif req['scope_key']==NATIVE_KEY:
            from workflows.data_v1_final.labels.existing_sprime_fast55k_resume_v4 import contract as Producer
        elif req['scope_key']==NATIVE_V2_KEY:
            from workflows.data_v1_final.labels.existing_sprime_fast55k_resume_v2 import contract as Producer
        else:
            from workflows.data_v1_final.labels.existing_sprime_fast55k_resume_v1 import contract as Producer
        need(Producer.KEY==req['scope_key'] and Producer.MODULE==producers[req['scope_key']],'EXACT_KNOWN_RESUME_PRODUCER_NOT_OLD_PARTIAL_ALIAS')
        Producer.plan(old);resume_review,old_partial,old_partial_proof=Producer.resume_authority(old)
        if req['scope_key']in (NATIVE_V8_KEY,NATIVE_V9_KEY,NATIVE_V10_KEY,NATIVE_V11_KEY,NATIVE_V12_KEY,NATIVE_V13_KEY):
            geometry=meta(r['geometry_reference']);recovery=meta(geometry['metadata_checkpoint_recovery_reference'])
            expected_schema,expected_old={NATIVE_V13_KEY:('ACTUAL5494_APPEND_ONLY_METADATA_RECOVERY_INTEGRITY_V1','4525494'),NATIVE_V12_KEY:('ACTUAL5482_APPEND_ONLY_METADATA_RECOVERY_INTEGRITY_V1','4525482'),NATIVE_V11_KEY:('ACTUAL5481_APPEND_ONLY_METADATA_RECOVERY_INTEGRITY_V1','4525481'),NATIVE_V8_KEY:('ACTUAL5455_APPEND_ONLY_METADATA_RECOVERY_INTEGRITY_V1','4525455'),NATIVE_V9_KEY:('ACTUAL5478_APPEND_ONLY_METADATA_RECOVERY_INTEGRITY_V1','4525478'),NATIVE_V10_KEY:('ACTUAL5480_APPEND_ONLY_METADATA_RECOVERY_INTEGRITY_V1','4525480')}[req['scope_key']]
            need(recovery['schema']==expected_schema
              and recovery['old_job_id']==expected_old and recovery['actual_new_job_id']==str(proof['job_id'])
              and recovery['all_old_logical_rows_equal_before_after'] is True
              and recovery['prefix_and_suffix_all_sources_covered'] is True,'ACTUAL_APPEND_ONLY_METADATA_PREFIX_INTEGRITY')
        need(accepted['old4525232_C0_partial_history_unchanged']is True,'ORIGINAL_C0_PREFIX_PARTIAL_NOT_PROMOTED')
        expected_files=('__init__.py','contract.py','metadata.py','run.py','geometry.py','cache.py','README.md')
        if req['scope_key']in (NATIVE_V10_KEY,NATIVE_V11_KEY,NATIVE_V12_KEY,NATIVE_V13_KEY):expected_files=('__init__.py','contract.py','metadata.py','run.py','geometry.py','recovery.py','resource.py','io.py','README.md')
        elif req['scope_key']in (NATIVE_V8_KEY,NATIVE_V9_KEY):expected_files=('__init__.py','contract.py','metadata.py','run.py','geometry.py','recovery.py','resource.py','README.md')
        elif req['scope_key']==NATIVE_V7_KEY:expected_files=('__init__.py','contract.py','metadata.py','run.py','geometry.py','lookup_cache.py','README.md')
        elif req['scope_key']==NATIVE_V6_KEY:expected_files=('__init__.py','contract.py','metadata.py','run.py','geometry.py','geometry_tables.py','io.py','README.md')
        elif req['scope_key']==NATIVE_V5_KEY:expected_files=('__init__.py','contract.py','metadata.py','run.py','geometry.py','packet_io.py','resource_census.py','README.md')
        elif req['scope_key']==NATIVE_KEY:expected_files=('__init__.py','contract.py','metadata.py','run.py','geometry.py','resource_census.py','README.md')
        elif req['scope_key']==NATIVE_V2_KEY:expected_files=expected_files[:-1]+('test_boundaries.py','README.md')
        need(Producer.FILES==expected_files,'EXACT_REGISTERED_RESUME_V1_SEVEN_OR_V2_EIGHT_SOURCE_SET')
        for name in Producer.FILES:
            need(Q.pin(Producer.HERE/name)in req['source_references'],'ALL_EXACT_REGISTERED_RESUME_PARENT_SOURCE_PINS')
        for root in (old['output_directory'],str(Producer.OLDROOT)):
            need(root in meta(p['bounded_export_review_reference'])['transitive_closed_output_roots'],'BOTH_NEW_AND_ORIGINAL_C0_PARTIAL_ROOTS_EXPLICITLY_REVIEWED')
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
    return parent_review(p,accepted,r,proof,old,chain,[registration['request_reference'],registration['submission_reference']],native,header_refs)

def parent_review(p,accepted,r,proof,old,chain,registration_refs,native,header_refs):
    """The same frozen scope/configuration review for either real execution kind."""
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
    refs=unique([*(p[k] for k in REQUIRED),*chain.values(),r['plan_reference'],*registration_refs,accepted['registration_reference'],*old['source_references'],*review['source_references'],*configuration_sources,*header_refs])
    data=unique([*data,*old['data_references']])
    from . import closed_domain_resume as Closed
    _,_,closed_refs,closed_data=Closed.reviews(p,accepted)
    refs=unique([*refs,*closed_refs]);data=unique([*data,*closed_data])
    need(not {x['path'] for x in refs}&{x['path'] for x in data},'SMALL_NUMERIC_OR_SELECTOR_FILES_REMAIN_DATA')
    return accepted,r,proof,old,review,data,refs
def sources():
    from . import domain,wire,source,writer,verify,test_v1,configuration,projection,frame_mapping
    refs=[Q.pin(HERE/n) for n in FILES]+F.sources()
    refs.extend(Q.pin(REPO/'workflows/data_v1_final/export/lossless_sqlite_io_v1'/n)for n in ('__init__.py','codec.py','README.md'))
    refs.extend(configuration.ORIGINALS.proof()['source_references'])
    refs.extend(Q.pin(B.HERE/n) for n in B.FILES)
    from workflows.data_v1_final.labels.existing_sprime_pilot_general_cpu_day_v1 import contract as General
    from workflows.data_v1_final.labels.required_molecule_size_rho_v1 import run as RequiredSizeRho
    from workflows.data_v1_final.export.pilot_D5_parallel_guide_v1 import resource as CreditlessResources
    from workflows.data_v1_final.export.pilot_D5_parallel_guide_v1 import writer_adapter as PrivateWriter
    from workflows.data_v1_final.export.pilot_D5_parallel_guide_v1 import parquet_qa as SingleParquetQA
    refs.extend(Q.pin(REPO/'workflows/data_v1_final/export/pilot_D5_parallel_guide_v1'/n)for n in ('__init__.py','resource.py','writer_adapter.py','native_io.py','parquet_qa.py'))
    refs.extend(Q.pin(General.HERE/n) for n in General.FILES)
    refs.extend(Q.pin(REPO/'workflows/data_v1_final/execution/cpu_analysis_general_nodes_v1'/n)
      for n in ('__init__.py','contract.py','quota_provider.py'))
    for name,m in list(sys.modules.items()):
        path=getattr(m,'__file__',None)
        if name.startswith('workflows.') and path and pathlib.Path(path).suffix=='.py':
            path=pathlib.Path(path).absolute();need(REPO in path.parents,'SOURCE_DEPENDENCIES_FROM_ACTUAL_REPOSITORY');refs.append(Q.pin(path))
    return unique(refs)
