"""Actual native1000 adoption plus bounded557002 new author SDF graph calls."""
from __future__ import annotations
import argparse,collections,concurrent.futures as cf,hashlib,io,json,multiprocessing as mp,os,sys,time,traceback,unittest,zipfile
from pathlib import Path
from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2 import runtime as R
from workflows.expansion.marcel_drugs_keys_main_v1 import runtime as B
from workflows.expansion.marcel_drugs_native_graph_profile_v1 import run as PROFILE,reader as V,kernel as K
from workflows.expansion.marcel_archive_bootstrap_v1 import archive as A
from . import contract as C,cache as F
Q=C.Q


def fixtures(out,sources):
    old,functions=PROFILE.fixtures(out,sources)
    from .test_v1 import Boundaries
    Boundaries.functions=functions
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(Boundaries);Q.need(suite.countTestCases()==3,'EXACT3_NEW_FULL_BOUNDARIES')
    stream=io.StringIO();result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    gate={'tests_run':result.testsRun,'original_profile_methods':old['tests_run'],'new_methods':3,
        'failures':len(result.failures),'errors':len(result.errors),'skips':len(result.skipped),
        'expected_failures':len(result.expectedFailures),'unexpected_successes':len(result.unexpectedSuccesses),
        'transcript':stream.getvalue(),'before_all_original_DATA_bodies':True,'original_kernel_proof':old['kernel_proof']}
    Q.write_new(out/'full_fixture3.json',gate)
    Q.need(result.testsRun==3 and result.wasSuccessful() and not(result.skipped or result.expectedFailures or result.unexpectedSuccesses),
        'ORIGINAL3_AND_NEW3_PASS_BEFORE_FULL_DATA')
    return gate,functions


def adopt(old,current_source,current_raw,rawref,journal,relations,origin):
    observation=old['original_worker_observation'];result=observation['result']
    Q.need(F.digest(current_source)==old['source_sha256'] and result['source']==current_source
        and len(current_raw)==old['raw_record_bytes'] and hashlib.sha256(current_raw).hexdigest()==old['raw_record_sha256'],
        'CURRENT_ORIGINAL_ZIP_BYTES_BIND_OLD_PROFILE_NATIVE_OBSERVATION')
    journal.write({'event':'ACTUAL_NATIVE1000_C0_OBSERVATION_ADOPTED_DURABLE_BEFORE_SQL_UNION',
        'original_profile_origin_references':origin,'original_profile_payload':old['original_payload'],
        'original_worker_observation':observation,'current_full_raw_record_reference':rawref,
        'new_SDMolSupplier_call_for_this_record':False,'old_allocation_metadata_preserved_not_claimed_live':True},True)
    ordinal=current_source['physical_ordinal'];m=result['native_graph_vs_source_key_set_mismatch']
    relations.db.execute('INSERT INTO native_results VALUES(?,?,?,?)',(ordinal,result['identity_state'],int(result['has_any_unknown']),None if m is None else int(m)))
    relations.db.executemany('INSERT INTO native_keys VALUES(?,?,?)',[(ordinal,k,w) for k,w in result['native_graph_full_key_and_WP5_pairs']])
    return result


