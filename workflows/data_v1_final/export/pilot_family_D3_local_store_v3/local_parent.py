"""Read a genuinely closed user-authorized head D4; never synthesize Slurm C0."""
import pathlib,re
from . import contract as C

SCHEMA='ROOT_LOCAL_HEAD_D4_BOUNDED_COMPONENT_ACCEPTANCE_V1'
STATUS='ACTUAL_LOCAL_EXIT0_BOUNDED_COMPONENTS_ACCEPTED_NOT_FINAL_COMMON'
COMPLETE='PROVISIONAL55K_FAST_TYPED_NATIVE_RANDOM_AND_TRAIN_D4_COMPLETE_PENDING_ACTUAL_LOCAL_EXIT_ZERO'

def numeric_scope(receipt,envelope=None):
    """Accept only the actual validation scope explicitly selected by the user."""
    envelope=C.meta(receipt['plan_reference'])if envelope is None else envelope
    reference=envelope.get('guide_validation_scope_reference')
    if reference is None:
        C.need(receipt['independent_numeric_replay_equal']is True
          and len(receipt['numeric_repetitions'])==2,'ORIGINAL_TWO_ACTUAL_NUMERIC_REPLAYS_REQUIRED')
        return False
    policy=C.meta(reference);scope=policy['operative_scope'];unchanged=policy['unchanged']
    C.need(policy['schema']=='USER_DATA_V1_GUIDE_REQUIRED_VALIDATION_SCOPE_V1'
      and policy['status']=='USER_DIRECTED'and policy['version']=='v1-pilot-provisional'
      and scope['finish_current_first_complete_statistics_pass_including_median_and_MAD']is True
      and scope['full_second_statistics_pass_required']is False
      and scope['do_not_claim_full_second_statistics_pass_was_performed']is True
      and scope['retain_original_Source6_and_Source3_checks']is True
      and scope['retain_10000_export_source_readback_and_count_checks']is True
      and scope['retain_formal_delivery_file_hashes']is True and all(unchanged.values()),
      'EXPLICIT_USER_SINGLE_COMPLETE_PASS_SCOPE_WITH_SCIENTIFIC_RULES_UNCHANGED')
    C.need(receipt['verification_scope']=='GUIDE_REQUIRED_ONE_COMPLETE_ACTUAL_PASS'
      and receipt['independent_numeric_replay_equal']is None
      and receipt['full_second_statistics_pass_performed']is False
      and receipt['guide_required_checks_passed']is True
      and len(receipt['numeric_repetitions'])==1,'ONE_REAL_COMPLETE_PASS_NOT_FICTITIOUS_REPLAY')
    return True

def first_complete_pass(receipt,envelope):
    """A real stopped predecessor supplies data, never a fabricated final exit."""
    continuation=C.meta(envelope['first_complete_pass_continuation_reference'])
    C.need(continuation['schema']=='ACTUAL_LOCAL_D4_FIRST_COMPLETE_PASS_GUIDE_CONTINUATION_V1'
      and continuation['guide_validation_scope_reference']==envelope['guide_validation_scope_reference']
      and continuation['first_complete_pass_preserved']is True
      and continuation['scientific_methods_or_quality_rules_changed']is False
      and continuation['full_second_statistics_pass_performed']is False
      and continuation['first_numeric_reference']==receipt['numeric_repetitions'][0],
      'EXPLICIT_FIRST_COMPLETE_PASS_CONTINUATION_NOT_NEW_NUMERICAL_DATA')
    prior,proof,launch,exit=(C.meta(continuation['actual_prior_'+k+'_reference'])
      for k in ('receipt','proof','launch','exit'))
    C.need(prior['startup_proof_reference']==continuation['actual_prior_proof_reference']
      and prior['job_id']==proof['execution_id']and proof['execution_kind']=='LOCAL_HEADNODE'
      and proof['uid']==1278 and proof['node']=='sonmi'and proof['Slurm_job_id']is None
      and proof['execution_id']=='LOCAL_D4_PID'+str(proof['pid'])+'_START'+str(proof['start_ticks'])
      and exit['exit_code']==1 and exit['actual_pid']==proof['pid']==launch['pid']
      and str(exit['actual_start_ticks'])==str(proof['start_ticks'])==str(launch['start_ticks'])
      and exit['launch_reference']==continuation['actual_prior_launch_reference']
      and prior['held']is False and prior['errors']==[]
      and prior['numeric_repetitions']==receipt['numeric_repetitions'],
      'REAL_NATURALLY_STOPPED_FIRST_PASS_PROCESS_NOT_PROMOTED_TO_EXIT_ZERO')
    C.need(all(prior[k]==receipt[k]for k in ('prefix_reference','population_reference','geometry_reference',
      'coverage_reference','eligibility_reference','typed_reader_config_reference','schema_only_header_reference',
      'closed_geometry_origin_reference')),'SAME_COMPLETE_FIRST_PASS_COMPONENTS_AND_ORIGINAL_GEOMETRY_LINEAGE')
    return continuation

