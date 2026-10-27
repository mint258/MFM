"""Fresh Main CPU profile, original all-row context and1000 native graph readers."""
import argparse,collections,concurrent.futures as cf,hashlib,io,json,multiprocessing as mp,os,sys,time,traceback,unittest,zipfile
from pathlib import Path,PurePosixPath
from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2 import runtime as R
from workflows.expansion.marcel_drugs_keys_main_v1 import runtime as B
from workflows.expansion.marcel_archive_bootstrap_v1 import archive as A
from . import contract as C,reader as V,kernel as K
Q=C.Q


def fixtures(out,sources):
    from .test_v1 import Boundaries
    functions,proof=K.load(sources);Boundaries.functions=functions
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(Boundaries);Q.need(suite.countTestCases()==3,'EXACT3_PURE_BOUNDARIES')
    s=io.StringIO();r=unittest.TextTestRunner(stream=s,verbosity=2).run(suite)
    v={'tests_run':r.testsRun,'failures':len(r.failures),'errors':len(r.errors),'skips':len(r.skipped),'expected_failures':len(r.expectedFailures),
        'unexpected_successes':len(r.unexpectedSuccesses),'transcript':s.getvalue(),'kernel_proof':proof,'before_original_DATA_bodies':True}
    Q.write_new(out/'fixtures3.json',v);Q.need(r.wasSuccessful() and r.testsRun==3 and not(r.skipped or r.expectedFailures or r.unexpectedSuccesses),'PURE3_PASS_BEFORE_ANY_PRODUCER_BODY');return v,functions


class Dispatch:
    def __init__(self,pool,writer,relations,budget):
        self.pool,self.writer,self.relations,self.budget=pool,writer,relations,budget;self.pending={};self.submitted=self.completed=0
        self.states=collections.Counter();self.workers=collections.Counter();self.cpu=collections.Counter();self.unknown=self.mismatch=self.compare_unknown=0
    def enqueue(self,payload):
        self.writer.write({'event':'EXACT_ORIGINAL_RECORD_AND_CACHED_SOURCE_KEYS_DURABLE_BEFORE_NATIVE_DISPATCH','payload':payload},True)
        self.pending[self.pool.submit(K.work,payload)]=payload;self.submitted+=1
        if len(self.pending)>=32:self.collect(False)
    def collect(self,all_rows):
        while self.pending:
            done,_=cf.wait(self.pending,timeout=1,return_when=cf.FIRST_COMPLETED);self.budget.check(False)
            for future in done:
                payload=self.pending.pop(future);source=payload['source'];cached=payload['cached_source_keys']
                try:
                    value=future.result();result=value['result'];Q.need(result['source']==source and result['cached_source_SMILES_observation']==cached
                        and result['raw_record_reference']==payload['raw_record_reference'],'NATIVE_RESULT_EXACT_ORIGINAL_SOURCE_AND_CACHED_IDENTITY')
                except Exception as exc:
                    result={'source':source,'cached_source_SMILES_observation':cached,'raw_record_reference':payload['raw_record_reference'],
                        'identity_state':'TECHNICAL_NATIVE_GRAPH_UNRESOLVED','has_any_unknown':True,'native_graph_full_key_and_WP5_pairs':[],
                        'native_graph_vs_source_key_set_mismatch':None,'conservative_all_observed_full_key_and_WP5_pairs':cached['full_key_and_WP5_pairs'],
                        'error':type(exc).__name__+': '+str(exc),'unknown_is_chemical_exclusion':False,'full_or_pool_release':False}
                    value={'worker_pid':None,'worker_CPU_seconds':None,'result':result}
                self.writer.write({'event':'NATIVE_GRAPH_RESULT_DURABLE_BEFORE_SQL_AND_NAME_UNION','worker_observation':value},False)
                ordinal=source['physical_ordinal'];m=result['native_graph_vs_source_key_set_mismatch']
                self.relations.db.execute('INSERT INTO native_results VALUES(?,?,?,?)',(ordinal,result['identity_state'],int(result['has_any_unknown']),None if m is None else int(m)))
                self.relations.db.executemany('INSERT INTO native_keys VALUES(?,?,?)',[(ordinal,k,w) for k,w in result['native_graph_full_key_and_WP5_pairs']])
                self.completed+=1;self.states[result['identity_state']]+=1;self.unknown+=result['has_any_unknown'];self.mismatch+=m is True;self.compare_unknown+=m is None
                pid=str(value['worker_pid']);self.workers[pid]+=1
                if value['worker_CPU_seconds'] is not None:self.cpu[pid]+=value['worker_CPU_seconds']
            if done and not all_rows:return


