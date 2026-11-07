"""Run exactly the prepared32 once, admitted CPU16, original10 tests then real UFF."""
from __future__ import annotations
import argparse,collections,concurrent.futures as cf,json,multiprocessing as mp,os,pathlib,sys,time,traceback
REPO=pathlib.Path(__file__).absolute().parents[4];sys.path.insert(0,str(REPO));sys.dont_write_bytecode=True
from workflows.data_v1_final.conformers.n1_pprime2_pilot_v4 import contract as C,core,io as I


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    options=('prepared','prepare-accounting','root-preflight','quota-provider-review','ledger-root','output')
    for name in options:parser.add_argument('--'+name,type=pathlib.Path,required=True)
    a=parser.parse_args();prepared_ref=I.request_ref(a.root_preflight,a.prepared)
    accounting_ref=I.request_ref(a.root_preflight,a.prepare_accounting)
    proof,catalog,admission=I.admit(__file__,a,options,C.SCOPE_KEY,C.SCOPE,'conformer',[prepared_ref,accounting_ref])
    correction_ref=catalog['count_correction_authority_reference'];correction=C.load_count_correction(correction_ref)
    expected=correction['expected_source_pm7_n1_molecules']
    C.need(a.ledger_root==I.LEDGER,'ONE_SHARED_N1_GENERATION_ONCE_LEDGER_REQUIRED')
    C.need(proof['request']['scope']['mode']=='BOUNDED_PERFORMANCE_BATCH','REAL32_BOUNDED_SCIENCE_PILOT_REQUIRED')
    out=I.new_output(a.output);(out/'packets').mkdir();started=time.monotonic();budget=I.Budget(proof,out,a.ledger_root,
        quota_provider_review_reference=admission['quota_provider_review_reference'])
    tests=I.test10();tests_ref=I.json_new(out/'synthetic10_actual_receipt.json',tests,[out,a.ledger_root])
    if tests['status']!='PASS':
        I.json_new(out/'receipt.json',{'schema':'N1_PPRIME2_PILOT32_RECEIPT_V4','status':'SYNTHETIC10_FAILED_NO_SCIENCE',
            'test_receipt':tests_ref,'new_UFF_calls':0,'new_QM_calls':0,'common':False,'pilot_membership':False,
            'final_common_reference':None,'actual_terminal_accounting_required':True},[out,a.ledger_root]);return 3
    # The first science-data read is after actual main admission and actual tests.
    prepared=I.read(prepared_ref)
    C.need(prepared['schema']=='N1_PPRIME2_PILOT_PREPARED32_V4' and prepared['status']=='ACTUAL_INPUT32_READY_NOT_GENERATED'
        and prepared['selected_count']==32 and prepared['mother_count']==prepared['expected_mother_count']==expected
        and prepared['count_correction_authority']==correction_ref and prepared['catalog']==I.ref(I.HERE/'frozen_sources.json')
        and prepared['common'] is False and prepared['pilot_membership'] is False and prepared['final_common_reference'] is None,
        'ACTUAL_CLOSED_INPUT32_WITH_NO_FINAL_COMMON_REQUIRED')
    accounting=I.read(accounting_ref);I.authorized(proof,[accounting['raw_sacct_reference']])
    prep_terminal=I.terminal_c0(accounting_ref,prepared['job_id'])
    authority_ref=prepared['source_population_authority'];tasks_refs=prepared['tasks'];base_refs=prepared['baseline_packets']
    I.authorized(proof,[authority_ref,*tasks_refs,*base_refs,prepared['mother_inventory'],prepared['source_sha_validation'],prepared['formal_config'],
        prepared['role_status_usable_audit'],prepared['metadata_aggregation_before_validation']])
    authority=I.read(authority_ref)
    C.need(authority['schema']=='N1_PPRIME2_SOURCE_POPULATION_AUTHORITY_V4'
        and authority['status']=='ORIGINAL_SOURCE_POPULATION_CLOSED_PILOT_ONLY' and authority['mother_count']==authority['expected_mother_count']==expected
        and authority['count_correction_authority']==correction_ref
        and authority['role_status_usable_audit']==prepared['role_status_usable_audit']
        and authority['metadata_aggregation_before_validation']==prepared['metadata_aggregation_before_validation']
        and authority['job_id']==prepared['job_id'] and authority['common'] is False and authority['pilot_membership'] is False
        and authority['final_common_reference'] is None,'ORIGINAL_SOURCE_POPULATION_AUTHORITY_NOT_FINAL_COMMON_REQUIRED')
    audit=I.read(prepared['role_status_usable_audit']);before=I.read(prepared['metadata_aggregation_before_validation'])
    joint_dimensions=['source_role','effective_role','Sprime_status','Sprime_usable_equals_source_N',
        'original_Sprime_usable_count','pm7_S_usable_equals1','pm7_S_usable_count',
        'physical_original_Sprime_usable_count','metadata_eligibility_reason','final_status','final_reason']
    for value in (audit,before):
        C.need(value['schema']=='N1_PPRIME2_ROLE_STATUS_USABLE_AUDIT_V4' and value['status']=='ALL_OBSERVED_MOTHER_COUNTS_CONSERVED'
            and value['job_id']==prepared['job_id'] and value['count_correction_authority']==correction_ref
            and value['per_molecule_reference']==correction['per_molecule_reference']
            and value['source_sha_validation']==prepared['source_sha_validation']
            and value['usability_semantics_provenance']==catalog['usability_semantics_provenance']
            and value['joint_dimensions']==joint_dimensions
            and value['role_status_strictusable_joint_dimensions']==joint_dimensions[:4]
            and set(value['marginals'])==set(value['marginal_totals'])==set(joint_dimensions)
            and value['mother_count']==value['expected_mother_count']==value['mother_unique_ids']==value['joint_total']==expected
            and sum(row['molecules'] for row in value['joint_counts'])==expected
            and value['role_status_strictusable_joint_total']==expected
            and sum(row['molecules'] for row in value['role_status_strictusable_joint_counts'])==expected
            and all(n==expected for n in value['marginal_totals'].values())
            and all(sum(row['molecules'] for row in rows)==expected for rows in value['marginals'].values()),
            'ALL_MOTHER_ROLE_STATUS_USABLE_AGGREGATES_MUST_CONSERVE_REVIEWED_POPULATION')
    C.need(audit['all_mother_ids_sha256']==before['all_mother_ids_sha256']
        and audit['metadata_aggregation_before_validation']==prepared['metadata_aggregation_before_validation']
        and audit['role_status_strictusable_joint_counts']==before['role_status_strictusable_joint_counts']
        and all(audit['marginals'][name]==before['marginals'][name] for name in joint_dimensions[:-2]),
        'SAME_UNFILTERED_MOTHER_BEFORE_AND_AFTER_VALIDATION_REQUIRED')
    C.need(len(tasks_refs)==len(base_refs)==32 and len({item['path'] for item in tasks_refs})==32,'EXACT_UNIQUE32_TASK_AND_BASELINE_REFERENCES_REQUIRED')
    tasks=[I.read(item) for item in tasks_refs];mids=[task['meta']['molecule_id'] for task in tasks]
    C.need(len(set(mids))==32 and mids==authority['selected_molecule_ids'],'EXACT_PREPARED_STABLE_HASH_ROSTER_REQUIRED')
    bases={item['path']:item for item in base_refs}
    for task in tasks:
        C.validate_task(task,authority_ref);base_ref=task['authority_references']['accepted_baseline_evidence']
        C.need(bases.get(base_ref['path'])==base_ref,'BASELINE_PACKET_NOT_IN_PREPARED32')
        base=I.read(base_ref)
        C.need(base['molecule_id']==task['meta']['molecule_id'] and base['source_population_authority']==authority_ref
            and C.sha_value(base['original_row'])==task['baseline_row_sha256']
            and base['original_row']==task['existing_conformers'][0]
            and base['validation']['status']=='ORIGINAL_SOURCE_AND_BASELINE_VALIDATED_NO_NEW_UFF'
            and base['validation']['atomic_numbers']==task['source_atomic_numbers'],'ACTUAL_BASELINE_PACKET_ROW_OR_ATOM_ORDER_DIFFERS')
        I.reserve_task(task)
    # No existing or unknown attempt is implicitly cleared/resubmitted.
    a.ledger_root.mkdir(parents=True,exist_ok=True,mode=0o700)
    consumed=[task['task_key'] for task in tasks if (a.ledger_root/(task['task_key']+'.json')).exists()]
    records=[];errors=[];claims=[];packets=[];index=0;active={}
    if consumed:budget.stop='EXISTING_OR_UNKNOWN_ONCE_KEYS_REQUIRE_ROOT_REVIEW'
    if not consumed:
        with cf.ProcessPoolExecutor(max_workers=16,mp_context=mp.get_context('spawn'),initializer=core.worker_init,
                initargs=(I.ref(I.HERE/'frozen_sources.json'),authority_ref,prepared_ref,admission)) as pool:
            while active or index<len(tasks):
                reserved=sum(I.reserve_task(task) for task in active.values())
                budget.observe(list(pool._processes.values()),reserve=reserved)
                while budget.stop is None and index<len(tasks) and len(active)<16:
                    task=tasks[index];reserved=sum(I.reserve_task(item) for item in active.values())+I.reserve_task(task)
                    budget.observe(list(pool._processes.values()),reserve=reserved)
                    if budget.stop is not None:break
                    try:
                        start_ref=I.claim(task,a.ledger_root,out,proof);claims.append({'task_key':task['task_key'],'start_reference':start_ref})
                        # Claim before dispatch is deliberately conservative: if
                        # submit fails this attempt is unknown, never retried.
                        index+=1;future=pool.submit(core.process_task,task);active[future]=task
                    except Exception as exc:
                        errors.append({'phase':'claim_or_dispatch','task_key':task['task_key'],
                            'error':type(exc).__name__+': '+str(exc),'traceback':traceback.format_exc()})
                        budget.stop='CLAIM_OR_DISPATCH_FAILED_NO_RETRY';break
                if not active:break
                done,_=cf.wait(active,timeout=1,return_when=cf.FIRST_COMPLETED)
                for future in done:
                    task=active.pop(future)
                    try:
                        packet=future.result();record=I.packet_new(out,task,packet,a.ledger_root)
                        records.append(record);packets.append(packet)
                        I.json_new(out/('finished_'+task['task_key']+'.json'),{'schema':'N1_ACTUAL_ATTEMPT_PACKET_DURABLE_V2',
                            'task_key':task['task_key'],'start_reference':next(row['start_reference'] for row in claims if row['task_key']==task['task_key']),
                            'packet':record,'common':False,'pilot_membership':False},[out,a.ledger_root])
                    except Exception as exc:
                        errors.append({'phase':'started_task_or_durable_readback','task_key':task['task_key'],
                            'error':type(exc).__name__+': '+str(exc),'traceback':traceback.format_exc()})
                        budget.stop=budget.stop or 'UNKNOWN_STARTED_TASK_OR_READBACK_FAILURE_NO_RETRY'
    summaries=[packet['summary'] for packet in packets]
    complete=len(records)==32 and len({item['task_key'] for item in records})==32 and not errors and not consumed
    done_keys={item['task_key'] for item in records};claimed={row['task_key'] for row in claims}
    statistics={'actual_optimizer_calls_attempted':sum(row['optimizer_calls_attempted'] for row in summaries),
        'actual_optimizer_calls_finished':sum(row['optimizer_calls_finished'] for row in summaries),
        'actual_candidate_events_in_packets':sum(len(packet['candidate_optimizer_events']) for packet in packets),
        'Pprime_actual2_molecules':sum(row['Pprime_actual_records']==2 for row in summaries),
        'selected_0p5_unique2_molecules':sum(row['selected_unique_at_0p5_A']==2 for row in summaries),
        'below_0p5_fallback_molecules':sum(bool(row['below_dedup_threshold']) for row in summaries),
        'pending_molecules':sum(packet['supplement'] is None for packet in packets),
        'status_counts':dict(collections.Counter(row['status'] for row in summaries)),
        'actual_worker_task_counts':[{'pid':pid,'start_ticks':ticks,'completed':count}
            for (pid,ticks),count in sorted(collections.Counter((packet['runtime']['pid'],packet['runtime']['start_ticks']) for packet in packets).items())]}
    receipt={'schema':'N1_PPRIME2_PILOT32_RECEIPT_V4',
        'status':'ACTUAL32_PACKETS_CLOSED_REQUIRES_SCIENTIFIC_AND_COST_ROOT_REVIEW' if complete else 'INCOMPLETE_PILOT32_NO_RETRY',
        'job_id':str(proof['job_id']),'prepared':prepared_ref,'prepare_actual_terminal':prep_terminal,
        'source_population_authority':authority_ref,'startup_proof':I.ref(a.root_preflight),'test10_receipt':tests_ref,
        'count_correction_authority':correction_ref,'mother_count':expected,'role_status_usable_audit':prepared['role_status_usable_audit'],
        'scientific_ast_proof':I.science_ast_proof(),'configured_workers':16,'expected':32,'claimed':len(claims),
        'completed_durable_readback_packets':len(records),'packets':records,'claims':claims,
        'unknown_started_task_keys':sorted(claimed-done_keys),'unstarted_task_keys':[task['task_key'] for task in tasks[index:]],
        'preexisting_or_unknown_once_keys':consumed,'errors':errors,'statistics':statistics,'budget':budget.report(),
        'elapsed_seconds':time.monotonic()-started,'common':False,'pilot_membership':False,'production_membership':False,
        'final_common_reference':None,'new_QM_calls':0,'old_source_files_modified':False,
        'actual_parent_allocated_core_seconds':None,'actual_all_related_terminal_cost_closure_required':True,
        'C0_is_not_scientific_acceptance':True,'automatic_full_source_population_release':False,
        'original_success_rate_unique_geometry_graph_stereo_and_readback_root_review_required':True}
    final=I.json_new(out/'receipt.json',receipt,budget.roots)
    print(json.dumps({'receipt':final,'status':receipt['status'],'actual2':statistics['Pprime_actual2_molecules'],'common':False}))
    return 0 if complete else 3


if __name__=='__main__':raise SystemExit(main())