def closed(accepted):
    C.need(accepted['schema']==SCHEMA and accepted['status']==STATUS
      and accepted['reviewer']=='root' and accepted['complete_55k_components'] is True
      and accepted['pilot_counts']==C.COUNTS and accepted['full_Common_D2_D3_D4_D5_D6_release'] is False
      and accepted['old4525232_C0_partial_history_unchanged'] is True,'REAL_LOCAL_D4_LIMITED_ACCEPTANCE')
    chain=accepted['actual_parent']
    C.need(set(chain)=={'manifest','proof','launch','actual_exit'},'LOCAL_CHAIN_HAS_NO_FAKE_ACCOUNTING')
    r,proof,launch,exit=(C.meta(chain[k])for k in ('manifest','proof','launch','actual_exit'))
    envelope=C.meta(r['plan_reference']);old=envelope['operative_plan'];identity=proof['execution_id']
    origin_ref=envelope.get('statistics_resume_origin_reference')
    origin=C.meta(origin_ref)if origin_ref else None
    workers=2
    if envelope.get('headnode_resource_choice_reference'):
        choice=C.meta(envelope['headnode_resource_choice_reference'])
        C.need(choice['schema']=='ROOT_D4_OPERATIONAL_WORKER_CHOICE_V1'
          and choice['status']=='ROOT_APPLIED_OPERATIONAL_CHOICE'and choice['reviewer']=='root'
          and choice['D4_only']is True and choice['node']=='sonmi'and choice['workers']in(8,16)
          and choice['cpu_affinity']==list(range(choice['workers']))and choice['user_specified_exact_worker_count']is False
          and choice['existing_user_headnode_authority_reference']==envelope['headnode_authority_reference']
          and choice['worker_rss_cap_bytes']==3<<30 and choice['whole_output_cap_bytes']==56<<30
          and choice['account_floor_bytes']==100000000000 and choice['scientific_methods_or_quality_rules_changed']is False,
          'EXPLICIT_ROOT_RESOURCE_CHOICE_UNDER_EXISTING_HEAD_D4_AUTHORITY')
        if envelope.get('concurrency16_continuation_reference'):
            from workflows.data_v1_final.labels.existing_sprime_fast55k_head_stats_resume_v4 import runtime as Continuation
        elif envelope.get('tool_cache_continuation_reference'):
            from workflows.data_v1_final.labels.existing_sprime_fast55k_head_stats_resume_v3 import runtime as Continuation
        else:
            from workflows.data_v1_final.labels.existing_sprime_fast55k_head_stats_resume_v2 import runtime as Continuation
        Continuation.reconfiguration(envelope,origin)
        workers=choice['workers']
    expected_data=C.unique([*old['data_references'],*(origin['runtime_additional_data_references']if origin else [])])
    C.need(proof['schema']=='ACTUAL_USER_AUTHORIZED_HEADNODE_D4_PROCESS_PROOF_V1'
      and proof['execution_kind']=='LOCAL_HEADNODE' and proof['Slurm_job_id'] is None
      and proof['uid']==1278 and proof['node']=='sonmi' and proof['actual_affinity']==list(range(workers))
      and re.fullmatch(r'LOCAL_D4_PID[0-9]+_START[0-9]+',identity) is not None
      and identity=='LOCAL_D4_PID'+str(proof['pid'])+'_START'+str(proof['start_ticks'])
      and proof['job_id']==identity and proof['legacy_job_id_field_is_local_execution_id'] is True,
      'REAL_PID_START_IDENTITY_NOT_NUMERIC_SLURM_ID')
    request=C.meta(proof['request_reference'])
    C.need(request==proof['request'] and request['schema']=='ACTUAL_LOCAL_HEAD_D4_REQUEST_V1'
      and request['execution_kind']=='LOCAL_HEADNODE' and request['node']=='sonmi'
      and request['cpus']==workers and request['wall_seconds']==86400
      and request['memory_policy']=='OBSERVED_LOCAL_PROCESS_NO_SLURM_ALLOCATION'
      and len(request['data_references'])==len(expected_data)
      and {v['path']:v for v in request['data_references']}=={v['path']:v for v in expected_data},
      'SAME_LOCAL_REQUEST_AND_SCIENTIFIC_INPUTS')
    module='workflows.data_v1_final.labels.existing_sprime_fast55k_head_stats_resume_v1.run'if origin else 'workflows.data_v1_final.labels.existing_sprime_fast55k_head_v1.run'
    if workers==8:module='workflows.data_v1_final.labels.existing_sprime_fast55k_head_stats_resume_v2.run'
    if envelope.get('tool_cache_continuation_reference'):module='workflows.data_v1_final.labels.existing_sprime_fast55k_head_stats_resume_v3.run'
    if envelope.get('concurrency16_continuation_reference'):module='workflows.data_v1_final.labels.existing_sprime_fast55k_head_stats_resume_v4.run'
    if envelope.get('guide_validation_scope_reference'):
        module='workflows.data_v1_final.labels.existing_sprime_fast55k_head_finalize_guide_v1.run'
    C.need(launch['schema']=='ACTUAL_MAIN_HEAD_D4_LOCAL_LAUNCH_V1'
      and launch['execution_kind']=='LOCAL_HEADNODE' and launch['Slurm_job_id'] is None
      and launch['pid']==proof['pid'] and str(launch['start_ticks'])==str(proof['start_ticks'])
      and launch['uid']==1278 and launch['actual_worker_cap']==workers and launch['plan_reference']==r['plan_reference']
      and launch['argv']==[C.PY,'-B','-m',module,
        '--plan',r['plan_reference']['path']],'ACTUAL_LOCAL_LAUNCH_CORRELATION')
    C.need(exit['schema']=='ACTUAL_MAIN_HEAD_D4_PROCESS_EXIT_V1' and exit['execution_kind']=='LOCAL_HEADNODE'
      and exit['Slurm_job_id'] is None and exit['no_Slurm_C0_claimed'] is True
      and exit['launch_reference']==chain['launch'] and exit['actual_pid']==proof['pid']
      and str(exit['actual_start_ticks'])==str(proof['start_ticks']) and exit['exit_code']==0,
      'ACTUAL_LOCAL_ZERO_EXIT_NOT_ARTIFACT_INFERRED_SUCCESS')
    authority=C.meta(envelope['headnode_authority_reference'])
    C.need(authority['status']=='USER_AUTHORIZED' and authority['D4_only'] is True
      and authority['node']=='sonmi','EXPLICIT_USER_HEAD_D4_ONLY')
    C.need(r['schema']=='EXISTING_SPRIME_FAST55K_PILOT_DAY_RECEIPT_V1' and r['status']==COMPLETE
      and r['producer_execution_kind']=='LOCAL_HEADNODE' and r['Slurm_job_id'] is None
      and r['job_id']==identity and r['startup_proof_reference']==chain['proof']
      and not r['held'] and r['errors']==[] and r['pilot_counts']==C.COUNTS
      and r['new_QM_UFF_calls']==0 and r['temporary_complete_old_Sprime_domain_only'] is True
      and r['available_orders']==['fixed_random'] and r['full_three_order'] is False and r['D7'] is False,
      'COMPLETE_LOCAL_D4_ACTUAL_COMPONENTS_AND_PILOT_SCOPE')
    if numeric_scope(r,envelope):first_complete_pass(r,envelope)
    components=C.COMPONENTS+('schema_only_header_reference',)
    C.need(accepted['component_references']=={k:r[k]for k in components},'EXACT_LOCAL_COMPONENT_REFERENCES')
    gate=C.meta(accepted['source6_reference'])
    C.need(gate['status']=='PASS' and gate['tests']==6 and gate['failures']==gate['errors']==0,
      'SAME_LOCAL_D4_ORIGINAL_SIX_CHECKS')
    current_gate=C.meta(r['fixture_gate'])
    C.need(current_gate['status']=='PASS'and current_gate['tests']==6 and current_gate['failures']==current_gate['errors']==0,
      'ACTUAL_FINAL_STATISTICS_PROCESS_ORIGINAL_SOURCE6_PASS')
    from workflows.data_v1_final.labels.existing_sprime_fast55k_resume_v13 import contract as Producer
    from workflows.data_v1_final.labels.existing_sprime_fast55k_resume_v12 import contract as Previous
    template=C.meta(envelope['scientific_template_plan_reference']);Previous.plan(template)
    execution_fields={'node','workers','pending','output_directory','metadata_recovery_reference',
      'root_carveout_review_reference','source_references','scope_parameters','source_metadata_frame_review_reference'}
    C.need(set(old)-execution_fields==set(template)-execution_fields and all(old[k]==v for k,v in template.items()if k not in execution_fields)
      and old['node']=='sonmi' and old['workers']==workers and old['pending']==2*workers
      and old['whole_output_cap_bytes']==56<<30 and old['scope_parameters']==Producer.scope(old)
      and pathlib.Path(old['output_directory']).parent==C.ROOT/'artifacts/labels/source_status_v1/existing_sprime_fast55k_resume_v13',
      'SAME_VALIDATED_SCIENTIFIC_TEMPLATE_ONLY_EXPLICIT_LOCAL_EXECUTION_CHANGES')
    resource=C.meta(old['metadata_recovery_reference'])
    C.need(resource['schema']=='ROOT_D4_PARTIAL5494_CHECKPOINT_RECOVERY_V1'
      and resource['status']=='APPROVED_CLOSED_METADATA_SERIALIZATION_RESOURCE_CONTINUATION'
      and resource['reviewer']=='root' and resource['old_job_id']=='4525494'
      and resource['new_output_root']==old['output_directory'] and resource['raw_WP5_and_LMDB_unchanged'] is True
      and len(resource['staged_serialization_files'])==5
      and resource['actual_completed_base_F64_and_prefix_snapshot_reused'] is True
      and resource['unaccepted_partial_input_views_scientifically_adopted'] is False,'SAME_LOCAL_RESOURCE_ONLY_RECOVERY')
    Producer.resume_authority(old)
    geometry_identity=identity
    if origin:
        C.need(origin['schema']=='ACTUAL_LOCAL_D4_CLOSED_GEOMETRY_STATISTICS_CONTINUATION_V1'
          and r['closed_geometry_origin_reference']==origin_ref and r['statistics_continuation_only']is True
          and origin['geometry_input_views_or_eligibility_regenerated']is False
          and origin['scientific_methods_or_quality_rules_changed']is False
          and origin['worker_software_rss_cap_bytes']==3<<30 and origin['whole_output_cap_bytes']==56<<30,
          'EXPLICIT_CLOSED_COMPONENT_REUSE_AND_UNCHANGED_MATHEMATICS_LIMITS')
        previous=C.meta(origin['actual_prior_receipt_reference']);pp=C.meta(origin['actual_prior_proof_reference'])
        pe=C.meta(origin['actual_prior_exit_reference']);pl=C.meta(origin['actual_prior_launch_reference'])
        C.need(previous['startup_proof_reference']==origin['actual_prior_proof_reference']
          and pp['execution_kind']=='LOCAL_HEADNODE'and pp['Slurm_job_id']is None and pp['uid']==1278
          and pe['exit_code']==1 and pe['actual_pid']==pp['pid']==pl['pid']
          and str(pe['actual_start_ticks'])==str(pp['start_ticks'])==str(pl['start_ticks'])
          and pe['launch_reference']==origin['actual_prior_launch_reference']and previous['job_id']==pp['execution_id']
          and previous['held']is False and previous['errors']==[]and previous['numeric_repetitions']==[],
          'REAL_FAILED_PRENUMERIC_PARENT_NOT_PROMOTED_TO_SUCCESS')
        C.need(all(r[k]==previous[k]for k in ('geometry_reference','coverage_reference','eligibility_reference',
          'population_reference','prefix_reference','schema_only_header_reference')),
          'EXACT_COMPLETED_COMPONENT_REFERENCES_NO_VALUE_OR_SELECTION_REPLACEMENT')
        summary=C.meta(origin['geometry_metadata_summary_reference'])
        C.need(summary['schema']=='ACTUAL_CLOSED_LOCAL_D4_GEOMETRY_METADATA_SUMMARY_V1'
          and summary['geometry_reference']==r['geometry_reference']and summary['unknown_input_bindings']==0
          and summary['all_in_scope_actual_direct_children_bound']is True,
          'SMALL_OPERATIONAL_SUMMARY_POINTS_TO_ORIGINAL_LARGE_DATA_MANIFEST')
        recovery=C.meta(summary['metadata_checkpoint_recovery_reference']);geometry_identity=pp['execution_id']
    else:
        geometry=C.meta(r['geometry_reference']);recovery=C.meta(geometry['metadata_checkpoint_recovery_reference'])
    C.need(recovery['schema']=='ACTUAL5494_APPEND_ONLY_METADATA_RECOVERY_INTEGRITY_V1'
      and recovery['old_job_id']=='4525494' and recovery['actual_new_job_id']==geometry_identity
      and recovery['all_old_logical_rows_equal_before_after'] is True
      and recovery['prefix_and_suffix_all_sources_covered'] is True,'LOCAL_D4_COMPLETE_PREFIX_TAIL_INTEGRITY')
    href=r['schema_only_header_reference'];header=C.meta(href)
    C.need(header['schema']=='ACTUAL_CPU146_FIELD_SCHEMA_ONLY_QA_V1'
      and header['status']=='ACTUAL_CPU_FIELD_SCHEMA_EXTRACTED_NOT_NATIVE_PRINTED_UNIT_VALIDATION' and header['uid']==1278
      and header['actual_node']=='sonmi' and header['actual_parent_job_id']==geometry_identity
      and header['numerical_statistics_or_MID_or_coordinates_included'] is False
      and header['native_printed_units_verified'] is False and len(header['fields'])==146
      and {f['field_id']for f in header['fields']}==set(range(146))
      and header['actual_input_references']['field_map']==old['field_map_reference']
      and header['actual_input_references']['registry']==old['base_registry_reference'],'SAME_LOCAL_PURE_SCHEMA_HEADER')
    registration=C.meta(accepted['registration_reference'])
    C.need(registration['schema']=='ACTUAL_LOCAL_HEAD_D4_REGISTRATION_V1'
      and registration['receipt_reference']==chain['manifest'] and registration['proof_reference']==chain['proof']
      and registration['launch_reference']==chain['launch'] and registration['exit_reference']==chain['actual_exit']
      and registration['request_reference']==proof['request_reference'],'LOCAL_REGISTRATION_NO_SBATCH_ALIAS')
    return r,proof,old,registration

