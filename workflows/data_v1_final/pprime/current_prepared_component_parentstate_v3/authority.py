"""Small truthful RUNNING-parent authority and independent closed-byte readback."""
import csv,fcntl,hashlib,io,json,pathlib,re
from . import contract as C
from workflows.data_v1_final.pprime.formal_packed_sharded_day_v3 import contract as Prep
from workflows.data_v1_final.pprime.formal_packed_sharded_day_v2 import io as I,publication as U
SCHEMA='ROOT_APPROVED_CURRENT_PARENT_PREPARED_COMPONENT_V1'
STATUS='APPROVED_CPU_VERIFY_CLOSED_COMPONENT_NOT_PARENT_C0'
ASSIGNMENT='ROOT_EXCLUSIVE_PREPARED_COMPONENT_SLOT_HANDOFF_V1'
HEADER='PPRIME_CPU_CLOSED_ASSIGNED_PAIRS_HEADER_V2'
SERIAL=C.Q.ROOT/'control/root_data_v1_sequential_submit.lock'
NATIVE_LOCK=C.Q.ROOT/'control/pprime_dual_parallel_20261030/single_root_native_autowire.lock'
OPROOT=C.Q.ROOT/'control/pprime_full_start_user_20261030_v1/full38_resource_v3_rollout'

def observed_parent_state(state,exit_code):
    # Actual account state is independent of a committed component's byte closure.
    C.need(state in {'RUNNING','COMPLETED','FAILED','TIMEOUT','CANCELLED','OUT_OF_MEMORY','NODE_FAIL','PREEMPTED'},'KNOWN_ACTUAL_PREPARATION_PARENT_STATE')
    C.need(type(exit_code)is str and re.fullmatch(r'[0-9]+:[0-9]+',exit_code),'ACTUAL_PREPARATION_EXIT_CODE')
    if state in {'RUNNING','COMPLETED'}:C.need(exit_code=='0:0','RUNNING_OR_COMPLETED_PARENT_ZERO_EXIT')
    return state

