"""Resource-phase entry; original scientific helper objects are direct."""
import argparse,json,math,multiprocessing as mp,os,struct,time,traceback,unittest
from collections import Counter,deque
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from secondary_cpu_queue_v1 import common as Q
from secondary_pubchem_screening_alpha_v1 import run as ORIGINAL,contracts as C,source,kernel,journal,materialize_shards
from secondary_pubchem_screening_alpha_v1.runtime import Budget,Stop,owned_bytes
from .guard import require_startup
from . import phase as A
from .inverse import proof as source_inverse
fixtures=ORIGINAL.fixtures
reference_rows=ORIGINAL.reference_rows
differences=ORIGINAL.differences
scientific=ORIGINAL.scientific
run_group=ORIGINAL.run_group
validate_requested_parts=ORIGINAL.validate_requested_parts


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--plan',type=Path,required=True);parser.add_argument('--startup-proof',type=Path,required=True)
    args=parser.parse_args();plan,proof=require_startup(args.plan,args.startup_proof)
    out=Q.literal(plan['output_directory']);out.mkdir(parents=True,mode=0o700,exist_ok=False);started=time.monotonic()
    budget=None;receipt=None
    try:
        tests,resource_tests,budget=A.startup_phase(lambda:fixtures(out),lambda:A.fixtures3(out),lambda:Budget(plan,proof,out));scope_proof=kernel.verify_source(plan)
        source.write_json(out/'source_scope_proof.json',scope_proof,budget)
        if A.phase(plan)=='QA0':return A.close_qa0(plan,proof,out,tests,resource_tests,scope_proof,budget,started)
        mode=plan['mode'];base={'endpoint':Q.ENDPOINT,'uid':1264,'node':proof['node'],'job_id':str(proof['job_id']),
            'plan_reference':Q.ref(args.plan),'startup_proof_reference':Q.ref(args.startup_proof),'mode':mode,
            'scope_parameters':plan['scope_parameters'],'scope_mode':plan['scope_mode'],'performance_profile':plan['performance_profile'],'fixtures':tests,'source_scope_proof':scope_proof,
            'frozen_manifest_reference':plan['frozen_manifest_reference'],'source_references':plan['source_references'],
            'raw_reference':plan['raw_reference'],'full_source_pool_release_authorized':False,'guide_filtered_dedup_1M_reference_completed':False,
            'old_success_objects_modified':False,'technical_unknown_is_chemical_exclusion':False,'UFF_QM_training_calls':0}
        base.update(resource_phase=A.phase(plan),resource_fixtures=resource_tests,source_inverse_proof=source_inverse())
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
            'resource_phase':A.phase(plan),'resource_phase_observation_failure':A.failure_details(exc,budget),
            'mode':plan['mode'],'error':type(exc).__name__+': '+str(exc),'traceback':traceback.format_exc(),
            'runtime_budget':budget.receipt() if budget else None,'scientific_body_or_completed_feature_success_not_fabricated':True,
            'forced_signals_sent':False,'pool_release_authorized':False,'actual_terminal_parent_cost_pending_Root_accounting':True}
        source.write_json(out/'failure.json',failure);raise
    finally:
        if budget:budget.finish()

if __name__=='__main__':raise SystemExit(main())
