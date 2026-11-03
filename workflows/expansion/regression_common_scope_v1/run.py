"""Allocated SQL-only Common binding of actual closed full15879477 decisions."""
import argparse,json,os,traceback,io,unittest
from pathlib import Path
from . import sql,source
from ..alpha_runtime_v1 import common as Q
from ..alpha_runtime_v1.guard import Guard
from ..portable_sources_v1 import transport as T
from ..alpha_common_graph_continuation_v1 import io as I


def common_lineage(manifest,small):
    """Keep accepted completion outputs separate from original source authority."""
    if manifest.get('producer_schema')=='ALPHA_COMMON_GENERIC_REPRESENTATION_REPAIR_COMPLETION_PRODUCER_V1':
        from ..exact_nn_cached_v1.alpha_common_repaired import validate_manifest
        source_ref=manifest['original_full_source_receipt_reference']
    else:
        from ..exact_nn_cached_v1.alpha_common import validate_manifest
        source_ref=manifest['actual_full_receipt_reference']
    validate_manifest(manifest)
    producer=small(source_ref)
    Q.need(producer['schema']=='ALPHA_COMMON_GRAPH_CONTINUATION_PRODUCER_V1'and producer['mode']=='full',
        'ORIGINAL_FULL_ALPHA_COMMON_SOURCE_RECEIPT_REQUIRED_NOT_COMPLETION_PLAN')
    common=small(manifest['common_population_manifest']);plan=small(producer['plan'])
    origin=small(plan['origin_input_manifest_reference'])
    return producer,common,plan,origin,source_ref


