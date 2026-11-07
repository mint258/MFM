"""One unchanged original log, uniform true profile then explicitly authorized full."""
import argparse,collections,concurrent.futures as cf,hashlib,io,json,multiprocessing as mp,os,random,sys,time,traceback,unittest
from pathlib import Path
from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2 import runtime as R
from workflows.expansion.marcel_identity_format_probe_v1 import run as M
from . import contract as C,rows as V,kernel as K,runtime as B
Q=C.Q


def selected(mode):return set(random.Random(C.SEED).sample(range(C.N),C.PILOT_N)) if mode=='profile' else None


def fixtures(out,source_refs):
    from .test_v1 import Boundaries
    functions,proof=K.load(source_refs);Boundaries.functions=functions
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(Boundaries);Q.need(suite.countTestCases()==3,'EXACT3_BOUNDARIES_BEFORE_LOG_BODY')
    s=io.StringIO();r=unittest.TextTestRunner(stream=s,verbosity=2).run(suite)
    v={'tests_run':r.testsRun,'failures':len(r.failures),'errors':len(r.errors),'skips':len(r.skipped),
        'expected_failures':len(r.expectedFailures),'unexpected_successes':len(r.unexpectedSuccesses),'transcript':s.getvalue(),
        'kernel_proof':proof,'before_source_log_body':True}
    Q.write_new(out/'fixtures3.json',v);Q.need(r.wasSuccessful() and r.testsRun==3
        and not(r.skipped or r.expectedFailures or r.unexpectedSuccesses),'PURE3_PASS_BEFORE_ORIGINAL_IDENTITY_LOG');return v


class Dispatch:
    def __init__(self,pool,writer,relations,budget):
        self.pool,self.writer,self.relations,self.budget=pool,writer,relations,budget;self.pending={};self.submitted=self.completed=0
        self.states=collections.Counter();self.worker_rows=collections.Counter();self.worker_CPU=collections.Counter();self.unknown=0
    def enqueue(self,row):
        self.writer.write({'event':'ORIGINAL_CONFORMER_SOURCE_DURABLE_BEFORE_DISPATCH','source':row},True)
        self.pending[self.pool.submit(K.work,row)]=row;self.submitted+=1
        if len(self.pending)>=32:self.collect(False)
    def collect(self,all_rows):
        while self.pending:
            done,_=cf.wait(self.pending,timeout=1,return_when=cf.FIRST_COMPLETED);self.budget.check(False)
            for future in done:
                row=self.pending.pop(future)
                try:value=future.result();Q.need(value['result']['source']==row,'WORKER_ALL_ORIGINAL_SOURCE_FIELDS_UNCHANGED')
                except Exception as exc:value={'worker_pid':None,'worker_CPU_seconds':None,'result':{'source':row,
                    'identity_state':'TECHNICAL_UNRESOLVED','has_any_unknown':True,'full_key_and_WP5_pairs':[],
                    'error':type(exc).__name__+': '+str(exc),'unknown_is_chemical_exclusion':False}}
                self.writer.write({'event':'ORIGINAL_CONFORMER_IDENTITY_RESULT_DURABLE','worker_observation':value},False)
                self.relations.result(value['result']);self.completed+=1;self.states[value['result']['identity_state']]+=1
                self.unknown+=value['result']['has_any_unknown'];pid=str(value['worker_pid']);self.worker_rows[pid]+=1
                if value['worker_CPU_seconds'] is not None:self.worker_CPU[pid]+=value['worker_CPU_seconds']
            if done and not all_rows:return


