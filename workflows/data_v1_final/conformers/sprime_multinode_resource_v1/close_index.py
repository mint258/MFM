"""Read-only CPU terminal classification and exact global consumption index."""
from __future__ import annotations
import json,pathlib
from . import contract as C,runtime_io as R


def terminal_batch(descriptor,config_reference,value,proof):
    # All descriptor references are real Root-collected metadata after terminal;
    # deterministic output paths are derived from its registered exact request.
    required=[descriptor[k] for k in ('plan','prepared','request','submission','accounting')]
    R.authorized(proof,required)
    plan=C.read(descriptor['plan']);prepared=C.read(descriptor['prepared']);request=C.read(descriptor['request']);sub=C.read(descriptor['submission'])
    jid=str(sub['job_id']);parents=C.accounting(descriptor['accounting'],[jid])
    C.need(sub['schema']=='CPU_AUTO_MEMORY_SUBMISSION_V1' and sub['sbatch_returncode']==0 and sub['request']==request,
        'REAL_REGISTERED_SUCCESSFUL_SUBMISSION_REQUIRED')
    C.need(plan['schema']==C.SCHEMAS['plan'] and plan['config']==prepared['config']==config_reference
        and prepared['plan']==descriptor['plan'] and request['scope_key'] in {'sprime_formal_cpu_auto_v3_run','sprime_multinode_resource_v1_run'}
        and request['scope_parameters']==C.scope('run',config_reference) and request['pilot'] is False
        and request['kind']=='conformer','EXACT_REGISTERED_V3_RUN_PLAN_AND_SCOPE_REQUIRED')
    R.authorized(proof,[plan['draft'],plan['root_review'],prepared['tasks']])
    C.approve_wave(plan['draft'],C.read(plan['draft']),plan['root_review'],config_reference)
    slots=[slot for slot in plan['jobs'] if slot['job_name']==request['job_name']]
    C.need(len(slots)==1,'REGISTERED_REQUEST_NOT_IN_ROOT_WAVE');slot=slots[0]
    out=pathlib.Path(slot['output_root']);C.need(C.BASE in out.parents and '..' not in out.parts
        and not any(p.is_symlink() for p in (out,*out.parents)) and R.validate_terminal_resource(descriptor,request,slot)
        and request['cpus']==slot['cpus']==16 and request['wall_seconds']==slot['wall_seconds'],'ACTUAL_SLOT_RESOURCE_BINDING_CHANGED')
    argv=request['execution_argv'];code=R.terminal_primary(request)
    C.need(argv[:3]==[R.PY,'-B',code] and argv[-2:]==['--output',str(out)]
        and argv[3:5]==['--config',config_reference['path']] and argv[5:7]==['--prepared',descriptor['prepared']['path']]
        and C.ref(code) in request['source_references'],'ACTUAL_PRIMARY_FULL_INPUT_OUTPUT_AND_SOURCE_BINDING_REQUIRED')
    C.need(len(argv)==13 and argv[7]=='--root-preflight' and argv[9]=='--quota-reuse-review',
        'EXACT_RUN_COMPLETE_OPTION_CHAIN_REQUIRED')
    with C.pinned(prepared['tasks'],C.CAP).open() as stream:tasks=[json.loads(line) for line in stream]
    C.need(len(tasks)==prepared['molecules'] and len({t['meta']['task_key'] for t in tasks})==len(tasks),'EXACT_PREPARED_TASK_SET_REQUIRED')
    expected={t['meta']['task_key']:t for t in tasks};packets=list((out/'packets').glob('*.json.gz')) if (out/'packets').exists() else []
    C.need({p.name[:-8] for p in packets}<=set(expected),'UNEXPECTED_PACKET_OUTSIDE_FROZEN_BATCH')
    outcomes=[];unstarted=[];errors=[];external=[]
    for key,task in expected.items():
        meta=task['meta'];ledger=C.ledger_path(key);dispatch_path=out/'dispatch'/(key+'.json');packet_path=out/'packets'/(key+'.json.gz')
        start_path=out/'starts'/(key+'.json');error_path=out/'errors'/(key+'.json')
        if not ledger.exists():
            C.need(not any(p.exists() for p in (dispatch_path,packet_path,start_path,error_path)),'OUTPUT_WITHOUT_CANONICAL_DISPATCH_LEDGER')
            unstarted.append(meta);continue # source guarantees durable ledger BEFORE submit
        ledger_reference=C.ref(ledger);dispatch=C.read(ledger_reference)
        C.need(dispatch.get('task_key')==key and dispatch.get('molecule_id')==meta['molecule_id'],'CONFLICTING_LEDGER_IDENTITY')
        if dispatch.get('job_id')!=jid:
            external.append({'task_key':key,'molecule_id':meta['molecule_id'],'ledger_reference':ledger_reference,
                'owner_job_id':dispatch.get('job_id'),'status':'ALREADY_CONSUMED_ELSEWHERE_NOT_UNSTARTED'})
            continue
        C.need(dispatch['schema']=='SPRIME_DISPATCH_INTENT_V3' and dispatch['task_sha256']==C.sha_value(task)
            and dispatch['prepared_reference']==descriptor['prepared'] and dispatch['plan_reference']==descriptor['plan'],
            'OWN_TASK_PLAN_PREPARED_DISPATCH_BINDING_CHANGED')
        outcome={'molecule_id':meta['molecule_id'],'task_key':key,'cohort':meta['cohort'],'expected_conformers':meta['expected_conformers'],
            'seed':dispatch['seed'],'task_sha256':dispatch['task_sha256'],'ledger_reference':ledger_reference,'owner_job_id':jid,
            'package_reference':None,'science_result_observed':False,'scientific_status':None,
            'execution_resolution':'EXECUTION_UNRESOLVED','worker_started':start_path.exists(),
            'start_reference':C.ref(start_path) if start_path.exists() else None,'failure_metadata_reference':C.ref(error_path) if error_path.exists() else None}
        if packet_path.exists():
            try:
                reference=dict(C.ref(packet_path),molecule_id=meta['molecule_id']);packet=R.read_packet(reference,value)
                start=packet.get('formal_start')
                C.need(start_path.exists() and C.read(C.ref(start_path))==start and start['dispatch_reference']==ledger_reference
                    and start['task_sha256']==dispatch['task_sha256'] and start['job_id']==jid
                    and packet['summary']['molecule_id']==meta['molecule_id'] and packet['summary']['seed']==dispatch['seed'],
                    'DURABLE_PACKAGE_SOURCE_TASK_AND_REAL_WORKER_BINDING_INVALID')
                outcome.update(package_reference=reference,science_result_observed=True,scientific_status=packet['summary']['status'],
                    execution_resolution='DURABLE_PACKAGE_VALIDATED')
            except Exception as exc:errors.append({'task_key':key,'error':repr(exc),'execution_resolution':'INVALID_PACKET_REMAINS_CONSUMED_UNKNOWN'})
        outcomes.append(outcome)
    C.need(len(outcomes)+len(unstarted)+len(external)==len(tasks),'TERMINAL_CLASSIFICATION_MUST_CONSERVE_ALL_PREPARED_TASKS')
    import pyarrow as pa
    unstarted_ref=R.write_parquet_new(R.OUT/'unstarted_metas.parquet',pa.Table.from_pylist(unstarted) if unstarted else pa.table({
        'molecule_id':pa.array([],type=pa.string()),'task_key':pa.array([],type=pa.string())}))
    outcomes_ref=R.write_json_new(R.OUT/'terminal_outcomes.json',outcomes)
    result={'schema':'SPRIME_FORMAL_CPU_CLOSED_BATCH_V3','status':'ACTUAL_TERMINAL_BATCH_CLASSIFIED','batch_id':slot['batch_id'],
        'plan':descriptor['plan'],'prepared':descriptor['prepared'],'request':descriptor['request'],'submission':descriptor['submission'],
        'accounting':descriptor['accounting'],'actual_parent_job_id':jid,'actual_parent':parents[jid],
        'terminal_outcomes':outcomes_ref,'unstarted_metas':unstarted_ref,'unstarted_count':len(unstarted),
        'consumed_outcomes':len(outcomes),'valid_packets':sum(r['science_result_observed'] for r in outcomes),
        'execution_unresolved':sum(not r['science_result_observed'] for r in outcomes),'consumed_elsewhere':external,'errors':errors,
        'parent_TIMEOUT_does_not_discard_valid_packets':True,'parent_C0_does_not_prove_scientific_success':True,
        'requested_allocation_core_seconds_ceiling':slot['cpus']*slot['wall_seconds'],
        'actual_allocated_core_seconds':int(parents[jid]['alloc_cpus'])*int(parents[jid]['elapsed_raw_seconds']),
        'actual_elapsed_minus_requested_wall_seconds':int(parents[jid]['elapsed_raw_seconds'])-slot['wall_seconds'],
        'difference_is_reported_not_assumed_to_be_cleanup':True,'request_ceiling_is_not_actual_cost_guarantee':True,
        'automatic_retry':False,'common_frozen':False}
    R.write_json_new(R.OUT/'closed_batch.json',result)


