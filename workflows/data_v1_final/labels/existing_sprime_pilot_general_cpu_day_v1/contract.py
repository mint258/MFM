"""Bounded pilot authorities are distinct from final Common/D4/D5 releases."""
import csv,io
from pathlib import Path
from workflows.data_v1_final.conformers.pm7_precache_day_v1 import metadata as P
from workflows.data_v1_final.labels.normalization_typed_cache_v1.contract import reference
need=P.need;meta=P.meta;RUN=P.RUN;REPO=P.REPO;PY=P.PY
HERE=REPO/'workflows/data_v1_final/labels/existing_sprime_pilot_general_cpu_day_v1'
KEY='existing_sprime_pilot_general_cpu_day_v1';MODULE='workflows.data_v1_final.labels.existing_sprime_pilot_general_cpu_day_v1.run'
FILES=('__init__.py','contract.py','run.py','metadata.py','geometry.py','source_inverse.py','test_boundaries.py','README.md')
GLOBAL_SOURCE_COUNTS={'records':11231854,'molecules':1220466,'task_rows':157245956,'fields':146,'logical_groups':171}
PILOT_COUNTS={'TRAIN':50000,'VAL':5000};D5_GUIDE_TRAIN_COUNTS=(120000,240000,600000)

def unique(refs):return P.unique([reference(r,source=r.get('bytes')==0) for r in refs])

def scope(p):
    return {'purpose':'PROVISIONAL_EXISTING_COMPLETE_SPRIME_PILOT_D4_AND_D5_COMPONENTS',
        'requested_cpus':16,'node':p['node'],'wall_seconds':86400,'softwall_drain_seconds':900,
        'output_directory':p['output_directory'],'whole_output_cap_bytes':p['whole_output_cap_bytes'],
        'pilot_counts':PILOT_COUNTS,'original_population_counts':GLOBAL_SOURCE_COUNTS,
        'pilot_input_review_reference':p['pilot_input_review_reference'],
        'projection_origin_review_reference':p['projection_origin_review_reference'],
        'pm7_prefix_review_reference':p['pm7_prefix_review_reference'],'field_scope':p['field_scope'],
        'original_TSQR_chunk':256,'original_QR_reduction':'ORIGINAL_LOGICAL_OWNER_GROUP_ORDERED_LEFT_FOLD',
        'quality_new_mask_fraction':.01,'independent_numeric_replay_required':True,
        'full_Common_D4_D5_D3_D6_release':False,'new_QM_UFF_calls':0,'internal_child_C0_fabricated':False}

def plan(p):
    need(p['schema']=='EXISTING_SPRIME_PILOT_GENERAL_CPU_DAY_PLAN_V1' and p['status']=='ROOT_REVIEWED_EXECUTABLE_BOUNDED_PILOT'
        and p['reviewer']=='root' and p['cpus']==p['requested_cpus']==p['workers']==16 and p['node'] in ('compute-0-2','compute-0-8','compute-0-9','compute-0-10','compute-0-11','compute-0-12','compute-0-13','compute-0-14','compute-0-15','compute-0-16','compute-0-17','compute-0-18','compute-0-19')
        and p['wall_seconds']==86400 and p['softwall_drain_seconds']==900,'NEW_EXACT_GENERIC16_DAY_PILOT_NOT_FINAL_AUTHORITY')
    need(type(p['whole_output_cap_bytes'])is int and 32<<30<=p['whole_output_cap_bytes']<=512<<30
        and p['TSQR_chunk']==256 and p['quality_new_mask_fraction']==.01
        and p['independent_numeric_replay_required']is True and p['full_Common_D4_D5_D3_D6_release']is False,
        'EXPLICIT_BOUNDED_OUTPUT_AND_UNCHANGED_MATH_QUALITY')
    need(Path(p['output_directory']).parent==RUN/'artifacts/labels/source_status_v1/existing_sprime_pilot_general_cpu_day_v1'
        and p['scope_parameters']==scope(p),'FRESH_VERSIONED_PROVISIONAL_PILOT_OUTPUT_AND_EXACT_SCOPE')
    review=meta(p['pilot_input_review_reference'])
    need(review['schema']=='ROOT_EXISTING_COMPLETE_SPRIME_PILOT_INPUT_REVIEW_V1' and review['reviewer']=='root'
        and review['status']=='APPROVED_BOUNDED_OLD_COMPLETE_SPRIME_NOT_FINAL_COMMON'
        and review['pilot_counts']==PILOT_COUNTS and review['seed']==20261025
        and review['no_label_success_or_runtime_size_selection']is True and review['field_scope']==p['field_scope']
        and review['pending_Sprime_availability_not_new_scientific_failure']is True
        and review['full_Common_D4_D5_D3_D6_release']is False,'ROOT_EXPLICIT_PILOT_MOTHER_NOT_FULL_GATE_WAIVER')
    need(p['source_references'] and p['data_references'],'REAL_SOURCE_AND_DATA_REFERENCES_REQUIRED')
    active=p['field_scope']['active_field_ids'];need(type(active)is list and len(active)==len(set(active))
        and all(type(fid)is int and 0<=fid<146 for fid in active),'ROOT_EXACT_ENABLED_FIELD_OWN_TASK_QUALITY_SCOPE')
    for ref in p['source_references']:need(P.pin(ref['path'])==ref,'EXACT_CURRENT_PILOT_SOURCE')
    for ref in p['data_references']:reference(ref)
    return p

