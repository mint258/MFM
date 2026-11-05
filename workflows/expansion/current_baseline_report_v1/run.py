"""Admitted current190 state reuse + actual full1M coverage + unchanged baseline report."""
import argparse
import json
from pathlib import Path
import sqlite3
from ..alpha_runtime_v1 import common as Q
from ..alpha_runtime_v1.profile import admit
from ..alpha_runtime_v1.guard import Guard
from ..corrected_baseline_statistics_v1 import authority
from ..corrected_baseline_statistics_v1 import state as original_state
from ..pubchem_generic_recovery_overlay_v1.runtime import actual_parent,VERSION
from . import state

STATISTICS_SHA='62419f8391a004ba55c2a1e4b8447494fdcfe49001a18c674b1d6bd927869d40'


def read(ref):return authority.read(ref)


def statistics(ref):
    Q.need(ref['bytes']==6683 and ref['sha256']==STATISTICS_SHA,'Actual accepted current190 statistics authority required')
    review=read(ref);producer=read(review['producer_receipt_reference']);original=read(review['original_population_tables_receipt_reference'])
    Q.need(review['schema']=='ROOT_ALPHA_CURRENT_BASELINE_WITH_COMMON_STATISTICS_ACTUAL_ACCEPTANCE_V1'
      and review['status']=='ACCEPTED_CURRENT_1M_AND_COMPLETE_COMMON_POPULATION_STATISTICS'
      and review['reviewer']=='root' and review['population_version']==VERSION
      and actual_parent(review)['JobIDRaw']=='1885190'
      and review['populations']==dict(pubchem_1m=1000000,v1_common=1196122)
      and review['Common_logical_digest_before']==review['Common_logical_digest_after']
      and producer['actual_parent']['job_id']=='1885190' and producer['population_version']==VERSION
      and producer['original_statistics_receipt']==original
      and producer['current1M_fully_recounted'] is True and producer['Common_feature_rows_recomputed']==0,
      'Complete corrected1M/fullCommon native statistics, never historical1M relabel')
    q=authority.baseline(review['corrected_baseline_receipt_reference'],review['corrected_baseline_actual_reference'])
    refs=original['population_manifest_references']
    Q.need(set(refs)=={'pubchem_1m','v1_common'} and refs['pubchem_1m']==producer['current_population_manifest_reference'],
      'Exact original190 population manifests must remain the DB identity bindings')
    query=read(refs['pubchem_1m']);common=read(refs['v1_common'])
    Q.need(query['authority_reference']==review['corrected_baseline_receipt_reference']
      and query['population_version']==VERSION and common['expected_molecules']==1196122
      and common['is_sample'] is False and common['population_roles']==['TRAIN','VAL'],
      'Same corrected183 query and complete Common population required')
    return review,original,refs,q,common


