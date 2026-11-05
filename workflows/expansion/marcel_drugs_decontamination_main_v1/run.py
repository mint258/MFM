"""One finite Main CPU readonly projection; no native/graph/download operations."""
import argparse,collections,io,time,traceback,unittest
from pathlib import Path
from . import contract as C,projection as P,runtime as I
Q=C.Q

def fixtures(out):
    from .test_v1 import Boundaries
    Boundaries.output_root=out;suite=unittest.defaultTestLoader.loadTestsFromTestCase(Boundaries)
    Q.need(suite.countTestCases()==3,'EXACT3_SYNTHETIC_IO_AND_GUARD_METHODS')
    stream=io.StringIO();r=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    from workflows.expansion import decontamination as D,common
    from workflows.expansion.identity_v2 import projection_v2 as V
    from workflows.expansion.marcel_drugs_keys_main_v1 import runtime as B
    from workflows.expansion.marcel_kraken_decontamination_main_v1 import runtime as K
    objects={'strict_consumer':(P.identity_keys,D.identity_keys),'full_keys':(P.full_keys,V.full_keys),'wp5':(P.wp5_key,common.wp5_key),
        'Writer_write':(I.Writer.write,B.Writer.write),'Budget_check':(I.Budget.check,B.Budget.check),'JSONL_rows':(I.rows,K.rows)}
    Q.need(I.Budget is B.Budget and I.Writer is B.Writer and all(a is b for a,b in objects.values()),'ORIGINAL_CONSUMER_READER_WRITER_BUDGET_FUNCTION_OBJECTS')
    proof={name:{'module':a.__module__,'filename':a.__code__.co_filename,'first_line':a.__code__.co_firstlineno} for name,(a,_) in objects.items()}
    gate={'tests_run':r.testsRun,'failures':len(r.failures),'errors':len(r.errors),'skips':len(r.skipped),
        'expected_failures':len(r.expectedFailures),'unexpected_successes':len(r.unexpectedSuccesses),'transcript':stream.getvalue(),
        'all_before_any_DATA':True,'only_synthetic_IO':True,'original_function_objects':proof,'new_graph_or_key_derivations':0}
    Q.write_new(out/'fixtures3.json',gate)
    Q.need(r.testsRun==3 and r.wasSuccessful() and not(r.skipped or r.expectedFailures or r.unexpectedSuccesses),'SOURCE3_ACTUAL_PASS_BEFORE_UNION_DATA')
    return gate

