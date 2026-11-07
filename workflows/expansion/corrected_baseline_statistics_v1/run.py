"""Admitted private clone + original full current1M recount; original Common is reused."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sqlite3
from ..alpha_runtime_v1 import common as Q
from ..alpha_runtime_v1.profile import admit
from ..alpha_runtime_v1.guard import Guard
from . import authority,state
MODULE='workflows.expansion.corrected_baseline_statistics_v1.run'


def run(plan_path,startup_proof):
    plan=Q.load(plan_path);proof=Q.load(startup_proof);actual=admit(plan,minimum_workers=16)
    request=proof['request']
    Q.need(plan['schema']=='PUBCHEM_CORRECTED_BASELINE_STATISTICS_PLAN_V1'
        and plan['population_version']==authority.VERSION and plan['scope_key']==request['scope_key']=='corrected_baseline_population_statistics_v1'
        and request['producer_plan_reference']==Q.reference(plan_path)and request['execution_argv']==plan['execution_argv']
        and str(proof['job_id'])==actual['job_id']and proof['uid']==1264
        and proof['boot_id']==Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'Actual new-version statistics startup')
    for path in Path(__file__).parent.glob('*.py'):Q.need(Q.reference(path)in request['source_references'],'Actual new wrapper source pin')
    budget=authority.read(plan['reviewed_storage_budget_reference'])
    Q.need(budget['schema']=='ROOT_ALPHA_ALL_FUTURE_STORAGE_BUDGET_V2'and budget['reviewer']=='root'
        and budget['scope_total_caps_bytes']['reports']==plan['output_cap_bytes']
        and budget['other_future_reserved_bytes_for_each_scope']['reports']==plan['other_future_reserved_bytes']
        and budget['minimum_free_after_all_future_bytes']==plan['minimum_free_bytes'],'Actual reviewed reports aggregate budget')
    guard=Guard(plan);out=Path(plan['output_directory']);out.mkdir(parents=True,exist_ok=True)
    import fcntl
    lock=(out/'wrapper.lock').open('a+b');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    try:
        authority.baseline(plan['corrected_baseline_receipt_reference'],plan['corrected_baseline_actual_reference'])
        review,original=authority.common(plan['common_statistics_actual_reference'])
        from ..distribution_report_v1 import __main__ as runtime,aggregate,io,functional_groups,population_tables,render
        byname={Path(ref['path']).name:ref for ref in original['source_references']}
        Q.need(len(byname)==10,'Exact original statistics_cache10 sources required')
        for ref in byname.values():Q.verify(ref)
        for module in(runtime,aggregate,io,functional_groups,population_tables,render):
            Q.need(Path(module.__file__).resolve()==Path(byname[Path(module.__file__).name]['path']).resolve(),'Actual imported original statistics_cache module, not a patched copy')
        root_scope=dict(current=plan['corrected_baseline_receipt_reference'],review=plan['corrected_baseline_actual_reference'],
            common=plan['common_statistics_actual_reference'],original_statistics_sources=original['source_references'],
            analysis_version=plan['analysis_version'])
        fingerprint=hashlib.sha256(json.dumps(root_scope,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        closed=out/'clone_scope_closed.json';database=out/'counted_statistics.sqlite'
        if closed.exists():
            clone=Q.load(closed);Q.need(clone['scope_fingerprint']==fingerprint,'Same corrected version and closed Common scope required on resume')
        else:
            Q.need(not database.exists(),'Preserve incomplete clone; explicit actual repair before reuse')
            clone=state.clone(review['closed_database_path'],review['closed_database_frame'],database,guard.check)
            clone.update(scope_fingerprint=fingerprint,scope=root_scope);Q.write(closed,clone)
        # Only one unchanged original1M ingest follows. No Common feature rows
        # or old1M rows are sent to the enrichment workers in this run.
        pop_ref=authority.population(plan,out/'corrected_baseline_population.json')
        recipe=authority.read(original['functional_group_recipe_reference'])
        Q.need(functional_groups.recipe()==recipe,'Exact original installed SMARTS/countUnique/statistical recipe')
        derived={**plan,'schema':'EXPANSION_DISTRIBUTION_PLAN_V1','population_manifests':[pop_ref],
            'nearest_manifests':[],'stage':'population_tables'}
        derived_path=out/('original_statistics_derived_plan_'+actual['job_id']+'.json')
        if derived_path.exists():Q.need(Q.load(derived_path)==derived,'Same derived plan for this actual parent required')
        else:Q.write(derived_path,derived)
        # Original runtime's own profile/Guard controls recount and export. This
        # wrapper's actual launcher proof remains bound to plan_path, not to the
        # derived metadata; both references are recorded below without relabel.
        result=runtime.run(derived_path,'population_tables',startup_proof=startup_proof)
        db=sqlite3.connect(database.as_uri()+'?mode=ro',uri=True)
        try:
            db.execute('PRAGMA main.cache_size=-1048576')
            after=state.digest(db,'v1_common',guard.check)
            Q.need(after==clone['Common_logical_digest'],'Every closed Common logical row must remain byte-exact after new1M recount')
            Q.need(dict(db.execute('SELECT name,expected FROM populations WHERE complete=1'))==dict(pubchem_1m=1000000,v1_common=1196122),'Both complete actual populations required')
        finally:db.close()
        guard.sample();guard.check()
        return Q.write(out/'receipt.json',dict(schema='PUBCHEM_CURRENT_BASELINE_WITH_CLOSED_COMMON_STATISTICS_V1',
            status='CURRENT_POPULATION_TABLES_COMPLETE_PENDING_ACTUAL_C0_AND_ROOT_REVIEW',population_version=authority.VERSION,
            corrected_baseline_receipt_reference=plan['corrected_baseline_receipt_reference'],
            corrected_baseline_actual_reference=plan['corrected_baseline_actual_reference'],
            Common_statistics_actual_reference=plan['common_statistics_actual_reference'],
            Common_logical_digest_before=clone['Common_logical_digest'],Common_logical_digest_after=after,
            Common_feature_rows_recomputed=0,old_baseline_or_source_database_modified=False,current1M_fully_recounted=True,
            moment_subtraction_or_statistical_algorithm_change=False,effective_population_recovery_changed=True,
            original_recorded_screening_decisions_changed=False,
            clone_proof_reference=Q.reference(closed),current_population_manifest_reference=pop_ref,
            original_statistics_receipt=result,original_runtime_derived_plan_reference=Q.reference(derived_path),
            actual_launcher_plan_reference=Q.reference(plan_path),startup_proof_reference=Q.reference(startup_proof),
            actual_parent=actual,runtime=guard.receipt(),exact_nearest_or_R_N_or_training_release=False))
    finally:guard.close();lock.close()


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',required=True,type=Path);p.add_argument('--startup-proof',required=True,type=Path)
    a=p.parse_args();run(a.plan,a.startup_proof)


if __name__=='__main__':main()
