"""Three finite CPU stages, exact scientific kernel, append-only rows and no pool release."""
import argparse,json,math,multiprocessing as mp,os,struct,time,traceback,unittest
from collections import Counter,deque
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from secondary_cpu_queue_v1 import common as Q
from . import contracts as C,source,kernel,journal,materialize_shards
from .runtime import Budget,Stop,owned_bytes
from .guard import require_startup


def fixtures(out):
    from . import test_v1
    test_v1.TEST_ROOT=out;suite=unittest.defaultTestLoader.loadTestsFromTestCase(test_v1.Boundaries)
    Q.need(suite.countTestCases()==5,'EXACT_FIVE_NEW_PURE_FIXTURES_REQUIRED')
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    value={'tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'skips':len(result.skipped),
        'expected_failures':len(result.expectedFailures),'unexpected_successes':len(result.unexpectedSuccesses),'scientific_body_reads':0}
    source.write_json(out/'fixtures5.json',value)
    Q.need(result.wasSuccessful() and result.testsRun==5 and not(result.skipped or result.expectedFailures or result.unexpectedSuccesses),'FIVE_FIXTURES_PASS_BEFORE_ANY_DATA_BODY')
    return value


def reference_rows(reference,budget):
    path=source.verify(reference,budget);records={};counts=Counter()
    with path.open('rb') as stream:
        for raw in iter(lambda:stream.readline(C.CONTAINER_CAP//32+1),b''):
            budget.check();Q.need(len(raw)<=C.CONTAINER_CAP//32 and raw.endswith(b'\n'),'FINITE_COMPLETE_MAIN_JOURNAL_ROW')
            value=json.loads(raw);ordinal=value['input']['ordinal'];Q.need(ordinal not in records and len(records)<10000,'ONLY_EXACT_MAIN10000_REFERENCE_OBJECTS')
            records[ordinal]=value;counts[value['category']]+=1
    Q.need(sorted(records)==source.sample() and len(records)==10000 and dict(counts)=={'accepted':8773,'chemReject':1223,'technicalUnresolved':4},
        'ACTUAL_MAIN_JOURNAL_FIXED_SEED_ORDINAL_SET_AND_THREE_STATES_REQUIRED')
    return records


def differences(a,b,path='$'):
    if type(a) is not type(b):return [path+':TYPE']
    if isinstance(a,float):return [] if struct.pack('<d',a)==struct.pack('<d',b) else [path+':BINARY64']
    if isinstance(a,dict):
        if set(a)!=set(b):return [path+':KEYS']
        return [item for key in sorted(a) for item in differences(a[key],b[key],path+'.'+key)]
    if isinstance(a,list):
        if len(a)!=len(b):return [path+':LENGTH']
        return [item for index,(x,y) in enumerate(zip(a,b)) for item in differences(x,y,path+'['+str(index)+']')]
    return [] if a==b else [path+':VALUE']


def scientific(value):
    row=value['input'];parts=row['source_part']
    return {'input':{key:row[key] for key in ('ordinal','part_index','offset_bytes','source_row_bytes','smiles_bytes','cid_source_ascii','source_smiles','source_smiles_sha256','source_row_sha256','source_terminator_hex')},
        'source_part_bytes':parts['bytes'],'source_part_sha256':parts['sha256'],'category':value['category'],
        'technical_codes':value['technical_codes'],'audit_parse_succeeded':value['audit_parse_succeeded'],'audit_flags':value['audit_flags'],
        'legacy_dispatcher_result':value['legacy_dispatcher_result'],
        'exception_type_and_message':{key:{name:error.get(name) for name in ('type','message')} for key,error in value['errors'].items()}}


def run_group(pool,records,group,out,budget,worker_stop,reference=None):
    writer=journal.Writer(out,group,budget);pending=deque();seen=compared=mismatches=0
    detail=(out/(group+'.comparison.jsonl')).open('xb') if reference is not None else None
    def collect():
        nonlocal compared,mismatches
        original,future=pending.popleft();error=None
        try:value=future.result()
        except Exception as exc:value=None;error={'type':type(exc).__name__,'message':str(exc),'traceback':traceback.format_exc()}
        value=writer.complete(original,value,error)
        if reference is not None:
            ordinal=original['ordinal'];Q.need(ordinal in reference,'ALPHA_ORDINAL_NOT_IN_FIXED_MAIN_REFERENCE')
            diff=differences(scientific(reference[ordinal]),scientific(value));compared+=1;mismatches+=bool(diff)
            journal.append(detail,{'ordinal':ordinal,'scientific_equal':not diff,'different_field_paths':diff,
                'worker_timing_PID_traceback_source_paths_excluded_as_provenance':True},budget,drain=True)
    try:
        for original in records:
            if budget.stop.is_set():worker_stop.set();break
            budget.check();writer.dispatch(original)  # Complete source row is durable BEFORE submit.
            pending.append((original,pool.submit(kernel.chemical_task,original)));seen+=1
            if len(pending)>=32:collect()
        while pending:
            if budget.stop.is_set():worker_stop.set()
            collect()
    finally:
        while pending:collect()
        result=writer.close()
        if detail is not None:detail.flush();os.fsync(detail.fileno());detail.close()
    result['expected_reference_rows']=len(reference) if reference is not None else None
    result['comparison']={'compared_rows':compared,'scientific_mismatches':mismatches,
        'method':'ALL_FIELDS_TYPED_BINARY64_NO_NUMERIC_TOLERANCE','Main_body_unchanged':True,
        'different_part_path_is_declared_physical_relocation_not_scientific_field':True}
    result['actual_input_rows_dispatched']=seen
    source.write_json(out/(group+'.receipt.json'),result)
    return result


def validate_requested_parts(plan,parts):
    chosen=parts[plan['first_part']:plan['last_part']+1]
    Q.need(chosen and chosen[0]['first_ordinal']==plan['first_ordinal'] and chosen[-1]['last_ordinal']==plan['last_ordinal']
        and sum(row['records'] for row in chosen)==plan['last_ordinal']-plan['first_ordinal']+1,'FROZEN_MANIFEST_MATCHES_ACTUAL_INDEX_BOUNDARIES')
    return chosen


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--plan',type=Path,required=True);parser.add_argument('--startup-proof',type=Path,required=True)
    args=parser.parse_args();plan,proof=require_startup(args.plan,args.startup_proof)
    out=Q.literal(plan['output_directory']);out.mkdir(parents=True,mode=0o700,exist_ok=False);started=time.monotonic()
    budget=None;receipt=None
    try:
        budget=Budget(plan,proof,out);tests=fixtures(out);scope_proof=kernel.verify_source(plan)
        source.write_json(out/'source_scope_proof.json',scope_proof,budget)
        mode=plan['mode'];base={'endpoint':Q.ENDPOINT,'uid':1264,'node':proof['node'],'job_id':str(proof['job_id']),
            'plan_reference':Q.ref(args.plan),'startup_proof_reference':Q.ref(args.startup_proof),'mode':mode,
            'scope_parameters':plan['scope_parameters'],'scope_mode':plan['scope_mode'],'performance_profile':plan['performance_profile'],'fixtures':tests,'source_scope_proof':scope_proof,
            'frozen_manifest_reference':plan['frozen_manifest_reference'],'source_references':plan['source_references'],
            'raw_reference':plan['raw_reference'],'full_source_pool_release_authorized':False,'guide_filtered_dedup_1M_reference_completed':False,
            'old_success_objects_modified':False,'technical_unknown_is_chemical_exclusion':False,'UFF_QM_training_calls':0}
        if mode=='inventory':
            inventory=source.inventory(plan,out,budget)
            receipt={**base,'schema':'ALPHA_PUBCHEM_PHYSICAL_INVENTORY_RECEIPT_V1','status':'ALPHA_PHYSICAL500_COMPLETE_NO_CHEMISTRY',
                'inventory':inventory,'single_stream_reader_processes':1,'sixteen_chemical_or_gzip_workers_claimed':False}
        else:
            inventory,parts=source.load_inventory(plan,budget)
            context=mp.get_context('spawn');worker_stop=context.Event()
            with ProcessPoolExecutor(max_workers=16,mp_context=context,initializer=kernel.initialize,
                    initargs=(worker_stop,context.Barrier(16),str(out/'worker_logs'))) as pool:
                if mode=='profile':
                    reference=reference_rows(plan['main_uniform_journal_reference'],budget)
                    uniform=run_group(pool,source.read_selected(parts,inventory['inventory']['uniform_locators'],budget),
                        'uniform10000',out,budget,worker_stop,reference)
                    Q.need(uniform['completed_rows']==10000 and uniform['dispatched_rows']==10000 and uniform['comparison']['compared_rows']==10000,'COMPLETE10000_PROFILE_ROWS')
                    Q.need(len(uniform['worker_records'])==16 and min(uniform['worker_records'].values())>0,'ACTUAL16_NONEMPTY_UNIFORM_CHEMICAL_WORKERS_REQUIRED')
                    longest=run_group(pool,source.read_selected(parts,inventory['inventory']['longest_locators'],budget),
                        'longest16',out,budget,worker_stop)
                    Q.need(longest['completed_rows']==16,'INDEPENDENT_LONGEST16_DIAGNOSTIC_COMPLETE')
                    draft=materialize_shards.proposed(parts,inventory['inventory']['source_index'],plan['alpha_inventory_receipt_reference'])
                    draft_ref=source.write_json(out/'proposed_full_partition_not_authorized.json',draft,budget)
                    equal=uniform['comparison']['scientific_mismatches']==0
                    receipt={**base,'schema':'ALPHA_PUBCHEM_UNIFORM_PROFILE_RECEIPT_V1',
                        'status':'ALPHA_UNIFORM10000_EQUIVALENT_PROFILE_COMPLETE' if equal else 'ALPHA_UNIFORM10000_SCIENTIFIC_MISMATCH_HOLD',
                        'uniform':uniform,'longest_diagnostic':longest,'longest_excluded_from_uniform_mean':True,'comparison':uniform['comparison'],
                        'reference_journal':plan['main_uniform_journal_reference'],'proposed_full_partition':draft_ref,
                        'profile_phase_allocation_not_substituted_for_measured_CPU':True,'full_output_budget_not_frozen_by_this_profile':True}
                else:
                    selected=validate_requested_parts(plan,parts);claim=materialize_shards.claim(plan,proof)
                    def rows():
                        for part in selected:yield from source.iter_part(part,budget)
                    result=run_group(pool,rows(),'full_shard',out,budget,worker_stop)
                    expected=plan['last_ordinal']-plan['first_ordinal']+1
                    complete=result['completed_rows']==result['dispatched_rows']==expected and sum(result['counts'].values())==expected and not budget.stop.is_set()
                    receipt={**base,'schema':'ALPHA_PUBCHEM_ORDINAL_FEATURE_SHARD_RECEIPT_V1',
                        'status':'ALPHA_ORDINAL_SHARD_ROWS_CLOSED_NO_POOL_RELEASE' if complete else 'ALPHA_ORDINAL_SHARD_PARTIAL_UNREAD_ROWS_RETAINED',
                        'claim_reference':claim,'first_ordinal':plan['first_ordinal'],'last_ordinal':plan['last_ordinal'],
                        'expected_rows':expected,'result':result,'source_row_conservation':complete,
                        'unread_rows':expected-result['dispatched_rows'],'all_full_features_recovered_claimed':False}
            for path in (out/'worker_logs').glob('*.log'):
                with path.open('rb') as stream:os.fsync(stream.fileno())
            receipt['native_worker_log_references']=[source.pin(path) for path in sorted((out/'worker_logs').glob('*.log'))]
        receipt['runtime_budget']=budget.receipt();receipt['wall_seconds']=time.monotonic()-started
        receipt['actual_owned_output_bytes_before_final_receipt']=owned_bytes(out)
        receipt['cost_decision_reference']=plan['cost_decision_reference'];receipt['cost_overrun_action']='REPORT_AND_CONTINUE'
        receipt['actual_terminal_parent_cost_pending_Root_accounting']=True
        source.write_json(out/'receipt.json',receipt)
        print(json.dumps({'receipt_reference':source.pin(out/'receipt.json'),'status':receipt['status'],'pool_release_authorized':False}))
        return 0 if receipt['status'] in {'ALPHA_PHYSICAL500_COMPLETE_NO_CHEMISTRY','ALPHA_UNIFORM10000_EQUIVALENT_PROFILE_COMPLETE','ALPHA_ORDINAL_SHARD_ROWS_CLOSED_NO_POOL_RELEASE'} else 3
    except BaseException as exc:
        failure={'schema':'ALPHA_PUBCHEM_STAGE_FAILURE_V1','status':'FAILED_OR_PARTIAL_ALL_ARTIFACTS_RETAINED','job_id':str(proof['job_id']),
            'mode':plan['mode'],'error':type(exc).__name__+': '+str(exc),'traceback':traceback.format_exc(),
            'runtime_budget':budget.receipt() if budget else None,'scientific_body_or_completed_feature_success_not_fabricated':True,
            'forced_signals_sent':False,'pool_release_authorized':False,'actual_terminal_parent_cost_pending_Root_accounting':True}
        source.write_json(out/'failure.json',failure);raise
    finally:
        if budget:budget.finish()

if __name__=='__main__':raise SystemExit(main())
