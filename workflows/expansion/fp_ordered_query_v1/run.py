"""Admitted full filtered Parquet -> FP-ordered exact seven-field JSONL."""
import argparse
import hashlib
import os
from pathlib import Path
import traceback
from ..alpha_runtime_v1 import common as Q
from ..alpha_runtime_v1.guard import Guard
from ..alpha_runtime_v1.profile import admit
from ..alpha_closed500_handoff_v1.sql import SQLStopper
from ..exact_nn_cached_v1.sql_runtime import configure
from ..portable_sources_v1.transport import bind_plan
from ..exact_nn_cached_v1.contracts import typed_filtered
from ..pubchem_generic_recovery_overlay_v1.runtime import VERSION
from . import authority,core


def stamp(s):return {k:getattr(s,k) for k in ('st_dev','st_ino','st_uid','st_nlink','st_size','st_mtime_ns','st_ctime_ns')}


def execute(plan_path,startup_proof):
    plan=Q.load(plan_path);proof=Q.load(startup_proof);actual=admit(plan,minimum_workers=16);request=proof['request']
    Q.need(plan['schema']=='PUBCHEM_FULL_FP_ORDERED_QUERY_PLAN_V1' and plan['population_version']==VERSION
      and plan['scope_key']==request['scope_key']=='fp_ordered_full_query_v1'
      and request['producer_plan_reference']==Q.reference(plan_path) and request['execution_argv']==plan['execution_argv']
      and proof['endpoint']==actual['endpoint']=='218.192.171.238:22' and proof['uid']==1264
      and str(proof['job_id'])==actual['job_id'] and proof['boot_id']==Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
      'Actual Alpha allocated source/profile/plan/startup binding required')
    for p in Path(__file__).parent.glob('*.py'):
        Q.need(Q.reference(p) in request['source_references'],'Every independent producer source pinned')
    borrowed=[Q.reference(Path(f.__code__.co_filename)) for f in
      (typed_filtered,configure,SQLStopper.__init__,authority.validate_header)]
    Q.need(all(ref in request['source_references'] for ref in borrowed),
      'Actual unchanged typed-source/science-header/SQL helper implementations pinned')
    budget=authority.read(plan['reviewed_storage_budget_reference']);scope=plan['storage_budget_scope']
    Q.need(budget['schema']=='ROOT_ALPHA_ALL_FUTURE_STORAGE_BUDGET_V2' and budget['reviewer']=='root'
      and budget['endpoint']=='218.192.171.238:22' and budget['uid']==1264
      and budget['quota_root']==plan['quota_authority']['quota_root']
      and budget['scope_total_caps_bytes'][scope]==plan['output_cap_bytes']
      and budget['other_future_reserved_bytes_for_each_scope'][scope]==plan['other_future_reserved_bytes']
      and budget['minimum_free_after_all_future_bytes']==plan['minimum_free_bytes']
      and 0<plan['sql_memory_bytes']<plan['parent_rss_cap_bytes']<=plan['software_rss_budget_bytes'],
      'Actual aggregate future-budget/SQL/spill/RSS binding required')
    cache=Path(plan['future_full_nn_cache_directory'])
    Q.need(cache.is_absolute() and cache.is_relative_to('/gfshome/alpha/pubchem_expansion_20261103/exact')
      and not cache.exists(),'A fresh full-NN cache namespace; never the current baseline201 cache')
    out=Path(plan['output_directory']);scope_root=Path(plan['output_scope_root'])
    Q.need(out.is_absolute() and scope_root==Path('/gfshome/alpha/pubchem_expansion_20261103')/scope
      and scope_root in out.parents and not out.exists(),'Fresh source output under the exact reviewed aggregate scope')
    guard=Guard(plan);db=None;monitor=None
    try:
        out.mkdir(parents=True)
        import io,unittest
        from .test_core import Source
        log=io.StringIO();tests=unittest.TextTestRunner(stream=log,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Source))
        test_ref=Q.write(out/'source_tests.json',dict(tests=tests.testsRun,errors=len(tests.errors),failures=len(tests.failures),
          skips=len(tests.skipped),transcript=log.getvalue()))
        Q.need(tests.testsRun==4 and tests.wasSuccessful() and not tests.skipped,'Four meaningful native SQL/source-boundary fixtures required')
        inputs=authority.read(plan['input_authority_reference']);filtered,pool,review=authority.validate(inputs)
        bind_plan(plan);typed_filtered(filtered) # unchanged complete-source/all11/X195 scientific gates
        source_ref=filtered['candidates'];source=Path(source_ref['path']);before=stamp(source.lstat())
        Q.need(source.is_file() and not source.is_symlink() and before['st_uid']==1264 and before['st_nlink']==1
          and before['st_size']==source_ref['bytes'],'Own closed typed candidate source required')
        import duckdb
        db=duckdb.connect(str(out/'projection.duckdb'));configure(db,plan,out/'spill');monitor=SQLStopper(db,guard.check)
        with source.open('rb') as held:
            Q.need(stamp(os.fstat(held.fileno()))==before,'Held source FD must match admitted path')
            sha=hashlib.sha256()
            for block in iter(lambda:held.read(8<<20),b''):sha.update(block);guard.check()
            Q.need(sha.hexdigest()==source_ref['sha256'] and stamp(os.fstat(held.fileno()))==before,
              'Actual complete candidate EOF SHA, not a metadata-only source assertion')
            db.read_parquet('/proc/self/fd/'+str(held.fileno())).create_view('candidates')
            expected=filtered['counts']['eligible_molecules']
            projection,order=core.write_projection(db,out/'fp_ordered_full_query.jsonl',expected,guard.check)
            emitted_before=stamp(Path(projection['path']).lstat());Q.verify(projection)
            equivalence=core.prove(db,projection['path'],expected,guard.check)
            Q.need(stamp(os.fstat(held.fileno()))==before==stamp(source.lstat())
              and stamp(Path(projection['path']).lstat())==emitted_before,
              'Same full source FD/path and serialized output frames across all equivalence checks')
        db.execute('CHECKPOINT');monitor.close();monitor=None;db.close();db=None
        proof_ref=Q.write(out/'all_row_equivalence_and_order.json',dict(schema='PUBCHEM_FULL_FP_ORDERED_QUERY_EQUIVALENCE_V1',
          status='COMPLETE',source_candidates_reference=source_ref,source_complete_EOF_SHA_verified=True,
          source_current_frame=before,projection_reference=projection,projection_current_frame=emitted_before,
          projection_complete_EOF_SHA_verified=True,order_proof=order,full_multiset_proof=equivalence,
          original_seven_fields_unchanged=True,source_identity_rows_removed=0,no_chemical_perception_calls=True))
        guard.sample();guard.check()
        return Q.write(out/'manifest.json',dict(schema='EXPANSION_TYPED_DECONTAMINATED_QUERY_PROJECTION_V1',
          producer_schema=core.PRODUCER,status='COMPLETE',population_version=VERSION,
          source_endpoint='218.192.171.238:22',source_uid=1264,filtered_pool_receipt=inputs['filtered_pool_receipt_reference'],
          filtered_pool_actual_review_reference=inputs['filtered_pool_actual_review_reference'],source_candidates_reference=source_ref,
          projection=projection,projection_order=core.ORDER,projection_ordinal_domain='ZERO_BASED_NEW_PHYSICAL_FP_ORDERED_STREAM',
          fingerprint_recipe='ECFP4_2048_radius2_chiralityFalse_rdkit2025.09.5',targets_present=False,downstream_features_present=False,
          all_row_equivalence_and_order_reference=proof_ref,fields=list(core.FIELDS),execution_order_only_changed=True,
          baseline_sample_ordinal_source_allowed=False,all_candidate_identities_retained=True,duplicate_FP_identity_rows_retained=True,
          cache_namespace_id='fp-ordered-full-'+projection['sha256'],future_full_nn_cache_directory=str(cache),
          new_manifest_body_SHA_and_source_key_required=True,new_private_cache_required=True,
          query_cache_IDs_and_first_ordinals_are_new_internal_provenance=True,
          strict_same_N_queue_claim=False,successor_N_complete_sort_tuple_uniqueness_gate='PENDING_ACTUAL_CLOSED_RANK_DATABASE_ROOT_REVIEW',
          actual_parent=actual,actual_parent_C0_acceptance='PENDING_ROOT_TERMINAL_ACCOUNTING',input_authority_reference=plan['input_authority_reference'],
          borrowed_source_references=borrowed,resource_plan=Q.reference(plan_path),startup_proof_reference=Q.reference(startup_proof),
          source_tests=test_ref,runtime=guard.receipt()))
    except BaseException as exc:
        if out.is_dir():Q.write(out/'failure.json',dict(error=repr(exc),traceback=traceback.format_exc(),partials_retained=True,
          original_query_NN_rank_kernel_or_baseline_modified=False))
        raise
    finally:
        if monitor is not None:monitor.close()
        if db is not None:db.close()
        guard.close()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--plan',required=True,type=Path);p.add_argument('--startup-proof',required=True,type=Path)
    a=p.parse_args();execute(a.plan,a.startup_proof)


if __name__=='__main__':main()
