"""Read-only334 package +14control +2 unresolved closure; no generation or full release."""
from __future__ import annotations
import argparse,concurrent.futures as cf,hashlib,importlib.util,io,json,os,pathlib,re,socket,stat,sys,time,traceback,unittest
from collections import Counter
from model import need,terminal_rows,descriptive_strata,validate_cost_decision
sys.dont_write_bytecode=True
ROOT=pathlib.Path('/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025');REPO=ROOT/'repository'
CONFORMERS=REPO/'workflows/data_v1_final/conformers';HERE=pathlib.Path(__file__).absolute().parent
sys.path[:0]=[str(CONFORMERS/'recovery_v1'),str(CONFORMERS),str(REPO)]
from recovery_common import IO,MISSING,bind_inputs,load_plan,packet_reader,read_packet,scientific_sha,task_sha,expected_seed,require_sources
from workflows.data_v1_final.conformers.recovery_auto_memory_v1 import owned_costs as COST
from snapshot_costs import verify_snapshot
from workflows.data_v1_final.conformers.recovery_auto_memory_v1.resource_runtime import producer_argv,PARAMETERS
AUTO_OUTPUT=ROOT/'artifacts/conformers/recovery_v1/auto_memory_20261026_v2'
SCOPE_KEY='sprime_timeout_closure334plus2_snapshot_v2'
PARAMS={'original_job_id':'4520364','recovery_job_id':'4521110','original_tasks':336,'original_packages':334,
    'independent_same_seed_controls':14,'unresolved_after_timeout':2,'new_UFF_QM_calls':0,'new_seeds':0,'new_logical_retries':0,
    'test_methods':3,'fixtures_before_packet_bodies':True,
    'cost_basis':'ROOT_APPROVED_POINT_IN_TIME_SNAPSHOT','future_registry_scan':False}
OUTPUT_CAP=1024**3
COST_DECISION_PATH=REPO/'configs/data_v1/user_allocation_overrun_report_continue_20261026_v1.json'


def reference(path):return COST.ref(pathlib.Path(path).absolute())


def metadata(path):return json.loads(COST.read(pathlib.Path(path).absolute()))


def clean(value):return {key:value[key] for key in ('path','bytes','sha256')}


def identity(path):
    path=pathlib.Path(path);st=path.lstat()
    need(not path.is_symlink() and stat.S_ISREG(st.st_mode) and st.st_uid==1278,'OWNED_REGULAR_PACKAGE_REQUIRED')
    return {'device':st.st_dev,'inode':st.st_ino,'bytes':st.st_size,'mtime_ns':st.st_mtime_ns,'uid':st.st_uid}


def full_reference(path):
    path=pathlib.Path(path);before=identity(path);h=hashlib.sha256()
    with path.open('rb') as stream:
        a=os.fstat(stream.fileno())
        for block in iter(lambda:stream.read(1024**2),b''):h.update(block)
        b=os.fstat(stream.fileno())
    need((a.st_dev,a.st_ino,a.st_size,a.st_mtime_ns,a.st_uid)==(b.st_dev,b.st_ino,b.st_size,b.st_mtime_ns,b.st_uid)
        and identity(path)==before,'PACKAGE_CHANGED_DURING_FULL_SHA')
    return {'path':str(path),'bytes':before['bytes'],'sha256':h.hexdigest()},before


def check_packet(item,validator):
    role,mid,path,prior_ref,prior_identity,task=item
    ref,before=full_reference(path)
    if prior_ref is not None:need(ref==clean(prior_ref),'ORIGINAL_PACKAGE_FULL_SHA_CHANGED')
    if prior_identity is not None:need(before==prior_identity,'ORIGINAL_PACKAGE_FSTAT_IDENTITY_CHANGED')
    packet,detail=read_packet(dict(ref,molecule_id=mid),task,validator)
    need(identity(path)==before and packet['summary']['molecule_id']==mid
        and packet['summary']['seed']==expected_seed(task),'PACKAGE_POSTREAD_IDENTITY_OR_TASK_SEED_CHANGED')
    # read_packet reuses the original SHA, gzip EOF/CRC, native pointer, atom/geometry and task checks.
    return {'role':role,'molecule_id':mid,'package':packet,'detail':detail,'reference':dict(ref,molecule_id=mid),
        'file_identity_before_after':before,'gzip_complete_EOF_CRC_and_original_validator_passed':True,
        'original_task_sha256':task_sha(task),'seed':expected_seed(task),'scientific_sha256_excluding_summary_elapsed_seconds':scientific_sha(packet)}


