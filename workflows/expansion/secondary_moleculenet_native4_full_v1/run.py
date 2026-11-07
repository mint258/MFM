"""Actual full physical inventory attempt, unchanged native worker, no pool release."""
import argparse,io,json,os,sys,time,traceback,unittest
from pathlib import Path
from secondary_moleculenet_csv6_identity_v1.runtime import Budget,owned_bytes
from secondary_moleculenet_csv6_identity_v1 import journal as J
from . import contracts as C,guard as G,full as F
Q=C.Q


def fixtures(out):
    from .test_v1 import Boundaries
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(Boundaries);Q.need(suite.countTestCases()==3,'EXACT_NEW3_FULL_BOUNDARIES')
    s=io.StringIO();r=unittest.TextTestRunner(stream=s,verbosity=2).run(suite);v={'tests_run':r.testsRun,'failures':len(r.failures),'errors':len(r.errors),'skips':len(r.skipped),
        'expected_failures':len(r.expectedFailures),'unexpected_successes':len(r.unexpectedSuccesses),'transcript':s.getvalue(),
        'before_any_original_DATA_and_Budget':True,'old_B3_native3_audit3_reexecuted':False,'graph_parse_key_UFF_QM_calls':0}
    Q.write_new(out/'fixtures3.json',v);Q.need(r.wasSuccessful() and r.testsRun==3 and not(r.skipped or r.expectedFailures or r.unexpectedSuccesses),'NEW_PURE3_BEFORE_DATA_MONITOR');return v