def prefix_adapter(request):
    """Only two explicitly implemented producer versions, never arbitrary import."""
    argv=request['execution_argv'];pair=(request['scope_key'],argv[3] if len(argv)>=4 else None)
    if pair==('pm7_precache_day_v1','workflows.data_v1_final.conformers.pm7_precache_day_v1.run'):
        from workflows.data_v1_final.conformers.pm7_precache_day_v1 import io as producer_io
        return P,producer_io
    if pair==('pm7_precache_hof_resume_day_v1','workflows.data_v1_final.conformers.pm7_precache_hof_resume_day_v1.run'):
        from workflows.data_v1_final.conformers.pm7_precache_hof_resume_day_v1 import metadata as producer,io as producer_io
        return producer,producer_io
    raise ValueError('ONLY_EXACT_REGISTERED_OLD_OR_HOF_RESUME_PRODUCER_MODULE_SCOPE_PAIR')

def prefix_origin(p):
    """Registered immutable prefix, explicitly not a claim of live-parent C0."""
    v=meta(p['pm7_prefix_review_reference'])
    need(v['schema']=='ROOT_PM7_IMMUTABLE_PILOT_PREFIX_READONLY_REVIEW_V1' and v['reviewer']=='root'
        and v['status']=='APPROVED_NEW_PARENT_FULL_PREFIX_READBACK_NOT_PRODUCER_C0'
        and v['new_parent_complete_SHA_owner_claim_graph_bits_validation_required']is True
        and v['unknown_or_partial_packet_accepted']is False,'EXPLICIT_PM7_PREFIX_READONLY_AUTHORITY')
    request=meta(v['request_reference']);sub=meta(v['submission_reference']);proof=meta(v['proof_reference'])
    jid=str(sub['job_id']);argv=request['execution_argv'];planref=v['plan_reference'];old=meta(planref)
    producer,producer_io=prefix_adapter(request)
    need(request==sub['request']==proof['request'] and sub['request_reference']==proof['request_reference']==v['request_reference']
        and sub['sbatch_returncode']==0 and sub['uid']==proof['uid']==1278 and str(proof['job_id'])==jid
        and request['scope_key']==producer.KEY and request['cpus']==16
        and request['node'] in ('compute-0-2','compute-0-8','compute-0-9','compute-0-10','compute-0-11','compute-0-12','compute-0-13','compute-0-14','compute-0-15','compute-0-16','compute-0-17','compute-0-18','compute-0-19') and request['wall_seconds']==86400,
        'EXACT_ACTUAL_PM7_REQUEST_SUBMISSION_PROOF_NOT_NEW_OR_FAKE_PARENT')
    need(planref in request['source_references'] and argv==[PY,'-B','-m',producer.MODULE,'--plan',planref['path'],
        '--root-preflight',v['proof_reference']['path'],'--output',old['output_directory']]
        and v['prefix_locator']==str(Path(old['output_directory'])/'pilot_cache_prefix.json')
        and v['producer_parent_C0_claimed']is False,'UNIQUE_REGISTERED_IMMUTABLE_PREFIX_LOCATOR_NO_FUTURE_HASH')
    observation=meta(v['owner_observation_reference'])
    need(observation['schema']=='ROOT_PM7_PARENT_RUNNING_OBSERVATION_V1' and observation['actual_parent_state']=='RUNNING'
        and str(observation['job_id'])==jid and observation['uid']==1278 and observation['node']==request['node']
        and observation['allocated_cpus']==16 and observation['proof_reference']==v['proof_reference']
        and observation['request_reference']==v['request_reference'] and observation['query_returncode']==0,
        'ACTUAL_RUNNING_PRODUCER_OBSERVATION_AT_ROOT_BINDING_NOT_A_PARENT_C0_ASSERTION')
    need(P.pin(observation['raw_observation_reference']['path'])==observation['raw_observation_reference'],'ACTUAL_RUNNING_PARENT_RAW_METADATA_PIN')
    for ref in request['source_references']:need(P.pin(ref['path'])==ref,'REGISTERED_PM7_OWNER_SOURCE_BYTES_UNCHANGED')
    return v,old,proof

