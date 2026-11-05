"""Fresh central-v2 actual CPU admission and unchanged natural-drain observer."""
import hashlib,io,json,os,socket,sqlite3,threading,time,traceback,unittest
from pathlib import Path
from . import contract as C
from workflows.data_v1_final.labels.source_status_cpu_auto_memory_v1 import support as S,resource_runtime as R
load=S.load;require=S.require;small_ref=S.small_ref;save=S.save;pin=S.ref;new_root=S.new_root;unique_bytes=S.unique_bytes


def load_data(reference,maximum=64<<20):
    """CPU-only bounded scientific JSON. Call only after startup and fixtures."""
    C.reference(reference);p=Path(reference['path']);before=S.identity(p);C.need(0<before[2]<=maximum,'BOUNDED_SCIENTIFIC_JSON_NOT_SMALL_METADATA')
    require(reference)
    with p.open('rb') as stream:
        raw=stream.read(maximum+1);after=os.fstat(stream.fileno())
        C.need([after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns]==before==S.identity(p),'SCIENCE_JSON_STABLE_SAME_FD')
    C.need(len(raw)==reference['bytes']<=maximum and hashlib.sha256(raw).hexdigest()==reference['sha256'],'EXACT_BOUNDED_SCIENCE_JSON_SHA')
    return json.loads(raw.decode('utf-8-sig'))

def guard(config_path,proof_path,stage):
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.runtime import require_startup
    cfg=C.validate_config(load(config_path));C.need(cfg['stage']==stage,'EXACT_ENTRY_STAGE')
    raw=load(proof_path);req=raw['request'];bp=req['producer_resource_binding_reference'];binding=load(require(bp))
    C.need(binding['schema']=='COMPACT_NUMERIC_RESOURCE_BINDING_V1' and binding['scientific_config_reference']==small_ref(config_path)
      and binding['scope_key']==cfg['scope_key'] and binding['scope_parameters']==cfg['scope_parameters']
      and binding['resource_authority_reference']==req['queue_authority_reference'],'EXACT_NEW_NOMEM_RESOURCE_BINDING')
    refs=[small_ref(config_path),bp,*cfg['small_references']]
    proof=require_startup(proof_path,expected_kind='analysis',expected_scope_key=cfg['scope_key'],expected_scope_parameters=cfg['scope_parameters'],
      expected_source=Path(__import__('sys').modules['__main__'].__file__),required_references=refs)
    C.need(req['pilot']==(cfg['mode']=='pilot512') and req['cpus']==16 and req['wall_seconds']==cfg['wall_seconds']
      and req['estimated_peak_output_bytes']>=cfg['whole_output_cap_bytes'],'EXACT16CPU_NOMEM_FINITE_ACTUAL_ALLOCATION')
    C.need(all(os.environ.get(k)=='1' for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS')),'FIXED_SINGLE_THREAD_NUMERIC_ENVIRONMENT')
    C.need({r['path']:r for r in cfg['data_references']}=={r['path']:r for r in req['data_references']},'EXACT_DECLARED_DATA_LOCATORS_AND_TRANSITIVE_C0_CATALOG')
    declared={r['path']:r for r in req['source_references']}
    for r in cfg['source_references']:C.need(declared.get(r['path'])==r,'ALL_TRANSITIVE_SOURCE_AUTHORIZED');require(r)
    for name in C.FILES:C.need(small_ref(C.HERE/name) in req['source_references'],'ALL_FOURTEEN_EXACT_CURRENT_NAMESPACE_ASSETS')
    C.technical_review(cfg,load(require(cfg['technical_review_reference'])))
    review=load(require(cfg['technical_review_reference']));reserve=review['remaining_numeric_cache_reserve_bytes']+review['other_unwritten_output_cap_bytes']
    C.need(proof['account_free_bytes']>=200000000000+reserve,'REAL_FRESH_QUOTA_FOR_ALL_REMAINING_AND_OTHER_CAPS_PLUS200GB')
    return cfg,proof,binding


def fixtures(root):
    from . import source_inverse,test_boundaries
    inverse=source_inverse.proof();suite=unittest.defaultTestLoader.loadTestsFromTestCase(test_boundaries.Boundaries)
    C.need(suite.countTestCases()==3,'EXACT_THREE_COMPACT_BOUNDARIES');out=io.StringIO();result=unittest.TextTestRunner(stream=out,verbosity=2).run(suite)
    ok=result.testsRun==3 and result.wasSuccessful() and not(result.skipped or result.expectedFailures or result.unexpectedSuccesses)
    ref=save(root/'fixture_gate.json',{'status':'PASS' if ok else 'FAIL_NO_DATA','tests_run':result.testsRun,'failures':len(result.failures),
      'errors':len(result.errors),'skips':len(result.skipped),'expected_failures':len(result.expectedFailures),'unexpected_successes':len(result.unexpectedSuccesses),
      'transcript':out.getvalue(),'source_inverse':inverse,'scientific_DATA_read':False});print(out.getvalue(),flush=True)
    C.need(ok,'COMPACT_BOUNDARIES_BEFORE_DATA');return ref


class Budget:
    def __init__(self,cfg,proof,binding,root):
        self.cfg=cfg;self.proof=proof;self.root=Path(root);self.done=threading.Event();self.start=time.time();self.ledger=None;R.start_observer(proof,binding)
        self.thread=threading.Thread(target=self.loop,daemon=True);self.thread.start()
    def loop(self):
        while not self.done.wait(1):
            try:
                # This cap is a software bound, never an sbatch memory request.
                # Output tickets conservatively include unpublished/partial bytes. No rglob race during rename.
                if self.ledger is not None:
                    db=sqlite3.connect(self.ledger.as_uri()+'?mode=ro',uri=True,timeout=10)
                    try:cap,charged=db.execute('SELECT cap,charged FROM budget WHERE id=1').fetchone()
                    finally:db.close()
                    if charged>=cap:R.mark_stop('COMPACT_OUTPUT_TICKET_SOFT_STOP',{'charged':charged,'cap':cap})
                if time.time()-self.proof['observed_unix_seconds']>=self.cfg['wall_seconds']-max(180,self.cfg.get('softwall_drain_seconds',300)):
                    R.mark_stop('COMPACT_SOFTWALL_STOP_NEW_WINDOWS_NATURAL_DRAIN',{})
            except Exception as exc:R.mark_stop('COMPACT_RESOURCE_OBSERVATION_UNKNOWN',{'error':repr(exc)})
    def attach_ledger(self,path):self.ledger=Path(path).absolute()
    def close(self):
        self.done.set();self.thread.join();R.MONITOR.finish()


def failed(root,exc):
    save(Path(root)/'failure.json',{'error':repr(exc),'traceback':traceback.format_exc(),'old_books_unchanged':True,
      'partials_and_costs_retained':True,'automatic_retry':False,'automatic_next_stage':False})