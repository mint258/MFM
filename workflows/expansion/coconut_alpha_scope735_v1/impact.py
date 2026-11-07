"""Whole corrected-pool effect of the accepted735 ledger's three exact compositions."""
import argparse
import json
import os
from pathlib import Path
import sys
import traceback
from workflows.expansion.coconut_alpha_cached735_v1 import support as S
from .run import native_parent,rows


from .impact_sql import query

def admit(plan,proof,pp,sp):
    from workflows.expansion.alpha_runtime_v1 import profile
    authority=profile.admit(plan,minimum_workers=16)
    S.need(plan['schema']=='ALPHA_COCONUT735_CORRECTED_POOL_IMPACT_PLAN_V1'
        and plan['scope_key']==proof['request']['scope_key']=='alpha_coconut735_corrected_pool_impact_v1'
        and proof['request']['producer_plan_reference']==S.pin(pp)
        and proof['request']['execution_argv']==plan['execution_argv']
        and plan['execution_argv'][-4:]==sys.argv[-4:]==['--plan',str(pp),'--startup-proof',str(sp)]
        and proof['endpoint']==plan['endpoint']=='218.192.171.238:22'
        and proof['uid']==plan['uid']==os.getuid()==1264
        and str(proof['job_id'])==os.environ.get('SLURM_JOB_ID')
        and proof['boot_id']==Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'EXACT_ALPHA_IMPACT_SCOPE_JOB_BOOT')
    declared={r['path']:r for r in proof['request']['source_references']}
    for file in [*Path(__file__).parent.glob('*.py'),Path(S.__file__)]:
        S.need(declared.get(str(file.absolute()))==S.pin(file),'EXACT_NEW_IMPACT_AND_LEDGER_MODULES')
    for ref in plan['code_references']:S.read(ref,2<<20)
    return authority


def execute(plan,proof,guard,out):
    from workflows.expansion.pubchem_generic_recovery_overlay_v1 import reader as R
    from workflows.expansion.alpha_closed500_handoff_v1.sql import connection,SQLStopper
    from workflows.expansion.coconut735_recovery_v1 import consumer as C
    # Every borrowed source body must belong to this actual sealed invocation.
    declared=proof['request']['source_references']
    import inspect
    for function in (R.validate_header,R.bind,R.finish,connection,SQLStopper,C.identity_keys):
        S.need(S.pin(inspect.getsourcefile(function)) in declared,'DECLARED_UNCHANGED_OVERLAY_READER_AND_V3_COMPOSITION_OBJECTS')
    ledger_ref=plan['ledger_receipt_reference'];ledger=S.load(ledger_ref)
    native_parent(S.load(plan['ledger_actual_accounting_reference']),ledger_ref,ledger['profile_admission']['job_id'])
    S.need(ledger['schema']=='ALPHA_COCONUT735_APPROVED_SCOPE_LEDGER_PRODUCER_V1'
        and ledger['result']['disposition_counts']=={'EXACT_COMPOSITION_COVERED':3,'APPROVED_SOURCE_SCOPE_DISPOSITION':732}
        and ledger['result']['new_graph_identities']==0 and ledger['result']['new_lower_bound_rules']==0,
        'ACTUAL_COMPLETE_SOURCE_LEDGER_NOT_PARTIAL_PROPOSAL')
    coverage_ref=ledger['result']['coverage_reference'];coverage=S.load(coverage_ref)
    overlay_ref=ledger['result']['overlay_reference'];compositions=[]
    for row in rows(overlay_ref):
        keys=C.identity_keys(row)
        S.need(row['inchikeys']==[] and len(keys)==1 and keys[0][0]=='composition'
               and C.vector(row['non_h_composition']),'ORIGINAL_FINITE_EXACT_COMPOSITION_ONLY_NOT_EMPTY_BOUND')
        compositions.append((row['source_id'],keys[0][1]))
    S.need(len(compositions)==3,'ALL_THREE_ACCEPTED_COMPOSITION_RULES')
    dispositions=rows(coverage['physical_dispositions'])
    S.need(len(dispositions)==735 and sum(r['new_exclusion_status']=='APPROVED_SOURCE_SCOPE_DISPOSITION' for r in dispositions)==732,
        'COMPLETE_PHYSICAL_SOURCE_LEDGER_REFERENCED_IN_IMPACT')
    pool_ref=plan['source_pool_receipt_reference'];pool=R.validate_header(S.load(pool_ref))
    db=connection(out,plan['workers'],plan['duckdb_memory_bytes']);stop=SQLStopper(db,guard.check)
    witnesses=[]
    try:
        witnesses=R.bind(db,pool,guard.check)
        result=query(db,compositions,pool['unique_full_keys'])
        guard.check();R.finish(witnesses)
        S.need(S.load(pool_ref)==pool,'UNCHANGED_ROOT_SEALED_CORRECTED_POOL_AUTHORITY')
        result.update(source_pool_receipt_reference=pool_ref,population_version=pool['population_version'],
            ledger_receipt_reference=ledger_ref,ledger_actual_accounting_reference=plan['ledger_actual_accounting_reference'],
            accepted_composition_reference=overlay_ref,physical735_coverage_reference=coverage_ref,
            all_original735_UNKNOWN_retained=True,original_legacy_sources_modified=False,
            candidate_rows_or_chemical_fields_modified=False)
        return result
    finally:stop.close();db.close()


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',required=True,type=Path)
    p.add_argument('--startup-proof',required=True,type=Path);a=p.parse_args()
    plan=json.loads(a.plan.read_text());proof=json.loads(a.startup_proof.read_text())
    authority=admit(plan,proof,a.plan,a.startup_proof)
    from workflows.expansion.alpha_runtime_v1.guard import Guard
    guard=Guard(plan);out=Path(plan['output_directory'])
    try:
        out.mkdir(parents=True,exist_ok=False)
        import io,unittest
        text=io.StringIO();tested=unittest.TextTestRunner(stream=text,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromName(__package__+'.test_source'))
        S.need(tested.testsRun==2 and tested.wasSuccessful() and not tested.skipped,'TWO_LEDGER_AND_WHOLE_POPULATION_SQL_FIXTURES')
        fixture=S.save(out/'source_tests.json',dict(tests=tested.testsRun,failures=len(tested.failures),errors=len(tested.errors),transcript=text.getvalue()))
        result=execute(plan,proof,guard,out);result['source_tests_reference']=fixture;guard.sample()
        ref=S.save(out/'coconut735_exact_composition_full_pool_impact.json',result)
        S.save(out/'receipt.json',dict(schema='ALPHA_COCONUT735_CORRECTED_POOL_IMPACT_PRODUCER_V1',
            status='WHOLE_CORRECTED_POOL_IMPACT_CLOSED_PENDING_ACTUAL_C0_AND_ROOT_REVIEW',
            plan_reference=S.pin(a.plan),startup_proof_reference=S.pin(a.startup_proof),
            profile_admission=authority,result_reference=ref,result=result,runtime=guard.receipt(),
            all11_index_or_filter_ready=False,actual_parent_C0_pending_root_readback=True,global_pool_release=False))
    except BaseException as exc:
        if out.is_dir():S.save(out/'failure.json',dict(error=repr(exc),traceback=traceback.format_exc(),partials_retained=True))
        raise
    finally:guard.close()


if __name__=='__main__':main()

