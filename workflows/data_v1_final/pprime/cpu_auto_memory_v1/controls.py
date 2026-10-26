"""New primary producer startup, bounded dispatch and truthful auto-memory closure."""
from __future__ import annotations
import concurrent.futures as cf,hashlib,json,multiprocessing as mp,os,pathlib,stat,subprocess,sys,time,traceback
from .memory import MemoryObserver,need
ROOT=pathlib.Path('/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025')
REPO=ROOT/'repository';PROJECT=ROOT.parent.parent;PY='/share/home/zixiao/.conda/envs/chemprop/bin/python'
ACTIVE=None


def ref(path):
    path=pathlib.Path(path);h=hashlib.sha256()
    with path.open('rb') as f:
        a=os.fstat(f.fileno())
        for chunk in iter(lambda:f.read(1024**2),b''):h.update(chunk)
        b=os.fstat(f.fileno())
    need((a.st_dev,a.st_ino,a.st_size,a.st_mtime_ns)==(b.st_dev,b.st_ino,b.st_size,b.st_mtime_ns),'REFERENCE_CHANGED_DURING_READ')
    return {'path':str(path),'bytes':a.st_size,'sha256':h.hexdigest()}


def normalized(pin):return {key:pin[key] for key in ('path','bytes','sha256')}


def check(pin):
    need(ref(pin['path'])==normalized(pin),'ACTUAL_INPUT_OR_OUTPUT_REFERENCE_CHANGED')
    return pathlib.Path(pin['path'])


def load(path):return json.loads(pathlib.Path(path).read_text())


def write_new(path,value):
    with pathlib.Path(path).open('x',encoding='utf-8') as f:json.dump(value,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())


class SoftDispatchStop(RuntimeError):
    def __init__(self,completed,total):
        super().__init__('NEW_DISPATCH_STOPPED_IN_FLIGHT_WORK_DRAINED')
        self.completed=completed;self.total=total


def bounded_thread_map(function,items,allow,*,workers=16):
    """Only workers in flight; complete output preserves original pool.map order."""
    rows={};active={};index=0;error=None
    with cf.ThreadPoolExecutor(max_workers=workers) as pool:
        while active or index<len(items):
            while error is None and index<len(items) and len(active)<workers and allow():
                active[pool.submit(function,items[index])]=index;index+=1
            if not active:break
            done,_=cf.wait(active,timeout=.25,return_when=cf.FIRST_COMPLETED)
            for future in done:
                slot=active.pop(future)
                try:rows[slot]=future.result()
                except Exception as exc:
                    if error is None:error=exc
            if error is not None:
                # The context manager naturally drains all already-submitted work.
                for future,slot in list(active.items()):
                    try:rows[slot]=future.result()
                    except Exception:pass
                active.clear();break
    if error is not None:raise error
    ordered=[rows[key] for key in sorted(rows)]
    if len(rows)!=len(items):raise SoftDispatchStop(ordered,len(items))
    return ordered


