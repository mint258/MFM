"""Fresh Main CPU16 no_mem producer, source/result durable before strict5."""
import argparse,collections,concurrent.futures as cf,io,json,multiprocessing as mp,os,sys,time,traceback,unittest
from pathlib import Path
from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2 import runtime as R
from workflows.expansion.common_molecular_fp_candidate_v1 import census as Census
from . import contract as C,io as I,kernel as K,scan as S,resources as B
Q=C.Q

def fixtures(out):
    from .test_v1 import Boundaries
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(Boundaries);Q.need(suite.countTestCases()==3,'EXACT3_NEW_PURE_BEFORE_DATA')
    transcript=io.StringIO();result=unittest.TextTestRunner(stream=transcript,verbosity=2).run(suite)
    value={'tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'skips':len(result.skipped),
        'expected_failures':len(result.expectedFailures),'unexpected_successes':len(result.unexpectedSuccesses),
        'transcript':transcript.getvalue(),'before_DATA_and_monitor':True}
    Q.write_new(out/'fixtures3.json',value);Q.need(result.testsRun==3 and result.wasSuccessful()
        and not(result.skipped or result.expectedFailures or result.unexpectedSuccesses),'PURE3_MUST_PASS');return value

class Dispatch:
    def __init__(self,pool,db,writer,budget):
        self.pool,self.db,self.writer,self.budget=pool,db,writer,budget;self.pending={};self.pids=collections.Counter();self.cpu=collections.Counter()
        self.bytes_by_role=collections.Counter();self.cpu_by_role=collections.Counter()
    def hold(self,mid,reason):
        self.writer.write({'phase':'MID_REDUCTION','molecule_id':mid,'status':'HOLD','reason':reason,'strict5_projection':None},False)
        self.db.execute('INSERT INTO results VALUES(?,?,NULL)',(mid,'HOLD'))
    def enqueue(self,task):
        self.budget.check();self.pending[self.pool.submit(K.work,task)]=task
        if len(self.pending)>=32:self.collect(False)
    def collect(self,all_rows):
        while self.pending:
            done,_=cf.wait(self.pending,timeout=1,return_when=cf.FIRST_COMPLETED);self.budget.check(False)
            for future in done:
                task=self.pending.pop(future);mid=task['molecule_id']
                before=self.writer.bytes
                try:
                    value=future.result();r=value['reduction'];Q.need(r['molecule_id']==mid and r['effective_role']==task['effective_role'] and r['native_records']==task['native_records'],'WORKER_SOURCE_MID_ROLE_RECORD_BINDING')
                    for result in r['graph_variant_results']:self.writer.write({'phase':'GRAPH_RESULT','molecule_id':mid,**result},False)
                    summary={k:v for k,v in r.items() if k!='graph_variant_results'};summary['graph_result_count']=len(r['graph_variant_results'])
                    self.writer.write({'phase':'MID_REDUCTION',**summary},False)
                    self.db.execute('INSERT INTO results VALUES(?,?,?)',(mid,r['status'],None if r['strict5_projection'] is None else json.dumps(r['strict5_projection'],separators=(',',':'))))
                    self.pids[str(value['worker_pid'])]+=1;self.cpu[str(value['worker_pid'])]+=value['worker_CPU_seconds']
                    self.cpu_by_role[task['effective_role']]+=value['worker_CPU_seconds']
                except Exception as exc:self.hold(mid,'TECHNICAL_UNRESOLVED:'+type(exc).__name__+':'+str(exc))
                self.bytes_by_role[task['effective_role']]+=self.writer.bytes-before
                self.db.commit()
            if done and not all_rows:return

