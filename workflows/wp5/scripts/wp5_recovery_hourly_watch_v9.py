"""Hourly effective78 watcher with original guide stop conditions 2/3/5/6.
Default dry-run. No scientific queue writes, cancellation or Slurm submission.
"""
import argparse, collections, hashlib, json, math, os, socket, subprocess, time, uuid
from pathlib import Path
from wp5_hourly_observe_v8 import ROOT, effective_jobs, accounting
R=ROOT
CALCS={"pm7_B","pm7_cation","pm7_anion","pm7_water","pm7_octanol","xtb_singlepoint",
       "xtb_vipea","xtb_vfukui","xtb_ALPB_water","xtb_ALPB_octanol","xtb_fod","xtb_perturbed_gradient"}
ACTIVE={'RUNNING','PENDING','COMPLETING','CONFIGURING','RESIZING','SUSPENDED'}
TERMINAL={'COMPLETED','FAILED','CANCELLED','NODE_FAIL','PREEMPTED','BOOT_FAIL','OUT_OF_MEMORY','TIMEOUT','DEADLINE','REVOKED'}
EXPECTED_MOLECULES=1220466
EXPECTED_RECORDS=11231854
MAX_PUBLISHER_AGE_SECONDS=180

def emit(event,**data):
    print(json.dumps({'event':event,'time':time.time(),**data},ensure_ascii=False),flush=True)

def atomic(path,data):
    path=Path(path);tmp=path.with_name(path.name+'.'+str(os.getpid())+'.pending')
    with tmp.open('w') as stream:
        json.dump(data,stream,indent=2,allow_nan=False);stream.write('\n');stream.flush();os.fsync(stream.fileno())
    os.replace(tmp,path)

def numeric(value):
    return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value)

def integer(value):
    return isinstance(value,int) and not isinstance(value,bool)

def publisher_guard(publisher,now):
    timestamp=publisher.get('time')
    age=now-timestamp if numeric(timestamp) else None
    good=(publisher.get('uid')==1278 and publisher.get('hostname')=='sonmi'
          and numeric(age) and 0<=age<=MAX_PUBLISHER_AGE_SECONDS)
    return {'valid':bool(good),'uid':publisher.get('uid'),'hostname':publisher.get('hostname'),
            'age_seconds':age,'max_age_seconds':MAX_PUBLISHER_AGE_SECONDS}