def nearest(plan,review,refs,common,out):
    ref=plan['nearest_receipt_reference'];native=read(ref);actual=read(plan['nearest_actual_review_reference'])
    parent=actual_parent(actual)
    Q.need(actual['schema']=='ROOT_ALPHA_FIXED1M_SCIENTIFIC_COVERAGE_ACTUAL_ACCEPTANCE_V1'
      and actual['status']=='APPROVED_COMPLETE_CORRECTED_1M_TO_FULL_COMMON_EXACT_COVERAGE'
      and actual['reviewer']=='root' and actual['producer_receipt_reference']==ref
      and actual['queries']==1000000 and actual['reference_molecules']==1196122
      and actual['nearest_similarity_exact'] is True
      and actual['baseline_receipt_reference']==native['baseline_receipt']==review['corrected_baseline_receipt_reference']
      and actual['reference_manifest_reference']==native['reference_manifest'],
      'Actual Root-reviewed full1M exact coverage C0 required; this adapter grants no acceptance')
    Q.need(native['schema']=='EXPANSION_EXACT_SCIENTIFIC_COVERAGE_V1' and native['status']=='COMPLETE'
      and native['nearest_similarity_exact'] is True and native['fingerprint_recipe']=='ECFP4_2048_radius2_chiralityFalse_rdkit2025.09.5'
      and native['reference_role']=='before' and native['queries']==native['projection']['rows']==1000000
      and native['reference_molecules']==1196122 and native['decontamination_applied_to_sample'] is False,
      'Actual complete scientific before coverage, never novelty/sample approximation')
    proof=read(native['launcher_startup_proof_reference'])
    Q.need(str(proof['job_id'])==str(parent['JobIDRaw']) and proof['uid']==1264
      and proof['request']['producer_plan_reference']==native['resource_plan'],
      'Actual allocated NN startup/producer/accounting must agree')
    packed=read(native['reference_manifest'])
    Q.need(packed['schema']=='expansion_exact_ecfp4_reference_v1' and packed['status']=='COMPLETE'
      and packed['molecules']==1196122 and packed['input_manifest']==common['authority_reference']
      and packed['fingerprint_recipe']==native['fingerprint_recipe'],
      'NN complete Common reference must be the authority of the retained Common statistics')
    evidence=dict(schema='PUBCHEM_NATIVE_COVERAGE_DISTRIBUTION_BINDING_V1',status='COMPLETE',
      native_scientific_coverage_receipt_reference=ref,native_actual_review_reference=plan['nearest_actual_review_reference'],
      actual_parent=parent,actual_accounting_reference=actual['actual_accounting_reference'],
      queries=1000000,nearest_similarity_exact=True,query_population_manifest_reference=refs['pubchem_1m'],
      reference_population_manifest_references=[refs['v1_common']],native_receipt_or_projection_modified=False,
      binding_only_not_an_independent_NN_recomputation=True)
    eref=Q.write(out/'exactNN_population_binding.json',evidence)
    result=dict(schema='EXPANSION_EXACT_NEAREST_DISTRIBUTION_V1',status='COMPLETE',comparison='pubchem_to_v1',
      nearest_similarity_exact=True,fingerprint_recipe=native['fingerprint_recipe'],query_population='pubchem_1m',
      query_population_manifest_reference=refs['pubchem_1m'],reference_populations=['v1_common'],
      reference_population_manifest_references=[refs['v1_common']],expected_queries=1000000,
      producer_evidence_reference=eref,results=dict(identity_column='full_key',artifacts=[{
        **native['projection'],'format':'jsonl'}]),value_column='nearest_reference_tanimoto',
      original_scientific_coverage_receipt_reference=ref,population_version=VERSION,
      statistics_actual_review_reference=plan['statistics_actual_review_reference'])
    return Q.write(out/'exactNN_distribution_manifest.json',result)


