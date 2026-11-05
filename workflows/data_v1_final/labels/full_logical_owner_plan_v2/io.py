"""Fresh actual central-v2 CPU, same-fd hash and bounded natural drain."""
import contextlib,hashlib,io,json,os,stat,sys,time,unittest
from pathlib import Path
from . import contract as C
from workflows.data_v1_final.labels.source_status_cpu_auto_memory_v1 import support as S,resource_runtime as R
from workflows.data_v1_final.labels.bounded_projection_v1 import materialize as M
from workflows.data_v1_final.labels.normalization_compact_runtime_v2.runtime import wall_clock,remaining_wall
load=M.load;pin=M.pin;require=M.require

def save(path,value):
    raw=(json.dumps(value,sort_keys=True,indent=2,allow_nan=False)+'\n').encode();C.need(len(raw)<=2<<20,'EXISTING_COMPACT_SMALL_PLAN_READER_LIMIT')
    with Path(path).open('xb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
    return pin(path)

def frame(s):return [s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns]

@contextlib.contextmanager
def opened(ref,expected=None,hash_content=True):
    C.reference(ref);p=Path(ref['path']);s=p.lstat();C.need(stat.S_ISREG(s.st_mode) and s.st_uid==os.getuid() and s.st_size==ref['bytes'],'REAL_OWNED_REGULAR_PINNED_INPUT')
    fd=os.open(str(p),os.O_RDONLY|os.O_NOFOLLOW)
    with os.fdopen(fd,'rb') as f:
        before=frame(os.fstat(f.fileno()));C.need(before==frame(p.lstat()) and (expected is None or before==expected),'INPUT_CURRENT_SAME_FD_FRAME')
        if hash_content:
            h=hashlib.sha256()
            for block in iter(lambda:f.read(1<<20),b''):h.update(block)
            C.need(h.hexdigest()==ref['sha256'],'ALLOCATED_CPU_INPUT_WHOLE_SHA');f.seek(0)
        C.need(frame(os.fstat(f.fileno()))==before==frame(p.lstat()),'INPUT_CHANGED_DURING_HASH')
        try:yield f,before
        finally:C.need(frame(os.fstat(f.fileno()))==before==frame(p.lstat()),'INPUT_CHANGED_DURING_READ')

def data_json(ref,maximum=8<<20):
    with opened(ref) as (f,_):
        raw=f.read(maximum+1);C.need(len(raw)==ref['bytes']<=maximum,'BOUNDED_CPU_METADATA_BODY');return json.loads(raw.decode('utf-8-sig'))

def guard(path,proof_path,output):
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.runtime import require_startup
    cfg=C.config(load(path));raw=load(proof_path);req=raw['request'];bp=req['producer_resource_binding_reference'];binding=load(require(bp))
    C.need(binding['schema']=='FULL_LOGICAL_OWNER_PLAN_RESOURCE_BINDING_V2' and binding['scientific_config_reference']==pin(path)
      and binding['scope_key']==C.KEY and binding['scope_parameters']==C.PARAMETERS and binding['resource_authority_reference']==req['queue_authority_reference'],'EXACT_NEW_PLAN_RESOURCE_BINDING')
    proof=require_startup(proof_path,expected_kind='analysis',expected_scope_key=C.KEY,expected_scope_parameters=C.PARAMETERS,
      expected_source=Path(sys.modules['__main__'].__file__),expected_execution_argv=[M.PY,'-B','-m',C.MODULE,'--config',str(Path(path).absolute()),
      '--startup-proof',str(Path(proof_path).absolute()),'--output',str(Path(output).absolute())],required_references=[pin(path),bp,*cfg['small_references']])
    C.need(req['cpus']==16 and req['pilot'] is False and req['wall_seconds']==cfg['wall_seconds'] and req['estimated_peak_output_bytes']>=C.CAP,'EXACT16_NOMEM_NONPILOT_MAX2H')
    C.need({r['path']:r for r in cfg['data_references']}=={r['path']:r for r in req['data_references']},'EXACT_DECLARED_PLANNER_DATA')
    declared={r['path']:r for r in req['source_references']}
    for r in cfg['source_references']:C.need(declared.get(r['path'])==r,'EXACT_ALL_PLANNER_SOURCES');require(r)
    for name in C.FILES:C.need(pin(C.HERE/name) in req['source_references'],'ALL_NINE_NEW_NAMESPACE_ASSETS')
    C.review(cfg,load(require(cfg['technical_review_reference'])))
    C.need(proof['account_free_bytes']>=200000000000+C.CAP+cfg['other_output_cap_bytes'],'ACTUAL_QUOTA_ALL_OTHER_FUTURE_CAPS_PLUS200GB')
    C.need(all(os.environ.get(k)=='1' for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS')),'ONE_NATIVE_THREAD_PER_WORKER')
    return cfg,proof,binding

def fixtures(root):
    from . import source_inverse,test_boundaries
    inverse=source_inverse.proof();suite=unittest.defaultTestLoader.loadTestsFromTestCase(test_boundaries.Boundaries);C.need(suite.countTestCases()==3,'EXACT_THREE_PLANNER_BOUNDARIES')
    output=io.StringIO();r=unittest.TextTestRunner(stream=output,verbosity=2).run(suite)
    ok=r.testsRun==3 and r.wasSuccessful() and not(r.skipped or r.expectedFailures or r.unexpectedSuccesses)
    ref=S.save(root/'fixtures.json',{'status':'PASS' if ok else 'FAIL_NO_DATA','tests_run':r.testsRun,'transcript':output.getvalue(),'source_inverse':inverse,'DATA_read':False},root,C.CAP)
    C.need(ok,'THREE_PURE_AND_SOURCE_INVERSE_BEFORE_DATA');return ref

class Budget:
    def __init__(self,cfg,proof,binding,root):
        self.cfg=cfg;self.proof=proof;self.root=root
        self.clock=wall_clock(proof,cfg['wall_seconds']);S.save(root/'wall_clock_budget.json',self.clock,root,C.CAP)
        R.start_observer(proof,binding)
        if self.stop():
            R.MONITOR.finish();raise R.SourceStatusSoftStop('LOGICAL_PLAN_RESOURCE_STOP_BEFORE_DATA')
    def stop(self):
        remaining=remaining_wall(self.clock,time.monotonic())
        if remaining<=300:R.mark_stop('PLANNER_SOFTWALL_NO_NEW_PARTITIONS_NATURAL_DRAIN',{'remaining_seconds':remaining,'drain_seconds':300,'clock':self.clock})
        if S.unique_bytes(self.root)+(64<<20)>=C.CAP:R.mark_stop('PLANNER_1GIB_OUTPUT_SOFT_CAP',{})
        return R.stop_requested()
    def close(self):R.MONITOR.finish()