def imports(plan):
    for name,module in list(sys.modules.items()):
        p=getattr(module,'__file__',None)
        if p and Path(p).suffix=='.py' and (name.startswith('secondary_') or name=='workflows' or name.startswith('workflows.')):
            Q.need(C.ROOT/'code' in Path(p).absolute().parents and Q.ref(p) in plan['source_references'],'ALL_ACTUAL_TRANSITIVE_SOURCE_FILES:'+name)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',type=Path,required=True);p.add_argument('--startup-proof',type=Path,required=True);args=p.parse_args()
    plan,proof=G.require_startup(args.plan,args.startup_proof);parent,census,oldplan=C.inputs(plan)
    out=Q.literal(plan['output_directory']);Q.need(C.ROOT/'artifacts' in out.parents and not out.exists(),'NEW_FULL_INVENTORY_OUTPUT');out.mkdir(parents=True,mode=0o700)
    started=time.monotonic();budget=None;inputs=None;ledger=None;once=None;fx=None;stage='NEW_FIXTURES'
    try:
        fx=fixtures(out);imports(plan)
        # Original monitor and drain constants; reserve admin inside whole4GiB.
        budget_plan={**plan,'output_cap_bytes':C.SCIENCE_CAP};budget=Budget(budget_plan,proof,out)
        stage='FIVE_CLOSED_SOURCE_SHA_AND_CENSUS';inputs=F.Inputs(plan['data_references'],budget);ledger=F.Ledger(out,budget)
        counts,ids=F.bind_context(inputs,ledger,census);selected=inputs.selection();reused,old_audit=F.bind_profile(inputs,ledger,selected)
        F.coverage(census,counts,ids,reused);inputs.check()
        integrity=J.write_json(out/'closed_context_readback.json',{'schema':'NATIVE4_FULL_CLOSED_CONTEXT_READBACK_V1','five_current_whole_SHA_stable_FD_verified':True,
            'input_references':plan['data_references'],'frames':[list(v) for v in inputs.frames],'source_census':census,'SDF_physical_population':39633,
            'old3195_source_result_selection_index_exact':True,'old_profile_reducer_counts':old_audit,'original_relationship_checks':parent['relationship_checks'],
            'mapping_gaps_are_not_repaired_or_identity_accepted':True,'sqlite_readonly_immutable_is_not_itself_closure_proof':True},budget)
        native,functions,kernel=F.load_native(plan);ledger.functions=functions;imports(plan);kernel_ref=J.write_json(out/'original_kernel_proof.json',kernel,budget)
        stage='GLOBAL_ONCE_REGISTER';once=F.register_once(plan,proof,out)
        stage='OLD3195_REUSE_AND_NEW36438_TASKS';profile=F.key_inventory(plan,inputs,ledger,budget,native)
        stage='ALL_ENTITY_AND_INDEX_CONTEXT_UNIONS';unions=F.unions(inputs,ledger,out,budget);index=F.index_relations(inputs,out,budget)
        Q.need(unions['physical_native_records']==sum(census[s]['SDF']+census[s]['MOL2'] for s in C.IDS)
            and index['all_ID_rows_by_source']=={s:census[s]['IDs'] for s in C.IDS},'ALL_NATIVE_MOL2_ID_CONTEXTS_PRESERVED')
        inputs.check();budget.sample();Q.need(budget.reason is None,'RESOURCE_STOP_CANNOT_CLAIM_FULL_CLOSURE');outputs=ledger.close();ledger=None
        whole_bytes=owned_bytes(out)+(once['bytes'] if once else 0);Q.need(whole_bytes<C.CAP,'SCIENCE_PLUS_ONCE_ADMIN_WITHIN_WHOLE4GIB')
        receipt={'schema':'SECONDARY_NATIVE4_FULL_PHYSICAL_INVENTORY_RECEIPT_V1','status':'ALL39633_SDF_ATTEMPT_RESULTS_AND_ORIGINAL_CONTEXT_RECORDED_UNKNOWNS_RETAINED',
            'job_id':str(proof['job_id']),'uid':1264,'endpoint':Q.ENDPOINT,'node':plan['node'],'plan_reference':Q.ref(args.plan),'startup_proof_reference':Q.ref(args.startup_proof),
            'native_profile_receipt_reference':plan['native_profile_receipt_reference'],'native_profile_accounting_reference':plan['native_profile_accounting_reference'],
            'accepted_audit_receipt_reference':plan['accepted_audit_receipt_reference'],'accepted_audit_accounting_reference':plan['accepted_audit_accounting_reference'],
            'scope_parameters':plan['scope_parameters'],'fixtures':fx,'closed_context_readback_reference':integrity,'kernel_proof_reference':kernel_ref,
            'population_once_reference':once,'native_result_inventory':profile,'outputs':outputs,'entity_unions':unions,'all_original_index_relations':index,
            'actual_owned_science_and_control_bytes_before_receipt':whole_bytes,'algorithm_science_subcap_bytes':C.SCIENCE_CAP,'registered_whole_output_cap_bytes':C.CAP,
            'runtime':budget.receipt(),'elapsed_seconds':time.monotonic()-started,'original3195_results_including_UNKNOWNs_unchanged':True,
            'MOL2_graph_charge_stereo':'UNKNOWN_NO_GRAPH_PARSER_OR_PARTIAL_CHARGE_INFERENCE','old_or_new_UNKNOWN_is_chemical_rejection':False,
            'original_component_ID_gaps_and_all_conformers_preserved':True,'mapping_or_full_inventory_closure_is_identity_acceptance':False,
            'Parquet_full_keys_source_SMILES_only_native_union_in_native_result_index_and_entity_unions':True,
            'new_network_UFF_QM_calls':0,'automatic_fallback_policy_graph_pool_decontamination_training_release':False,
            'actual_new_parent_terminal_cost_pending_Root':True,'cost_overrun_action':'REPORT_AND_CONTINUE','prior677_seconds_is_not_pure_key_timing_or_worst_bound':True}
        J.write_json(out/'receipt.json',receipt,budget);print(json.dumps({'status':receipt['status'],'receipt_reference':J.pin(out/'receipt.json')}));return 0
    except BaseException as exc:
        partial=None
        if ledger:
            try:partial=ledger.close()
            except BaseException as close_exc:partial={'close_error':type(close_exc).__name__+': '+str(close_exc),'all_output_paths_and_durable_prefixes_retained':True,'unclosed_outputs_not_pinned_as_complete':True}
            ledger=None
        Q.write_new(out/'failure.json',{'schema':'NATIVE4_FULL_PARTIAL_PREFIX_RETAINED_V1','status':'HOLD_NOT_ALL_PHYSICAL_INVENTORY_CLOSED',
            'stage':stage,'error':type(exc).__name__+': '+str(exc),'traceback':traceback.format_exc(),'fixtures':fx,'population_once_reference':once,
            'outputs':partial,'runtime':budget.receipt() if budget else None,'unfinished_claims_not_retried_or_removed':True,
            'original_results_modified':False,'scientific_or_pool_release':False,'actual_parent_cost_pending_Root':True})
        raise
    finally:
        if ledger:ledger.close()
        if inputs:inputs.close()
        if budget:budget.finish()


if __name__=='__main__':raise SystemExit(main())
