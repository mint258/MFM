"""Same closed-byte component verification; only scoped source admission differs."""
import csv,io,json,pathlib,types
from . import contract as C
from workflows.data_v1_final.pprime.current_prepared_component_parentstate_v3 import authority as Original


def metadata_bind(plan,allowed_owner='EARLY_MAIN'):
    r=C.meta(plan['shared_preparation_root_acceptance_reference']);a=r['prepare_parent_registration']
    C.need(r['schema']==Original.SCHEMA and r['status']==Original.STATUS and r['reviewer']=='root' and r['parent_C0_claimed']is False and r['hash_workers_closed_claimed']is False,'SAME_TRUTHFUL_CLOSED_COMPONENT_ADMINISTRATIVE_HANDOFF')
    req,proof,prior=[C.meta(a[k])for k in ('request_reference','proof_reference','plan_reference')]
    submission=C.meta(a['submission_reference'])
    C.need(submission['request']==req and submission['request_reference']==a['request_reference'] and submission['sbatch_returncode']==0 and submission['uid']==1278
      and str(submission['job_id'])==str(proof['job_id']),'REAL_REGISTERED_PREPARATION_SUBMISSION')
    C.need(req==proof['request'] and proof['request_reference']==a['request_reference'] and proof['uid']==1278
      and req['cpus']==16 and req['scope_key']==C.MODES['SHARED_PREPARE'] and prior['mode']=='SHARED_PREPARE'
      and a['plan_reference']in req['source_references'],'ACTUAL_FILL_PREPARATION_PARENT_NOT_LEGACY_READY_PARENT')
    C.need(req['execution_argv']==[C.Q.PY,'-B','-m',C.MODULE,'--plan',a['plan_reference']['path'],'--startup-proof',a['proof_reference']['path']] and req['node']==prior['node'],'ACTUAL_PREPARATION_MODULE_AND_FULL_ARGV')
    C.need(prior['fill_source_authority_reference']==plan['fill_source_authority_reference'] and prior['original_protocol_reference']==plan['original_protocol_reference'],'SAME_FILL_SOURCE_AND_ORIGINAL_PROTOCOL')
    observation=C.meta(r['prepare_parent_observation_reference']);state=Original.observed_parent_state(observation['state'],observation['exit_code'])
    C.need(str(observation['job_id'])==str(proof['job_id']) and observation['uid']==1278 and observation['node']==req['node']
      and observation['request_reference']==a['request_reference'] and observation['proof_reference']==a['proof_reference'],'SAME_ACTUAL_PREPARATION_OBSERVATION')
    raw=C.Q.read_small(observation['raw_reference']['path']);ref=observation['raw_reference']
    C.need(len(raw)==ref['bytes'] and __import__('hashlib').sha256(raw).hexdigest()==ref['sha256'] and observation['query_returncode']==0,'REAL_PARENT_OBSERVATION_RAW')
    rows=[v for v in csv.DictReader(io.StringIO(raw.decode()),delimiter='|')if v['JobIDRaw']==str(proof['job_id'])]
    C.need(len(rows)==1 and rows[0]['State']==state and rows[0]['ExitCode']==observation['exit_code'] and rows[0]['UID']=='1278' and rows[0]['AllocCPUS']=='16' and rows[0]['NodeList']==req['node'],'EXACT_NATIVE_CURRENT_PREPARENT_ACCOUNTING')
    C.need(pathlib.Path(r['actual_source3_reference']['path'])==pathlib.Path(prior['output_directory'])/'source3.json','SAME_PREPARATION_SOURCE3')
    fixture=C.meta(r['actual_source3_reference'])
    C.need(fixture['tests_run']==3 and all(fixture[k]==0 for k in ('failures','errors','skips','expected_failures','unexpected_successes')),'SAME_ORIGINAL_THREE_SOURCE_CHECKS')
    for name in C.FILES:C.need(C.Q.pin(C.HERE/name)in req['source_references'],'ACTUAL_SOURCE_NOT_HOTPATCHED')
    href=plan['prepared_shard_header_reference'];h=C.meta(href);scope=C.meta(h['generation_partition_QA_reference']);generation=C.meta(h['generation_shard_header_reference'])
    C.need(pathlib.Path(href['path']).parent==pathlib.Path(prior['output_directory']) and __import__('re').fullmatch(r'prepared_shard_[0-9]{5}_header.json',pathlib.Path(href['path']).name),'EXACT_ATOMIC_PREPARED_HEADER_LOCATION')
    C.need(h['schema']=='PPRIME_CPU_CLOSED_ASSIGNED_PAIRS_HEADER_V2' and 0<h['records']<=C.MAX_RECORDS and h['native_invokes']==0 and h['production_once_written']is False
      and h['native_physical_IDs_and_original_first2_input_hashes_verified']is True and h['shared_prepare_plan_reference']==a['plan_reference'] and h['shared_prepare_proof_reference']==a['proof_reference'],
      'REAL_CLOSED_FILL_PAIRS_NOT_HEADER_RELABEL')
    C.need(scope['schema']=='PPRIME_FILL_FIXED_RANDOM_SCOPE_CLOSED_V1' and scope['original_ready_anti_join_performed'] and scope['complete_ordinary_order_before_first2']
      and not scope['uses_energy_or_diversity_D7'] and scope['old_parent_4525659_state']=='FAILED' and not scope['old_parent_upgraded']
      and str(scope['actual_job_id'])==str(proof['job_id']) and h['generation_shard_header_reference']in scope['component_references']
      and generation['scope_source_reference']==plan['fill_source_authority_reference'],'ACTUAL_CLOSED_SCOPED_FILL_ANTI_JOIN_AND_COMPLETE_ORDER')
    assignment_ref=r['external_assignment_reference'];assignment=C.meta(assignment_ref)
    C.need(assignment['owner']==allowed_owner and assignment['prepared_shard_header_reference']==href and assignment['generation_shard_header_reference']==h['generation_shard_header_reference']
      and assignment['physical_once_ledger']==str(C.ledger(plan)) and assignment['central_serialization_lock']==str(Original.SERIAL)
      and assignment['no_whole_shard_physical_preclaim']is True,'ACTUAL_EXCLUSIVE_CURRENT_COMPONENT_SAME_ONCE_LEDGER')
    C.need(h['original_protocol_reference']==plan['original_protocol_reference'] and h['source_context_reference']==plan['source_context_reference'],'SAME_ORIGINAL_INPUT_CONTEXT')
    src=[plan['shared_preparation_root_acceptance_reference'],*a.values(),r['prepare_parent_observation_reference'],observation['raw_reference'],r['actual_source3_reference'],href,
      assignment_ref,h['generation_partition_QA_reference'],h['generation_shard_header_reference'],h['audit_membership_reference'],h['pilot_reuse_reference'],h['publication_manifest_reference']]
    data=[C.P.triple(h[k])for k in ('index_reference','source_audit_reference','audit_selected_reference')]
    return h,C.unique(src),C.unique(data)


def verify_component(plan,proof,budget,allowed_owner='EARLY_MAIN'):
    old=Original.verify_component
    f=types.FunctionType(old.__code__,dict(old.__globals__,C=C,metadata_bind=metadata_bind),old.__name__,old.__defaults__,old.__closure__)
    f.__kwdefaults__=old.__kwdefaults__
    return f(plan,proof,budget,allowed_owner)