def sample():
    available=next(int(line.split()[1])*1024 for line in pathlib.Path('/proc/meminfo').read_text().splitlines() if line.startswith('MemAvailable:'))
    rss=int(pathlib.Path('/proc/self/statm').read_text().split()[1])*os.sysconf('SC_PAGE_SIZE')
    return {'unix_seconds':time.time(),'self_RSS_bytes':rss,'MemAvailable_bytes':available}


def exact_stage(plan_path,binding_path,evidence_path):
    value=load_plan(plan_path,approved=True);binding=metadata(binding_path);evidence=metadata(evidence_path)
    need(binding['schema']=='SPRIME_AUTO_MEMORY_RECOVERY_RESOURCE_BINDING_V1'
        and binding['status']=='ROOT_APPROVED_FOR_EXACT_RECOVERY_RESOURCE_REPLACEMENT'
        and binding['historical_plan_reference']==reference(plan_path) and binding['output']==str(AUTO_OUTPUT)
        and binding['cpus']==16 and binding['memory_policy']=='SLURM_DEFAULT_UNSPECIFIED'
        and binding['slurm_memory_requested'] is False and 'memory_gib' not in binding,'EXACT_HISTORICAL_RESOURCE_REPLACEMENT_REQUIRED')
    need(evidence['schema']=='SPRIME_TIMEOUT_RECOVERY_STAGE_EVIDENCE_V1' and evidence['endpoint']=='202.38.247.57:22'
        and evidence['uid']==1278 and evidence['original_job_id']=='4520364' and evidence['recovery_job_id']=='4521110'
        and evidence['recovery_output_directory']==str(AUTO_OUTPUT)
        and evidence['worker_to_missing_mapping_status']=='NOT_DURABLY_RECORDED','ACTUAL_ROOT_TIMEOUT_STAGE_EVIDENCE_REQUIRED_NO_INVENTED_MAPPING')
    need(pathlib.Path(evidence['cost_decision_reference']['path'])==COST_DECISION_PATH,'EXACT_ACTUAL_USER_COST_DECISION_PATH_REQUIRED')
    cost_policy=validate_cost_decision(COST.load_pin(evidence['cost_decision_reference']))
    submission=COST.load_pin(evidence['recovery_submission_reference']);startup=COST.load_pin(evidence['recovery_startup_proof_reference'])
    need(str(submission['job_id'])==str(startup['job_id'])=='4521110' and submission['sbatch_returncode']==0
        and submission['uid']==startup['uid']==1278 and submission['request']==startup['request'],'EXACT_ACTUAL_RECOVERY_SUBMISSION_AND_STARTUP_REQUIRED')
    request=startup['request']
    need(request['kind']=='conformer' and request['scope_key']=='sprime_recovery_auto_memory_2plus14'
        and request['scope_parameters']==PARAMETERS and request['cpus']==16 and request['memory_policy']=='SLURM_DEFAULT_UNSPECIFIED'
        and 'memory_gib' not in request and request['execution_argv']==producer_argv(binding,binding_path,
            pathlib.Path(evidence['recovery_startup_proof_reference']['path'])),'ACTUAL_UNCHANGED2PLUS14_PRODUCER_SCOPE_REQUIRED')
    need(value['recipe_config'] in request['source_references'] and reference(binding_path) in request['source_references'],
        'HISTORICAL_RECIPE_AND_RESOURCE_BINDING_NOT_PINNED')
    for name in ('run_recovery_auto.py','resource_runtime.py','source_edits_v1.json'):
        need(reference(CONFORMERS/'recovery_auto_memory_v1'/name) in request['source_references'],'ACTUAL_RECOVERY_SOURCE_CHANGED:'+name)
    refs=evidence['stage_identity_evidence_references'];need(isinstance(refs,list) and refs,'ACTUAL_STAGE_IDENTITY_EVIDENCE_PINS_REQUIRED')
    for ref in refs:COST.verify(ref)
    return value,binding,evidence,startup,cost_policy


