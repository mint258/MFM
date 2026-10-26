"""N1 identities, immutable source bindings and pure selection boundaries."""
from __future__ import annotations
import copy,hashlib,importlib.util,json,math,pathlib,re

SEED_DOMAIN='sprime-ETKDGv3-v1-n1-pprime2:'
SOURCE_N=1;UFF_DESIRED=2;CANDIDATES=10;MAX_CANDIDATES=300;THRESHOLD_A=0.5;ORDER_SEED=20261025
COUNT_CORRECTION_REFERENCE={'path':'/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/repository/configs/data_v1/conformers/n1_pprime2_source_count_correction_v1.json',
    'bytes':2857,'sha256':'df97851fdb4a03bcdc11d43b2e27abfc54dca964ceb326e15c1a34e598f70dbc'}
USABILITY_SEMANTICS_REFERENCES=[
    {'path':'/share/home/zixiao/descriptor_analysis/runs/pretraining_readonly_audit_20261023_v1/scripts/s_population_alignment_v4.py',
        'bytes':17889,'sha256':'6d835e763411aca8fa127d45d4ceca0365c8f08cfa3aba0fd885df8cba9e6ae3'},
    {'path':'/share/home/zixiao/descriptor_analysis/runs/pretraining_readonly_audit_20261023_v1/reports/s_sprime_alignment_v4.json',
        'bytes':3804,'sha256':'764b4ccde3e51ed99990084bb4d26fd2972b27d4fb7b0f22ac6ef84e595286fa'}]
SCOPE_KEY='n1_pprime2_pilot32_v4'
SCOPE={'source_pm7_n1_mother_population':5105,'pilot_molecules':32,'PM7_source_count':1,
    'retained_baseline_count':1,'UFF_desired_count':2,'candidate_requested_per_molecule':10,
    'max_candidate_cap':300,'seed_domain':SEED_DOMAIN,'rdkit_version':'2025.09.5',
    'dedup_rmsd_A':0.5,'uff_max_iterations':2000,'uff_energy_tolerance':1e-6,
    'uff_force_tolerance':1e-4,'new_QM_calls':0,'automatic_retry':False,
    'same_geometry_SHA_cannot_create_second_row':True,'production_population_release':False,
    'source_population_authority':'ORIGINAL_N1_ROLES_AND_VERIFIED_BASELINE',
    'final_common_authority_required':False,'common':False,'pilot_membership':False,
    'source_count_authority':'ROOT_REVIEWED_ACTUAL4521326_SAME_INPUT_PINS',
    'live_account_quota_policy':'MAIN_LOGIN_SAME_STORAGE_REVIEWED_REFRESH30_FRESH120_POLL60',
    'additional_provider_output_reserve_bytes':67108864,
    'whole_output_cap_bytes':8589934592}
PREP_SCOPE_KEY='n1_pprime2_prepare32_v4'
PREP_SCOPE={'source_pm7_n1_mother_population':5105,'pilot_molecules':32,'new_UFF_calls':0,'new_QM_calls':0,
    'source_payload_graph_stereo_checks':True,'source_pointers_from_bound_canonical_index_only':True,
    'final_common_authority_required':False,'common':False,'pilot_membership':False,
    'source_count_authority':'ROOT_REVIEWED_ACTUAL4521326_SAME_INPUT_PINS',
    'all_mother_role_status_strictusable_aggregation':True,
    'live_account_quota_policy':'MAIN_LOGIN_SAME_STORAGE_REVIEWED_REFRESH30_FRESH120_POLL60',
    'additional_provider_output_reserve_bytes':67108864,
    'whole_output_cap_bytes':8589934592}


def need(value,message):
    if not value:raise ValueError(message)


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode('utf-8')


def sha_value(value):return hashlib.sha256(canonical(value)).hexdigest()


def proposed_seed(mid):
    need(isinstance(mid,str) and mid,'MOLECULE_ID_REQUIRED')
    value=int.from_bytes(hashlib.sha256((SEED_DOMAIN+mid).encode()).digest()[:4],'big')
    return max(value&0x7fffffff,1)