def execute(plan,out,guard):
    transport=T.Transport(plan['parent_transport_manifest'],'218.192.171.238:22',1264)
    def small(ref):return Q.load(transport.verify(ref))
    def replica(ref):return transport.entries.get(T.identity(ref),T.triple(ref))
    old=small(plan['original_full_regression_reference']);oldplan=small(old['plan'])
    Q.need(old['schema']=='pubchem_v1_complete_input_regression_full_v3' and old['mode']=='full'
      and old['status']=='FULL_X_RULE_PASS_COMMON_SCOPE_PENDING' and old['job_id']=='4520414' and old['uid']==1278
      and old['evaluated_records']==15879477 and old['full_v1_selection_regression_passed'] is False
      and old['common_population_scope_bound'] is False and old['all_mismatch_details_stored'] is True
      and oldplan['sources']==old['source_refs'] and oldplan['sources'].get('common_population') is None,'ORIGINAL_IMMUTABLE_FULL_REGRESSION_NOT_ALREADY_COMMON_BOUND')
    coverage=old['complete_source_coverage'];Q.need(coverage['complete_original_source_coverage'] is True
      and coverage['records']==coverage['unique_records']==coverage['matched_unique_original_ids']==15879477,'CLOSED_ALL_ORIGINAL_SOURCE_COVERAGE')
    account=small(plan['original_regression_accounting_reference'])
    parents=account.get('actual_parents') or [account.get('actual_parent',{})]
    parent=[r for r in parents if str(r.get('JobIDRaw',r.get('job_id')))==old['job_id']]
    Q.need(len(parent)==1 and parent[0].get('State',parent[0].get('state'))=='COMPLETED'
      and parent[0].get('ExitCode',parent[0].get('exit_code'))=='0:0','ACTUAL_ORIGINAL_MAIN_C0_NOT_ALPHA_IMPERSONATION')
    Q.need(parent[0].get('UID','1278')=='1278' and parent[0].get('User','zixiao')=='zixiao'
      and parent[0].get('endpoint','202.38.247.57:22')=='202.38.247.57:22','PRESERVED_ACTUAL_MAIN_ORIGIN_IDENTITY')
    transport.verify(account['raw_sacct_reference'])
    by_name={Path(r['path']).name:r for r in oldplan['code_sources']}
    originals=[by_name[name] for name in ('regression_x_v1.py','regression_x_v2.py','regression_x_full_v3.py')]
    code=[transport.verify(ref).read_text() for ref in originals]
    semantics=source.prove(*code,old['boolean_bit_order'])
    common_manifest=small(plan['common_reference_manifest'])
    common_producer,common,common_plan,origin,common_source_ref=common_lineage(common_manifest,small)
    mapping={row['origin_reference']['path']:row['destination_reference'] for row in common_plan['transport_bindings']}
    formal_origin=origin['origin_formal_reference'];formal=mapping[formal_origin['path']]
    equivalent=T.triple(old['source_refs']['formal_population'])==T.triple(formal_origin)
    members=[mapping[ref['path']] for ref in common['membership_tables']]
    refs=[old['record_decisions'],old['all_mismatches'],formal,*members];bodies=[];tables=[]
    import pyarrow as pa
    import duckdb
    db=duckdb.connect();db.execute('SET threads='+str(plan['workers']));db.execute("SET memory_limit='"+str(int(plan['duckdb_memory_bytes']))+"B'")
    db.execute("SET temp_directory=''")
    try:
        for ref in refs:
            guard.check();bodies.append(I.Body(replica(ref),guard))
        compact_file=bodies[0].parquet();metadata=compact_file.schema_arrow.metadata
        Q.need(compact_file.metadata.num_rows==old['evaluated_records'] and metadata[b'schema']==b'v1_full_x_compact_record_v3'
          and json.loads(metadata[b'boolean_bits'])==old['boolean_bit_order'] and json.loads(metadata[b'cause_bits'])==old['cause_bit_order'],
          'ACTUAL_COMPACT_PARQUET_METADATA_AND_CLOSED_BIT_ORDER')
        def table(index,columns):
            value=bodies[index].parquet().read(columns=columns,use_threads=False);bodies[index].check();guard.check();tables.append(value);return value
        db.from_arrow(table(0,['record_id','molecule_id','source_family','decision_bits','cause_bits'])).create_view('compact')
        sql.decode_view(db,old['boolean_bit_order'],old['cause_bit_order'])
        mismatch_table=table(1,['record_id','molecule_id','source_family','details_json'])
        explanation,causes=sql.explanation_rows(mismatch_table.to_pylist(),old['cause_bit_order'])
        schema=pa.schema([('record_id',pa.string()),('molecule_id',pa.string()),('source_family',pa.string()),('cause_bits',pa.int64())])
        ex=pa.Table.from_pylist(explanation,schema=schema);tables.append(ex);db.from_arrow(ex).create_view('explanations')
        db.from_arrow(table(2,['record_id','molecule_id'])).create_view('formal')
        parts=[table(i,['molecule_id','effective_role','records','common_population']) for i in range(3,len(bodies))]
        member_table=pa.concat_tables(parts);tables.append(member_table);db.from_arrow(member_table).create_view('membership')
        report=sql.bind(db,old['boolean_bit_order'],common_producer['result']['expected_all_common_census'],equivalent)
        metrics=report['metrics'];checks=report['checks']
        checks['actual_all15879477_rows']=metrics['original_records']==metrics['original_unique_records']==old['evaluated_records']
        checks['every_original_boolean_count_matches_closed_receipt']=all(metrics['boolean_counts'][name]==old['counts'][name] for name in old['boolean_bit_order'])
        checks['actual_all_mismatch_rows_and_causes_match_closed_receipt']=len(explanation)==old['mismatch_rows'] and causes==old['causes']
        checks['actual_full_molecular_count_matches_closed_receipt']=metrics['original_molecules']==old['molecules_observed']
        checks['actual_global_molecular_selection_matches_closed_receipt']=(metrics['global_molecular_selection']['old_selected_molecules']==old['old_selected_molecules']
          and metrics['global_molecular_selection']['new_selected_molecules']==old['conditional_new_selected_molecules']
          and metrics['global_molecular_selection']['changed_molecules']==old['conditional_changed_molecules'])
        checks['actual_global_decision_changes_match_closed_receipt']=(metrics['chemical_changed_records']==old['counts']['chemical_admission_changed']
          and metrics['global_conditional_changed_records']==old['counts']['conditional_final_changed'])
        checks['complete_original_Common_denominator_and_exclusion_mass']=(metrics['membership_rows']==common['denominator_molecules']
          and metrics['membership_rows']-metrics['common_molecules']==common['excluded_molecules'])
        checks['original_formal_contract_count_matches_closed_plan']=(equivalent and metrics['formal_records']==oldplan['expected_formal_records'])
        from ..common_molecular_fp_candidate_v1.census import Census
        old_census=Census();new_census=Census()
        for mid,role,old_n,new_n in db.execute('SELECT molecule_id,effective_role,old_records,new_records FROM common_counts ORDER BY molecule_id').fetchall():
            if old_n:old_census.add(mid,role,int(old_n))
            if new_n:new_census.add(mid,role,int(new_n))
        actual_old,actual_new=old_census.result(),new_census.result();expected=common_producer['result']['expected_all_common_census']
        checks['exact_old_and_new_Common_MID_role_record_digest']=actual_old==actual_new==expected
        report.update(passed=all(checks.values()),failed_checks=[k for k,v in checks.items() if not v],
          original_semantic_source_proof=semantics,original_regression_source_references=originals,
          common_expected_census=expected,actual_old_Common_census=actual_old,actual_new_Common_census=actual_new,
          original_formal_source_reference=old['source_refs']['formal_population'],Common_original_formal_source_reference=formal_origin,
          original_formal_source_equivalence_proven=equivalent,native_record_expectation_is_not_assumed_without_source_equivalence=True,
          actual_source_readbacks=[dict(destination_reference=b.reference,frame=list(b.frame)) for b in bodies],
          all_mismatch_explanation_counts=causes,original_regression_reference=plan['original_full_regression_reference'],
          original_Main_actual_parent=parent[0],common_reference_manifest=plan['common_reference_manifest'],
          original_Alpha_Common_source_receipt_reference=common_source_ref)
        for body in bodies:body.check()
        guard.sample();guard.check();return report
    finally:
        db.close()
        for body in bodies:body.close()


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',type=Path,required=True);p.add_argument('--startup-proof',type=Path,required=True);a=p.parse_args()
    plan=Q.load(a.plan);proof=Q.load(a.startup_proof);T.bind_plan(plan);request=proof['request']
    Q.need(plan['schema']=='ALPHA_COMMON_SELECTION_REGRESSION_BIND_PLAN_V1'
      and request['scope_key']==plan['scope_key']=='regression_common_scope_v1'
      and request['producer_plan_reference']==Q.reference(a.plan) and request['execution_argv']==plan['execution_argv'], 'EXACT_ACTUAL_SQL_BIND_PLAN')
    Q.need(proof['uid']==os.getuid()==1264 and str(proof['job_id'])==os.environ['SLURM_JOB_ID']
      and proof['boot_id']==Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'ACTUAL_ALPHA_SQL_BIND_PARENT')
    for file in Path(__file__).parent.glob('*.py'):Q.need(Q.reference(file) in request['source_references'],'CURRENT_SQL_BIND_SOURCE')
    out=Path(plan['output_directory']);guard=Guard(plan)
    try:
        Q.need(not out.exists(),'FRESH_COMMON_BIND_OUTPUT');out.mkdir(parents=True)
        from .test_sql import Source
        suite=unittest.defaultTestLoader.loadTestsFromTestCase(Source);stream=io.StringIO();test=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
        tests=Q.write(out/'source_tests.json',dict(tests=test.testsRun,failures=len(test.failures),errors=len(test.errors),skips=len(test.skipped),transcript=stream.getvalue(),before_full_DATA=True))
        Q.need(test.testsRun==5 and test.wasSuccessful() and not test.skipped,'FIVE_SQL_SEMANTIC_BOUNDARIES_REQUIRED')
        result=execute(plan,out,guard)
        Q.write(out/'receipt.json',dict(schema='ALPHA_COMMON_SELECTION_REGRESSION_BIND_PRODUCER_V1',
          status='BINDING_VERIFIED_PENDING_ACTUAL_ALPHA_C0' if result['passed'] else 'STOP_REVIEW',result=result,
          job_id=os.environ['SLURM_JOB_ID'],uid=os.getuid(),endpoint='218.192.171.238:22',plan=Q.reference(a.plan),startup_proof=Q.reference(a.startup_proof),
          resources=guard.receipt(),source_tests=tests,full_v1_selection_regression_passed=False,common_population_scope_bound=False,
          original_4520414_receipt_modified=False,new_chemical_evaluator_calls=0,actual_parent_C0_pending_Root_review=True))
        Q.need(result['passed'],'ACTUAL_COMMON_SCOPE_COMPARISONS_FAILED_REVIEW_REQUIRED')
    except BaseException as exc:
        if out.is_dir():Q.write(out/'failure.json',dict(error=repr(exc),traceback=traceback.format_exc(),original_receipts_modified=False,partials_retained=True))
        raise
    finally:guard.close()


if __name__=='__main__':main()