class ProducerContext:
    def __init__(self,stage,args):
        global ACTIVE
        need(stage in {'frame','retention'} and ACTIVE is None,'ONE_NEW_PRIMARY_STAGE_CONTEXT_REQUIRED')
        self.stage=stage;self.args=args;self.plan=load(args.scope_plan);self.started=time.monotonic();self.partial=None
        plan=self.plan;kind='qm' if stage=='frame' else 'analysis'
        key='pprime_frame72_cpu_auto_memory_v1' if stage=='frame' else 'pprime_retention2000_cpu_auto_memory_v1'
        need(plan['schema']=='PPRIME_CPU_AUTO_MEMORY_STAGE_PLAN_V1' and plan['stage']==stage and plan['kind']==kind
             and plan['scope_key']==key and plan['new_UFF_calls']==0,'EXACT_NEW_PPRIME_STAGE_PLAN_REQUIRED')
        need(plan['memory_policy']=='SLURM_DEFAULT_UNSPECIFIED' and plan['slurm_memory_requested'] is False,'NO_OLD_MEMORY_PLAN_OR_PROOF')
        from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2 import runtime
        required=[ref(args.scope_plan),plan['old_scientific_plan'],plan['source_equivalence_proof'],plan['config'],plan['prepared'],plan['resource_authority']]
        if stage=='frame':required.append(plan['pilot_config'])
        self.proof=runtime.require_startup(args.root_preflight,expected_scope_key=key,
            expected_scope_parameters=plan['scope_parameters'],expected_source=pathlib.Path(sys.modules['__main__'].__file__).absolute(),
            expected_kind=kind,required_references=required)
        req=self.proof['request']
        need(req.get('producer_stage_plan_reference')==ref(args.scope_plan)
             and req.get('producer_memory_soft_limits')==plan['soft_limits'],'EXACT_REVIEWED_PRODUCER_PLAN_AND_SOFT_LIMITS_REQUIRED')
        need(plan['soft_limits']['algorithm_rss_soft_cap_bytes']==plan['scope_parameters']['algorithm_rss_soft_cap_bytes']
             and plan['soft_limits']['minimum_mem_available_bytes']==plan['scope_parameters']['minimum_mem_available_bytes'],
             'EXACT_ROOT_SCOPE_SOFT_BUDGETS_REQUIRED')
        need(req['memory_policy']=='SLURM_DEFAULT_UNSPECIFIED' and 'memory_gib' not in req
             and self.proof['memory_limits_requested'] is False and self.proof['memory_admission_evaluated'] is False,'TRUTHFUL_NEW_MEMORY_REQUEST_REQUIRED')
        need(str(args.config)==plan['config']['path'] and check(plan['config'])==args.config,'EXACT_FROZEN_CONFIG_REQUIRED')
        if stage=='frame':
            need(args.execute and str(args.pilot_config)==plan['pilot_config']['path'] and str(args.prepared/'prepared.json')==plan['prepared']['path']
                 and args.prepared_sha256==plan['prepared']['sha256'] and str(args.output)==plan['run_output'],'EXACT72_FRAME_ARGUMENTS_REQUIRED')
        else:
            need(str(args.original_prepared/'prepared.json')==plan['prepared']['path'] and args.original_prepared_sha256==plan['prepared']['sha256']
                 and str(args.output)==plan['run_output'],'EXACT_ORIGINAL2000_RETENTION_ARGUMENTS_REQUIRED')
        self.prefix=pathlib.Path(plan['output_prefix'])
        expected=ROOT/'artifacts/vector_frame_audit' if stage=='frame' else ROOT/'artifacts/pprime_retention_v1'
        need(self.prefix.parent==expected and not self.prefix.exists(),'NEW_STAGE_OUTPUT_PREFIX_ONLY')
        self.prefix.mkdir(mode=0o700)
        self.startup_ref=ref(args.root_preflight);self.monitor=MemoryObserver(plan['soft_limits'],self.prefix/'STOP_NEW_DISPATCH.json')
        self.monitor.start();ACTIVE=self
        write_new(self.prefix/'stage_started.json',{'schema':'PPRIME_AUTO_MEMORY_STARTED_V1','stage':stage,'plan':ref(args.scope_plan),
            'startup_proof':self.startup_ref,'job_id':str(self.proof['job_id']),'memory_policy':'SLURM_DEFAULT_UNSPECIFIED',
            'slurm_memory_requested':False,'new_UFF_calls':0,'new_QM_calls_authorized':72 if stage=='frame' else 0})
    def runtime_record(self):
        return {'job_id':str(self.proof['job_id']),'node':self.proof['request']['node'],'allocated_cpus':16,'workers':16,
            'memory_policy':'SLURM_DEFAULT_UNSPECIFIED','slurm_memory_requested':False,
            'actual_slurm_memory_environment':{k:os.environ.get(k) for k in ('SLURM_MEM_PER_NODE','SLURM_MEM_PER_CPU','SLURM_MEM_PER_GPU')}}
    def check_config(self,path,config):
        need(ref(path)==self.plan['config'] and self.proof['account_free_bytes']-self.plan['estimated_peak_output_bytes']>=config['quota_reserve_bytes'],
            'ORIGINAL_CONFIG_AND_WHOLE_RUN_QUOTA_REQUIRED')
        need(config['max_output_bytes']==self.plan['stage_output_cap_bytes'],'ORIGINAL_SCIENTIFIC_OUTPUT_CAP_CHANGED')
    def allow(self):
        if time.monotonic()-self.started>=self.plan['dispatch_deadline_seconds']:self.monitor.latch('FINITE_STAGE_DISPATCH_DEADLINE')
        return self.monitor.allow_new_dispatch()
    def map_thread_rows(self,function,items):
        try:return bounded_thread_map(function,items,self.allow,workers=16)
        except SoftDispatchStop as exc:self.partial=exc.completed;raise
    def map_process_cases(self,function,cases,config,pilot,prepared,out,deadline):
        refs=[];errors=[];active={};index=0;processes=[]
        pool=cf.ProcessPoolExecutor(max_workers=16,mp_context=mp.get_context('spawn'))
        try:
            while active or index<len(cases):
                while index<len(cases) and len(active)<16 and self.allow():
                    case=cases[index];index+=1
                    future=pool.submit(function,case,config,pilot,prepared,out,deadline);active[future]=case['case_id']
                if not active:break
                done,_=cf.wait(active,timeout=.25,return_when=cf.FIRST_COMPLETED)
                for future in done:
                    case_id=active.pop(future)
                    try:refs.append(future.result())
                    except Exception as exc:errors.append({'case_id':case_id,'type':type(exc).__name__,'message':str(exc)})
            if index<len(cases):errors.append({'type':'SOFT_DISPATCH_STOP','remaining_case_ids':[case['case_id'] for case in cases[index:]],
                'message':'No new calls dispatched; already in-flight calls drained naturally'})
        finally:
            processes=list(pool._processes.values());pool.shutdown(wait=True,cancel_futures=False)
        closure=[{'pid':p.pid,'exitcode':p.exitcode,'alive':p.is_alive()} for p in processes]
        return refs,errors,closure
    def finish_frame(self):
        out=pathlib.Path(self.plan['run_output']);closed=load(out/'run_closed.json')
        record_count=len(closed['results']);records=[load(check(pin)) for pin in closed['results']]
        calls=sum(r.get('QM_call_attempted') is True for r in records)
        durable=sum(r.get('raw_reference',{}).get('raw_call_durable') is True for r in records)
        parsed=sum(r.get('status')=='CONTROL_CALL_RETAINED_AND_PARSED' for r in records)
        pids=sorted({r['pid'] for r in records});evaluation=None;code=None
        if record_count==calls==durable==parsed==72 and closed['all_workers_joined'] and not closed['execution_errors'] and self.monitor.allow_new_dispatch():
            target=self.prefix/'frame_evaluation.json'
            argv=[PY,'-B',self.plan['original_evaluator']['path'],'--config',self.plan['config']['path'],'--run',str(out),'--output',str(target)]
            code=subprocess.run(argv,cwd=PROJECT,stdin=subprocess.DEVNULL).returncode
            if target.is_file():evaluation=load(target)
        accepted=bool(code==0 and len(pids)==16 and evaluation and evaluation['status']=='INPUT_FRAME_SUPPORTED_ON_TESTED_CONTROLS_WITH_LIMITS'
            and not evaluation['contradictions'] and not evaluation['incomplete'])
        return accepted,{'actual_cases_closed':record_count,'QM_calls_attempted':calls,'actual_durable_raw_calls':durable,
            'actual_independently_parsed_cases':parsed,'actual_worker_pids':pids,'execution_closure':ref(out/'run_closed.json'),
            'evaluation_returncode':code,'evaluation':ref(self.prefix/'frame_evaluation.json') if (self.prefix/'frame_evaluation.json').is_file() else None,
            'frame_status':evaluation.get('status') if evaluation else 'EVALUATION_DEFERRED_OR_EXECUTION_INCOMPLETE',
            'remaining_case_ids':[item for e in closed['execution_errors'] for item in e.get('remaining_case_ids',[])]}
    def finish_retention(self):
        out=pathlib.Path(self.plan['run_output']);manifest_path=out/'retention_manifest.json';manifest=load(manifest_path)
        for key in ('source_audit','stable_full_hits','pilot_retention_union','engine_record_audit_membership','engine_selected',
                    'original_prepared','original_pairs','original_audit_selected20','original_audit_membership','audit_policy'):check(manifest[key])
        import pyarrow.parquet as pq
        from workflows.data_v1_final.pprime.queued_retention_v1.binding_v1 import validate_closed
        lineage={'original_prepared':self.plan['prepared'],'original_pairs':self.plan['original_pairs'],'config':self.plan['config']}
        counts=validate_closed(manifest,load(manifest['source_audit']['path']),load(manifest['pilot_retention_union']['path']),
            load(manifest['stable_full_hits']['path']),pq.read_table(manifest['engine_selected']['path']).to_pylist(),
            [r['record_id'] for r in pq.read_table(manifest['original_audit_selected20']['path']).to_pylist()],lineage)
        return True,{'retention_manifest':ref(manifest_path),'actual_counts':counts,'new_UFF_QM_calls':0}
    def close(self,accepted,details,error):
        if self.partial is not None:write_new(self.prefix/'source_audit_partial.json',self.partial)
        memory_file=self.prefix/'actual_memory.json.gz';memory=self.monitor.close(memory_file)
        whole_output=None;output_error=None
        try:
            total=0
            for folder,dirs,files in os.walk(self.prefix,followlinks=False):
                for path in [pathlib.Path(folder),*[pathlib.Path(folder)/name for name in files]]:
                    info=path.lstat()
                    need(info.st_uid==os.getuid() and (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)),'WHOLE_OUTPUT_OWNER_OR_TYPE_CHANGED')
                    total+=info.st_size
                need(all(not (pathlib.Path(folder)/name).is_symlink() for name in dirs),'WHOLE_OUTPUT_SYMLINK_REJECTED')
            whole_output=total;need(total+1024**2<=self.plan['estimated_peak_output_bytes'],'WHOLE_STAGE_OUTPUT_BUDGET_EXCEEDED')
        except Exception as exc:output_error=repr(exc)
        accepted=bool(accepted and memory['thread_closed'] and output_error is None)
        result={'schema':'PPRIME_CPU_AUTO_MEMORY_ACTUAL_STAGE_V1','stage':self.stage,
            'status':('ACTUAL_FRAME_CONTROLS_PASS_WITH_LIMITS' if self.stage=='frame' else 'ACTUAL_RETENTION_PREPARATION_COMPLETE_NOT_QM_AUTHORITY') if accepted else 'ACTUAL_STAGE_INCOMPLETE_OR_NOT_ACCEPTED',
            'job_id':str(self.proof['job_id']),'node':self.proof['request']['node'],'plan':ref(self.args.scope_plan),'startup_proof':self.startup_ref,
            'memory_policy':'SLURM_DEFAULT_UNSPECIFIED','memory_limits_requested':False,'memory_admission_evaluated':False,
            'algorithm_soft_limits':self.plan['soft_limits'],'actual_memory_evidence':ref(memory_file),'memory_closure':memory,
            'details':details,'error':error,'whole_output_bytes_before_receipt':whole_output,'whole_output_error':output_error,'production_membership':False,'new_UFF_calls':0,
            'full_or2000_QM_release':False,'signals_sent':False,'automatic_retry':False,
            'cost_basis':'Root actual terminal sacct parent, including failures and preparation/evaluation overhead; not worker seconds.'}
        write_new(self.prefix/'stage_receipt.json',result)
        print(json.dumps({'status':result['status'],'receipt':ref(self.prefix/'stage_receipt.json'),'details':details}))
        return 0 if accepted else 3


def start_frame(args):return ProducerContext('frame',args)
def start_retention(args):return ProducerContext('retention',args)


def _run(main,stage):
    details={};error=None;accepted=False
    try:
        main();need(ACTIVE is not None and ACTIVE.stage==stage,'PRIMARY_CONTEXT_NOT_STARTED')
        accepted,details=ACTIVE.finish_frame() if stage=='frame' else ACTIVE.finish_retention()
    except Exception as exc:error={'type':type(exc).__name__,'message':str(exc),'traceback':traceback.format_exc()}
    if ACTIVE is None:
        if error:raise RuntimeError(error['message'])
        return 1
    return ACTIVE.close(accepted,details,error)


def run_frame_primary(main):sys.exit(_run(main,'frame'))
def run_retention_primary(main):sys.exit(_run(main,'retention'))