def projection_origins(p):
    v=meta(p['projection_origin_review_reference'])
    need(v['schema']=='ROOT_PILOT_SELECTED_TYPED_PROJECTION_ORIGIN_REVIEW_V1' and v['status']=='APPROVED_CURRENT_PARENT_SELECTED_TYPED_REVALIDATION'
        and v['reviewer']=='root' and v['old_failed_parent_states_and_costs_preserved']is True
        and v['all_selected_base_and14_tasks_whole_SHA_owner_bits_quality_revalidation_required']is True
        and v['old_timeout_or_unknown_promoted']is False,'EXPLICIT_SELECTED_CACHE_TECHNICAL_ADOPTION_NOT_OLD_C0')
    need(v['projection_origins'],'REAL_OLD_COMMITTED_PROJECTION_ORIGINS')
    for origin in v['projection_origins']:
        need(origin['actual_parent_state'] in ('COMPLETED','FAILED','TIMEOUT') and origin['new_scientific_retry']is False,'ACTUAL_ORIGINAL_PROJECTION_STATE_RETAINED')
        for root in [origin.get('metadata_output_root',origin['parts_output_root']),*origin.get('parts_output_roots',[origin['parts_output_root']])]:
            path=Path(root);need(path.is_absolute() and '..'not in path.parts and RUN/'artifacts/labels/source_status_v1' in path.parents,'EXPLICIT_BOUNDED_ORIGINAL_TYPED_METADATA_AND_PART_ROOTS')
        accounting=meta(origin['accounting_reference']);proof=meta(origin['proof_reference']);jid=str(proof['job_id'])
        row=[r for r in accounting['parents'] if str(r['job_id'])==jid]
        need(accounting['query_returncode']==0 and accounting['uid']==1278 and accounting['endpoint']=='202.38.247.57:22' and len(row)==1
            and row[0]['state']==origin['actual_parent_state'] and accounting['raw_sacct_reference']==origin['raw_reference']
            and proof['uid']==1278,'REAL_PROJECTION_PARENT_AND_RAW_COST_CHAIN')
        raw,actual=P.small(origin['raw_reference']['path']);need(actual==origin['raw_reference'],'ACTUAL_RAW_ACCOUNTING_BYTE_PIN')
        rr=[r for r in csv.DictReader(io.StringIO(raw.decode('utf-8-sig')),delimiter='|') if r['JobIDRaw']==jid]
        need(len(rr)==1 and rr[0]['UID']=='1278' and rr[0]['State'].split()[0]==row[0]['state'] and rr[0]['ExitCode']==row[0]['exit_code']
            and int(rr[0]['AllocCPUS'])==row[0]['alloc_cpus']==proof['request']['cpus']
            and int(rr[0]['ElapsedRaw'])==row[0]['elapsed_raw_seconds'] and rr[0]['NodeList']==row[0]['node']==proof['request']['node'],
            'EXACT_TERMINAL_PARENT_RAW_UID_CPU_NODE_ELAPSED_NOT_FAKE_C0')
    return v

def logical(groups):
    need(len(groups)==171 and [g['group_index'] for g in groups]==list(range(171))
        and len({g['source_job_id'] for g in groups})==171,'ORIGINAL171_LOGICAL_GROUPS_CARRIED_THROUGH_BOUNDED_SELECTION')
    return groups

def closed_children(expected,seen,unknown,closed):
    need(all(type(n)is int and n>=0 for n in (expected,seen,unknown,closed)) and seen==expected and unknown==0 and closed==seen,
        'EVERY_IN_SCOPE_ACTUAL_CALL_DOUBLE_HASH_CLOSED_UNKNOWN_IS_HOLD')

def remaining_future(total,cap,closed_allocated_covered_by_quota):
    need(all(type(n)is int and n>=0 for n in (total,cap,closed_allocated_covered_by_quota)) and total>=cap,'EXACT_CURRENT_PARENT_FUTURE_ONCE_IN_TOTAL')
    return total-min(cap,closed_allocated_covered_by_quota)

def user_policy(reference,selection_reference):
    value=meta(reference);r=value['r674'];n=r['normalization'];loss=r['loss']
    need(value['schema']=='USER_FROZEN_D1_V3_DESIGN_POLICY_V1' and value['contract_version']=='v3.0'
        and value['status']=='USER_FROZEN_DESIGN_1_TO_4_FRAME_TEST_CONDITIONAL' and value['selection_authority_reference']==selection_reference
        and r['native_six_order']==['xx','xy','yy','xz','yz','zz'] and n['frobenius_weights']==[1,2,1,2,2,1] and n['center_value']==0
        and loss['denominator']==9 and loss['target_weight']==1 and loss['delta']==1 and loss['kind']=='FROBENIUS_RADIAL_HUBER'
        and n['degenerate_or_missing_scale_target_state']=='LOSS_DISABLED_SCALE_UNBOUND_OR_DEGENERATE'
        and n['winsor_quantile_probabilities']==[.001,.999] and n['scale']=='SERIES_STD_DDOF0'
        and r['eligibility']['rule']=='ALL_SIX_ORIGINAL_VALID_SAME_ACTUAL_GEOMETRY_AND_ENABLED_POLICY'
        and r['eligibility']['loss_ineligibility_creates_new_numeric_mask']is False
        and r['eligibility']['original_quality_mask_fraction_gt_0_01_remains_HOLD']is True,'EXACT_ACTUAL_PUBLISHED_D1_V3_DESIGN')
    return value