def task_key(mid):
    return hashlib.sha256(('n1-pprime2-once-generation-v1:'+mid).encode()).hexdigest()


def reference_shape(ref):
    need(isinstance(ref,dict) and set(ref)=={'path','bytes','sha256'},'EXACT_REFERENCE_TRIPLE_REQUIRED')
    need(isinstance(ref['path'],str) and pathlib.Path(ref['path']).is_absolute()
        and '..' not in pathlib.Path(ref['path']).parts,'ABSOLUTE_LITERAL_REFERENCE_REQUIRED')
    need(type(ref['bytes']) is int and ref['bytes']>0 and isinstance(ref['sha256'],str)
        and re.fullmatch('[0-9a-f]{64}',ref['sha256']),'POSITIVE_BYTES_AND_EXACT_SHA_REQUIRED')
    return ref


def pinned_small(ref):
    reference_shape(ref);need(ref['bytes']<=1<<20,'SMALL_SOURCE_METADATA_ONLY')
    path=pathlib.Path(ref['path']);need(path.is_file() and not path.is_symlink(),'REGULAR_PINNED_SOURCE_REQUIRED')
    with path.open('rb') as stream:body=stream.read((1<<20)+1)
    need(len(body)==ref['bytes'] and hashlib.sha256(body).hexdigest()==ref['sha256'],'FROZEN_SMALL_SOURCE_CHANGED')
    return path


def module_from_pin(name,ref):
    path=pinned_small(ref);spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def load_count_correction(reference):
    need(reference==COUNT_CORRECTION_REFERENCE,'EXACT_ROOT_COUNT_CORRECTION_REFERENCE_REQUIRED')
    value=json.loads(pinned_small(reference).read_text())
    need(value.get('schema')=='ROOT_REVIEWED_N1_SOURCE_POPULATION_COUNT_CORRECTION_V1'
        and value.get('status')=='APPROVED_FOR_EXACT_SOURCE_COUNT_CORRECTION_AND_RECOUNT'
        and value.get('reviewer')=='root' and value.get('endpoint')=='202.38.247.57:22'
        and value.get('uid')==1278,'ACTUAL_ROOT_REVIEWED_MAIN_COUNT_CORRECTION_REQUIRED')
    need(value['expected_source_pm7_n1_molecules']==SCOPE['source_pm7_n1_mother_population']==PREP_SCOPE['source_pm7_n1_mother_population']
        and value['source_population_rows']==1220466 and value['predicate']=='S_conformers=1'
        and value['role_filter_before_mother_count'] is False and value['legacy_expected_count']==5040
        and value['legacy_count_provenance']=='UNPROVEN_HARDCODE_NOT_INDEPENDENT_SOURCE_MEASUREMENT'
        and value['all5105_source_rows_preserved'] is True,'EXACT_OBSERVED_MOTHER_DEFINITION_NO_TRIM_OR_ROLE_FILTER')
    need(value['common'] is False and value['pilot_membership'] is False and value['production_membership'] is False
        and value['final_common_reference'] is None and value['same_task_key_seed_and_once_ledger_required'] is True
        and value['scientific_recipe_tolerances_and_quality_thresholds_changed'] is False
        and value['second_geometry_clones_allowed'] is False and value['retry_or_new_UFF_QM_authorized_by_this_count_record'] is False,
        'METADATA_COUNT_CORRECTION_IS_NOT_SCIENCE_OR_RETRY_AUTHORITY')
    parent=value['actual_parent']
    need(parent['JobIDRaw']=='4521326' and parent['UID']=='1278' and parent['State']=='FAILED' and parent['ExitCode']=='3:0'
        and parent['ElapsedRaw']=='123' and parent['AllocCPUS']=='16' and parent['NodeList']=='compute-0-13'
        and value['actual_allocated_core_seconds']==1968,'REAL_FAILED_PREPARE_COUNT_EVIDENCE_AND_COST_REQUIRED')
    prepared=json.loads(pinned_small(value['prepared_reference']).read_text())
    validation=json.loads(pinned_small(value['source_sha_validation_reference']).read_text())
    population=json.loads(pinned_small(value['source_population_authority_reference']).read_text())
    need(prepared['schema']=='N1_PPRIME2_PILOT_PREPARED32_V2' and prepared['job_id']=='4521326'
        and prepared['status']=='PENDING_INPUT32_NOT_READY' and prepared['mother_count']==5105
        and prepared['selected_count']==prepared['eligible_count']==0 and prepared['new_UFF_calls']==prepared['new_QM_calls']==0
        and prepared['reason_counts']=={'MOTHER_COUNT_NOT5040':5105}
        and prepared['source_sha_validation']==value['source_sha_validation_reference']
        and prepared['source_population_authority']==value['source_population_authority_reference'],
        'PRIOR_GLOBAL_COUNT_GATE_IS_NOT_PHYSICAL_BASELINE_EXCLUSION_EVIDENCE')
    need(validation['status']=='ALL_ACTUAL_SOURCE_SHA_VERIFIED' and validation['runtime']=={'job_id':'4521326','uid':1278,'allocated_cpus':16},
        'PRIOR_ACTUAL_SOURCE_SHA_VALIDATION_REQUIRED')
    matches=[row for row in validation['inputs'] if row['reference']==value['per_molecule_reference']]
    need(len(matches)==1 and matches[0]['actual']==value['per_molecule_reference']
        and matches[0]['status']=='ACTUAL_FULL_SHA_MATCH','EXACT_PRIOR_PER_MOLECULE_SHA_BINDING_REQUIRED')
    need(population['schema']=='N1_PPRIME2_SOURCE_POPULATION_AUTHORITY_V2' and population['job_id']=='4521326'
        and population['mother_count']==5105 and population['expected_mother_count']==5040
        and population['source_sha_validation']==value['source_sha_validation_reference']
        and value['per_molecule_reference'] in population['source_inputs'],
        'PRIOR_COUNT_OBSERVATION_AND_SAME_SOURCE_PINS_REQUIRED')
    return value