def observe(plan,out,proof,budget,functions,native):
    refs=plan['data_references'];start=time.monotonic()
    frames={r['path']:V.M.verify_file(r,lambda:budget.check(True)) for r in refs};verify_wall=time.monotonic()-start
    arc,inv,source_ref,keys_ref,native_ref,old_blob=refs
    Q.need(inv['bytes']<=64<<10,'ORIGINAL_SMALL_INVENTORY_BOUND_AFTER_FIXTURES')
    inv_bytes=Path(inv['path']).read_bytes()
    Q.need(len(inv_bytes)==inv['bytes'] and hashlib.sha256(inv_bytes).hexdigest()==inv['sha256']
        and V.M.frame(Path(inv['path']).lstat())==frames[inv['path']],'EXACT_OLD_BOOTSTRAP_INVENTORY')
    inventory=[json.loads(v) for v in inv_bytes.splitlines()]
    Q.need(len(inventory)==2 and [v['name'] for v in inventory]==['Drugs.csv','Drugs.sdf'],'ALL_ORIGINAL_TWO_MEMBERS_FIXED_ORDER')
    (out/'sqlite_tmp').mkdir();os.environ['SQLITE_TMPDIR']=str(out/'sqlite_tmp')
    relations=V.V.Relations(out,budget)
    relations.db.executescript('CREATE TABLE native_results(ordinal INTEGER PRIMARY KEY,state TEXT,unknown INTEGER,mismatch INTEGER);'
        'CREATE TABLE native_keys(ordinal INTEGER,full_key TEXT,wp5 TEXT,PRIMARY KEY(ordinal,full_key));')
    journal=B.Writer(out/'all_native_graph_results.jsonl',budget);blob=V.Blob(out/'selected_original_records.raw',budget)
    source=V.Journal(source_ref,frames[source_ref['path']],lambda:budget.check(True))
    dispatch=None;members=[];adopted=set();adopt_states=collections.Counter();bound=0;names=None
    origin={k:plan[k] for k in ('accepted_native_profile_receipt_reference','accepted_native_profile_accounting_reference')}
    origin['startup_proof_reference']=native['startup_proof_reference'];origin['raw_accounting_reference']=C.meta(plan['accepted_native_profile_accounting_reference'])['raw_sacct_reference']
    allocation={'parent_pid':os.getpid(),'parent_ticks':budget.ticks,'job_id':str(proof['job_id']),'node':proof['request']['node'],'boot_id':proof['boot_id']}
    try:
        cache=F.load_full(keys_ref,frames[keys_ref['path']],relations.db,functions,budget)
        old=F.load_native(native_ref,frames[native_ref['path']],old_blob,frames[old_blob['path']],cache,functions,budget,native,C.meta(native['startup_proof_reference']))
        with cf.ProcessPoolExecutor(max_workers=16,mp_context=mp.get_context('spawn'),initializer=K.initialize,
            initargs=(proof['request']['source_references'],)) as pool:
            dispatch=PROFILE.Dispatch(pool,journal,relations,budget)
            try:
                def bind(row,raw=None):
                    nonlocal bound
                    budget.check(True);Q.need(source.next()==row,'EVERY633101_ORIGINAL_SOURCE_ROW_EXACT_FROM_ZIP')
                    if row['member']=='Drugs.sdf':
                        cached=cache.get(row);V.bind_raw(raw,row);ref=blob.append(raw);bound+=1
                        if row['physical_ordinal'] in old:
                            ordinal=row['physical_ordinal'];Q.need(ordinal not in adopted,'NO_DUPLICATE_OLD_NATIVE_ADOPTION')
                            result=adopt(old[ordinal],row,raw,ref,journal,relations,origin);adopted.add(ordinal);adopt_states[result['identity_state']]+=1
                        else:dispatch.enqueue({'source':row,'cached_source_keys':cached,'raw_record_reference':ref,'allocation':allocation})
                    relations.add(row)
                    if row['member']=='Drugs.sdf':relations.result(cached)
                with Path(arc['path']).open('rb') as f:
                    Q.need(V.M.frame(os.fstat(f.fileno()))==frames[arc['path']],'SAME_CURRENT_WHOLE_SHA_ARCHIVE_FD')
                    pre=A.preflight(f,arc['bytes']);f.seek(0)
                    with zipfile.ZipFile(f,'r') as z:
                        infos,_=A.directory(z,pre,sum(v['decoded_bytes'] for v in inventory));Q.need(len(infos)==2,'ALL_ORIGINAL_ZIP_MEMBERS')
                        for info,row in zip(infos,inventory):
                            Q.need(info.filename==row['name'] and not info.is_dir() and info.file_size==row['decoded_bytes']
                                and info.compress_size==row['compressed_bytes'] and info.CRC==row['CRC32_observed']
                                and row['EOF_CRC_passed'] is True,'EXACT_PRODUCER_MEMBER_CRC_LENGTH_METADATA')
                            with z.open(info) as stream:
                                member=V.M.Member(stream,row,lambda:budget.check(True))
                                if info.filename=='Drugs.csv':
                                    parser=V.P.NameCSV(lambda ordinal,name,details:bind(V.source_row('Drugs.csv',ordinal,details)))
                                    while True:
                                        block=member.read(1<<20)
                                        if not block:break
                                        parser.feed(block)
                                    csv_summary=parser.finish()
                                else:
                                    tracked=V.TrackedRecord(member)
                                    def emit(ordinal,name,fields,details):
                                        source_row=V.source_row('Drugs.sdf',ordinal,details);bind(source_row,tracked.take(source_row))
                                    count=V.P.sdf_rows(tracked,emit,lambda:budget.check(True))
                                    Q.need(not tracked.current and count==C.N,'ALL558002_ORIGINAL_PHYSICAL_RECORDS_ONCE')
                                members.append(member.finish())
                    Q.need(V.M.frame(os.fstat(f.fileno()))==frames[arc['path']]==V.M.frame(Path(arc['path']).lstat()),'ORIGINAL_ARCHIVE_STABLE_AFTER_COMPLETE_MEMBER_READS')
                source.finish(C.N+C.CSV_N)
                Q.need(bound==C.N and adopted==set(old) and len(adopted)==C.INHERITED and dispatch.submitted==C.NEW,
                    'EXACT1000_ADOPTED_PLUS557002_NEW_WITHOUT_REPLAYING_NATIVE_PROFILE')
                dispatch.collect(True);Q.need(dispatch.completed==C.NEW,'EVERY_NEW_GRAPH_RESULT_DURABLE_UNKNOWNS_RETAINED')
            finally:dispatch.collect(True)
        context=relations.context()
        Q.need(relations.db.execute('SELECT count(*) FROM results').fetchone()[0]==C.N
            and relations.db.execute('SELECT count(*) FROM native_results').fetchone()[0]==C.N,'FULL_SOURCE_AND_NATIVE_SQL_ROWS_EXACTLY558002')
        journal.close();blobref=blob.close();sdf=next(r for r in members if r['name']=='Drugs.sdf')
        Q.need(blob.rows==C.N and blobref['bytes']==sdf['decoded_bytes'] and blobref['sha256']==sdf['decoded_sha256'],
            'NEW_ALL_RAW_BLOB_EXACT_COMPLETE_ORIGINAL_SDF_BYTES_SHA_NO_RECORD_DROPPED')
        names=B.Writer(out/'all_CSV_names_all_source_and_native_full_key_unions.jsonl',budget);full_names=F.FullNames(names)
        counts=V.export_names(relations,full_names,budget);names.close()
        Q.need(full_names.names==C.CSV_N and full_names.rows==C.N,'ALL75099_NAMES_COVER_ALL558002_CONFORMERS')
        relations.db.commit();relations.db.close()
        for ref in refs:Q.need(V.M.frame(Path(ref['path']).lstat())==frames[ref['path']],'ALL_SIX_ORIGINAL_INPUTS_STABLE_AT_FULL_CLOSURE')
        for ref in proof['request']['source_references']:Q.need(Q.pin(ref['path'])==ref,'ORIGINAL_AND_NEW_SOURCE_BYTES_UNCHANGED_AT_FULL_CLOSURE')
        states=dispatch.states+adopt_states
        return {'input_context':context,'all_member_observations':members,'CSV_grammar':csv_summary,
            'all6_DATA_current_whole_SHA_fstat_verified':True,'all_original_ZIP_members_CRC_SHA_EOF_complete':True,
            'source_key_full_rows_reused_without_SMILES_recomputation':C.N,'native_profile_C0_observations_adopted':len(adopted),
            'new_native_graph_dispatches':dispatch.submitted,'new_native_graph_completed_rows':dispatch.completed,
            'all_native_graph_completed_rows':C.N,'native_graph_NOT_YET_EXAMINED_rows':0,
            'native_graph_unknown_rows':dispatch.unknown,'native_graph_source_key_set_mismatch_rows':dispatch.mismatch,
            'native_graph_source_key_comparison_UNKNOWN_rows':dispatch.compare_unknown,'identity_state_counts':dict(states),
            'all_name_union_counts':counts,'native_result_journal_reference':journal.reference(),'all_original_SDF_raw_blob_reference':blobref,
            'all_name_union_reference':names.reference(),'new_worker_record_counts':dict(dispatch.workers),
            'new_worker_CPU_seconds':dict(dispatch.cpu),'whole_DATA_SHA_verification_wall_seconds':verify_wall,
            'original_function_objects':{name:{'module':fn.__module__,'filename':fn.__code__.co_filename,'first_line':fn.__code__.co_firstlineno}
                for name,fn in {'sdf_rows':V.P.sdf_rows,'sdf_record':V.P.sdf_record,'native_graph_file':K.graph_file,'native_work':K.work,
                    'old_Dispatch_enqueue':PROFILE.Dispatch.enqueue,'old_Budget_check':B.Budget.check,'old_export_names':V.export_names}.items()},
            'profile1000_native_program_calls_replayed':False,'unknown_or_graph_mismatch_is_chemical_exclusion':False,
            'native_composition_fallback_claimed':False,'full_native_coverage_is_pool_or_global_decontamination_release':False}
    finally:
        source.close()
        prefix=blob.close();Q.write_new(out/'actual_original_raw_prefix.json',{'actual_reference':prefix,'records':blob.rows,
            'future_or_unwritten_size_SHA_claimed':False,'complete558002_claimed_by_prefix_alone':False})
        if not journal.stream.closed:journal.close()
        if names is not None and not names.stream.closed:names.close()
        try:relations.db.commit();relations.db.close()
        except Exception:pass


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',type=Path,required=True);p.add_argument('--startup-proof',type=Path,required=True);a=p.parse_args()
    plan=Q.load(a.plan);native,full,original,data,parents=C.inputs(plan)
    Q.need(plan['schema']=='MARCEL_DRUGS_NATIVE_GRAPH_FULL_PLAN_V1' and plan['mode']=='full'
        and plan['scope_parameters']==C.parameters() and plan['data_references']==data,'EXACT_FINITE_FULL_NATIVE_PLAN')
    argv=[Q.PY,'-B','-m',C.MODULE,'--plan',str(a.plan),'--startup-proof',str(a.startup_proof)]
    proof=R.require_startup(a.startup_proof,expected_scope_key=C.KEY,expected_scope_parameters=C.parameters(),expected_execution_argv=argv,
        expected_source=__file__,expected_kind='analysis',required_references=[Q.pin(a.plan),*parents,plan['cost_decision_reference']])
    req=proof['request'];review=C.meta(req['scope']['review'])
    authority=C.meta(req['queue_authority_reference']);allowed={'compute-0-'+str(n) for n in authority['allowed_nodes']['analysis']}
    Q.need(req['node'] in allowed and req['cpus']==16 and req['memory_policy']=='SLURM_DEFAULT_UNSPECIFIED' and req['pilot'] is False
        and req['wall_seconds']==plan['wall_seconds']==C.WALL and req['estimated_peak_output_bytes']==plan['output_cap_bytes']==C.CAP
        and req['data_references']==data and not req.get('deferred_authority_references')
        and req['scope']['mode']=='FULL_SOURCE_AFTER_PROFILE' and review['profile_reviewed'] is True
        and review['approved_profile_reference']==plan['accepted_native_profile_receipt_reference']
        and review['closed1000_adoption_and557002_new_only_reviewed'] is True,'EXACT_ROOT_FULL_SCOPE_16CPU_NO_MEM_12H_12GiB')
    cost=C.meta(plan['cost_decision_reference']);Q.need(cost['status']=='USER_AUTHORIZED' and cost['on_overrun']=='REPORT_AND_CONTINUE'
        and cost['scientific_quality_thresholds_unchanged'] is True,'ACTUAL_QUALITY_AND_REPORT_CONTINUE_AUTHORITY')
    for path in C.source_paths():Q.need(Q.pin(path) in req['source_references'],'ALL_DIRECT_ORIGINAL_AND_NEW_SOURCE_BYTES_PINNED')
    Q.need(Path(sys.modules['__main__'].__file__).absolute()==C.HERE/'run.py'
        and sys.argv==[str(C.HERE/'run.py'),*argv[4:]] and sys.version_info[:3]==(3,11,14),'EXACT_FULL_PRIMARY_ARGV_AND_PYTHON')
    out=Path(plan['output_directory']);allowed=Q.ROOT/'artifacts/expansion/marcel_drugs_native_graph_full_v1'
    Q.need(out.is_absolute() and '..' not in out.parts and allowed in out.parents and not out.exists()
        and not any(p.is_symlink() for p in (out,*out.parents)),'FRESH_NEW_FULL_NATIVE_OUTPUT_ONLY')
    out.mkdir(parents=True,mode=0o700)
    for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='1'
    os.environ['CUDA_VISIBLE_DEVICES']=''
    # Same original Budget object/functions; reserve the existing16*16MiB /tmp envelope separately from shared output.
    resource_plan=dict(plan);resource_plan['output_cap_bytes']=C.SHARED_CAP
    budget=B.Budget(resource_plan,proof,out);started=time.monotonic();gate=None
    try:
        gate,functions=fixtures(out,req['source_references']);budget.check(force=True)
        result=observe(plan,out,proof,budget,functions,native)
        Q.write_new(out/'receipt.json',{'schema':'MARCEL_DRUGS_NATIVE_GRAPH_FULL_RECEIPT_V1',
            'status':'ALL558002_NATIVE_GRAPH_OBSERVATIONS_COMPLETE_UNKNOWNS_AND_CONSERVATIVE_UNIONS_RETAINED',
            'mode':'full','job_id':str(proof['job_id']),'uid':1278,'node':req['node'],'endpoint':'202.38.247.57:22',
            'plan_reference':Q.pin(a.plan),'startup_proof_reference':Q.pin(a.startup_proof),'data_references':data,
            **{k:plan[k] for k in ('accepted_native_profile_receipt_reference','accepted_native_profile_accounting_reference',
                'accepted_source_key_full_receipt_reference','accepted_source_key_full_accounting_reference','profile_budget_root_review_reference')},
            'fixtures':gate,**result,'owned_output_bytes_before_receipt':budget.used(),'observed_parent_children_RSS_peak_bytes':budget.peak,
            'minimum_MemAvailable_bytes':budget.minimum,'elapsed_seconds':time.monotonic()-started,'actual_terminal_cost':'PENDING_ROOT_ACCOUNTING',
            'shared_output_budget_bytes':C.SHARED_CAP,'reserved_node_local_SDF_bytes':C.NODE_SDF_RESERVE,
            'new_network_UFF_QM_calls':0,'global_decontamination_or_pool_or_training_release':False})
        return 0
    except BaseException as exc:
        Q.write_new(out/'failure.json',{'error':repr(exc),'traceback':traceback.format_exc(),'fixtures':gate,
            'original_inputs_and_durable_full_prefixes_retained':True,'unknown_is_chemical_exclusion':False,
            'partial_full_attempt_is_accepted_full':False,'global_decontamination_pool_training_release':False,'actual_terminal_cost':'PENDING_ROOT_ACCOUNTING'})
        raise
if __name__=='__main__':raise SystemExit(main())
