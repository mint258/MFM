"""Fresh Main CPU identity-only projection of three actual full-C0 journals."""
import argparse,collections,io,os,sqlite3,time,traceback,unittest
from pathlib import Path
from . import contract as C,projection as P,runtime as I
Q=C.Q


def fixtures(out):
    from .test_v1 import Boundaries
    Boundaries.output_root=out
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(Boundaries);Q.need(suite.countTestCases()==3,'EXACT3_SYNTHETIC_BOUNDARIES')
    stream=io.StringIO();r=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    from workflows.expansion.marcel_kraken_keys_main_v1 import source as S,run as K
    from workflows.expansion import decontamination as D,common
    from workflows.expansion.marcel_drugs_keys_main_v1 import runtime as B
    Q.need(I.Budget is B.Budget and I.Writer is B.Writer,'DIRECT_ORIGINAL_BUDGET_AND_WRITER_CLASS_OBJECTS')
    functions={'original_relationship':(P.relationship,S.relationship),'original_comparison':(P.comparison,K.comparison),
        'original_consumer':(P.identity_keys,D.identity_keys),'original_wp5':(P.wp5_key,common.wp5_key),
        'original_Budget_init':(I.Budget.__init__,B.Budget.__init__),'original_Budget_check':(I.Budget.check,B.Budget.check),
        'original_Writer_write':(I.Writer.write,B.Writer.write)}
    Q.need(all(a is b for a,b in functions.values()),'DIRECT_ORIGINAL_FUNCTION_OBJECTS_NO_CHEMICAL_KERNEL_COPY')
    proof={name:{'module':a.__module__,'filename':a.__code__.co_filename,'first_line':a.__code__.co_firstlineno}
        for name,(a,b) in functions.items()}
    result={'tests_run':r.testsRun,'failures':len(r.failures),'errors':len(r.errors),'skips':len(r.skipped),
        'expected_failures':len(r.expectedFailures),'unexpected_successes':len(r.unexpectedSuccesses),'transcript':stream.getvalue(),
        'direct_unchanged_function_proof':proof,'all_before_any_DATA':True,'new_graph_or_key_derivations':0}
    Q.write_new(out/'fixtures3.json',result)
    Q.need(r.wasSuccessful() and r.testsRun==3 and not(r.skipped or r.expectedFailures or r.unexpectedSuccesses),'PURE3_PASS_BEFORE_DATA')
    return result


def get(db,key):
    value=db.execute('SELECT context,context_ref,dispatch_sha,dispatch_ref,result,result_ref FROM records WHERE k=?',(key,)).fetchone()
    Q.need(value is not None,'RESULT_OR_DISPATCH_WITHOUT_EXACT_SOURCE_CONTEXT');return value