def observed_progress():
    need(AUTO_OUTPUT.is_dir() and not AUTO_OUTPUT.is_symlink(),'ACTUAL_RECOVERY_OUTPUT_DIRECTORY_REQUIRED')
    allowed={'controls','reproduction'}|{f'progress_{i:02d}_00.json' for i in range(1,15)}
    need({path.name for path in AUTO_OUTPUT.iterdir()}==allowed,'RECOVERY_TIMEOUT_DIRECTORY_SET_CHANGED_REAUDIT_REQUIRED')
    need(not list((AUTO_OUTPUT/'reproduction').iterdir()),'MISSING_PACKAGE_NOW_EXISTS_REAUDIT_REQUIRED')
    rows=[]
    for i in range(1,15):
        path=AUTO_OUTPUT/f'progress_{i:02d}_00.json';body=metadata(path)
        need(body['closed_physical_executions']==i and body['expected_physical_executions']==16
            and body['missing_original_tasks_closed']==0,'ACTUAL_PROGRESS_SCOPE_OR_MISSING_CLOSURE_CHANGED')
        rows.append({'reference':reference(path),'body':body})
    # Absence is observed explicitly; never synthesize these producer finalizations.
    need(all(not(AUTO_OUTPUT/name).exists() for name in ('physical_executions.json','errors.json','memory_evidence.json.gz','recovery_receipt.json')),
        'NEW_DURABLE_PRODUCER_FINALIZATION_REQUIRES_REVIEW')
    return rows


def argv_for(a):
    result=[sys.executable,'-B',str(HERE/'run_v1.py'),'--plan',str(a.plan),'--resource-binding',str(a.resource_binding),
        '--stage-evidence',str(a.stage_evidence),'--whole-owned-accounting',str(a.whole_owned_accounting),
        '--prior-related-cost-selection',str(a.prior_related_cost_selection)]
    if a.legacy_scope_classification is not None:result+=['--legacy-scope-classification',str(a.legacy_scope_classification)]
    return result+['--root-preflight',str(a.root_preflight),'--output',str(a.output)]