def observe(plan,out,proof,budget):
    reference=plan['input_reference'];verify_start=time.monotonic();fr=M.verify_file(reference,budget.check);verification_wall=time.monotonic()-verify_start
    wanted=selected(plan['mode']);expected=C.PILOT_N if wanted is not None else C.N
    Q.write_new(out/'selected_ordinals.json',{'mode':plan['mode'],'selection':'UNIFORM_WITHOUT_REPLACEMENT' if wanted is not None else 'ALL_PHYSICAL_SDF_ORDINALS',
        'seed':C.SEED if wanted is not None else None,'selected_SDF_rows':expected,'ordinals':sorted(wanted) if wanted is not None else None,
        'all_source_CSV_and_SDF_context_still_traversed':True})
    (out/'sqlite_tmp').mkdir();os.environ['SQLITE_TMPDIR']=str(out/'sqlite_tmp');relations=V.Relations(out,budget)
    journal=B.Writer(out/'selected_conformer_results.jsonl',budget);input_started=time.monotonic();source_h=hashlib.sha256();source_bytes=0;source_lines=0
    dispatch=None
    try:
        with cf.ProcessPoolExecutor(max_workers=16,mp_context=mp.get_context('spawn'),initializer=K.initialize,initargs=(proof['request']['source_references'],)) as pool:
            dispatch=Dispatch(pool,journal,relations,budget)
            try:
                with Path(reference['path']).open('rb') as f:
                    Q.need(M.frame(os.fstat(f.fileno()))==fr,'SAME_HASHED_LOG_FRAME')
                    while True:
                        budget.check();line=f.readline((8<<20)+1)
                        if not line:break
                        Q.need(len(line)<=8<<20 and line.endswith(b'\n'),'EXACT_COMPLETE_BOUNDED_ORIGINAL_JSONL_ROW')
                        source_h.update(line);source_bytes+=len(line);source_lines+=1;row=json.loads(line);relations.add(row)
                        if row['member']=='Drugs.sdf' and (wanted is None or row['physical_ordinal'] in wanted):dispatch.enqueue(row)
                    Q.need(M.frame(os.fstat(f.fileno()))==fr==M.frame(Path(reference['path']).lstat())
                        and source_bytes==reference['bytes'] and source_h.hexdigest()==reference['sha256']
                        and source_lines==C.N+C.CSV_N,'COMPLETE_CURRENT633101_SOURCE_LINES_SHA_FRAME')
                dispatch.collect(True)
                Q.need(dispatch.submitted==dispatch.completed==expected,'EXACT_SELECTED_SOURCE_AND_DURABLE_RESULT_COUNT')
            finally:dispatch.collect(True)
        input_wall=time.monotonic()-input_started;context=relations.context()
        q=relations.db.execute('SELECT count(*) FROM results').fetchone()[0];Q.need(q==expected,'DURABLE_INDEX_RESULT_COUNT')
        journal.close();name_writer=B.Writer(out/'all_CSV_name_conservative_identity_unions.jsonl',budget)
        try:names=relations.export(name_writer.write,plan['mode']=='full')
        finally:name_writer.close()
        relations.db.commit();relations.db.close()
        return {'selected_completed_rows':dispatch.completed,'selected_unknown_rows':dispatch.unknown,'identity_state_counts':dict(dispatch.states),
            'input_context':context,'name_identity_union_counts':names,'selected_result_journal_reference':journal.reference(),
            'all_CSV_name_union_reference':name_writer.reference(),'worker_record_counts':dict(dispatch.worker_rows),'worker_CPU_seconds':dict(dispatch.worker_CPU),
            'source_full_SHA_verification_wall_seconds':verification_wall,'source_scan_and_selected_worker_phase_wall_seconds':input_wall,
            'uniform_sample_means_exclude_no_extra_diagnostic_cohort':True,'native_graph_stereo_or_pool_accepted':False}
    finally:
        if not journal.stream.closed:journal.close()
        try:relations.db.close()
        except Exception:pass


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',type=Path,required=True);p.add_argument('--startup-proof',type=Path,required=True);a=p.parse_args()
    plan=Q.load(a.plan);_,parents=C.inputs(plan);params=C.parameters(plan['mode'],plan['output_cap_bytes'])
    Q.need(plan['schema']=='MARCEL_DRUGS_KEYS_PLAN_V1' and plan['scope_parameters']==params,'EXACT_KEYS_STAGE_PLAN')
    argv=[Q.PY,'-B','-m',C.MODULE,'--plan',str(a.plan),'--startup-proof',str(a.startup_proof)]
    proof=R.require_startup(a.startup_proof,expected_scope_key=C.scope_key(plan['mode']),expected_scope_parameters=params,expected_execution_argv=argv,
        expected_source=__file__,expected_kind='analysis',required_references=[Q.pin(a.plan),*parents,plan['cost_decision_reference']])
    req=proof['request'];authority=C.M.meta(req['queue_authority_reference']);allowed={'compute-0-'+str(n) for n in authority['allowed_nodes']['analysis']}
    Q.need(req['node'] in allowed and req['pilot'] is (plan['mode']=='profile') and req['wall_seconds']==plan['wall_seconds']
        and type(plan['wall_seconds']) is int and 600<=plan['wall_seconds']<=(7200 if plan['mode']=='profile' else 172800)
        and plan['wall_seconds']%60==0 and req['estimated_peak_output_bytes']==plan['output_cap_bytes']
        and req['data_references']==[plan['input_reference']] and not req.get('deferred_authority_references'),'EXACT_CPU16_NO_MEM_ACTUAL_PROFILE_OR_REVIEWED_FULL')
    review=C.M.meta(req['scope']['review']);Q.need(req['scope']['mode']==('BOUNDED_PERFORMANCE_BATCH' if plan['mode']=='profile' else 'FULL_SOURCE_AFTER_PROFILE')
        and review['all_native_conformers_variants_and_unknowns_retained'] is True
        and review['global_decontamination_pool_training_release'] is False,'ROOT_EXACT_IDENTITY_ONLY_REVIEW')
    cost=C.M.meta(plan['cost_decision_reference']);Q.need(cost['status']=='USER_AUTHORIZED' and cost['on_overrun']=='REPORT_AND_CONTINUE'
        and cost['scientific_quality_thresholds_unchanged'] is True,'COST_AND_QUALITY_AUTHORITY')
    for path in [*(C.HERE/n for n in C.FILES),*C.OLD]:Q.need(Q.pin(path) in req['source_references'],'ALL_CURRENT_IMPORT_AND_FROZEN_SOURCE_PINS')
    Q.need(Path(sys.modules['__main__'].__file__).absolute()==C.HERE/'run.py' and sys.argv==[str(C.HERE/'run.py'),*argv[4:]]
        and sys.version_info[:3]==(3,11,14),'EXACT_PRIMARY_FULL_ARGV_AND_SAMPLER_PYTHON')
    for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='1'
    out=Path(plan['output_directory']);Q.need(out.is_absolute() and '..' not in out.parts and Q.ROOT/'artifacts' in out.parents and not out.exists(),'FRESH_JOB_OUTPUT');out.mkdir(parents=True,mode=0o700)
    budget=B.Budget(plan,proof,out);gate=None;started=time.monotonic()
    try:
        gate=fixtures(out,req['source_references']);budget.check(force=True);result=observe(plan,out,proof,budget)
        owned=budget.used();Q.write_new(out/'receipt.json',{'schema':'MARCEL_DRUGS_KEYS_RECEIPT_V1',
            'status':'EXACT_SELECTED_CONFORMER_KEYS_OBSERVED_UNKNOWNS_RETAINED','mode':plan['mode'],'job_id':str(proof['job_id']),
            'uid':1278,'node':req['node'],'endpoint':'202.38.247.57:22','input_reference':plan['input_reference'],
            'accepted_probe_receipt_reference':plan['accepted_probe_receipt_reference'],'accepted_probe_accounting_reference':plan['accepted_probe_accounting_reference'],
            'plan_reference':Q.pin(a.plan),'startup_proof_reference':Q.pin(a.startup_proof),'fixtures':gate,**result,
            'owned_output_bytes_before_receipt':owned,'observed_parent_and_children_RSS_peak_bytes':budget.peak,'minimum_MemAvailable_bytes':budget.minimum,
            'elapsed_seconds':time.monotonic()-started,'actual_terminal_cost':'PENDING_ROOT_ACCOUNTING','cost_overrun_action':'REPORT_AND_CONTINUE',
            'profile_is_full_normalization_coverage':False,'native_graph_stereo_or_pool_training_release':False})
        return 0
    except BaseException as exc:
        Q.write_new(out/'failure.json',{'schema':'MARCEL_DRUGS_KEYS_FAILURE_V1','error':type(exc).__name__+': '+str(exc),'traceback':traceback.format_exc(),
            'fixtures':gate,'durable_source_result_prefixes_retained':True,'actual_cost':'PENDING_ROOT_ACCOUNTING','source_or_pool_accepted':False})
        raise


if __name__=='__main__':raise SystemExit(main())