def observe(plan,baseline,out,budget,check,progress,writers):
    journal_ref,context_ref,union_ref=plan['data_references'];db=sqlite3.connect(out/'job_owned_identity_join.sqlite')
    db.execute('CREATE TABLE records(k TEXT PRIMARY KEY,root INTEGER,kind TEXT,secondary INTEGER,context TEXT,context_ref TEXT,dispatch_sha TEXT,dispatch_ref TEXT,result TEXT,result_ref TEXT)')
    db.execute('CREATE INDEX original_root_order ON records(root,kind,secondary)')
    db.execute('CREATE TABLE projected(root INTEGER PRIMARY KEY,source_id TEXT UNIQUE,identity_sha TEXT)')
    counters=collections.Counter();states=collections.Counter();unknown=collections.Counter();comparisons=collections.Counter();multiple=0;unresolved=0
    try:
        root=-1;global_conf=0;local=0;declared=0;native_root=None
        for ctx,location in I.rows(context_ref,check,progress):
            key=P.locator(ctx);kind=ctx['kind']
            Q.need(ctx['selected_for_key_projection'] is True and ctx['original_MolBlock_text_retained_in_pinned_archive'] is True
                and ctx['original_native_assignment_IDs_and_ordinals_unchanged'] is True and ctx['new_role_or_source_acceptance'] is False
                and ctx['source_tuple_position']==0,'EXACT_COMPLETE_PRODUCER_RELATIONSHIP_FLAGS')
            if kind=='root_SMILES':
                Q.need(local==declared and ctx['root_assignment_ordinal']==root+1,'ORIGINAL_ROOT_ORDER_AND_PRIOR_ALL_CONFORMERS')
                root+=1;local=0;declared=ctx['all_original_conformer_relationships'];native_root=ctx['native_root_ID']
            else:
                Q.need(ctx['root_assignment_ordinal']==root and ctx['native_root_ID']==native_root
                    and ctx['secondary_assignment_ordinal']==local and ctx['global_conformer_assignment_ordinal']==global_conf,
                    'EXACT_ORIGINAL_ROOT_LOCAL_GLOBAL_ORDER')
                local+=1;global_conf+=1
            db.execute('INSERT INTO records VALUES(?,?,?,?,?,?,NULL,NULL,NULL,NULL)',(key,root,kind,
                -1 if kind=='root_SMILES' else ctx['secondary_assignment_ordinal'],P.canonical(ctx).decode(),P.canonical(location).decode()))
            counters['context_'+kind]+=1;progress.update(phase='CONTEXT',closed_context_rows=sum(counters.values()))
            if sum(counters.values())%256==0:db.commit()
        Q.need(root==1551 and global_conf==21287 and local==declared and counters['context_root_SMILES']==1552,
            'ALL1552_ROOTS_ALL21287_CONFORMERS_AND_EXACT_CONTEXT_EOF');db.commit()
        for event,location in I.rows(journal_ref,check,progress):
            typ=event['event'];Q.need(typ in ('EXACT_SOURCE_DURABLE_BEFORE_KEY_DISPATCH','SOURCE_KEY_RESULT_DURABLE_BEFORE_AGGREGATE'),'ONLY_ORIGINAL_JOURNAL_EVENTS')
            result=None
            if typ=='EXACT_SOURCE_DURABLE_BEFORE_KEY_DISPATCH':source=event['source']
            else:result=event['worker_observation']['result'];source=result['source']
            key=P.locator(source);P.native(source['source_string']);record=get(db,key);ctx=P.strict_json(record[0])
            Q.need(P.relationship(source,True)==ctx,'ORIGINAL_SOURCE_TEXT_SHA_NATIVE_ID_AND_CONTEXT_BINDING')
            source_sha=P.sha(source)
            if result is None:
                Q.need(record[2] is None and record[4] is None,'ONE_REAL_DISPATCH_EVENT_PER_SOURCE')
                db.execute('UPDATE records SET dispatch_sha=?,dispatch_ref=? WHERE k=?',(source_sha,P.canonical(location).decode(),key))
                counters['dispatch_'+source['kind']]+=1
            else:
                Q.need(record[2]==source_sha and record[4] is None,'RESULT_AFTER_EXACT_DISPATCH_WITHOUT_DUPLICATES')
                compact=P.compact(result);Q.need(result.get('source_or_pool_accepted') is False,'ORIGINAL_RESULT_NOT_A_POOL_RELEASE')
                saved={k:v for k,v in result.items() if k!='source'}
                db.execute('UPDATE records SET result=?,result_ref=? WHERE k=?',(P.canonical(saved).decode(),P.canonical(location).decode(),key))
                counters['result_'+source['kind']]+=1;states[compact['identity_state']]+=1;unknown[source['kind']]+=compact['has_any_unknown']
            if sum(counters.values())%256==0:db.commit()
            progress.update(phase='JOURNAL_JOIN',closed_results=counters['result_root_SMILES']+counters['result_conformer_MolBlock'])
        for phase in ('context_','dispatch_','result_'):
            Q.need(counters[phase+'root_SMILES']==1552 and counters[phase+'conformer_MolBlock']==21287,'EXACT_EVERY_SOURCE_DISPATCH_AND_RESULT:'+phase)
        Q.need(dict(states)==baseline['identity_state_counts'] and dict(unknown)==baseline['unknown_by_kind']
            and db.execute('SELECT count(*) FROM records WHERE dispatch_sha IS NULL OR result IS NULL').fetchone()[0]==0,'EXACT_OLD_STATES_UNKNOWN_COUNTS_AND_NO_DANGLING_SOURCE');db.commit()
        identities=I.Writer(out/'identities.jsonl',budget);provenance=I.Writer(out/'all_native_identity_provenance.jsonl',budget)
        evidence=I.Writer(out/'all_root_union_projection_evidence.jsonl',budget);writers.extend((identities,provenance,evidence))
        roots=0
        for original,location in I.rows(union_ref,check,progress):
            Q.need(original['root_assignment_ordinal']==roots,'EXACT_CONTIGUOUS_ORIGINAL_ROOT_UNIONS')
            records=db.execute('SELECT context,context_ref,dispatch_ref,result,result_ref FROM records WHERE root=? ORDER BY secondary',(roots,)).fetchall()
            Q.need(records and P.strict_json(records[0][0])['kind']=='root_SMILES','ONE_NATIVE_ROOT_BEFORE_ALL_CONFORMERS')
            context=P.strict_json(records[0][0]);root_result=P.compact(P.strict_json(records[0][3]))
            conformers=[(P.strict_json(row[0]),P.compact(P.strict_json(row[3]))) for row in records[1:]]
            rebuilt=P.expected_union(context,root_result,conformers);Q.need(rebuilt==original,'EXACT_REBUILT_ORIGINAL_ALL_VARIANT_UNION_AND_COMPARISONS')
            row,is_unresolved=P.identity(original,baseline['archive_reference']['sha256']);unresolved+=is_unresolved
            identity_start=identities.bytes;identities.write(row,False)
            db.execute('INSERT INTO projected VALUES(?,?,?)',(roots,row['source_id'],P.sha(row)))
            for item in records:
                ctx=P.strict_json(item[0]);result=P.strict_json(item[3]);sid=row['source_id'] if ctx['kind']=='root_SMILES' else P.canonical(
                    [C.VERSION,'conformer',roots,ctx['global_conformer_assignment_ordinal'],ctx['native_root_ID']['text'],ctx['native_conformer_ID']['text']]).decode()
                provenance.write({'source_record_id':sid,'parent_identity_source_id':row['source_id'],'role':'all','original_native_role':None,
                    'role_basis':C.PARAMETERS['role_basis'],'source_version':C.VERSION,'original_relationship':ctx,'original_result_without_source_text':result,
                    'actual_full_producer_receipt_reference':plan['accepted_full_receipt_reference'],'original_relationship_event':P.strict_json(item[1]),
                    'original_dispatch_event':P.strict_json(item[2]),'original_result_event':P.strict_json(item[4]),'original_root_union_event':location,
                    'unknown_and_mismatch_is_not_an_exclusion':True},False)
            evidence.write({'source_id':row['source_id'],'source_version':C.VERSION,'original_union':original,'original_union_event':location,
                'projected_identity_offset_bytes':identity_start,'projected_identity_bytes':identities.bytes-identity_start,'projected_identity_canonical_sha256':P.sha(row)},False)
            comparisons.update(original['comparison_counts']);multiple+=original['multiple_observed_full_keys'];roots+=1
            progress.update(phase='PROJECTED_NATIVE_UNIONS',closed_root_unions=roots,closed_provenance_rows=provenance.rows)
        Q.need(roots==identities.rows==evidence.rows==1552 and provenance.rows==22839 and multiple==134
            and dict(comparisons)==baseline['root_SMILES_vs_MolBlock_comparison_counts'],'ALL_NATIVE_VARIANT_AND_MISMATCH_COUNTS_CONSERVED');db.commit()
        for writer in writers:writer.close()
        # Read every new identity through the actual original strict consumer;
        # the other new DATA streams also receive exact SHA/EOF/row readback.
        seen=0;consumer_counts=collections.Counter()
        for row,loc in I.rows(identities.reference(),check,progress):
            Q.need(set(row)=={'source_id','role','subdataset','inchikeys','non_h_composition'} and row['role']=='all' and row['subdataset']=='',
                'EXACT_ORIGINAL_CONSUMER_FIVE_FIELDS')
            expected=db.execute('SELECT source_id,identity_sha FROM projected WHERE root=?',(seen,)).fetchone()
            Q.need(expected==(row['source_id'],P.sha(row)),'ACTUAL_IDENTITY_REOPEN_ORIGINAL_ORDER_AND_DIGEST')
            consumer_counts.update(kind for kind,key in P.identity_keys(row));seen+=1
        Q.need(seen==1552,'ORIGINAL_CONSUMER_ALL1552_READBACK')
        for writer in (provenance,evidence):
            count=sum(1 for value,loc in I.rows(writer.reference(),check,progress));Q.need(count==writer.rows,'ALL_PROVENANCE_EVIDENCE_REOPENED_ROW_COUNT')
        identity_ref={**identities.reference(),'rows':1552};raw=[baseline['archive_reference'],*plan['data_references']]
        coverage={'schema':'expansion_all_source_identity_coverage_v1','dataset':'marcel_kraken','all_splits':True,'covered_roles':['all'],'covered_subdatasets':[],
            'unresolved_without_identity_or_composition':unresolved,'expected_identity_records':1552,'raw_artifacts':raw,'identities':identity_ref,
            'source_version':C.VERSION,'all_native_conformer_records':21287,'all_native_relationship_records':22839,
            'multiple_full_key_roots':multiple,'root_SMILES_vs_MolBlock_comparison_counts':dict(comparisons),'unknown_by_kind':dict(unknown),
            'all_old_DATA_whole_SHA_same_FD_EOF_verified':True,'all_new_DATA_readback_complete':True,'original_strict_identity_keys_consumer_rows':seen,
            'actual_full_receipt_reference':plan['accepted_full_receipt_reference'],'actual_full_accounting_reference':plan['accepted_full_accounting_reference'],
            'native_provenance_reference':provenance.reference(),'root_union_evidence_reference':evidence.reference(),
            'Root_candidate_acceptance_or_global_pool_release':False}
        coverage_ref=Q.write_new(out/'coverage.json',coverage)
        return {'coverage_reference':coverage_ref,'identities_reference':identity_ref,'native_provenance_reference':provenance.reference(),
            'root_union_evidence_reference':evidence.reference(),'root_rows':roots,'conformer_rows':21287,'relationship_rows':provenance.rows,
            'multiple_full_key_roots':multiple,'comparison_counts':dict(comparisons),'unknown_by_kind':dict(unknown),
            'unresolved_root_identities':unresolved,'consumer_readback_rows':seen,'consumer_key_kind_counts':dict(consumer_counts),
            'all_input_and_output_SHA_EOF_and_same_FD_verified':True,'dataset_ready_candidate_requires_new_actual_C0_and_independent_Root_review':True}
    finally:db.close()


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',type=Path,required=True);p.add_argument('--startup-proof',type=Path,required=True);args=p.parse_args()
    plan=Q.load(args.plan);baseline,parents=C.inputs(plan);proof=I.admit(args,plan,parents)
    out=Path(plan['output_directory']);Q.need(out.is_absolute() and Q.ROOT/'artifacts' in out.parents and '..' not in out.parts and not out.exists(),'FRESH_OUTPUT_NEVER_EDIT_OLD_SOURCE')
    out.mkdir(parents=True,mode=0o700);gate=None;budget=None;writers=[];progress={};started=time.monotonic()
    try:
        gate=fixtures(out);budget=I.Budget(plan,proof,out)
        def check():budget.check(False);Q.need(budget.stop_new is None,budget.stop_new or 'ORIGINAL_RESOURCE_STOP_NEW_SOURCE_ROWS')
        check();result=observe(plan,baseline,out,budget,check,progress,writers)
        Q.write_new(out/'receipt.json',{'schema':'KRAKEN_DECONTAMINATION_PROJECTION_RECEIPT_V1','status':'ALL_NATIVE_VARIANTS_PROJECTED_ORIGINAL_CONSUMER_READBACK_ROOT_ACCEPTANCE_REQUIRED',
            'job_id':str(proof['job_id']),'uid':1278,'endpoint':'202.38.247.57:22','node':proof['request']['node'],
            'plan_reference':Q.pin(args.plan),'startup_proof_reference':Q.pin(args.startup_proof),'accepted_full_receipt_reference':plan['accepted_full_receipt_reference'],
            'accepted_full_accounting_reference':plan['accepted_full_accounting_reference'],'fixtures':gate,'result':result,'source_version':C.VERSION,
            'global_pool_release':False,'new_graph_pickle_UFF_QM_network_calls':0,'old_data_or_once_modified':False,
            'elapsed_seconds':time.monotonic()-started,'observed_RSS_peak_bytes':budget.peak,'minimum_MemAvailable_bytes':budget.minimum,
            'runtime_statvfs_is_not_refreshed_account_quota':True,'logical_output_bytes_before_receipt':budget.used(),
            'actual_parent_cost':'PENDING_ROOT_TERMINAL_ACCOUNTING','cost_overrun_action':'REPORT_AND_CONTINUE'})
        return 0
    except BaseException as exc:
        Q.write_new(out/'failure.json',{'schema':'KRAKEN_DECONTAMINATION_PROJECTION_FAILURE_V1','error':type(exc).__name__+': '+str(exc),
            'traceback':traceback.format_exc(),'fixtures':gate,'progress':progress,'partial_DATA_references':[w.reference() for w in writers],
            'all_source_projection_complete':False,'dataset_ready_or_pool_release':False,'actual_parent_cost':'PENDING_ROOT_ACCOUNTING',
            'resource_stop_new':None if budget is None else budget.stop_new,'original_DATA_and_once_unchanged':True})
        raise
    finally:
        for writer in writers:
            if not writer.stream.closed:writer.close()


if __name__=='__main__':raise SystemExit(main())
