"""Fresh central-v2 admission, frozen resource clients and bounded own outputs."""
from __future__ import annotations
import gzip,hashlib,json,os,pathlib,socket,sys,time,unittest
from . import contract as C
from workflows.data_v1_final.conformers.formal_cpu_auto_v3 import contract as F,runtime_io as R
from workflows.data_v1_final.pprime.cpu_auto_memory_v1.memory import MemoryObserver


def ref(path):
    path=pathlib.Path(path);C.need(path.is_absolute() and '..' not in path.parts and not any(p.is_symlink() for p in (path,*path.parents)),'LITERAL_REGULAR_REF')
    h=hashlib.sha256()
    with path.open('rb') as f:
        a=os.fstat(f.fileno())
        for part in iter(lambda:f.read(1<<20),b''):h.update(part)
        b=os.fstat(f.fileno())
    C.need((a.st_dev,a.st_ino,a.st_size,a.st_mtime_ns,a.st_uid)==(b.st_dev,b.st_ino,b.st_size,b.st_mtime_ns,b.st_uid),'INPUT_CHANGED')
    return {'path':str(path),'bytes':b.st_size,'sha256':h.hexdigest()}


def body(reference,limit):
    r=C.triple(reference);C.need(r['bytes']<=limit,'BOUNDED_BODY_REQUIRED');path=pathlib.Path(r['path'])
    C.need(not any(p.is_symlink() for p in (path,*path.parents)),'NO_SYMLINK_INPUT')
    with path.open('rb') as stream:
        a=os.fstat(stream.fileno());raw=stream.read(limit+1);b=os.fstat(stream.fileno())
    C.need(len(raw)==r['bytes']==a.st_size and C.sha(raw)==r['sha256'] and
        (a.st_dev,a.st_ino,a.st_size,a.st_mtime_ns)==(b.st_dev,b.st_ino,b.st_size,b.st_mtime_ns),'BODY_SHA_OR_CURRENT_FRAME_CHANGED');return raw


def read(reference,limit=8<<20):return json.loads(body(reference,limit))
def authorized(proof,refs):R.authorized(proof,[C.triple(r) for r in refs])


def request_ref(proof_path,path):
    proof=json.loads(pathlib.Path(proof_path).read_text());wanted=str(pathlib.Path(path))
    found=[r for key in ('source_references','data_references') for r in proof['request'].get(key,[]) if r['path']==wanted]
    C.need(len(found)==1,'EXACT_DECLARED_CLI_REFERENCE');return C.triple(found[0])