def run(plan_path,startup_proof):
    plan=Q.load(plan_path);proof=Q.load(startup_proof);actual=admit(plan,minimum_workers=16);request=proof['request']
    Q.need(plan['schema']=='PUBCHEM_CURRENT_BASELINE_REPORT_PLAN_V1' and plan['population_version']==VERSION
      and plan['scope_key']==request['scope_key']=='current_baseline_exact_distribution_report_v1'
      and request['producer_plan_reference']==Q.reference(plan_path) and request['execution_argv']==plan['execution_argv']
      and str(proof['job_id'])==actual['job_id'] and proof['uid']==1264
      and proof['endpoint']==actual['endpoint']=='218.192.171.238:22'
      and proof['boot_id']==Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'Actual report launcher/profile binding')
    for p in [*Path(__file__).parent.glob('*.py'),Path(authority.__file__),
              Path(original_state.__file__)]:
        Q.need(Q.reference(p) in request['source_references'],'Actual wrapper and reused state-helper source pin')
    budget=read(plan['reviewed_storage_budget_reference'])
    Q.need(budget['schema']=='ROOT_ALPHA_ALL_FUTURE_STORAGE_BUDGET_V2' and budget['reviewer']=='root'
      and budget['scope_total_caps_bytes']['reports']==plan['output_cap_bytes']
      and budget['other_future_reserved_bytes_for_each_scope']['reports']==plan['other_future_reserved_bytes']
      and budget['minimum_free_after_all_future_bytes']==plan['minimum_free_bytes'],'Actual shared report-scope budget')
    out=Path(plan['output_directory']);Q.need(not out.exists(),'Fresh private report namespace required')
    guard=Guard(plan)
    try:
        out.mkdir(parents=True)
        import io as stream_io,unittest
        from .test_state import Source
        log=stream_io.StringIO();tests=unittest.TextTestRunner(stream=log,verbosity=2).run(
          unittest.defaultTestLoader.loadTestsFromTestCase(Source))
        test_ref=Q.write(out/'source_test.json',dict(tests=tests.testsRun,errors=len(tests.errors),
          failures=len(tests.failures),skips=len(tests.skipped),transcript=log.getvalue()))
        Q.need(tests.testsRun==1 and tests.wasSuccessful() and not tests.skipped,'Native dual-population clone boundary fixture required')
        review,original,refs,q,common=statistics(plan['statistics_actual_review_reference'])
        from ..distribution_report_v1 import __main__ as runtime,aggregate,io,functional_groups,population_tables,render
        byname={Path(r['path']).name:r for r in original['source_references']}
        Q.need(len(byname)==10,'Reuse the original ten statistics sources unchanged')
        for ref in byname.values():
            Q.verify(ref);Q.need(ref in request['source_references'],'All ten original statistics source pins required')
        for module in (runtime,aggregate,io,functional_groups,population_tables,render):
            Q.need(Path(module.__file__).resolve()==Path(byname[Path(module.__file__).name]['path']).resolve(),
              'Imported statistics module must be the original cache source, not a patched replacement')
        recipe=read(original['functional_group_recipe_reference'])
        Q.need(functional_groups.recipe()==recipe,'Exact original descriptor/functional-group recipe required')
        source_scope=Path(review['closed_database_path']).parent/'analysis_scope.json'
        old_scope=read(Q.reference(source_scope))
        Q.need(read(old_scope['functional_group_recipe_reference'])==recipe
          and old_scope['analysis_version'].startswith(VERSION),'Original190 scope and recipe provenance required')
        nref=nearest(plan,review,refs,common,out)
        expected={name:(ref,review['populations'][name],1) for name,ref in refs.items()}
        database=out/'counted_statistics.sqlite'
        clone=state.clone(review['closed_database_path'],review['closed_database_frame'],database,expected,guard.check)
        Q.need(clone['population_logical_digests']['v1_common']==review['Common_logical_digest_after'],
          'Closed Common logical digest must match actual190 Root review')
        clone_ref=Q.write(out/'population_clone_closed.json',clone)
        derived={**plan,'schema':'EXPANSION_DISTRIBUTION_PLAN_V1','population_manifests':[],
          'nearest_manifests':[nref],'stage':'nearest'}
        dpath=out/'original_distribution_plan.json';Q.write(dpath,derived)
        # No population ingestion/prepare path is called. New analysis_scope is
        # made by original runtime with its own new-directory recipe reference.
        runtime.run(dpath,'nearest',startup_proof=startup_proof)
        report=runtime.run(dpath,'baseline_report',startup_proof=startup_proof)
        db=sqlite3.connect(database.as_uri()+'?mode=ro',uri=True)
        try:
            db.execute('PRAGMA main.cache_size=-1048576');state.populations(db,expected)
            after=state.digests(db,guard.check)
            Q.need(after==clone['population_logical_digests'],'All five tables for both populations unchanged after exactNN/report')
        finally:db.close()
        guard.sample();guard.check()
        return Q.write(out/'receipt.json',dict(schema='PUBCHEM_CURRENT_BASELINE_EXACT_DISTRIBUTION_REPORT_V1',
          status='BASELINE_REPORT_COMPLETE_PENDING_ACTUAL_C0_AND_ROOT_REVIEW',population_version=VERSION,
          statistics_actual_review_reference=plan['statistics_actual_review_reference'],
          nearest_receipt_reference=plan['nearest_receipt_reference'],nearest_actual_review_reference=plan['nearest_actual_review_reference'],
          population_clone_proof_reference=clone_ref,population_logical_digests_after=after,
          population_feature_rows_recomputed=0,source_or_old_baseline_modified=False,
          original190_analysis_scope_reference=Q.reference(source_scope),original190_analysis_scope=old_scope,
          source_test_reference=test_ref,
          original_runtime_derived_plan_reference=Q.reference(dpath),original_distribution_receipt=report,
          actual_launcher_plan_reference=Q.reference(plan_path),startup_proof_reference=Q.reference(startup_proof),
          actual_parent=actual,runtime=guard.receipt(),task2_9_augmented_coverage_complete=False,
          R_N_or_conformer_or_D_or_training_release=False))
    finally:guard.close()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--plan',required=True,type=Path);p.add_argument('--startup-proof',required=True,type=Path)
    a=p.parse_args();run(a.plan,a.startup_proof)


if __name__=='__main__':main()