def count_evidence_references(catalog):
    ref=catalog['count_correction_authority_reference'];value=load_count_correction(ref)
    return [ref,*[value[name] for name in ('prepared_reference','source_sha_validation_reference','source_population_authority_reference')]]


def load_catalog(ref):
    value=json.loads(pinned_small(ref).read_text(encoding='utf-8'))
    need(value.get('schema')=='N1_PPRIME2_PILOT_DEPENDENCIES_V4','FROZEN_SOURCE_CATALOG_REQUIRED')
    correction=load_count_correction(value['count_correction_authority_reference'])
    need(value.get('seed_domain')==SEED_DOMAIN and value.get('source_N')==1
        and value.get('uff_desired_count')==2 and value.get('candidate_requested')==10
        and value.get('cap')==300 and value.get('rdkit_version')=='2025.09.5'
        and value.get('expected_source_pm7_n1_molecules')==correction['expected_source_pm7_n1_molecules'],'N1_SCIENCE_SCOPE_CHANGED')
    expected={'io','selection','original_fill_reference_only','graph_stereo_rmsd',
        'legacy_prepare_import','recipe','proposal_source_reference_only','proposal_config_reference_only'}
    need(set(value['references'])==expected,'EXACT_FROZEN_DEPENDENCY_ROLES_REQUIRED')
    for item in value['references'].values():pinned_small(item)
    need(len(value['inherited_v1_sources'])==6,'UNCHANGED_V1_SIX_SOURCES_REQUIRED')
    for item in value['inherited_v1_sources']:pinned_small(item)
    need(len(value['inherited_v2_sources'])==9,'UNCHANGED_V2_NINE_SOURCE_PROVENANCE_REQUIRED')
    for item in value['inherited_v2_sources']:pinned_small(item)
    need(len(value['inherited_v3_sources'])==9,'UNCHANGED_V3_COUNT_AND_AGGREGATION_NINE_SOURCE_PROVENANCE_REQUIRED')
    for item in value['inherited_v3_sources']:pinned_small(item)
    need(value['usability_semantics_provenance']==USABILITY_SEMANTICS_REFERENCES,'EXACT_ORIGINAL_PRODUCER_AND_CLOSED_USABILITY_DEFINITIONS_REQUIRED')
    for item in value['usability_semantics_provenance']:pinned_small(item)
    return value