def admit(script,args,options,stage):
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2 import runtime
    script=pathlib.Path(script).absolute();argv=[C.PY,'-B',str(script)];required=[]
    for option in options:
        path=getattr(args,option.replace('-','_'));C.need(path.is_absolute() and '..' not in path.parts,'EXACT_LITERAL_CLI')
        argv.extend(['--'+option,str(path)])
        if option not in {'root-preflight','output'}:required.append(request_ref(args.root_preflight,path))
    plan_ref=request_ref(args.root_preflight,args.plan);plan=read(plan_ref,1<<20)
    C.need(plan['schema']=='ROOT_PPRIME_CAUSAL15_SOURCE_PLAN_V1' and plan['status']=='APPROVED_FIXED6_SOURCE_PREPARATION_NOT_QM'
        and plan['reviewer']=='root' and plan['endpoint']=='202.38.247.57:22' and plan['uid']==1278
        and plan['origin_inventory_reference']==C.INVENTORY and plan['source_cases']==[c for pair in C.CASES.values() for c in pair]
        and plan['full_or2000_release']=='HOLD' and plan['original15FAIL_preserved'] is True,'ROOT_FIXED_SOURCE_PLAN_NOT_RELEASE')
    quota_ref=request_ref(args.root_preflight,args.quota_reuse_review);reuse,Q,resources=R.quota_reuse(quota_ref,F.sources())
    C.need(reuse['additional_QA_prepare_execute_caps_bytes']==2*C.CAP and reuse['preserved_previous_reserve_bytes']>=182*(8<<30)
        and reuse['whole_wave_output_reserve_bytes']>=reuse['preserved_previous_reserve_bytes']+2*C.CAP,
        'ROOT_QA_RESERVE_MUST_PRESERVE_EXISTING_WAVE_PLUS_BOTH2GIB_CAPS')
    resources.append(reuse['prior_resource_review_reference'])
    own=[ref(C.HERE/n) for n in C.FILES]
    refs=[*own,*plan['source_references'],plan_ref,C.INVENTORY,*plan['case_result_references'],*plan['execution_asset_references'],*resources]
    proof=runtime.require_startup(args.root_preflight,expected_scope_key='pprime_causal15_main_v1_'+stage,
        expected_scope_parameters=C.parameters(stage),expected_source=script,expected_execution_argv=argv,
        expected_kind='analysis' if stage=='prepare' else 'qm',required_references=(*required,*refs))
    req=proof['request'];C.need(req['node']=='compute-0-13' and req['cpus']==16 and req['pilot'] is False
        and req['memory_policy']=='SLURM_DEFAULT_UNSPECIFIED' and req['scope']['mode']=='BOUNDED_METADATA_PREPARATION'
        and req['estimated_peak_output_bytes']==C.CAP and 1200<=req['wall_seconds']<=172800,'CPU16_NODE13_NO_MEM_FINITE_SCOPE')
    os.environ.update({k:'1' for k in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS','BLIS_NUM_THREADS')})
    session={'proof_reference':ref(args.root_preflight),'plan_reference':plan_ref,'main_source':ref(script),'execution_argv':argv,
        'job_id':str(proof['job_id']),'parent_pid':os.getpid(),'parent_start_ticks':R.proc_ticks(os.getpid()),'boot_id':proof['boot_id'],
        'quota_reuse_review_reference':quota_ref,'own_source_references':own}
    return plan,proof,session


def continuation(session):
    proof=read(session['proof_reference']);C.need(os.getppid()==session['parent_pid'] and R.proc_ticks(os.getppid())==session['parent_start_ticks']
        and os.getuid()==1278 and os.environ.get('SLURM_JOB_ID')==session['job_id']==str(proof['job_id'])
        and socket.gethostname().split('.')[0]==proof['request']['node']=='compute-0-13'
        and pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()==session['boot_id']
        and proof['request']['execution_argv']==session['execution_argv'] and os.environ.get('SLURM_CPUS_PER_TASK')=='16',
        'SAME_LIVE_ADMITTED_PARENT_NOT_OLD_PROOF_AGE_WAIVER')
    for r in session['own_source_references']:C.need(ref(r['path'])==r,'NEW_QA_SOURCE_CHANGED')
    return proof


def new_output(path):
    C.need(C.BASE in path.parents and not path.exists() and not any(p.is_symlink() for p in (path,*path.parents)),'NEW_QA_OUTPUT_ONLY')
    path.mkdir(mode=0o700,parents=True,exist_ok=False);R.fsync_dir(path.parent);return path


def write(path,raw,out):
    C.need(out in pathlib.Path(path).parents and len(raw)<=C.CAP,'BOUNDED_OWN_OUTPUT')
    with R.lock(out):
        C.need(R.disk_bytes(out)+len(raw)+(64<<20)<=C.CAP,'WHOLE2GIB_PREWRITE_CAP')
        with pathlib.Path(path).open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
        R.fsync_dir(pathlib.Path(path).parent)
    return ref(path)


def json_new(path,value,out):return write(path,C.canonical(value)+b'\n',out)


def fixtures(out):
    from .test_cases import Boundaries
    result=unittest.TestResult();unittest.defaultTestLoader.loadTestsFromTestCase(Boundaries).run(result)
    ok=result.testsRun==8 and result.wasSuccessful() and not(result.skipped or result.expectedFailures or result.unexpectedSuccesses)
    value={'status':'PASS' if ok else 'FAIL','tests_run':result.testsRun,'expected_methods':8,
        'failures':[{'test':t.id(),'traceback':v} for t,v in result.failures],'errors':[{'test':t.id(),'traceback':v} for t,v in result.errors],
        'skipped':[str(v) for v in result.skipped],'scientific_bodies_read':False,'QM_UFF_calls':0}
    result_ref=json_new(out/'fixtures8.json',value,out);C.need(ok,'ALL8_PURE_BOUNDARIES_BEFORE_BODY');return result_ref


class Budget:
    def __init__(self,proof,session,out):
        self.out=out;self.started=time.monotonic();self.wall=proof['request']['wall_seconds'];self.stop=None
        self.resource=R.Budget(proof,session,{'stop_dispatch_before_wall_seconds':960,'algorithm_rss_soft_cap_bytes':64<<30,'minimum_MemAvailable_bytes':4<<30},out)
        self.memory=MemoryObserver({'algorithm_limits_are_slurm_requests':False,'sample_seconds':1,'maximum_sample_age_seconds':3,
            'algorithm_rss_soft_cap_bytes':64<<30,'minimum_mem_available_bytes':4<<30,'max_samples':172802,'max_evidence_uncompressed_bytes':32<<20},out/'STOP_NEW_DISPATCH.json')
    def start(self):self.resource.start_monitor();self.memory.start()
    def observe(self,processes=()):
        resource=self.resource.observe(processes)
        if resource:self.stop=self.stop or resource
        if not self.memory.allow_new_dispatch():self.stop=self.stop or 'OWN_DESCENDANT_MEMORY_STOP_NEW_DISPATCH'
        if time.monotonic()-self.started>=self.wall-960:self.stop=self.stop or 'ORIGINAL900_PLUS_DRAIN_DISPATCH_RESERVE'
        if R.disk_bytes(self.out)+(64<<20)>=C.CAP:self.stop=self.stop or 'WHOLE2GIB_STOP_NEW_DISPATCH'
        return self.stop
    def report(self):return {'stop_new_dispatch':self.stop,'resource':self.resource.report(),'memory_stop':self.memory.first_stop,
        'resource_monitor_signals_sent':False,'native_task_timeout_seconds':900,'native_timeout_signals_recorded_in_each_result':True}
    def close(self):
        self.resource.close_monitor();closure=self.memory.close(self.out/'actual_owned_memory.json.gz')
        json_new(self.out/'resource_observations.json',dict(self.report(),memory_thread_closure=closure),self.out)


def prepare_c0(reference,job_id,proof):
    value=read(reference,1<<20);authorized(proof,[value['raw_sacct_reference']])
    parents=F.accounting(reference,[str(job_id)]);row=parents[str(job_id)]
    C.need(value['endpoint']=='202.38.247.57:22' and value['uid']==1278 and row['state']=='COMPLETED'
        and row['exit_code']=='0:0' and row['alloc_cpus']==16 and row['node']=='compute-0-13','ACTUAL_PREPARE_C0_NOT_FUTURE_STATUS')
    return value