def metadata_bind(plan,allowed_owner='EARLY_MAIN'):
    C.need(allowed_owner in ('EARLY_MAIN','ALPHA'),'ONLY_EXPLICIT_MAIN_OR_ALPHA_EXCLUSIVE_COMPONENT_OWNER')
    review_ref=plan['shared_preparation_root_acceptance_reference'];r=C.meta(review_ref)
    C.need(r['schema']==SCHEMA and r['status']==STATUS and r['reviewer']=='root'
      and r['parent_C0_claimed']is False and r['hash_workers_closed_claimed']is False,'TRUTHFUL_CURRENT_PARENT_COMPONENT_NOT_C0_OR_WORKER_CLOSE')
    a=r['prepare_parent_registration'];req,sub,proof,prior=[C.meta(a[k])for k in ('request_reference','submission_reference','proof_reference','plan_reference')]
    C.need(req==sub['request']==proof['request'] and sub['request_reference']==proof['request_reference']==a['request_reference']
      and sub['sbatch_returncode']==0 and sub['uid']==proof['uid']==1278 and str(sub['job_id'])==str(proof['job_id'])
      and req['scope_key']=='pprime_formal_shared_pairs_prepare_v3' and req['cpus']==16 and req['node']==prior['node']
      and prior['mode']=='SHARED_PREPARE' and req['execution_argv']==[C.Q.PY,'-B','-m',Prep.MODULE,'--plan',a['plan_reference']['path'],
        '--startup-proof',a['proof_reference']['path']]and a['plan_reference']in req['source_references'],'ACTUAL_REGISTERED_PREPARATION_PARENT_FULLARGV_SOURCE')
    observation=C.meta(r['prepare_parent_observation_reference'])
    observed_state=observed_parent_state(observation['state'],observation.get('exit_code','0:0'))
    C.need(observation['job_id']==str(proof['job_id']) and observation['uid']==1278 and observation['node']==req['node']
      and observation['state']==observed_state and observation['request_reference']==a['request_reference']
      and observation['proof_reference']==a['proof_reference'] and observation['query_returncode']==0,
      'ACTUAL_PARENT_STATE_SNAPSHOT_NOT_WHOLE_PARENT_ACCEPTANCE')
    rawref=observation['raw_reference'];C.need(0<rawref['bytes']<=2<<20 and C.Q.pin(rawref['path'])==rawref,'EXACT_SMALL_ACTUAL_PARENT_OBSERVATION_RAW')
    rows=[x for x in csv.DictReader(io.StringIO(pathlib.Path(rawref['path']).read_text()),delimiter='|')if x['JobIDRaw']==str(proof['job_id'])]
    C.need(len(rows)==1 and rows[0]['State']==observed_state and rows[0]['ExitCode']==observation.get('exit_code','0:0')and rows[0]['UID']=='1278'and int(rows[0]['AllocCPUS'])==16
      and rows[0]['NodeList']==req['node'],'ACTUAL_PREP_PARENT_SLURM_STATE_EXIT_ROW_NOT_SELF_DECLARED_C0')
    fixture_ref=r['actual_source3_reference'];fixture=C.meta(fixture_ref)
    C.need(pathlib.Path(fixture_ref['path'])==pathlib.Path(prior['output_directory'])/'source3.json' and fixture['tests_run']==3
      and all(fixture[k]==0 for k in ('failures','errors','skips','expected_failures','unexpected_successes')),'REAL_SAME_PREP_PARENT_SOURCE3')
    for name in Prep.FILES:C.need(C.Q.pin(Prep.HERE/name)in req['source_references'],'EXACT_ACTUAL_LIVE_PREP_SOURCE_NOT_HOTPATCHED')
    href=plan['prepared_shard_header_reference'];h=C.meta(href);p=pathlib.Path(href['path'])
    C.need(p.parent==pathlib.Path(prior['output_directory']) and re.fullmatch(r'prepared_shard_[0-9]{5}_header.json',p.name)
      and h['schema']==HEADER and 0<h['records']<=C.MAX_RECORDS and h['native_invokes']==0 and h['production_once_written']is False
      and h['native_physical_IDs_and_original_first2_input_hashes_verified']is True and h['final_Common_or_training_admission']is False
      and h['shared_prepare_plan_reference']==a['plan_reference']and h['shared_prepare_proof_reference']==a['proof_reference']
      and h['generation_shard_header_reference']in prior['generation_shard_header_references']
      and h['original_protocol_reference']==plan['original_protocol_reference']and h['source_context_reference']==plan['source_context_reference'],
      'EXACT_ATOMIC_COMPLETE_SINGLE_SHARD_HEADER_NOT_PARTIAL_OR_OTHER_PARENT')
    assignment_ref=r['external_assignment_reference'];assignment=C.meta(assignment_ref)
    shard=C.meta(h['generation_shard_header_reference'])['shard_id']
    C.need(assignment['schema']==ASSIGNMENT and assignment['status']=='EXCLUSIVE_COMPONENT_SLOT_ASSIGNED_WITHOUT_NATIVE_RETRY'
      and assignment['reviewer']=='root' and assignment['owner']==allowed_owner and assignment['shard_id']==shard
      and assignment['prepared_shard_header_reference']==href and assignment['generation_shard_header_reference']==h['generation_shard_header_reference']
      and assignment['operator_state_path']==str(OPROOT/'state.json') and assignment['operator_native_lock']==str(NATIVE_LOCK)
      and assignment['central_serialization_lock']==str(SERIAL) and assignment['old_operator_not_live_during_state_edit']is True
      and assignment['state_status']=='EXTERNALLY_ASSIGNED_CURRENT_CLOSED_COMPONENT'
      and assignment['physical_once_ledger']==str(C.ledger(plan)) and assignment['no_whole_shard_physical_preclaim']is True,
      'ROOT_EXPLICIT_EXCLUSIVE_OPERATOR_SLOT_HANDOFF_NOT_CONCURRENT_LIVE_STATE_EDIT')
    snapshot=C.meta(assignment['immutable_state_after_snapshot_reference']);entry=snapshot['shards'][shard]
    C.need(entry['status']==assignment['state_status'] and entry['header_reference']==href and entry['assignment_owner']==allowed_owner,
      'IMMUTABLE_EXACT_OPERATOR_STATE_HANDOFF_SNAPSHOT_NOT_CURRENT_MUTABLE_STATE_READ')
    src=[review_ref,*a.values(),r['prepare_parent_observation_reference'],observation['raw_reference'],fixture_ref,assignment_ref,
      assignment['immutable_state_after_snapshot_reference'],prior['shared_pool_root_review_reference'],href,h['audit_membership_reference'],h['pilot_reuse_reference'],h['publication_manifest_reference']]
    data=[C.P.triple(h[k])for k in ('index_reference','source_audit_reference','audit_selected_reference')]
    return h,C.unique(src),C.unique(data)