def validate_task(task,source_population_authority_reference):
    """Prepared metadata is trusted only through Root's pinned CPU preparation.

    The core still rechecks actual source graph, atom order, stereo, baseline
    geometry/energy and payload SHA. A True membership flag alone is no authority.
    """
    need(task.get('schema')=='N1_PPRIME2_PILOT_TASK_V2','NEW_N1_PREPARED_TASK_REQUIRED')
    meta=task['meta'];mid=meta['molecule_id'];seed=proposed_seed(mid)
    need(task['task_key']==task_key(mid),'NEW_INDEPENDENT_ONCE_TASK_KEY_REQUIRED')
    for key,value in (('PM7_source_count',1),('source_N',1),('accepted_baseline_count',1),('UFF_desired_count',2)):
        need(type(meta.get(key)) is int and meta[key]==value,'SOURCE_N1_AND_UFF_TARGET2_MUST_BE_SEPARATE:'+key)
    need(len(task['records'])==1 and len(task['existing_conformers'])==1,'ONE_PM7_POINTER_AND_ONE_ACCEPTED_BASELINE_REQUIRED')
    need(meta.get('final_common_member') is False and meta.get('common') is False
        and meta.get('pilot_membership') is False and meta.get('production_membership') is False
        and task.get('final_common_reference') is None and meta.get('effective_role') in {'TRAIN','VAL'}
        and meta.get('Sprime_status')!='UFF_UNSUPPORTED','PILOT_ONLY_FROZEN_ROLES_NO_FAKE_FINAL_COMMON')
    refs=task['authority_references']
    need(set(refs)=={'source_population_authority','source_pointer_manifest','accepted_baseline_evidence','roles_manifest'},
        'COMPLETE_PREPARATION_PARENT_REFERENCES_REQUIRED')
    for ref in refs.values():reference_shape(ref)
    need(refs['source_population_authority']==source_population_authority_reference,'ACTUAL_SOURCE_POPULATION_AUTHORITY_REQUIRED')
    pointer=task['records'][0];baseline=task['existing_conformers'][0]
    need(pointer['molecule_id']==mid and baseline['molecule_id']==mid,'MOLECULE_POINTER_BASELINE_ID_MISMATCH')
    need(baseline['status']=='SUCCESS' and baseline['converged'] is True
        and type(baseline['sprime_conf_idx']) is int and baseline['sprime_conf_idx']==0,'ONE_VALID_ORIGINAL_BASELINE_REQUIRED')
    need(type(baseline['seed']) is int and baseline['seed']!=seed,'NEW_PROPOSAL_SEED_MUST_DIFFER_FROM_BASELINE')
    need(task['baseline_row_sha256']==sha_value(baseline),'BASELINE_FULL_ROW_CANONICAL_SHA_CHANGED')
    need(isinstance(task.get('baseline_geometry_id'),str) and task['baseline_geometry_id'], 'ORIGINAL_BASELINE_GEOMETRY_ID_REQUIRED')
    return meta,pointer,baseline,seed