def completion(catalog,config_reference,value,proof):
    root_draft_ref=catalog['root_draft'];R.authorized(proof,[root_draft_ref]);draft=C.read(root_draft_ref)
    C.need(draft['schema']==C.SCHEMAS['draft'] and draft['config']==config_reference,'ORIGINAL_ROOT_CENSUS_DRAFT_REQUIRED')
    R.authorized(proof,[draft['pilot_imports'],draft['original_deficits'],draft['pilot_review']])
    review,_,historical=C.pilot_review(draft['pilot_review']);imports=C.read(draft['pilot_imports']);rows={}
    required_parents=set(historical)|{draft['runtime']['job_id']};accounted=dict(historical);seen_jobs=set()
    for imported in imports:
        key=imported['task_key'];ledger=C.ledger_path(key);C.need(C.read(C.ref(ledger))==imported,'HISTORICAL_IMPORT_LEDGER_CHANGED')
        rows[key]={**imported,'ledger_reference':C.ref(ledger),'owner_job_id':None}
    for reference in catalog['batch_closures']:
        R.authorized(proof,[reference]);closed=C.read(reference)
        C.need(closed['schema']=='SPRIME_FORMAL_CPU_CLOSED_BATCH_V3' and closed['status']=='ACTUAL_TERMINAL_BATCH_CLASSIFIED',
            'ONLY_ACTUAL_CLOSED_BATCHES_ALLOWED')
        jid=closed['actual_parent_job_id'];C.need(jid not in seen_jobs,'DUPLICATE_BATCH_PARENT_CLOSURE');seen_jobs.add(jid)
        required_parents.add(jid);parents=C.accounting(closed['accounting'],[jid])
        for other,row in parents.items():
            C.need(other not in accounted or accounted[other]==row,'CONFLICTING_ACTUAL_PARENT_ACCOUNTING');accounted[other]=row
        plan=C.read(closed['plan']);C.need(plan['root_draft']==root_draft_ref and plan['config']==config_reference,'CLOSED_BATCH_OUTSIDE_THIS_CENSUS_LINEAGE')
        prepared=C.read(closed['prepared']);required_parents.add(prepared['runtime']['job_id']);required_parents.add(plan['runtime']['job_id'])
        R.authorized(proof,[closed['terminal_outcomes']]);outcomes=C.read(closed['terminal_outcomes'])
        for row in outcomes:
            key=row['task_key'];C.need(key not in rows,'MORE_THAN_ONE_CONSUMED_OUTCOME_FOR_ORIGINAL_DEFICIT');rows[key]=row
        for row in closed['consumed_elsewhere']:
            if row['owner_job_id'] is not None:required_parents.add(str(row['owner_job_id']))
    for reference in catalog['additional_accounting']:
        R.authorized(proof,[reference]);parents=C.accounting(reference)
        for jid,row in parents.items():
            C.need(jid not in accounted or accounted[jid]==row,'CONFLICTING_RELATED_PARENT_ACCOUNTING');accounted[jid]=row
    cost_review=C.read(catalog['related_parent_root_review'])
    C.need(cost_review['schema']=='SPRIME_RELATED_PARENT_ACCOUNTING_ROOT_REVIEW_V3' and cost_review['reviewer']=='root'
        and cost_review['status']=='CURRENT_TERMINAL_RELATED_PARENT_SET_REVIEWED'
        and required_parents<=set(cost_review['related_parent_ids'])==set(accounted)
        and cost_review['complete_owned_master_reviewed'] is True and cost_review['all_related_known_terminal_parents_included'] is True,
        'ROOT_COMPLETE_OWNED_LEDGER_CLASSIFICATION_AND_ALL_ENCOUNTERED_PARENT_COST_REQUIRED')
    # Every parent in the independent complete owned master needs an explicit
    # Root classification; deleting the same parent from two cost lists cannot
    # silently satisfy this check. Names and missing argv never imply unrelated.
    master=C.read(cost_review['owned_master_reference']);C.need(master['query_returncode']==0,'ACTUAL_OWNED_MASTER_REQUIRED')
    C.pinned(master['raw_sacct_reference'],8<<20)
    master_rows={str(row['JobIDRaw']):row for row in master['actual_parents']}
    classified={str(row['job_id']):row for row in cost_review['parent_classifications']}
    C.need(len(master_rows)==len(master['actual_parents']) and len(classified)==len(cost_review['parent_classifications'])
        and set(classified)==set(master_rows),'EVERY_COMPLETE_OWNED_MASTER_PARENT_REQUIRES_ROOT_CLASSIFICATION')
    terminal_related=set()
    for jid,classification in classified.items():
        C.need(classification['decision'] in {'RELATED_TERMINAL','RELATED_ACTIVE_APPEND_PENDING','UNRELATED_ROOT_REVIEWED'}
            and isinstance(classification['reason'],str) and classification['reason'],'NO_UNKNOWN_OR_NAME_FALLBACK_COST_CLASSIFICATION')
        if classification['decision']=='RELATED_TERMINAL':terminal_related.add(jid)
    C.need(terminal_related==set(accounted),'RELATED_TERMINAL_COST_SET_MUST_EQUAL_COMPLETE_MASTER_ROOT_CLASSIFICATION')
    for jid,row in accounted.items():
        actual=master_rows[jid]
        C.need(actual['State'].split()[0]==row['state'] and actual['ExitCode']==row['exit_code']
            and int(actual['AllocCPUS'])==int(row['alloc_cpus']) and int(actual['ElapsedRaw'])==int(row['elapsed_raw_seconds']),
            'RELATED_ACTUAL_COST_MUST_MATCH_INDEPENDENT_OWNED_MASTER')
    import pyarrow.parquet as pq
    original=pq.read_table(C.pinned(draft['original_deficits'])).to_pylist()
    expected_metas={r['task_key']:r for r in original if r['cohort']!='unsupported'};expected=set(expected_metas)
    C.need(len(expected)==90069 and set(rows)<=expected,'CONSUMED_OUTCOME_OUTSIDE_ORIGINAL_NON_UNSUPPORTED_POPULATION')
    for key,row in rows.items():
        meta=expected_metas[key]
        C.need(row['molecule_id']==meta['molecule_id'] and row['cohort']==meta['cohort']
            and row['expected_conformers']==meta['expected_conformers']
            and row['seed']==C.seed_for(meta['molecule_id'],meta['cohort']=='retry_once'),
            'GLOBAL_OUTCOME_MOLECULE_COHORT_N_SEED_MUST_MATCH_ORIGINAL_CENSUS')
        C.need(C.ref(C.ledger_path(key))==C.triple(row['ledger_reference']),'ACTUAL_ONCE_LEDGER_CHANGED_AFTER_CLOSE')
        C.need((row['science_result_observed'] is True and row['package_reference'] is not None and isinstance(row['scientific_status'],str))
            or (row['science_result_observed'] is False and row['package_reference'] is None and row['scientific_status'] is None),
            'PACKAGES_AND_UNKNOWN_MUST_REMAIN_DISJOINT_WITH_HONEST_SCIENTIFIC_STATUS')
    complete=set(rows)==expected;outcomes_ref=R.write_json_new(R.OUT/'all_consumed_outcomes.json',list(rows.values()))
    result={'schema':C.SCHEMAS['completion'],'status':'ALL_SPRIME_ATTEMPTS_TERMINAL' if complete else 'INCOMPLETE_NO_FINALIZATION',
        'config':config_reference,'root_draft':root_draft_ref,'pilot_imports':draft['pilot_imports'],'outcomes':outcomes_ref,
        'batch_closures':catalog['batch_closures'],'related_parent_root_review':catalog['related_parent_root_review'],
        'actual_parent_rows':accounted,'actual_accounted_core_seconds':sum(int(r['alloc_cpus'])*int(r['elapsed_raw_seconds']) for r in accounted.values()),
        'actual_cost_is_reviewed_point_in_time_not_final_pipeline_total':True,'this_and_later_stage_actual_cost_append_pending':True,
        'expected_deficits':90069,'consumed_count':len(rows),'missing_count':len(expected-set(rows)),
        'valid_packages':sum(r['science_result_observed'] for r in rows.values()),'execution_unresolved':sum(not r['science_result_observed'] for r in rows.values()),
        'full_forecast_status':C.FORECAST,'estimated_full_core_hours':None,'cost_policy':'REPORT_AND_CONTINUE','common_frozen':False}
    R.write_json_new(R.OUT/'completion_index.json',result)
