"""Separate real package outcomes and unresolved executions; no synthetic packages."""
from __future__ import annotations
from collections import Counter,defaultdict
import math,statistics


def need(ok,message):
    if not ok:raise ValueError(message)


def validate_cost_decision(value):
    need(value.get('schema')=='USER_AUTHORIZED_ALLOCATION_OVERRUN_REPORT_CONTINUE_V1'
        and value.get('status')=='USER_AUTHORIZED' and value.get('on_overrun')=='REPORT_AND_CONTINUE',
        'ACTUAL_USER_REPORT_AND_CONTINUE_COST_AUTHORITY_REQUIRED')
    need(value.get('original_threshold_multiplier')==1.5 and value.get('only_cost_stop_rule_changed') is True
        and value.get('scientific_quality_thresholds_unchanged') is True
        and value.get('retain_actual_accounting_including_failures_and_startup') is True
        and value.get('preserve_historical_requests_sources_and_results') is True,
        'COST_AUTHORITY_MUST_PRESERVE_QUALITY_HISTORICAL_RESULTS_AND_ACTUAL_COSTS')
    need(value.get('no_forced_termination') is True and value.get('max_single_job_wall_seconds')==172800
        and value.get('cpu_only') is True and value.get('quota_reserve_bytes')==200000000000
        and value.get('slurm_memory_policy')=='SLURM_DEFAULT_UNSPECIFIED','COST_AUTHORITY_RESOURCE_GUARDS_UNCHANGED')
    return {'on_overrun':'REPORT_AND_CONTINUE','historical_threshold_multiplier':1.5,
        'cost_alone_blocks_closure_or_full_planning':False,'cost_below_threshold_is_scientific_PASS':False,
        'scientific_quality_thresholds_unchanged':True,'actual_cost_accounting_required':True}


def terminal_rows(tasks,package_summaries,package_refs,missing,context,task_digest,seed_for):
    need(len(tasks)==336 and len(package_summaries)==len(package_refs)==334,'EXACT336_TASKS334_PACKAGES_REQUIRED')
    need(set(package_summaries)==set(package_refs) and set(tasks)==set(package_refs)|set(missing)
        and not set(package_refs)&set(missing) and len(missing)==2,'PACKAGE_OR_UNRESOLVED_UNION_MUST_BE_DISJOINT336')
    rows=[];failures=[]
    for mid,task in sorted(tasks.items()):
        meta=task['meta'];base={'molecule_id':mid,'cohort':meta['cohort'],'file_group':int(meta['file_group']),
            'expected_conformers':meta['expected_conformers'],'original_task_sha256':task_digest(task),
            'original_task_seed':seed_for(task),'new_logical_retry':False,'new_seed':False,'new_attempt_ledger_created':False}
        if mid in package_refs:
            summary=package_summaries[mid]
            rows.append(dict(base,row_kind='VALIDATED_ORIGINAL_PACKAGE',package_reference=package_refs[mid],
                scientific_status=summary['status'],science_result_observed=True,execution_resolution='DURABLE_PACKAGE_VALIDATED',
                scientific_failure_stage_claimed=False,terminal_failure_evidence=None))
        else:
            failure=dict(base,row_kind='UNRESOLVED_EXECUTION_FAILURE',package_reference=None,
                scientific_status=None,science_result_observed=False,execution_resolution='UNRESOLVED_AFTER_PARENT_TIMEOUT',
                failure_stage='UNKNOWN',scientific_failure_stage_claimed=False,prior_status_is_historical_only=meta['Sprime_status'],
                original_N=missing[mid],parent_timeout_evidence=context,
                worker_to_molecule_mapping_status='NOT_DURABLY_RECORDED',worker_pid=None,
                consumed_original_retry_cohort_without_new_attempt=True)
            rows.append(failure);failures.append(failure)
    return rows,failures


def descriptive_strata(tasks,summaries,missing):
    strata=defaultdict(lambda:{'ids':[],'closed':[],'unresolved':[]})
    for mid,task in tasks.items():
        meta=task['meta'];row=strata[(meta['cohort'],int(meta['file_group']))];row['ids'].append(mid)
        if mid in summaries:row['closed'].append(summaries[mid])
        else:
            need(mid in missing,'UNEXPECTED_UNOBSERVED_TASK');row['unresolved'].append(mid)
    result=[]
    for (cohort,group),row in sorted(strata.items()):
        n=len(row['ids']);closed=row['closed'];u=len(row['unresolved']);times=[float(v['elapsed_seconds']) for v in closed]
        need(all(math.isfinite(value) and value>=0 for value in times),'FINITE_OBSERVED_PACKAGE_TIMES_REQUIRED')
        successes=sum(v['status']=='SUCCESS' for v in closed)
        result.append({'cohort':cohort,'file_group':group,'original_task_denominator':n,'closed_package_molecules':len(closed),
            'execution_unresolved_molecules':u,'unresolved_ids':sorted(row['unresolved']),
            'closed_package_status_counts':dict(Counter(v['status'] for v in closed)),
            'observed_scientific_success_molecules':successes,'observed_success_fraction_all_tasks':successes/n,
            'latent_scientific_success_fraction_bounds':[successes/n,(successes+u)/n],
            'upper_success_fraction_is_unobserved_hypothesis_not_actual_success':True,
            'closed_package_worker_seconds_sum':sum(times),'closed_package_worker_seconds_min':min(times) if times else None,
            'closed_package_worker_seconds_max':max(times) if times else None,
            'closed_package_worker_seconds_median':statistics.median(times) if times else None,
            'worker_seconds_sum_lower_bound':sum(times),'worker_seconds_sum_upper_bound':None if u else sum(times),
            'missing_individual_worker_runtime_lower_bound':0 if u else None,
            'missing_individual_worker_runtime_upper_bound':None,
            'censoring_basis':'Actual parent TIMEOUT; individual task start/phase/PID/timing not durably mapped. Parent elapsed is not assigned to either molecule.',
            'hypothetical_missing_seconds_sensitivity':[{'seconds_per_unresolved_hypothesis':seconds,
                'hypothetical_worker_seconds_sum':sum(times)+u*seconds,'not_allocated_core_cost_or_runtime_forecast':True}
                for seconds in (60,600,1800,5400,14400)] if u else [],
            'completed_package_max_is_not_reliable_full_forecast':True})
    return result