def observe(plan,out,proof,budget,functions):
    refs=plan['data_references'];started=time.monotonic();frames={r['path']:V.M.verify_file(r,lambda:budget.check(False)) for r in refs};verification_wall=time.monotonic()-started
    arc,inv,source_ref,profile_ref=refs;original,ordered=V.selections();wanted=set(ordered)
    Q.write_new(out/'selection_draw_order.json',{'seed':C.SEED,'sampler_python':'3.11.14','source_sample_draw_order':original,'native_profile_draw_order':ordered,
        'native_profile_selected_rows':C.PROFILE_N,'completion_order_used_for_selection':False})
    cache=V.load_profile(profile_ref,frames[profile_ref['path']],functions,budget)
    Q.need(inv['bytes']<=64<<10,'ORIGINAL_SMALL_INVENTORY_BOUND_AFTER_FIXTURES')
    inv_bytes=Path(inv['path']).read_bytes();Q.need(len(inv_bytes)==inv['bytes'] and hashlib.sha256(inv_bytes).hexdigest()==inv['sha256']
        and V.M.frame(Path(inv['path']).lstat())==frames[inv['path']],'EXACT_PRODUCER_INVENTORY_BYTES')
    inventory=[json.loads(v) for v in inv_bytes.splitlines()];Q.need(len(inventory)==2 and [v['name'] for v in inventory]==['Drugs.csv','Drugs.sdf'],'EXACT_ORIGINAL_TWO_MEMBER_ORDER')
    (out/'sqlite_tmp').mkdir();os.environ['SQLITE_TMPDIR']=str(out/'sqlite_tmp');relations=V.V.Relations(out,budget)
    relations.db.executescript('CREATE TABLE native_results(ordinal INTEGER PRIMARY KEY,state TEXT,unknown INTEGER,mismatch INTEGER);'
        'CREATE TABLE native_keys(ordinal INTEGER,full_key TEXT,wp5 TEXT,PRIMARY KEY(ordinal,full_key));')
    journal=B.Writer(out/'native_graph_results.jsonl',budget);blob=V.Blob(out/'selected_original_records.raw',budget)
    source=V.Journal(source_ref,frames[source_ref['path']],lambda:budget.check(False));dispatch=None;members=[];bound_cached=set()
    allocation={'parent_pid':os.getpid(),'parent_ticks':budget.ticks,'job_id':str(proof['job_id']),'node':proof['request']['node'],'boot_id':proof['boot_id']}
    phase=time.monotonic()
    try:
        with cf.ProcessPoolExecutor(max_workers=16,mp_context=mp.get_context('spawn'),initializer=K.initialize,initargs=(proof['request']['source_references'],)) as pool:
            dispatch=Dispatch(pool,journal,relations,budget)
            try:
                def bind(row,raw=None):
                    Q.need(source.next()==row,'EXACT1750_SOURCE_ROW_DETAILS_ORDINAL_ID_NAME_SMILES_SHA_BYTES');ordinal=row['physical_ordinal']
                    if row['member']=='Drugs.sdf' and ordinal in cache:
                        V.cached_result(cache[ordinal],row,functions);bound_cached.add(ordinal)
                    if row['member']=='Drugs.sdf' and ordinal in wanted:
                        V.bind_raw(raw,row);ref=blob.append(raw)
                        dispatch.enqueue({'source':row,'cached_source_keys':cache[ordinal],'raw_record_reference':ref,'allocation':allocation})
                    relations.add(row)
                    if row['member']=='Drugs.sdf' and ordinal in cache:relations.result(cache[ordinal])
                with Path(arc['path']).open('rb') as f:
                    Q.need(V.M.frame(os.fstat(f.fileno()))==frames[arc['path']],'SAME_HASHED_ORIGINAL_ARCHIVE_FD');pre=A.preflight(f,arc['bytes']);f.seek(0)
                    with zipfile.ZipFile(f,'r') as z:
                        infos,decoded=A.directory(z,pre,sum(v['decoded_bytes'] for v in inventory));Q.need(len(infos)==2,'EXACT_ORIGINAL_ARCHIVE_TWO_MEMBERS')
                        for info,row in zip(infos,inventory):
                            Q.need(info.filename==row['name'] and not info.is_dir() and info.file_size==row['decoded_bytes'] and info.compress_size==row['compressed_bytes']
                                and info.CRC==row['CRC32_observed'] and row['EOF_CRC_passed'] is True,'EXACT_BOOTSTRAP_MEMBER_METADATA')
                            with z.open(info) as stream:
                                member=V.M.Member(stream,row,lambda:budget.check(False))
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
                                        original_row=V.source_row('Drugs.sdf',ordinal,details);bind(original_row,tracked.take(original_row))
                                    sdf_count=V.P.sdf_rows(tracked,emit,lambda:budget.check(False));Q.need(not tracked.current and sdf_count==C.N,'ALL558002_EXACT_SDF_RECORD_BOUNDARIES')
                                members.append(member.finish())
                    Q.need(V.M.frame(os.fstat(f.fileno()))==frames[arc['path']]==V.M.frame(Path(arc['path']).lstat()),'ORIGINAL_ARCHIVE_STABLE_AFTER_ALL_CRC_EOF')
                source.finish(C.N+C.D.CSV_N);Q.need(bound_cached==set(original) and dispatch.submitted==C.PROFILE_N,'ALL10000_SOURCE_KEYS_BOUND_AND_EXACT1000_NATIVE_DISPATCHES')
                dispatch.collect(True);Q.need(dispatch.completed==C.PROFILE_N,'EVERY_SELECTED_NATIVE_RESULT_DURABLE_UNKNOWN_RETAINED')
            finally:dispatch.collect(True)
        context=relations.context();Q.need(relations.db.execute('SELECT count(*) FROM results').fetchone()[0]==C.SOURCE_PROFILE_N,'ORIGINAL10000_SOURCE_KEY_CONFORMERS_REUSED_NOT_RECALCULATED')
        journal.close();blob_ref=blob.close();names=B.Writer(out/'all_CSV_names_all_observed_key_unions.jsonl',budget)
        try:name_counts=V.export_names(relations,names,budget)
        finally:names.close()
        relations.db.commit();relations.db.close()
        return {'input_context':context,'all_member_observations':members,'all_current_ZIP_EOF_CRC_SHA_and_source_row_bindings_complete':True,'CSV_grammar':csv_summary,
            'original_sdf_function_objects':{n:{'filename':getattr(V.P,n).__code__.co_filename,'first_line':getattr(V.P,n).__code__.co_firstlineno} for n in ('sdf_rows','sdf_record')},
            'source_profile_keys_reused_rows':len(bound_cached),'native_graph_completed_rows':dispatch.completed,'native_graph_unknown_rows':dispatch.unknown,
            'native_graph_source_key_set_mismatch_rows':dispatch.mismatch,'native_graph_source_key_comparison_UNKNOWN_rows':dispatch.compare_unknown,
            'native_graph_NOT_YET_EXAMINED_rows':C.N-dispatch.completed,'identity_state_counts':dict(dispatch.states),'all_name_union_counts':name_counts,
            'native_result_journal_reference':journal.reference(),'original_selected_records_blob_reference':blob_ref,
            'all_name_union_reference':names.reference(),'worker_record_counts':dict(dispatch.workers),'worker_CPU_seconds':dict(dispatch.cpu),
            'whole_DATA_SHA_verification_wall_seconds':verification_wall,'profile_observation_and_context_wall_seconds':time.monotonic()-phase,
            'native_composition_fallback_claimed':False,'graph_source_mismatch_is_chemical_exclusion':False,'full_or_pool_release':False}
    finally:
        source.close()
        prefix=blob.close();Q.write_new(out/'actual_raw_record_prefix.json',{'actual_reference':prefix,'records':blob.rows,'future_or_unwritten_SHA_claimed':False})
        if not journal.stream.closed:journal.close()
        try:relations.db.close()
        except Exception:pass


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',type=Path,required=True);p.add_argument('--startup-proof',type=Path,required=True);a=p.parse_args()
    plan=Q.load(a.plan);_,_,_,data,parents=C.inputs(plan);Q.need(plan['schema']=='MARCEL_DRUGS_NATIVE_GRAPH_PROFILE_PLAN_V1' and plan['mode']=='profile'
        and plan['scope_parameters']==C.PARAMETERS and plan['data_references']==data,'EXACT_NATIVE1000_PROFILE_ONLY_PLAN')
    argv=[Q.PY,'-B','-m',C.MODULE,'--plan',str(a.plan),'--startup-proof',str(a.startup_proof)]
    proof=R.require_startup(a.startup_proof,expected_scope_key=C.KEY,expected_scope_parameters=C.PARAMETERS,expected_execution_argv=argv,
        expected_source=__file__,expected_kind='analysis',required_references=[Q.pin(a.plan),*parents,plan['cost_decision_reference']])
    req=proof['request'];authority=C.meta(req['queue_authority_reference']);allowed={'compute-0-'+str(n) for n in authority['allowed_nodes']['analysis']}
    Q.need(req['node'] in allowed and req['pilot'] is True and req['wall_seconds']==plan['wall_seconds']==7200 and req['estimated_peak_output_bytes']==plan['output_cap_bytes']==C.CAP
        and req['data_references']==data and not req.get('deferred_authority_references'),'EXACT_CPU16_NO_MEM_2GiB2H_NATIVE_PROFILE')
    review=C.meta(req['scope']['review']);Q.need(req['scope']['mode']=='BOUNDED_PERFORMANCE_BATCH' and review['bounded_batch_limits_reviewed'] is True
        and review['author_native_SDF_reader_and_all_observed_union_reviewed'] is True and review['full_or_pool_release'] is False,'ROOT_EXACT_BOUNDED_NATIVE_GRAPH_SCOPE')
    cost=C.meta(plan['cost_decision_reference']);Q.need(cost['status']=='USER_AUTHORIZED' and cost['on_overrun']=='REPORT_AND_CONTINUE' and cost['scientific_quality_thresholds_unchanged'] is True,'ACTUAL_COST_AND_QUALITY_AUTHORITY')
    for path in [*(C.HERE/n for n in C.FILES),*C.OLD]:Q.need(Q.pin(path) in req['source_references'],'ALL_NEW_AND_REUSED_FROZEN_SOURCE_BYTES_PINNED')
    Q.need(Path(sys.modules['__main__'].__file__).absolute()==C.HERE/'run.py' and sys.argv==[str(C.HERE/'run.py'),*argv[4:]] and sys.version_info[:3]==(3,11,14),'EXACT_PRIMARY_ARGV_AND_ORIGINAL_SAMPLER_PYTHON')
    for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='1'
    out=Path(plan['output_directory']);Q.need(out.is_absolute() and '..' not in out.parts and Q.ROOT/'artifacts' in out.parents and not out.exists()
        and not any(v.is_symlink() for v in (out,*out.parents)),'FRESH_NATIVE_PROFILE_OUTPUT');out.mkdir(parents=True,mode=0o700)
    budget=B.Budget(plan,proof,out);gate=None;started=time.monotonic()
    try:
        gate,functions=fixtures(out,req['source_references']);budget.check(force=True);result=observe(plan,out,proof,budget,functions)
        Q.write_new(out/'receipt.json',{'schema':'MARCEL_DRUGS_NATIVE_GRAPH_PROFILE_RECEIPT_V1','status':'EXACT1000_NATIVE_GRAPH_OBSERVATIONS_COMPLETE_UNKNOWNS_AND_UNIONS_RETAINED',
            'mode':'profile','job_id':str(proof['job_id']),'uid':1278,'node':req['node'],'endpoint':'202.38.247.57:22','plan_reference':Q.pin(a.plan),'startup_proof_reference':Q.pin(a.startup_proof),
            'accepted_source_key_profile_receipt_reference':plan['accepted_source_key_profile_receipt_reference'],'accepted_source_key_profile_accounting_reference':plan['accepted_source_key_profile_accounting_reference'],
            'data_references':data,'fixtures':gate,**result,'owned_output_bytes_before_receipt':budget.used(),'observed_RSS_peak_bytes':budget.peak,
            'minimum_MemAvailable_bytes':budget.minimum,'elapsed_seconds':time.monotonic()-started,'actual_terminal_cost':'PENDING_ROOT_ACCOUNTING',
            'native_profile_C0_means_full_graph_population_accepted':False,'global_decontamination_or_pool_or_full_release':False})
        return 0
    except BaseException as exc:
        Q.write_new(out/'failure.json',{'error':repr(exc),'traceback':traceback.format_exc(),'fixtures':gate,'durable_prefixes_and_original_inputs_retained':True,
            'partial_profile_is_full':False,'unknown_is_exclusion':False,'full_or_pool_release':False,'actual_terminal_cost':'PENDING_ROOT_ACCOUNTING'});raise


if __name__=='__main__':raise SystemExit(main())