def parents(plan,accepted):
    r,proof,old,registration=closed(accepted)
    C.need(C.native_mode(plan),'LOCAL_D4_FIXED_RANDOM_ONLY')
    roots=C.meta(plan['bounded_export_review_reference'])['transitive_closed_output_roots']
    from workflows.data_v1_final.labels.existing_sprime_fast55k_resume_v13 import contract as Producer
    C.need(all(str(root)in roots for root in (old['output_directory'],Producer.OLDROOT,Producer.PHASE_ROOT)),
      'LOCAL_OUTPUT_AND_BOTH_ORIGINAL_CLOSED_ORIGINS_REVIEWED')
    envelope=C.meta(r['plan_reference']);guide_refs=[]
    if envelope.get('guide_validation_scope_reference'):
        continuation=C.meta(envelope['first_complete_pass_continuation_reference'])
        guide_refs=[envelope['guide_validation_scope_reference'],envelope['first_complete_pass_continuation_reference'],
          *(continuation['actual_prior_'+k+'_reference']for k in ('receipt','proof','launch','exit'))]
    return C.parent_review(plan,accepted,r,proof,old,accepted['actual_parent'],
      [registration['request_reference'],accepted['source6_reference'],r['fixture_gate'],
       envelope['headnode_authority_reference'],*guide_refs,
       *([r['closed_geometry_origin_reference'],C.meta(r['closed_geometry_origin_reference'])['geometry_metadata_summary_reference']]
         if r.get('closed_geometry_origin_reference')else[])],True,[r['schema_only_header_reference']])