def select_real_second(mid,baseline,candidates,distance,selection):
    """Pure admission/selection of core-produced events, not proof of real calls.

    Original identity SHA is protected. Different SHA but RMSD<0.5 remains the
    frozen select_fill fallback. All input rows/events are left unchanged.
    """
    need(baseline['origin']=='accepted_sprime' and baseline['geometry_sha256'], 'VALIDATED_REAL_BASELINE_REQUIRED')
    need(len(candidates)<=CANDIDATES,'SOURCE_N1_CANNOT_EXCEED10_OPTIMIZATION_EVENTS')
    seen_keys={baseline['candidate_key']};seen_ids=set();seen_sha={baseline['geometry_sha256']}
    seed=proposed_seed(mid);eligible=[];excluded=[];valid=[]
    for candidate in candidates:
        row=copy.deepcopy(candidate)
        need(row['origin']=='data_v1_n1_pprime2' and row['seed']==seed and row['seed']!=baseline['seed'],
            'ORIGINAL_PROPOSAL_SEED_AND_NEW_CANDIDATE_ORIGIN_REQUIRED')
        need(type(row['candidate_id']) is int and row['candidate_id']>=0,'REAL_NATIVE_CANDIDATE_ID_REQUIRED')
        need(row['candidate_key'] not in seen_keys and row['candidate_id'] not in seen_ids,'DUPLICATE_NATIVE_CANDIDATE_ID')
        seen_keys.add(row['candidate_key']);seen_ids.add(row['candidate_id'])
        need(row.get('optimizer_called') is True and row.get('optimization_finished') is True,
            'ACTUAL_FINISHED_OPTIMIZATION_EVENT_REQUIRED')
        if row.get('finite') is not True or type(row.get('optimizer_code')) is not int or row['optimizer_code']!=0 or row.get('stereo_valid') is not True:
            excluded.append({'candidate_key':row['candidate_key'],'reason':'NOT_FINITE_CONVERGED_AND_STEREO_VALID'});continue
        need(math.isfinite(float(row['energy'])),'FINITE_UFF_ENERGY_REQUIRED')
        sha=row['geometry_sha256'];need(isinstance(sha,str) and re.fullmatch('[0-9a-f]{64}',sha),'ACTUAL_GEOMETRY_SHA_REQUIRED')
        valid.append(row)
    # Same-identity events stay in the audit. A representative follows the
    # frozen energy/candidate-key ordering rather than raw event arrival order.
    for row in sorted(valid,key=lambda item:(item['energy'],item['candidate_key'])):
        sha=row['geometry_sha256']
        if sha in seen_sha:
            excluded.append({'candidate_key':row['candidate_key'],'reason':'GEOMETRY_SHA_ALREADY_PRESENT'});continue
        seen_sha.add(sha);eligible.append(row)
    selected=selection.select_fill([baseline],eligible,UFF_DESIRED,distance,THRESHOLD_A)
    pool=selection.select_fill([baseline],eligible,1+len(eligible),distance,THRESHOLD_A)
    second=selected[1] if len(selected)==2 else None
    return {'second':second,'eligible_geometry_candidates':len(eligible),'identity_or_quality_exclusions':excluded,
        'candidate_pool_unique_at_0p5_A':sum(not row['below_dedup_threshold'] for row in pool),
        'selected_unique_at_0p5_A':sum(not row['below_dedup_threshold'] for row in selected),
        'Pprime_actual_records':len(selected),'status':'REAL_SECOND_GEOMETRY_SELECTED' if second else 'PPRIME2_PENDING_NO_SECOND_REAL_GEOMETRY'}


def expanded_orders(mid,baseline,second,distance,selection):
    need(second is not None and second['geometry_sha256']!=baseline['geometry_sha256'],'SECOND_REAL_GEOMETRY_IDENTITY_REQUIRED')
    rows=[dict(baseline,conformer_id=0),dict(second,conformer_id=f"n1p2:{second['seed']}:{second['candidate_id']}")]
    return selection.conformer_orders(rows,distance,mid,'uff_sprime',ORDER_SEED)


def pilot32(rows,selection):
    """Only a deterministic subset helper; no parent table/common scan is implied."""
    mids=[row['meta']['molecule_id'] for row in rows]
    need(len(mids)==len(set(mids)),'DUPLICATE_PILOT_MOLECULE')
    ordered=sorted(rows,key=lambda row:(selection.stable_key(ORDER_SEED,row['meta']['molecule_id'],'n1_pprime2_pilot',0),row['meta']['molecule_id']))
    return {'status':'EXACT32_AVAILABLE' if len(ordered)>=32 else 'INSUFFICIENT32_NO_AUTOMATIC_WIDENING',
        'eligible_count':len(rows),'tasks':ordered[:32] if len(ordered)>=32 else []}