def validate_hashes(pair,value,task_names):
    C.need(value['record_id']==pair['record_id'] and value['original_pair_sha256']==hashlib.sha256(C.O.canonical(pair)).hexdigest()
      and re.fullmatch('[0-9a-f]{64}',value['geometry_sha256'])and type(value['hashes'])is list and len(value['hashes'])==12,
      'ORIGINAL_RECORD_PAIR_SHA_GEOMETRY_AND_ALL12_INPUT_HASHES')
    C.need([x['task']for x in value['hashes']]==task_names,'SAME_ORIGINAL_TASK_ORDER_NO_RECIPE_CHANGE')
    for task in value['hashes']:
        a=task['original_input_file_sha256'];b=task['candidate_input_file_sha256']
        C.need(a==b and a and len({x['name']for x in a})==len(a)and all(type(x['name'])is str and pathlib.PurePosixPath(x['name']).name==x['name']
          and re.fullmatch('[0-9a-f]{64}',x['sha256'])for x in a),'EXACT_ORIGINAL_INPUT_FILE_HASH_RECORDS_NO_WARMSTART_OR_VERSION_CHANGE')

def verify_component(plan,proof,budget,allowed_owner='EARLY_MAIN'):
    """CPU only, before Native/export. Never read active prepare DB/local scratch."""
    import duckdb
    h,src,data=metadata_bind(plan,allowed_owner);review=C.meta(plan['shared_preparation_root_acceptance_reference'])
    C.need(proof['uid']==1278 and proof['request']['cpus']==16 and all(r in proof['request']['data_references']for r in data)
      and all(r in proof['request']['source_references']for r in (plan['prepared_shard_header_reference'],plan['shared_preparation_root_acceptance_reference'])),
      'ACTUAL_CALLER_DATA_SOURCE_DECLARATIONS_UID_CPU_NOT_FAKE_QM_OR_COMPONENT_PARENT_PROOF')
    href=plan['prepared_shard_header_reference'];root=pathlib.Path(C.meta(h['shared_prepare_plan_reference'])['output_directory'])
    C.need(I.pin(href['path'],[root])==href,'WHOLE_STABLE_ATOMIC_HEADER_SHA')
    # Frozen source PREP pool and this caller's EXEC publication epoch may differ.
    # The header binds the actual original preparation plan; do not substitute
    # a new executor's pool authority for already committed source bytes.
    prep_pool_reference=C.meta(h['shared_prepare_plan_reference'])['shared_pool_root_review_reference']
    pool_spec=C.meta(prep_pool_reference)['pools']['PREP'];pool_root=pathlib.Path(pool_spec['root'])
    C.need(pool_root.is_dir()and(pool_root/'pool.lock').is_file()and(pool_root/'pool_state.json').is_file(),'EXISTING_ACTUAL_PREP_POOL_ONLY_NO_NEW_OLD_ROOT')
    pool=U.Pool(prep_pool_reference,'PREP');mr=h['publication_manifest_reference']
    C.need(I.pin(mr['path'],[pool.root])==mr,'WHOLE_STABLE_CLOSED_PUBLICATION_MAP_SHA');m=json.loads(I.body(mr,[mr],budget))
    C.need(m['schema']=='PPRIME_BYTE_IDENTICAL_LOCAL_TO_SHARED_PUBLICATION_V2' and m['kind']=='PREP'and m['all_file_SHA_bytes_equal']is True
      and str(m['actual_origin_job_id'])==str(C.meta(h['shared_prepare_proof_reference'])['job_id'])and m['pool_reference']==pool.reference,
      'REAL_PREPARATION_ATOMIC_PUBLISHED_BUNDLE_SAME_PARENT')
    token=m['pool_token']
    with pool.lock.open('a+b')as lock:
        fcntl.flock(lock,fcntl.LOCK_SH);state=C.meta(C.Q.pin(pool.state))
    C.need(state['tokens'][token]['status']=='COMMITTED_BYTE_VERIFIED'and state['tokens'][token]['identity']==m['identity']
      and pathlib.Path(mr['path']).parent==pool.root/('bundle_'+token),'ONLY_COMMITTED_IMMUTABLE_POOL_TOKEN_NOT_PARTIAL_RESERVED_UNKNOWN')
    targets=[]
    for row in m['entries']:
        budget.check();ref=row['target_reference'];C.need(ref['bytes']==row['origin_reference']['bytes']and ref['sha256']==row['origin_reference']['sha256']
          and I.pin(ref['path'],[pool.root/('bundle_'+token)])==ref,'INDEPENDENT_CPU_WHOLE_FILE_SHA_AND_STABLE_SAME_FD_READBACK')
        targets.append(ref)
    C.need(h['index_reference']in targets and h['source_audit_reference']in targets and h['audit_selected_reference']in targets,
      'ALL_REQUIRED_PREPARED_DATA_EXACT_PUBLISHED_TARGETS')
    for key in ('audit_membership_reference','pilot_reuse_reference'):
        ref=h[key];C.need(I.pin(ref['path'],[root,pool.root])==ref,'WHOLE_CLOSED_HEADER_SIDECAR_SHA')
    path=pathlib.Path(h['index_reference']['path']);frame=I.stamp(path.lstat());db=duckdb.connect(str(path),read_only=True);count=0;mids=set()
    protocol=C.meta(plan['original_protocol_reference']);tasks=[t['name']for t in protocol['tasks']]
    try:
        C.need([(v[0],v[1])for v in db.execute('DESCRIBE pairs').fetchall()]==[('rid','VARCHAR'),('mid','VARCHAR'),('rank','BIGINT'),('pair','BLOB'),('hashes','BLOB')],'EXACT_ORIGINAL_CLOSED_PAIRS_TABLE_NO_ACTIVE_LOCAL_DB')
        cursor=db.execute('SELECT rid,mid,rank,pair,hashes FROM pairs ORDER BY mid,rank')
        while rows:=cursor.fetchmany(128):
            budget.check()
            for rid,mid,rank,pair,hashed in rows:
                p=json.loads(bytes(pair));v=json.loads(bytes(hashed));C.need(p['record_id']==rid and p['molecule_id']==mid and type(rank)is int and rank in (0,1) and p['random_order_rank']==rank,
                  'ORIGINAL_PHYSICAL_RECORD_AND_FIXED_FIRST2_RANK')
                validate_hashes(p,v,tasks);count+=1;mids.add(mid)
        C.need(count==h['records']and len(mids)==h['MIDs'],'EXACT_COMPONENT_RECORD_AND_MID_CENSUS')
    finally:db.close();C.need(I.stamp(path.lstat())==frame,'READONLY_IMMUTABLE_PUBLISHED_INDEX_FRAME_UNCHANGED')
    return {'schema':'CURRENT_PARENT_CLOSED_PREPARED_COMPONENT_CPU_QA_V1','status':'WHOLE_CLOSED_COMPONENT_VERIFIED_NOT_PREP_PARENT_C0',
      'prepared_shard_header_reference':href,'publication_manifest_reference':mr,'component_root_review_reference':plan['shared_preparation_root_acceptance_reference'],
      'external_assignment_reference':review['external_assignment_reference'],'records':count,'MIDs':len(mids),'new_actual_CPU_job_id':str(proof['job_id']),
      'prep_parent_C0_claimed':False,'prep_hash_workers_closed_claimed':False,'new_QM_or_input_render_calls':0}