def component_numeric_scope(plan,components):
    accepted=C.meta(plan['pilot_acceptance_reference']);receipt=C.meta(accepted['actual_parent']['manifest'])
    C.need(receipt['numeric_repetitions']==components['numeric_repetitions'],
      'EXACT_ACCEPTED_NUMERIC_REFERENCES_NOT_INLINE_SUBSTITUTE')
    if receipt.get('producer_execution_kind')=='LOCAL_HEADNODE':return numeric_scope(receipt)
    C.need(len(components['numeric_repetitions'])==2 and receipt['independent_numeric_replay_equal']is True,
      'ORIGINAL_SLURM_TWO_REPLAY_SCOPE_UNCHANGED')
    return False

def geometry_producer(coverage,receipt):
    """Use the actual closed geometry producer for immutable reader provenance."""
    if not receipt.get('closed_geometry_origin_reference'):return receipt
    origin=C.meta(receipt['closed_geometry_origin_reference']);previous=C.meta(origin['actual_prior_receipt_reference'])
    C.need(previous['coverage_reference']==receipt['coverage_reference']
      and previous['job_id']==coverage['job_id']and previous['geometry_reference']==receipt['geometry_reference'],
      'ACTUAL_CLOSED_GEOMETRY_PRODUCER_NOT_FINAL_STATISTICS_PRODUCER_ALIAS')
    return previous

def workers(coverage,job_id):
    if coverage.get('producer_execution_kind')!='LOCAL_HEADNODE':return 16
    C.need(coverage.get('Slurm_job_id') is None and str(coverage['job_id'])==str(job_id)
      and re.fullmatch(r'LOCAL_D4_PID[0-9]+_START[0-9]+',str(job_id)) is not None,
      'LOCAL_COVERAGE_REAL_EXECUTION_ID_NOT_SLURM')
    return 2

def status(receipt):
    if receipt.get('producer_execution_kind')=='LOCAL_HEADNODE':
        C.need(receipt.get('Slurm_job_id') is None,'LOCAL_RECEIPT_NO_SLURM_ID')
        return COMPLETE
    return 'PROVISIONAL55K_FAST_TYPED_NATIVE_RANDOM_AND_TRAIN_D4_COMPLETE_PENDING_ACTUAL_C0_ROOT_SEAL'