# The original constants and pure functions above remain unchanged. These new
# outer scopes authorize source preparation and an independently reviewed wave.
SCOPE_KEY='n1_pprime2_source_full_wave_v1'
PREP_SCOPE_KEY='n1_pprime2_source_full_prepare_v1'
REDUCE_SCOPE_KEY='n1_pprime2_source_full_reduce_v1'
SOURCE_REVIEW_PATH=pathlib.Path('/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/n1_actual32_pilot_science_cost_root_review_v1.json')
V4=pathlib.Path(__file__).absolute().parent.parent/'n1_pprime2_pilot_v4'
MOTHER=5105;ELIGIBLE=4631;IMPORTED=32;NEW_ATTEMPTS=4599;BATCH_CAP=64
_source_scope={'source_pm7_n1_mother_population':MOTHER,'source_eligible_molecules':ELIGIBLE,
    'already_consumed_imported_molecules':IMPORTED,'new_unconsumed_molecules':NEW_ATTEMPTS,
    'PM7_source_count':1,'retained_baseline_count':1,'UFF_desired_count':2,'candidate_requested_per_molecule':10,
    'max_candidate_cap':300,'seed_domain':SEED_DOMAIN,'rdkit_version':'2025.09.5','dedup_rmsd_A':0.5,
    'uff_max_iterations':2000,'uff_energy_tolerance':1e-6,'uff_force_tolerance':1e-4,'new_QM_calls':0,
    'automatic_retry':False,'same_original_once_ledger':True,'same_geometry_SHA_cannot_create_second_row':True,
    'maximum_batch_molecules':BATCH_CAP,'configured_workers':16,'common':False,'pilot_membership':False,
    'production_membership':False,'physical_int64_integration_frozen':False,'production_population_release':False,
    'live_account_quota_policy':'MAIN_LOGIN_SAME_STORAGE_REVIEWED_REFRESH30_FRESH120_POLL60',
    'additional_provider_output_reserve_bytes':67108864,'whole_output_cap_bytes':8589934592}
SCOPE=dict(_source_scope,stage='INDEPENDENTLY_ROOT_REVIEWED_FINITE_SOURCE_WAVE',imported32_new_optimizer_calls=0)
PREP_SCOPE=dict(_source_scope,stage='FULL_SOURCE_BASELINE_VALIDATION_AND_TASK_FREEZE',new_UFF_calls=0,
    all_mother_role_status_strictusable_aggregation=True)
REDUCE_SCOPE=dict(_source_scope,stage='SOURCE_PACKET_COVERAGE_RECONCILIATION',new_UFF_calls=0,new_source_dispatch=False,
    transitive_body_authority='PINNED_SOURCE_ROSTER_AND_TERMINAL_BATCH_RECEIPTS_ONLY')


def source_review(reference):
    need(pathlib.Path(reference['path'])==SOURCE_REVIEW_PATH,'EXACT_ACTUAL32_SCIENCE_COST_REVIEW_LOCATOR')
    value=json.loads(pinned_small(reference).read_text())
    need(value['schema']=='ROOT_ACTUAL_N1_V4_PILOT32_SCIENCE_COST_REVIEW_V1'
        and value['status']=='APPROVED_FOR_SOURCE_FULL_N1_IMPLEMENTATION_AND_BOUNDED_PLANNING'
        and value['reviewer']=='root' and value['endpoint']=='202.38.247.57:22' and value['uid']==1278,'REAL_ACTUAL32_ROOT_SCIENCE_COST_REVIEW')
    need(value['source_mother']==MOTHER and value['source_eligible_physically_validated']==ELIGIBLE
        and value['actual_pilot_molecules']==value['actual_real_second_geometry']==IMPORTED
        and value['remaining_unconsumed_from_current_eligible_roster']==NEW_ATTEMPTS
        and value['actual_optimizer_calls_attempted']==value['actual_optimizer_calls_finished']==308
        and value['actual_saved_float64_all_present_geometry_SHA_readbacks']==IMPORTED
        and value['original_baseline_preserved'] is True and value['same_original_once_ledger_required'] is True
        and value['already_consumed_32_must_be_imported_without_new_optimizer_calls'] is True,'ACTUAL32_FULL_SOURCE_BOUNDARIES')
    need(value['formal_full_source_job_authorized_by_this_review'] is False and value['common'] is False
        and value['pilot_membership'] is False and value['production_population_release'] is False
        and value['descriptive_mean_is_not_tail_or_remaining_runtime_bound'] is True,'IMPLEMENTATION_REVIEW_IS_NOT_BATCH_GENERATION_RELEASE')
    return value