def observe(plan,baseline,archive,out,budget,check,progress,writers):
    union=plan['data_references'][0];before=I.file_guard(union)
    identities=I.Writer(out/'identities.jsonl',budget);provenance=I.Writer(out/'all_name_union_projection_evidence.jsonl',budget);writers.extend((identities,provenance))
    expected=[];totals=collections.Counter({k:0 for k in ('conformers','native_unknown','mismatch_conformers','mismatch_names','multi_SMILES_names','unresolved')})
    for original,location in I.rows(union,check,progress):
        ordinal=len(expected);row,counts=P.project(original,ordinal,archive['sha256']);totals.update(counts)
        identity_start=identities.bytes;identities.write(row,False);identity_sha=P.sha(row);expected.append((row['source_id'],identity_sha))
        provenance.write({'identity_source_id':row['source_id'],'source_version':C.VERSION,'original_CSV_physical_ordinal':ordinal,
            'original_name_fields':original['original_name_fields'],'role':'all','native_split':None,'native_split_state':'UNKNOWN_NOT_INFERRED',
            'role_basis':'ORIGINAL_CONSUMER_ALL_SOURCE_SCOPE_NOT_NATIVE_SPLIT','original_complete_name_union_event':location,
            'original_complete_union_canonical_sha256':P.sha(original),'original_source_native_key_union_preserved_by_reference':True,
            'counts_unchanged':counts,'actual_native_root_review_reference':plan['accepted_native_union_root_review_reference'],
            'projected_identity_offset_bytes':identity_start,'projected_identity_bytes':identities.bytes-identity_start,
            'projected_identity_canonical_sha256':identity_sha,'unknown_or_difference_is_chemical_exclusion':False},False)
        progress.update(phase='PROJECTED_COMPLETE_NAME_UNIONS',names=len(expected),conformers=totals['conformers'])
    Q.need(I.file_guard(union)==before,'WHOLE_UNION_SOURCE_FRAME_STABLE_AFTER_COMPLETE_EOF');P.mass(len(expected),totals)
    for writer in writers:writer.close()
    consumer_counts=collections.Counter();seen=0
    for row,location in I.rows(identities.reference(),check,progress):
        Q.need(set(row)=={'source_id','role','subdataset','inchikeys','non_h_composition'} and row['role']=='all' and row['subdataset']==''
            and row['non_h_composition'] is None and seen<C.N and (row['source_id'],P.sha(row))==expected[seen],
            'ALL_STRICT_FIVE_FIELD_OUTPUT_ORDER_AND_EXACT_IDENTITY_READBACK')
        consumer_counts.update(kind for kind,key in P.identity_keys(row));seen+=1
    Q.need(seen==C.N,'ALL75099_ORIGINAL_STRICT_CONSUMER_ROWS_REOPENED')
    count=0
    for value,location in I.rows(provenance.reference(),check,progress):
        Q.need(count<C.N and value['original_CSV_physical_ordinal']==count and value['native_split'] is None
            and (value['identity_source_id'],value['projected_identity_canonical_sha256'])==expected[count],
            'EVERY_ORIGINAL_NAME_UNION_EVIDENCE_ROW_REOPENED');count+=1
    Q.need(count==C.N and I.file_guard(union)==before,'ALL_PROVENANCE_ROWS_AND_OLD_INPUT_REMAIN_CLOSED')
    identity_ref={**identities.reference(),'rows':C.N};raw=[archive,union]
    coverage={'schema':'expansion_all_source_identity_coverage_v1','dataset':'marcel_drugs75k','source_version':C.VERSION,
        'all_splits':True,'covered_roles':['all'],'covered_subdatasets':[],'unresolved_without_identity_or_composition':0,
        'expected_identity_records':C.N,'raw_artifacts':raw,'identities':identity_ref,'all_source_context_rows':633101,
        'all_native_SDF_conformers':558002,'all_original_CSV_names':75099,'conservation':dict(totals),
        'all_key_variants_and_mismatches_conservatively_retained':True,'native_split':'UNKNOWN_NOT_INFERRED',
        'actual_union_root_review_reference':plan['accepted_native_union_root_review_reference'],
        'original_strict_identity_keys_consumer_rows':seen,'name_union_evidence_reference':provenance.reference(),
        'all_old_consumed_DATA_whole_SHA_same_FD_EOF_verified':True,'upstream_archive_and_graph_integrity_basis':'ACTUAL4523818_C0_AND_EXACT_ROOT_ACCEPTANCE_INHERITED_NOT_REPARSED',
        'all_new_DATA_readback_complete':True,'Root_candidate_acceptance_or_global_pool_release':False}
    coverage_ref=Q.write_new(out/'coverage.json',coverage)
    return {'coverage_reference':coverage_ref,'identities_reference':identity_ref,'name_union_evidence_reference':provenance.reference(),
        'names':seen,'conservation':dict(totals),'consumer_key_kind_counts':dict(consumer_counts),
        'all_input_and_output_SHA_EOF_and_same_FD_verified':True,'dataset_ready_candidate_requires_actual_C0_and_independent_Root_review':True}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',type=Path,required=True);p.add_argument('--startup-proof',type=Path,required=True);args=p.parse_args()
    plan=Q.load(args.plan);baseline,parents,archive,_=C.inputs(plan);proof=I.admit(args,plan,parents)
    out=Path(plan['output_directory']);Q.need(out.is_absolute() and Q.ROOT/'artifacts' in out.parents and '..' not in out.parts and not out.exists()
        and not any(x.is_symlink() for x in (out,*out.parents)),'FRESH_NON_SYMLINK_OWN_OUTPUT_NOT_OLD_DATA')
    out.mkdir(parents=True,mode=0o700);writers=[];gate=budget=None;progress={};started=time.monotonic()
    try:
        gate=fixtures(out);budget=I.Budget(plan,proof,out)
        def check():budget.check(False);Q.need(budget.stop_new is None,budget.stop_new or 'ORIGINAL_RESOURCE_STOP_NEW_ROWS_NATURAL_DRAIN')
        check();result=observe(plan,baseline,archive,out,budget,check,progress,writers);check()
        for path in [*(C.HERE/n for n in C.FILES),*C.OLD]:Q.need(Q.pin(path) in proof['request']['source_references'],'ORIGINAL_AND_NEW_SOURCE_BYTES_UNCHANGED_AFTER_DATA')
        Q.write_new(out/'receipt.json',{'schema':'DRUGS_DECONTAMINATION_PROJECTION_RECEIPT_V1',
            'status':'ALL75099_CONSERVATIVE_UNIONS_STRICT_CONSUMER_READBACK_ROOT_ACCEPTANCE_REQUIRED','job_id':str(proof['job_id']),
            'uid':1278,'endpoint':'202.38.247.57:22','node':proof['request']['node'],'plan_reference':Q.pin(args.plan),
            'startup_proof_reference':Q.pin(args.startup_proof),'accepted_native_union_root_review_reference':plan['accepted_native_union_root_review_reference'],
            'fixtures':gate,'result':result,'source_version':C.VERSION,'global_pool_release':False,'new_graph_key_SDF_UFF_QM_network_calls':0,
            'old_DATA_or_once_modified':False,'elapsed_seconds':time.monotonic()-started,'observed_RSS_peak_bytes':budget.peak,
            'minimum_MemAvailable_bytes':budget.minimum,'logical_output_bytes_before_receipt':budget.used(),
            'runtime_statvfs_is_not_refreshed_account_quota':True,'actual_parent_cost':'PENDING_ROOT_TERMINAL_ACCOUNTING','cost_overrun_action':'REPORT_AND_CONTINUE'})
        Q.need(budget.used()<=C.CAP,'WHOLE512MIB_INCLUDING_RECEIPT');return 0
    except BaseException as exc:
        Q.write_new(out/'failure.json',{'schema':'DRUGS_DECONTAMINATION_PROJECTION_FAILURE_V1','error':type(exc).__name__+': '+str(exc),
            'traceback':traceback.format_exc(),'fixtures':gate,'progress':progress,'partial_DATA_references':[w.reference() for w in writers],
            'all_source_projection_complete':False,'dataset_READY_or_pool_release':False,'actual_parent_cost':'PENDING_ROOT_ACCOUNTING',
            'resource_stop_new':None if budget is None else budget.stop_new,'original_DATA_and_once_unchanged':True})
        raise
    finally:
        for writer in writers:
            if not writer.stream.closed:writer.close()
if __name__=='__main__':raise SystemExit(main())
