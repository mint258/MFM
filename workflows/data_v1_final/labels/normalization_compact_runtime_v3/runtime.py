"""Fresh central-v2 actual CPU admission and unchanged natural-drain observer."""
import hashlib,io,json,math,os,re,socket,sqlite3,threading,time,traceback,unittest
from datetime import datetime
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
    C.need(binding['schema']=='COMPACT_NUMERIC_RESOURCE_BINDING_V2' and binding['scientific_config_reference']==small_ref(config_path)
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


def aware_time(value):
    C.need(type(value) is str,'CANONICAL_AWARE_ISO_TIME_REQUIRED');parsed=datetime.fromisoformat(value.replace('Z','+00:00'))
    C.need(parsed.tzinfo is not None and parsed.utcoffset() is not None,'CLOCK_TIMESTAMP_REQUIRES_EXPLICIT_TIMEZONE')
    C.need(math.isfinite(parsed.timestamp()),'FINITE_CLOCK_TIMESTAMP');return parsed


def slurm_seconds(value):
    C.need(type(value) is str,'FINITE_SLURM_DURATION_REQUIRED');match=re.fullmatch(r'(?:(\d+)-)?(\d+):(\d{2}):(\d{2})',value)
    C.need(match is not None,'FINITE_SLURM_DURATION_REQUIRED');days,hours,minutes,seconds=[int(v or 0) for v in match.groups()]
    C.need(minutes<60 and seconds<60 and (not days or hours<24),'VALID_SLURM_DURATION_COMPONENTS')
    return days*86400+hours*3600+minutes*60+seconds


def wall_clock(proof,wall_seconds,*,now_wall=None,now_monotonic=None):
    """Use real proof shape; deduct startup/fixtures once, then local monotonic."""
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.slurm_format import fields
    now_wall=time.time() if now_wall is None else now_wall;now_monotonic=time.monotonic() if now_monotonic is None else now_monotonic
    C.need(type(wall_seconds) is int and 0<wall_seconds<=172800 and math.isfinite(now_wall) and math.isfinite(now_monotonic),'FINITE_WALL_AND_CPU_MONOTONIC_ANCHOR')
    observed=aware_time(proof['observed_at']);root_observed=aware_time(proof['root_observed_at']);age=now_wall-observed.timestamp()
    C.need(age>=0,'CANONICAL_PROOF_OBSERVATION_IN_FUTURE');job=fields(proof['job_metadata'])
    C.need(job['JobId']==str(proof['job_id']) and job['JobState']=='RUNNING','ACTUAL_OWN_RUNNING_SLURM_CLOCK_CONTEXT')
    runtime=slurm_seconds(job['RunTime']);limit=slurm_seconds(job['TimeLimit']);C.need(0<=runtime<=172800 and 0<limit<=172800,'FINITE_MAX48H_SLURM_WALL_LIMIT')
    # Slurm's site-local unqualified timestamps use actual Root ISO timezone,
    # never an invented UTC offset or a replacement proof field.
    def scheduler_time(key):
        value=datetime.fromisoformat(job[key]);return value.replace(tzinfo=root_observed.tzinfo) if value.tzinfo is None else value
    start=scheduler_time('StartTime');end=scheduler_time('EndTime');start_epoch=start.timestamp();end_epoch=end.timestamp()
    C.need(math.isfinite(start_epoch) and math.isfinite(end_epoch) and start_epoch<=now_wall and end_epoch>start_epoch,'FINITE_ACTUAL_SLURM_START_END')
    C.need(abs((end_epoch-start_epoch)-limit)<=1,'SLURM_START_END_AND_TIME_LIMIT_CONSISTENCY')
    elapsed=math.ceil(max(runtime+age,now_wall-start_epoch));effective=min(wall_seconds,limit)
    remaining=min(effective-elapsed,end_epoch-now_wall)
    return {'schema':'COMPACT_CPU_LOCAL_MONOTONIC_WALL_BUDGET_V2','proof_observed_at':proof['observed_at'],'root_observed_at':proof['root_observed_at'],
      'slurm_RunTime':job['RunTime'],'slurm_TimeLimit':job['TimeLimit'],'slurm_StartTime':job['StartTime'],'slurm_EndTime':job['EndTime'],
      'slurm_naive_timestamp_timezone_basis':'ACTUAL_ROOT_OBSERVED_AT_OFFSET','proof_to_budget_seconds_including_startup_and_fixtures':age,
      'conservative_elapsed_at_anchor_seconds':elapsed,'effective_wall_seconds':effective,'remaining_at_anchor_seconds':remaining,
      'cpu_wall_at_anchor':now_wall,'cpu_monotonic_anchor':now_monotonic,'cpu_monotonic_deadline':now_monotonic+remaining,
      'proof_modified':False,'running_sources_signalled':False}


def remaining_wall(clock,now_monotonic):
    C.need(math.isfinite(now_monotonic) and now_monotonic>=clock['cpu_monotonic_anchor'],'MONOTONIC_CLOCK_REGRESSION_OR_NONFINITE')
    return clock['cpu_monotonic_deadline']-now_monotonic


class Budget:
    def __init__(self,cfg,proof,binding,root):
        self.cfg=cfg;self.proof=proof;self.root=Path(root);self.done=threading.Event();self.ledger=None
        self.clock=wall_clock(proof,cfg['wall_seconds']);save(self.root/'wall_clock_budget.json',self.clock)
        R.start_observer(proof,binding);self.observe()
        self.thread=threading.Thread(target=self.loop,daemon=True);self.thread.start()
    def observe(self):
        try:
            if self.ledger is not None:
                db=sqlite3.connect(self.ledger.as_uri()+'?mode=ro',uri=True,timeout=10)
                try:cap,charged=db.execute('SELECT cap,charged FROM budget WHERE id=1').fetchone()
                finally:db.close()
                if charged>=cap:R.mark_stop('COMPACT_OUTPUT_TICKET_SOFT_STOP',{'charged':charged,'cap':cap})
            remaining=remaining_wall(self.clock,time.monotonic());drain=max(180,self.cfg.get('softwall_drain_seconds',300))
            if remaining<=drain:R.mark_stop('COMPACT_SOFTWALL_STOP_NEW_WINDOWS_NATURAL_DRAIN',{'remaining_seconds':remaining,'drain_seconds':drain,'clock':self.clock})
        except Exception as exc:R.mark_stop('COMPACT_RESOURCE_OBSERVATION_UNKNOWN',{'error':repr(exc),'clock':self.clock})
    def loop(self):
        while not self.done.wait(1):self.observe()
    def attach_ledger(self,path):self.ledger=Path(path).absolute()
    def close(self):
        self.done.set();self.thread.join();R.MONITOR.finish()

def failed(root,exc):
    save(Path(root)/'failure.json',{'error':repr(exc),'traceback':traceback.format_exc(),'old_books_unchanged':True,
      'partials_and_costs_retained':True,'automatic_retry':False,'automatic_next_stage':False})