def expected_source_partition(eligible_keys,imported_keys,batch_cap=BATCH_CAP):
    keys=list(eligible_keys);imported=list(imported_keys);imports=set(imported)
    need(len(keys)==len(set(keys)) and len(imports)==len(imported),'DUPLICATE_SOURCE_OR_IMPORTED_ONCE_KEY')
    need(imports.issubset(keys) and type(batch_cap) is int and 1<=batch_cap<=BATCH_CAP,'EXACT_IMPORTED_SUBSET_AND_BOUNDED_WAVE')
    rest=sorted(set(keys)-imports);waves=[rest[i:i+batch_cap] for i in range(0,len(rest),batch_cap)]
    need(len(rest)+len(imports)==len(keys) and len(set(k for wave in waves for k in wave))==len(rest),'SOURCE_KEYS_IMPORT_AND_WAVES_EXACT_PARTITION')
    return {'imported_keys':sorted(imports),'new_keys':rest,'waves':waves}


def finite_batch_review(reference,prepared_reference,batch_reference,batch,quota_review_reference,science_review_reference):
    value=json.loads(pinned_small(reference).read_text())
    need(value['schema']=='ROOT_N1_SOURCE_FULL_FINITE_BATCH_REVIEW_V1' and value['status']=='APPROVED_FOR_EXACT_BOUNDED_SOURCE_BATCH'
        and value['reviewer']=='root' and value['endpoint']=='202.38.247.57:22' and value['uid']==1278,'SEPARATE_EXACT_ROOT_FINITE_BATCH_REVIEW')
    need(value['prepared_reference']==prepared_reference and value['batch_reference']==batch_reference
        and value['science_cost_review_reference']==science_review_reference and value['quota_provider_review_reference']==quota_review_reference,
        'EXACT_BATCH_SOURCE_AND_FRESH_QUOTA_REVIEW_PINS')
    keys=[row['task_key'] for row in batch['tasks']]
    need(value['approved_task_keys']==keys and len(keys)==len(set(keys)) and 0<len(keys)<=BATCH_CAP
        and value['approved_task_references']==[row['task_reference'] for row in batch['tasks']]
        and value['once_ledger_root']=='/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/conformers/n1_pprime2_pilot_v2/once_ledger'
        and value['new_optimizer_attempts_authorized_for_exact_keys'] is True and value['automatic_retry'] is False,'FINITE_SOURCE_TASKS_ONLY_NOT_GLOBAL_AUTHORIZATION')
    need(value['common'] is False and value['pilot_membership'] is False and value['production_membership'] is False
        and value['physical_int64_integration_frozen'] is False and value['production_population_release'] is False,'SOURCE_PACKET_GENERATION_ONLY')
    return value


def check_batch_partition(batch,imported_keys):
    rows=batch['tasks'];keys=[row['task_key'] for row in rows]
    need(0<len(rows)==batch['task_count']<=BATCH_CAP and len(keys)==len(set(keys)),'BOUNDED_UNIQUE_FINITE_BATCH_COUNT')
    need(not(set(keys)&set(imported_keys)) and all(row['state']=='UNCONSUMED_NEW_ATTEMPT_NOT_AUTHORIZED_UNTIL_FINITE_ROOT_REVIEW' for row in rows),
        'IMPORTED_OR_CONSUMED_TASK_CANNOT_ENTER_NEW_BATCH')
    return keys


def source_outcome(consumed,packet_available,second_available):
    need(not packet_available or consumed,'DURABLE_PACKET_WITHOUT_ONCE_CLAIM')
    need(not second_available or packet_available,'REAL_SECOND_REQUIRES_ACTUAL_PACKET')
    if packet_available:return 'REAL_SECOND_PACKET_SOURCE_ONLY' if second_available else 'CONSUMED_PACKET_PENDING_SECOND_GEOMETRY'
    return 'UNKNOWN_CONSUMED_NO_AUTORETRY' if consumed else 'UNSTARTED_UNCONSUMED_NOT_RETRIED'