def paired_observer_proof(observation,snapshot,summary,summary_mtime,now=None):
    now=time.time() if now is None else now
    issues=[];otime=observation.get('time');stime=snapshot.get('time')
    interval=snapshot.get('scan_interval',{})
    source=snapshot.get('control_sources',{})
    scan_start=interval.get('scan_start_epoch');scan_end=interval.get('scan_end_epoch')
    if not (numeric(scan_start) and numeric(scan_end) and scan_start<=scan_end
            and numeric(otime) and numeric(stime) and scan_end<=min(otime,stime)+2
            and interval.get('source_BEGIN_used') is False and interval.get('source_connection_closed') is True
            and interval.get('row_state_and_counts_json_same_snapshot') is True
            and interval.get('partial_counts_published') is False
            and interval.get('chunk_rows')==512 and interval.get('statement_wall_budget_seconds')==30.0):
        issues.append('OBSERVER_KEYSET_INTERVAL_NOT_CLOSED')
    if summary.get('scan_interval')!=interval or observation.get('scan_interval')!=interval:
        issues.append('OBSERVER_INTERVAL_PROVENANCE_DIFFER')
    if summary.get('control_sources')!=source or observation.get('control_sources')!=source:
        issues.append('OBSERVER_SOURCE_PROVENANCE_DIFFER')
    expected_sources={'observer':R/'scripts/wp5_hourly_observe_v8.py',
        'queue_scan_helper':R/'scripts/wp5_observer_scan_v2.py',
        'production_runtime':R/'scripts/wp5_runner_v13.py'}
    for name,path in expected_sources.items():
        expected={'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
        if source.get(name)!=expected:issues.append('OBSERVER_CURRENT_SOURCE_NOT_BOUND:'+name)
    observed_counts=snapshot.get('counts')
    observed_total=(sum(x['molecules'] for x in observed_counts)
        if isinstance(observed_counts,list) and all(integer(x.get('molecules')) and x['molecules']>=0 for x in observed_counts) else None)
    if not integer(observed_total) or interval.get('molecules_visited_once')!=observed_total or interval.get('full_primary_key_scan_EOF') is not True:
        issues.append('OBSERVER_PRIMARY_KEY_SCAN_NOT_CLOSED')
    # Do not compare visits to the expected meta population here: that genuine
    # difference must reach the unchanged original Guide2 STOP evaluator.
    if not numeric(otime) or not numeric(stime) or abs(otime-stime)>600:
        issues.append('OBSERVER_PAIR_TIMESTAMPS_NOT_CLOSED')
    if not numeric(summary_mtime) or not 0<=now-summary_mtime<=180:
        issues.append('OBSERVER_SUCCESS_STDOUT_NOT_FRESH')
    elif numeric(otime) and numeric(stime) and not max(otime,stime)-2<=summary_mtime<=max(otime,stime)+600:
        issues.append('STDOUT_NOT_FROM_SAME_OBSERVER_WINDOW')
    counts=snapshot.get('counts')
    if not isinstance(counts,list) or not all(integer(x.get('molecules')) and integer(x.get('records')) for x in counts):
        issues.append('OBSERVER_COUNTS_FIELDS_UNKNOWN')
    else:
        complete=[x for x in counts if x.get('state')=='COMPLETE']
        retry=[x for x in counts if x.get('state')=='RETRY_PENDING']
        checks={'complete_molecules':sum(x['molecules'] for x in complete),
                'complete_records':sum(x['records'] for x in complete),
                'retry_molecules':sum(x['molecules'] for x in retry),
                'durable_records':snapshot.get('durable_records'),
                'population_closed':snapshot.get('population_closed'),
                'task_denominators_closed':snapshot.get('task_denominators_closed')}
        for name,value in checks.items():
            if name not in summary or summary[name]!=value:issues.append('STDOUT_SNAPSHOT_DIFFER:'+name)
        if observation.get('complete_molecules')!=checks['complete_molecules']:
            issues.append('ROOT_OBSERVATION_COMPLETE_MOLECULES_DIFFER')
    if summary.get('effective_selection_ready') is not True or summary.get('effective_job_count')!=78:
        issues.append('STDOUT_EFFECTIVE78_NOT_READY')
    if summary.get('cumulative_actual_allocated_core_hours_known_sum')!=observation.get('cumulative_actual_allocated_core_hours_known_sum'):
        issues.append('STDOUT_ROOT_OBSERVATION_COST_DIFFER')
    return {'valid':not issues,'issues':issues,'observation_epoch':otime,
            'queue_snapshot_epoch':stime,'observer_stdout_mtime':summary_mtime,
            'population_and_task_flags_source':'queue_snapshot_and_success_stdout_not_root_observation'}

def evaluate_stop_conditions(publisher,observation,snapshot,selection,observer_success,now=None):
    """Pure helper; no filesystem writes, queue access, QM or scheduler commands."""
    now=time.time() if now is None else now
    guard=publisher_guard(publisher,now);notes=[];conditions=[]
    ready=(observer_success is True and guard['valid'] and selection.get('ready') is True)
    if not ready:
        return {'schema':'WP5_GUIDE_STOP_EVALUATION_V7','eligible':False,'conditions':[],
                'publisher_guard':guard,'observer_success':observer_success,
                'effective_selection_ready':selection.get('ready'),'notes':['PREREQUISITES_NOT_CLOSED_NO_STOP']}
    cost_ids=set(selection.get('actual_cost_job_ids',[]))
    # Guide2: actual one-queue population and the persisted prefix's 12N.
    meta=snapshot.get('meta',{});counts=snapshot.get('counts')
    try:population=int(meta['population_molecules']);records=int(meta['population_records'])
    except (KeyError,TypeError,ValueError):population=None;records=None
    population_known=(integer(population) and integer(records) and isinstance(counts,list)
                      and all(integer(x.get('molecules')) and integer(x.get('records')) for x in counts))
    if population_known:
        observed_molecules=sum(x['molecules'] for x in counts);observed_records=sum(x['records'] for x in counts)
        if (population,records)!=(EXPECTED_MOLECULES,EXPECTED_RECORDS) or (observed_molecules,observed_records)!=(population,records):
            conditions.append({'guide_condition':2,'reason':'POPULATION_OR_OUTPUT_COUNT_NOT_CLOSED',
                'details':{'population_molecules':population,'population_records':records,
                           'observed_molecules':observed_molecules,'observed_records':observed_records}})
    else:notes.append('POPULATION_FIELDS_UNKNOWN_NO_NUMERIC_INFERENCE')
    rates=snapshot.get('task_success_rates');durable_records=snapshot.get('durable_records')
    if isinstance(rates,list) and integer(durable_records) and durable_records>=0:
        names=[x.get('calc_type') for x in rates]
        # A truly empty persisted prefix has zero requested outcomes. Startup
        # failure with no SCI does not become a fabricated denominator failure.
        empty_prefix=(durable_records==0 and not rates)
        totals_known=all(integer(x.get('total')) for x in rates)
        if not empty_prefix and totals_known:
            closed=(len(names)==12 and set(names)==CALCS and all(x['total']==durable_records for x in rates))
            if not closed:
                conditions.append({'guide_condition':2,'reason':'POPULATION_OR_OUTPUT_COUNT_NOT_CLOSED',
                    'details':{'durable_records':durable_records,'expected_persisted_slots':12*durable_records,
                               'task_totals':{str(x.get('calc_type')):x.get('total') for x in rates},
                               'task_names_count':len(names)}})
        elif not empty_prefix:notes.append('TASK_DENOMINATORS_UNKNOWN_NO_ZERO_SUBSTITUTION')
    else:notes.append('TASK_DENOMINATOR_FIELDS_UNKNOWN_NO_STOP_INFERENCE')
    # Guide3: use this fresh publisher's measured quota, never null->0.
    quota=publisher.get('quota_parsed',{}).get('remaining_bytes')
    if numeric(quota) and quota>=0:
        if quota<300_000_000_000:
            conditions.append({'guide_condition':3,'reason':'QUOTA_REMAINING_BELOW_300GB',
                               'details':{'remaining_bytes':quota,'threshold_bytes':300_000_000_000}})
    else:notes.append('QUOTA_UNKNOWN_NO_STOP_INFERENCE')
    # Guide5: exact OWN top-level formal JobID/username witness from successful
    # sacct. Plain FAILED, NODE_FAIL and scientific per-call TIMEOUT are excluded.
    sacct=publisher.get('sacct',{});accounting_success=sacct.get('returncode')==0
    scheduler_failures={}
    if accounting_success:
        for line in sacct.get('stdout','').splitlines():
            fields=[v.strip() for v in line.split('|')]
            if len(fields)>=4 and fields[0] in cost_ids and fields[2]=='zixiao':
                state=fields[3].split()[0].rstrip('+') if fields[3] else None
                if state in {'OUT_OF_MEMORY','TIMEOUT'}:scheduler_failures[fields[0]]=state
        for state in ('OUT_OF_MEMORY','TIMEOUT'):
            jobs=sorted((job for job,value in scheduler_failures.items() if value==state),key=int)
            if jobs:conditions.append({'guide_condition':5,'reason':'SLURM_'+state,
                                       'details':{'actual_formal_job_ids':jobs,'scope':'All4formalphases_only'}})
    else:notes.append('SACCT_QUERY_NOT_SUCCESSFUL_NO_SCHEDULER_OR_COST_STOP')
    # Guide6: fresh all4-phase actual AllocCPUS*ElapsedRaw, precisely one row per
    # actual385 job. A missing/ambiguous ledger never yields an extrapolation.
    ledger,ledger_notes=accounting(publisher,cost_ids)
    ledger_closed=(accounting_success and len(cost_ids)==385 and set(ledger)==cost_ids
                   and not ledger_notes['different_duplicate_accounting_job_ids'])
    complete=observation.get('complete_molecules');projected=None;core=None
    if ledger_closed and integer(complete) and population_known and population>0 and complete>=population*.1 and 0<complete<=population:
        core=sum(x['allocated_core_hours'] for x in ledger.values())
        projected=core*population/complete
        if projected>50000:
            conditions.append({'guide_condition':6,'reason':'EXTRAPOLATED_ACTUAL_CORE_HOURS_ABOVE50000',
                'details':{'actual_allocated_core_hours':core,'completed_molecules':complete,
                           'population_molecules':population,'projected_core_hours':projected,
                           'actual_unique_job_count':len(cost_ids),'threshold_core_hours':50000,
                           'historical_startup_failure_costs_included':True}})
    elif not ledger_closed:notes.append('ALL385_ACCOUNTING_NOT_CLOSED_NO_COST_STOP')
    elif not integer(complete):notes.append('COMPLETE_MOLECULES_UNKNOWN_NO_COST_STOP')
    else:notes.append('BELOW10PCT_COMPLETE_NO_COST_STOP')
    return {'schema':'WP5_GUIDE_STOP_EVALUATION_V7','eligible':True,'conditions':conditions,
            'publisher_guard':guard,'actual_cost_job_count':len(cost_ids),'accounting_complete':ledger_closed,
            'accounting_missing_job_ids':sorted(cost_ids-set(ledger),key=int),
            'scheduler_oom_timeout_jobs':scheduler_failures,'actual_allocated_core_hours':core,
            'projected_core_hours_at10pct':projected,'notes':notes,'first5pct_owned_by_runner':True,
            'stop_for_startup_or_lock_failure':False}

def write_guide_stop(evaluation,evidence,dry_run=True):
    if dry_run or not evaluation['eligible'] or not evaluation['conditions']:
        return {'written':False,'dry_run':dry_run,'condition_count':len(evaluation['conditions'])}
    target=R/'STOP_NEW_MOLECULES.json'
    value={'time':time.time(),'reason':evaluation['conditions'][0]['reason'],
           'details':{'original_guide_conditions':evaluation['conditions'],'evidence':evidence},
           'job_id':os.environ.get('SLURM_JOB_ID'),'writer':'wp5_recovery_hourly_watch_v9',
           'uid':os.getuid(),'hostname':socket.gethostname(),'normal_runner_checkpoint_exit_only':True}
    pending=target.with_name(target.name+'.'+uuid.uuid4().hex+'.pending')
    atomic(pending,value)
    try:
        os.link(pending,target);return {'written':True,'path':str(target),'reason':value['reason']}
    except FileExistsError:
        return {'written':False,'existing_STOP_preserved':True,'path':str(target)}
    finally:pending.unlink(missing_ok=True)

def check_files(a):
    if a.apply_stop:raise ValueError('HISTORICAL_CHECK_ALWAYS_DRY_RUN_NEVER_WRITES_STOP')
    observation=json.loads(a.check_observation.read_text())
    path=a.queue_snapshot or a.check_observation.with_name(
        a.check_observation.name.replace('_root_observation_v8.json','_queue_snapshot_v8.json'))
    snapshot=json.loads(path.read_text());pub=json.loads(a.publisher.read_text())
    hour=a.check_observation.name.removeprefix('formal_hour').split('_',1)[0]
    stdout_path=a.observer_stdout or a.check_observation.with_name('continuation14_recovery_hour_'+hour+'_observer_stdout.json')
    summary=json.loads(stdout_path.read_text())
    proof=paired_observer_proof(observation,snapshot,summary,stdout_path.stat().st_mtime,a.as_of)
    # Historical as-of is a pure check-only switch; live watcher cannot use it.
    result=evaluate_stop_conditions(pub,observation,snapshot,effective_jobs(),proof['valid'],a.as_of)
    result.update(dry_run=True,STOP_written=False,observation_path=str(a.check_observation),
                  queue_snapshot_path=str(path),observer_stdout_path=str(stdout_path),observer_pair_proof=proof)
    print(json.dumps(result,indent=2,allow_nan=False))

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check',action='store_true')
    parser.add_argument('--hours-limit',type=float,default=192)
    parser.add_argument('--first-hour',type=int,default=1)
    parser.add_argument('--first-report-delay-seconds',type=float,default=3600)
    parser.add_argument('--apply-stop',action='store_true',help='Enable ONLY guide2/3/5/6 STOP flag writes; default dry-run')
    parser.add_argument('--check-observation',type=Path,help='Pure dry-run evaluation of actual saved v6 observation')
    parser.add_argument('--observer-stdout',type=Path,help='Successful observer CLI summary paired with saved observation/snapshot')
    parser.add_argument('--queue-snapshot',type=Path);parser.add_argument('--publisher',type=Path,default=R/'reports/observation_latest.json')
    parser.add_argument('--as-of',type=float,help='Historical check-only timestamp; never a live freshness override')
    a=parser.parse_args()
    if a.check:
        import ast
        ast.parse(Path(__file__).read_text());print('WATCH9_AST_PASS_NOT_STARTED_NO_STOP');return
    if a.check_observation:check_files(a);return
    if a.as_of is not None:raise ValueError('AS_OF_ONLY_ALLOWED_IN_NO_WRITE_HISTORICAL_CHECK')
    if not 0<=a.first_report_delay_seconds<=3600:raise ValueError('FIRST_REPORT_DELAY_MUST_BE_0_TO3600_SECONDS')
    assert socket.gethostname().split('.')[0]=='sonmi' and os.getuid()==1278
    stat=Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()
    identity={'status':'GUIDE_STOP_EFFECTIVE_HOURLY_WATCH_PROCESS_STARTED','time':time.time(),
        'uid':os.getuid(),'pid':os.getpid(),'start_ticks':stat[19],
        'source_path':str(Path(__file__).resolve()),'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'hours_limit':a.hours_limit,'science_queue_writes':False,'Slurm_submission':False,
        'dry_run':not a.apply_stop,'STOP_flag_only':a.apply_stop,'guide_conditions':[2,3,5,6]}
    atomic(R/'reports/recovery_hourly_watch_v9_identity.json',identity)
    (R/'reports/recovery_hourly_watch_v9.pid').write_text(str(os.getpid())+'\n')
    start=time.monotonic();next_report=start+a.first_report_delay_seconds;hour=a.first_hour;previous_alert=None
    emit('WATCH_STARTED',**identity,termination_scope='Latest effective72logicalmains+6cleanup')
    while time.monotonic()-start<a.hours_limit*3600:
        try:
            selection=effective_jobs()
            if not selection['ready']:
                emit('WAITING_FOR_ACTUAL_continuation14_RECEIPT_NO_STOP',waiting_reason=selection.get('waiting_reason'),actual_cost_jobs=len(selection['actual_cost_job_ids']));time.sleep(60);continue
            pub=json.loads(a.publisher.read_text());guard=publisher_guard(pub,time.time())
            ids=set(selection['effective_job_ids'])
            normalized={job:(pub.get('registered_job_states',{}).get(job) or '').split()[0]
                        if pub.get('registered_job_states',{}).get(job) else None for job in ids}
            failed={j:s for j,s in normalized.items() if s and s not in ACTIVE|{'COMPLETED'}}
            stop=R/'STOP_NEW_MOLECULES.json'
            alert=(stop.exists(),tuple(sorted(failed.items())),not guard['valid'])
            if alert!=previous_alert and any((alert[0],alert[1],alert[2])):
                emit('RUNTIME_INFORMATION_NO_NEW_STOP_RULE',STOP=json.loads(stop.read_text()) if stop.exists() else None,
                     current_failed_states=failed,publisher_guard=guard,historical_plain_FAILED_ignored=True)
            previous_alert=alert
            terminal=guard['valid'] and len(ids)==78 and all(s in TERMINAL for s in normalized.values())
            if time.monotonic()>=next_report or terminal:
                # One scheduled observation attempt per hour, including errors.
                next_report=time.monotonic()+3600
                if not guard['valid']:
                    emit('STALE_OR_WRONG_PUBLISHER_NO_OBSERVER_OR_STOP',publisher_guard=guard)
                else:
                    command=['ssh','-n','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','compute-0-20',
                        'cd /share/home/zixiao/descriptor_analysis && PYTHONPATH='+str(R/'scripts')+
                        ' timeout --signal=TERM --kill-after=30s 540s /share/home/zixiao/.conda/envs/chemprop/bin/python -B '+str(R/'scripts/wp5_hourly_observe_v8.py')+
                        ' --hour '+str(hour)+' --write-latest']
                    try:
                        run=subprocess.run(command,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=600)
                        stdout_path=R/'reports'/('continuation14_recovery_hour_'+str(hour)+'_observer_v9_stdout.json')
                        stdout_path.write_text(run.stdout)
                        if run.returncode:
                            emit('OBSERVER_ERROR_CONTINUE_NO_STOP',exit_code=run.returncode,stderr=run.stderr[-2000:])
                        else:
                            out=json.loads(run.stdout)
                            opath=R/'reports'/('formal_hour'+str(hour)+'_root_observation_v8.json')
                            spath=R/'reports'/('formal_hour'+str(hour)+'_queue_snapshot_v8.json')
                            observation=json.loads(opath.read_text());snapshot=json.loads(spath.read_text())
                            fresh_pub=json.loads(a.publisher.read_text())
                            proof=paired_observer_proof(observation,snapshot,out,stdout_path.stat().st_mtime)
                            decision=evaluate_stop_conditions(fresh_pub,observation,snapshot,selection,proof['valid'])
                            decision['observer_pair_proof']=proof
                            evidence={'observation_path':str(opath),'queue_snapshot_path':str(spath),
                                      'publisher_path':str(a.publisher),'hour':hour,
                                      'observer_returncode':run.returncode,'source_sha256':identity['source_sha256']}
                            stopped=write_guide_stop(decision,evidence,not a.apply_stop)
                            atomic(R/'reports'/('recovery_hour_'+str(hour)+'_guide_stop_v9.json'),
                                   {'time':time.time(),'evaluation':decision,'STOP_result':stopped,'evidence':evidence})
                            emit('HOURLY_PROGRESS',hour=hour,complete_molecules=out['complete_molecules'],
                                 complete_records=out['complete_records'],retry_molecules=out['retry_molecules'],
                                 population_closed=out['population_closed'],task_denominators_closed=out['task_denominators_closed'],
                                 effective_job_count=out['effective_job_count'],current_states=out['current_phase']['state_counts'],
                                 cumulative_core_hours=out['cumulative_actual_allocated_core_hours_known_sum'],
                                 guide_stop_evaluation=decision,STOP_result=stopped)
                    except Exception as error:
                        emit('OBSERVER_OR_EVALUATION_ERROR_CONTINUE_NO_STOP',error_type=type(error).__name__,message=str(error))
                    hour+=1
            if terminal:
                emit('ALL_EFFECTIVE_72MAIN_6CLEANUP_TERMINAL_REQUIRES_ROOT_REVIEW',
                     states=dict(collections.Counter(normalized.values())),scientific_completion_claimed=False);return
        except Exception as error:
            emit('WATCH_METADATA_ERROR_CONTINUE_NO_STOP',error_type=type(error).__name__,message=str(error))
        time.sleep(60)
    emit('BOUNDED_WATCH_LIFETIME_ENDED')
if __name__=='__main__':main()