def observe(plan,proof,out,budget):
    common,members,roles,formal,data,_=C.inputs(plan);bodies={};db=None;dispatch=None
    source=B.Writer(out/'source_identity.DATA.jsonl',budget);results=B.Writer(out/'graph_results.DATA.jsonl',budget)
    try:
        for ref in data:budget.check();bodies[ref['path']]=I.Body(ref,budget)
        db,expected=S.prepare(out,bodies,members,roles,common,plan['mode'],budget)
        context=mp.get_context('spawn');barrier=context.Barrier(16)
        proof_directory=out/'worker_sources';proof_directory.mkdir()
        with cf.ProcessPoolExecutor(max_workers=16,mp_context=context,initializer=K.initialize,initargs=(barrier,str(proof_directory))) as pool:
            dispatch=Dispatch(pool,db,results,budget)
            try:scan=S.scan_formal(db,bodies[formal['path']],source,dispatch,budget)
            finally:dispatch.collect(True)
        Census.require_same_membership(expected,scan['all_common_observed_census'])
        Q.need(db.execute('SELECT count(*) FROM selected s LEFT JOIN results r USING(mid) WHERE r.mid IS NULL').fetchone()[0]==0
            and db.execute('SELECT count(*) FROM results r LEFT JOIN selected s USING(mid) WHERE s.mid IS NULL').fetchone()[0]==0,'EXACT_SELECTED_SOURCE_RESULT_ANTI_JOIN')
        n=db.execute('SELECT count(*) FROM results').fetchone()[0];holds=db.execute("SELECT count(*) FROM results WHERE status<>'UNIQUE_GRAPH_PROJECTION_CANDIDATE'").fetchone()[0]
        Q.need(n==scan['selected_MIDs'] and len(dispatch.pids)==16,'EXACT_SELECTED_AND16_ACTUAL_WORKER_PIDS')
        worker_proofs=[]
        for pid in dispatch.pids:
            ref=Q.pin(proof_directory/f'worker_{pid}.json');v=C.meta(ref)
            Q.need(str(v['worker_pid'])==pid and v['job_id']==str(proof['job_id']) and
                v['original_function_objects_checked_in_this_worker'] is True,'ACTUAL_WORKER_KERNEL_SCOPE_PROOF')
            worker_proofs.append(ref)
        source.close();results.close();projection=B.Writer(out/'strict5_projection.DATA.jsonl',budget)
        projection_bytes_by_role=collections.Counter()
        try:
            for mid,raw,role in db.execute('SELECT r.mid,r.strict5,m.role FROM results r JOIN members m USING(mid) WHERE r.strict5 IS NOT NULL ORDER BY r.mid'):
                before=projection.bytes;projection.write(json.loads(raw),False);projection_bytes_by_role[role]+=projection.bytes-before
        finally:projection.close()
        selected_census=Census.Census()
        for mid,role,count in db.execute('SELECT m.mid,m.role,m.n FROM members m JOIN selected s USING(mid) ORDER BY m.mid'):selected_census.add(mid,role,count)
        output_refs=[source.reference(),results.reference(),projection.reference()]
        # Full rehash of each stable output is independently compared with the
        # producer writers, before this job can claim its selected audit closed.
        output_frames=[]
        for ref in output_refs:
            body=I.Body(ref,budget,allow_empty=True)
            if ref['path']==projection.reference()['path']:
                def member(mid):
                    row=db.execute('SELECT role,n FROM members m JOIN selected s USING(mid) WHERE m.mid=?',(mid,)).fetchone()
                    Q.need(row is not None,'READBACK_PROJECTION_MID_OUTSIDE_EXACT_SELECTED_SET');return row
                body.stream.seek(0);parsed_rows,parsed_census=I.read_strict5_rows(body.stream,member)
                Q.need(parsed_rows==projection.rows,'ACTUAL_STRICT5_PARSED_ROW_COUNT')
                if holds==0:Census.require_same_membership(selected_census.result(),parsed_census)
            output_frames.append({'reference':ref,'frame':body.frame});body.close()
        db.commit();db.close();db=None
        index_reference=I.seal_closed_output(out/'census.sqlite',budget)
        return {**scan,'expected_all_common_census':expected,'selected_census':selected_census.result(),
            'HOLD_MIDs':holds,'strict5_rows':projection.rows,'strict5_projection_reference':{**projection.reference(),'rows':projection.rows},
            'source_journal_reference':source.reference(),'graph_result_journal_reference':results.reference(),
            'all_output_journals_current_SHA_readback':output_frames,'input_current_SHA_frames':[{'reference':b.reference,'frame':b.frame} for b in bodies.values()],
            'closed_scalar_census_index_reference':index_reference,'strict5_independent_parsed_census':parsed_census,
            'graph_journal_actual_bytes_by_role':dict(dispatch.bytes_by_role),'strict5_actual_bytes_by_role':dict(projection_bytes_by_role),
            'worker_CPU_seconds_by_role':dict(dispatch.cpu_by_role),'worker_MID_counts':dict(dispatch.pids),'worker_CPU_seconds':dict(dispatch.cpu),
            'actual_worker_kernel_scope_proof_references':worker_proofs,'consumer_manifest_emitted':False}
    finally:
        if not source.stream.closed:source.close()
        if not results.stream.closed:results.close()
        if db is not None:db.commit();db.close()
        for body in bodies.values():body.close()

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',type=Path,required=True);p.add_argument('--startup-proof',type=Path,required=True);a=p.parse_args()
    plan=Q.load(a.plan);*_,data,parents=C.inputs(plan);params=C.parameters(plan['mode'],plan['output_cap_bytes'])
    Q.need(plan['schema']=='COMMON_MOLECULAR_FP_CPU_PLAN_V1' and plan['scope_parameters']==params,'EXACT_COMMON_FP_PLAN')
    argv=[Q.PY,'-B','-m',C.MODULE,'--plan',str(a.plan),'--startup-proof',str(a.startup_proof)]
    proof=R.require_startup(a.startup_proof,expected_scope_key=C.key(plan['mode']),expected_scope_parameters=params,
        expected_execution_argv=argv,expected_source=__file__,expected_kind='analysis',required_references=[Q.pin(a.plan),*parents,*data,plan['cost_decision_reference']])
    req=proof['request'];Q.need(req['node']=='compute-0-13' and req['pilot'] is (plan['mode']=='profile') and req['wall_seconds']==plan['wall_seconds']
        and req['estimated_peak_output_bytes']==plan['output_cap_bytes'] and req['data_references']==data and not req.get('deferred_authority_references'),'EXACT_CPU13_PROVIDER_AND_BODY_SCOPE')
    Q.need(Path(sys.modules['__main__'].__file__).absolute()==C.HERE/'run.py' and sys.argv==[str(C.HERE/'run.py'),*argv[4:]]
        and sys.version_info[:3]==(3,11,14),'EXACT_PRIMARY_AND_FULL_ARGV')
    for path in C.source_paths():Q.need(Q.pin(path) in req['source_references'],'ALL_CURRENT_NEW_AND_OLD_SOURCE_PINS')
    cost=C.meta(plan['cost_decision_reference']);Q.need(cost['status']=='USER_AUTHORIZED' and cost['on_overrun']=='REPORT_AND_CONTINUE'
        and cost['scientific_quality_thresholds_unchanged'] is True,'ACTUAL_COST_AND_UNCHANGED_QUALITY_AUTHORITY')
    review=C.meta(req['scope']['review']);Q.need(review['original_graph_and_accepted_difference_semantics_reviewed'] is True
        and review['Root_final_graph_review_required_before_consumer_manifest'] is True and review['NN_1M_pool_training_release'] is False
        and req['scope']['mode']==('BOUNDED_PERFORMANCE_BATCH' if plan['mode']=='profile' else 'FULL_SOURCE_AFTER_PROFILE'),'ROOT_EXACT_GRAPH_SCOPE')
    for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[name]='1'
    out=Path(plan['output_directory']);Q.need(Q.ROOT/'artifacts' in out.parents and '..' not in out.parts and not out.exists(),'FRESH_ARTIFACT_OUTPUT');out.mkdir(parents=True,mode=0o700)
    gate=None;budget=None;began=time.monotonic()
    try:
        gate=fixtures(out);budget=B.Budget(plan,proof,out);result=observe(plan,proof,out,budget)
        Q.write_new(out/'receipt.json',{'schema':'COMMON_MOLECULAR_FP_CPU_RECEIPT_V1','status':'SELECTED_MOLECULAR_GRAPH_AUDIT_COMPLETE_PENDING_ROOT_FINAL_REVIEW' if result['HOLD_MIDs']==0 else 'MOLECULAR_GRAPH_AUDIT_HOLD',
            'mode':plan['mode'],'job_id':str(proof['job_id']),'node':req['node'],'uid':1278,'endpoint':'202.38.247.57:22',
            'common_manifest_reference':plan['common_manifest_reference'],'data_references':data,'plan_reference':Q.pin(a.plan),'startup_proof_reference':Q.pin(a.startup_proof),
            'fixtures':gate,'result':result,'resources':budget.receipt(),'owned_output_bytes_before_receipt':budget.used(),
            'elapsed_seconds':time.monotonic()-began,'actual_terminal_cost':'PENDING_ROOT_ACCOUNTING','scientific_or_1M_NN_pool_training_release':False})
        return 0 if result['HOLD_MIDs']==0 else 3
    except BaseException as exc:
        Q.write_new(out/'failure.json',{'schema':'COMMON_MOLECULAR_FP_CPU_FAILURE_V1','error':type(exc).__name__+': '+str(exc),'traceback':traceback.format_exc(),
            'fixtures':gate,'resources':budget.receipt() if budget else None,'durable_prefixes_retained':True,'no_automatic_retry_or_signals':True,'no_common_subset_release':True})
        raise
if __name__=='__main__':raise SystemExit(main())