def main():
    started=time.monotonic()
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('plan','resource-binding','stage-evidence','whole-owned-accounting','prior-related-cost-selection','root-preflight','output'):p.add_argument('--'+name,type=pathlib.Path,required=True)
    p.add_argument('--legacy-scope-classification',type=pathlib.Path);a=p.parse_args()
    need(pathlib.Path(sys.modules['__main__'].__file__).absolute()==HERE/'run_v1.py' and pathlib.Path(sys.argv[0]).absolute()==HERE/'run_v1.py','ACTUAL_PRIMARY_ENTRY_REQUIRED')
    need(all(path.is_absolute() and '..' not in path.parts for path in (a.plan,a.resource_binding,a.stage_evidence,a.whole_owned_accounting,a.prior_related_cost_selection,a.root_preflight,a.output)),
        'ABSOLUTE_LITERAL_NEW_CLOSURE_ARGUMENTS_REQUIRED')
    preliminary=metadata(a.stage_evidence)
    required=[reference(path) for path in (a.plan,a.resource_binding,a.stage_evidence,a.whole_owned_accounting,a.prior_related_cost_selection)]
    required.extend(preliminary[key] for key in ('recovery_submission_reference','recovery_startup_proof_reference'))
    required.extend(preliminary['stage_identity_evidence_references'])
    required.append(preliminary['cost_decision_reference'])
    if a.legacy_scope_classification is not None:required.append(reference(a.legacy_scope_classification))
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2 import runtime as central
    proof=central.require_startup(a.root_preflight,expected_scope_key=SCOPE_KEY,expected_scope_parameters=PARAMS,
        expected_execution_argv=argv_for(a),expected_source=HERE/'run_v1.py',expected_kind='analysis',required_references=required)
    request=proof['request'];need(request['cpus']==16 and request.get('pilot') is False and request['memory_policy']=='SLURM_DEFAULT_UNSPECIFIED'
        and 'memory_gib' not in request and 0<request['wall_seconds']<=300 and request['estimated_peak_output_bytes']>=OUTPUT_CAP
        and proof['account_free_bytes']-request['estimated_peak_output_bytes']>=200000000000,'FINITE_CPU16_NO_MEMORY_CLOSURE_AND_QUOTA_REQUIRED')
    raw_job=proof['job_metadata']
    runtimes=re.findall(r'(?:^|\s)RunTime=([^\s]+)',raw_job) if isinstance(raw_job,str) else [raw_job['RunTime']]
    need(len(runtimes)==1,'ACTUAL_JOB_RUNTIME_REQUIRED')
    elapsed=runtimes[0];days=0
    if '-' in elapsed:day,elapsed=elapsed.split('-',1);days=int(day)
    hour,minute,second=map(int,elapsed.split(':'))
    need(0<=minute<60 and 0<=second<60 and hour>=0 and days>=0,'FINITE_SLURM_RUNTIME_REQUIRED')
    elapsed_at_start=days*86400+hour*3600+minute*60+second+max(0,time.time()-proof['memory_observation']['observed_unix_seconds'])
    dispatch_deadline=time.monotonic()+request['wall_seconds']-elapsed_at_start-45
    need(dispatch_deadline>time.monotonic(),'NO_REMAINING_WALL_FOR_NEW_PACKAGE_READS')
    require_sources(request['source_references'])
    for path in HERE.glob('*.py'):need(reference(path) in request['source_references'],'NEW_CLOSURE_SOURCE_NOT_PINNED:'+path.name)
    try:
        spec=importlib.util.spec_from_file_location('_timeout_closure_exact_three_synthetic',HERE/'test_v1.py')
        tests=importlib.util.module_from_spec(spec);spec.loader.exec_module(tests)
        suite=unittest.defaultTestLoader.loadTestsFromModule(tests);count=suite.countTestCases()
        print(json.dumps({'synthetic_methods_discovered':count,'packet_bodies_read':0}),flush=True)
        need(count==3,'EXACT_THREE_SYNTHETIC_METHODS_REQUIRED_BEFORE_PACKET_READS')
        transcript=io.StringIO();result=unittest.TextTestRunner(stream=transcript,verbosity=2).run(suite)
        fixture={'test_source':reference(HERE/'test_v1.py'),'test_methods':count,'tests_run':result.testsRun,
            'failures':len(result.failures),'errors':len(result.errors),'skips':len(result.skipped),
            'expected_failures':len(result.expectedFailures),'unexpected_successes':len(result.unexpectedSuccesses),
            'transcript':transcript.getvalue(),'executed_before_packet_bodies':True}
        print(json.dumps({'actual_synthetic_fixture_result':fixture}),flush=True)
        need(result.testsRun==3 and not(result.failures or result.errors or result.skipped or result.expectedFailures or result.unexpectedSuccesses),
            'SYNTHETIC_FIXTURE_FAILED_STOP_BEFORE_PACKET_BODIES')
    except Exception as exc:
        print(json.dumps({'status':'SYNTHETIC_FIXTURE_STOP_BEFORE_PACKET_BODIES','error':type(exc).__name__+': '+str(exc),'packet_bodies_read':0}),flush=True)
        raise
    os.environ.update({key:'1' for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','BLIS_NUM_THREADS')})
    value,binding,evidence,historical_startup,cost_policy=exact_stage(a.plan,a.resource_binding,a.stage_evidence)
    selection=verify_snapshot(reference(a.whole_owned_accounting),reference(a.prior_related_cost_selection),
        current_job_id=str(proof['job_id']),classification_ref=reference(a.legacy_scope_classification) if a.legacy_scope_classification is not None else None)
    need(not selection['unclassified_scope_parent_ids_for_root_review'],'APPROVED_SNAPSHOT_SCOPE_CLASSIFICATION_UNRESOLVED')
    parents={row['job_id']:row for row in selection['selected_parent_rows']}
    need(all(row['state'] in {'COMPLETED','FAILED','TIMEOUT','CANCELLED','OUT_OF_MEMORY','NODE_FAIL','PREEMPTED','BOOT_FAIL'} for row in parents.values()),
        'KNOWN_RELATED_PARENTS_IN_APPROVED_SNAPSHOT_MUST_BE_TERMINAL_AS_CAPTURED')
    for jid,elapsed in (('4520364',14425),('4521110',5409)):
        row=parents[jid];need(row['state']=='TIMEOUT' and row['elapsed_raw_seconds']==elapsed and row['alloc_cpus']==16,'ACTUAL_ORIGINAL_AND_RECOVERY_TIMEOUT_COST_REQUIRED:'+jid)
    preparation=parents['4520335'];need(preparation['elapsed_raw_seconds']==606 and preparation['alloc_cpus']==16 and preparation['allocated_core_seconds']==9696,
        'ACTUAL_PREPARATION606_SECONDS_MUST_NOT_DISAPPEAR')
    need(parents['4520527']['state']=='COMPLETED' and parents['4520527']['exit_code']=='0:0','ACTUAL_OLD_PARTIAL_AUDIT_REQUIRED')
    progress=observed_progress();audit,closed,tasks=bind_inputs(value)
    old_by_id={row['molecule_id']:row for row in closed};controls=value['replay_control_ids']
    expected_control_names={hashlib.sha256(mid.encode()).hexdigest()+'.json.gz' for mid in controls}
    need({path.name for path in (AUTO_OUTPUT/'controls').iterdir()}=={'reproduction'}
        and {path.name for path in (AUTO_OUTPUT/'controls/reproduction').iterdir()}==expected_control_names,'EXACT14_CONTROL_PACKAGE_NAMES_REQUIRED')
    validator=packet_reader();items=[]
    for mid,row in sorted(old_by_id.items()):items.append(('old',mid,pathlib.Path(row['reference']['path']),row['reference'],row['file_identity'],tasks[mid]))
    for mid in controls:items.append(('control',mid,AUTO_OUTPUT/'controls/reproduction'/(hashlib.sha256(mid.encode()).hexdigest()+'.json.gz'),None,None,tasks[mid]))
    need(len(items)==348,'334PLUS14_READ_SCOPE_REQUIRED')
    need(not a.output.exists() and ROOT/'artifacts/conformers/recovery_timeout_closure_v2' in a.output.parents
        and not any(path.is_symlink() for path in (a.output,*a.output.parents)),'NEW_SEPARATE_TIMEOUT_CLOSURE_OUTPUT_REQUIRED')
    IO.new_output_directory(a.output,{'external_output_root':str(ROOT/'artifacts/conformers/recovery_timeout_closure_v2'),'max_output_bytes':OUTPUT_CAP})
    active={};index=0;checked=[];errors=[];memory=[];stop=None
    with cf.ThreadPoolExecutor(max_workers=16) as pool:
        while active or index<len(items):
            try:
                row=sample()
                if len(memory)<1024:memory.append(row)
                if row['self_RSS_bytes']>8*1024**3 or row['MemAvailable_bytes']<4*1024**3:stop='ACTUAL_MEMORY_STOP_NEW_READS'
                if time.monotonic()>=dispatch_deadline:stop='FINITE_WALL_STOP_NEW_READS'
            except Exception as exc:stop='MEMORY_OBSERVATION_UNAVAILABLE:'+str(exc)
            while stop is None and not errors and index<len(items) and len(active)<16:
                active[pool.submit(check_packet,items[index],validator)]=items[index][1];index+=1
            if not active:break
            done,_=cf.wait(active,timeout=.5,return_when=cf.FIRST_COMPLETED)
            for future in done:
                mid=active.pop(future)
                try:checked.append(future.result())
                except Exception as exc:errors.append({'molecule_id':mid,'error':type(exc).__name__+': '+str(exc)})
    if len(checked)!=348 or errors:
        IO.write_json_new(a.output/'incomplete_read_audit.json',{'status':'INCOMPLETE_NO_JOINT_CLOSURE','verified_packages':len(checked),'errors':errors,
            'soft_stop':stop,'memory_samples':memory,'synthetic_fixture_result':fixture,'new_UFF_QM_calls':0,'formal_generation_authorized':False})
        return 3
    old={row['molecule_id']:row for row in checked if row['role']=='old'};replay={row['molecule_id']:row for row in checked if row['role']=='control'}
    need(set(old)==set(old_by_id) and set(replay)==set(controls),'ACTUAL_OLD_AND_CONTROL_SCOPE_CHANGED')
    control_report=[]
    for mid in controls:
        need(old[mid]['scientific_sha256_excluding_summary_elapsed_seconds']==replay[mid]['scientific_sha256_excluding_summary_elapsed_seconds'],
            'SAME_TASK_SEED_SCIENCE_DRIFT_EXCLUDING_ONLY_ELAPSED:'+mid)
        control_report.append({key:replay[mid][key] for key in replay[mid] if key!='package'})
    context={'original_parent':parents['4520364'],'recovery_parent':parents['4521110'],
        'actual_root_stage_evidence_reference':reference(a.stage_evidence),'progress_references':[row['reference'] for row in progress],
        'remaining_set_basis':'Original fixed2+14 scope minus14 verified same-seed control outputs; not a durable PID/task-phase mapping.',
        'original_task_body_reference':value['tasks_reference'],'producer_final_receipt_available':False,'producer_memory_closure_available':False}
    summaries={mid:row['package']['summary'] for mid,row in old.items()};refs={mid:row['reference'] for mid,row in old.items()}
    outcomes,failures=terminal_rows(tasks,summaries,refs,MISSING,context,task_sha,expected_seed)
    from run_pilot import parquet_new,verify_readback
    from statistics_tools import aggregate_statistics
    ordered=[old[mid]['package'] for mid in sorted(old)];geometries=sorted((row for packet in ordered for row in packet['conformers']),key=lambda row:(row['molecule_id'],row['sprime_conf_idx']))
    parquet_new(a.output/'validated_package_molecules334.parquet',[summaries[mid] for mid in sorted(summaries)])
    parquet_new(a.output/'validated_package_conformers334.parquet',geometries,coordinates=True)
    readback=verify_readback(a.output/'validated_package_conformers334.parquet',geometries)
    IO.write_json_new(a.output/'validated_package_references334.json',[refs[mid] for mid in sorted(refs)])
    IO.write_json_new(a.output/'terminal_outcomes336.json',outcomes)
    IO.write_json_new(a.output/'unresolved_after_timeout2.json',failures)
    IO.write_json_new(a.output/'scientific_success_packages.json',[refs[mid] for mid in sorted(refs) if summaries[mid]['status']=='SUCCESS'])
    IO.write_json_new(a.output/'scientific_failure_packages.json',[dict(reference=refs[mid],scientific_status=summaries[mid]['status']) for mid in sorted(refs) if summaries[mid]['status']!='SUCCESS'])
    IO.write_json_new(a.output/'same_seed_controls14.json',control_report)
    IO.write_json_new(a.output/'package_validation348.json',[{key:row[key] for key in row if key!='package'} for row in sorted(checked,key=lambda row:(row['role'],row['molecule_id']))])
    IO.write_json_new(a.output/'stratified_descriptive_and_censored_bounds.json',descriptive_strata(tasks,summaries,MISSING))
    IO.write_json_new(a.output/'closed_package_only_statistics.json',{'scope':'334_REAL_PACKAGES_ONLY_EXCLUDES2_UNRESOLVED_AND14_CONTROLS',
        'statistics':aggregate_statistics(ordered)})
    actual=sum(row['allocated_core_seconds'] for row in parents.values())
    IO.write_json_new(a.output/'approved_point_in_time_cost_snapshot.json',dict(selection,
        actual_known_related_core_seconds_at_snapshot=actual,actual_known_related_core_hours_at_snapshot=actual/3600,
        historical_original_estimate_core_seconds=230400,historical_original1p5_line_core_seconds=345600,historical_original1p5_line_exceeded=actual>345600,
        cost_decision_reference=evidence['cost_decision_reference'],allocation_overrun_policy=cost_policy,
        historical_overrun_must_be_reported=actual>345600,cost_alone_blocks_closure_or_full_planning=False,
        current_closure_parent_cost=None,current_closure_parent_id=str(proof['job_id']),
        current_closure_and_all_later_tasks_cost_must_be_appended_from_actual_terminal_Root_accounting=True,
        point_in_time_only_not_final_data_line_total=True,future_parent_states_not_required_for_this_snapshot=True,
        no_monetary_charge_does_not_make_actual_core_seconds_zero=True))
    disk=sum(path.stat().st_size for path in a.output.iterdir() if path.is_file());need(disk+2*1024**2<=OUTPUT_CAP,'FINITE1GIB_OUTPUT_BUDGET')
    report={'schema':'SPRIME336_PACKAGE_OR_TIMEOUT_OUTCOME_AUDIT_V2','status':'CLOSED_WITH_TWO_EXECUTION_UNRESOLVED_REQUIRES_ROOT_REVIEW',
        'runtime':{'job_id':str(proof['job_id']),'node':request['node'],'uid':os.getuid(),'reader_threads':16,'allocated_cpus':16,
            'memory_policy':'SLURM_DEFAULT_UNSPECIFIED','memory_requested':False,'scheduler_elapsed_floor_at_start_seconds':elapsed_at_start},
        'root_preflight':reference(a.root_preflight),'historical_plan':reference(a.plan),'resource_binding':reference(a.resource_binding),
        'synthetic_fixture_result':fixture,
        'actual_stage_evidence':reference(a.stage_evidence),'approved_point_in_time_owned_accounting':reference(a.whole_owned_accounting),
        'approved_prior_related_cost_selection':reference(a.prior_related_cost_selection),'cost_snapshot_observed_at':selection['approved_snapshot_observed_at'],
        'cost_basis':'ROOT_APPROVED_POINT_IN_TIME_SNAPSHOT_ONLY','future_registry_scanned':False,'not_final_data_line_total':True,
        'original_timeout_preserved':parents['4520364'],'recovery_timeout_preserved':parents['4521110'],
        'original_task_denominator':336,'validated_original_packages':334,'unresolved_execution_failures':2,'terminal_outcome_rows':336,
        'controls_validated_exact_excluding_only_summary_elapsed':14,'controls_added_to_population':0,
        'scientific_success_packages':sum(row['status']=='SUCCESS' for row in summaries.values()),
        'closed_package_scientific_status_counts':dict(Counter(row['status'] for row in summaries.values())),
        'execution_unresolved_scientific_status':'UNKNOWN_NOT_ASSIGNED','unresolved_worker_to_missing_mapping':'NOT_DURABLY_RECORDED',
        'producer_final_receipt_fabricated':False,'producer_monitor_closure_fabricated':False,'distinct_completed_worker_identity_claimed':False,
        'readback334_real_packages':readback,'physical_ID_scope':'Original package indices only; no formal identity assignment',
        'full_forecast_core_hours':None,'full_forecast_status':'RIGHT_CENSORED_NO_VALIDATED_FULL_FORECAST',
        'historical_original1p5_cost_line_exceeded_at_approved_snapshot':actual>345600,'current_closure_and_all_later_Root_terminal_cost_append_pending':True,
        'cost_decision_reference':evidence['cost_decision_reference'],'allocation_overrun_policy':cost_policy,
        'cost_overrun_must_be_reported':actual>345600,'cost_alone_blocks_closure_or_full_planning':False,'cost_below_threshold_is_scientific_PASS':False,
        'old336_package_C0_schema_satisfied':False,'pilot_accepted_for_planning':False,'formal_generation_authorized':False,'common_frozen':False,
        'root_next_action':'Review actual C0 and this approved point-in-time cost audit. Root appends this job and all later task costs from subsequent actual terminal Masters; report overruns and continue under the pinned cost decision. No future unrelated parent is a prerequisite for this snapshot. Independently review full budget/model with scientific quality gates unchanged; no automatic full release.',
        'new_UFF_QM_calls':0,'new_seeds':0,'new_logical_retries':0,'new_once_ledger_entries':0,
        'old_packages_or_reports_modified':False,'signals_sent_by_this_closure':False,'automatic_retry':False,
        'memory_samples':memory,'soft_stop_new_reads':stop,'wall_seconds_observed':time.monotonic()-started,
        'output_bytes_before_report':disk,'outputs':[IO.reference(path) for path in sorted(a.output.iterdir()) if path.is_file()]}
    IO.write_json_new(a.output/'joint_timeout_audit_report.json',report)
    print(json.dumps({'status':report['status'],'terminal_outcomes':336,'real_packages':334,'unresolved':2,'full_release':False}))
    return 0
if __name__=='__main__':sys.exit(main())