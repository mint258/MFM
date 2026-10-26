"""Small N1 pilot IO/admission/once adapters, not a queue or submitter."""
from __future__ import annotations
import argparse,ast,concurrent.futures as cf,csv,gzip,hashlib,io,json,os,pathlib,resource,shlex,socket,stat,sys,time,traceback,unittest
from . import contract as C,quota_provider as Q

HERE=pathlib.Path(__file__).absolute().parent
ROOT=pathlib.Path('/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025')
BASE=ROOT/'artifacts/conformers/n1_pprime2_pilot_v4'
# Count correction creates no new logical attempt or retry namespace.
LEDGER=ROOT/'artifacts/conformers/n1_pprime2_pilot_v2/once_ledger'
CAP=8<<30;PACKET_CAP=256<<20;TASK_CAP=8<<20;ADMIN_RESERVE=64<<20
FILES=('__init__.py','contract.py','core.py','frozen_sources.json','test_core.py','README.md','io.py','prepare_cpu.py','run32.py','quota_provider.py','test_quota_provider.py')


def ref(path):
    path=pathlib.Path(path).absolute();h=hashlib.sha256()
    with path.open('rb') as stream:
        before=os.fstat(stream.fileno());C.need(stat.S_ISREG(before.st_mode),'REGULAR_INPUT_REQUIRED')
        for chunk in iter(lambda:stream.read(8<<20),b''):h.update(chunk)
        after=os.fstat(stream.fileno())
    C.need((before.st_ino,before.st_size,before.st_mtime_ns)==(after.st_ino,after.st_size,after.st_mtime_ns),'INPUT_CHANGED_DURING_HASH')
    return {'path':str(path),'bytes':after.st_size,'sha256':h.hexdigest()}


def read(ref_value,limit=TASK_CAP):
    C.reference_shape(ref_value);path=pathlib.Path(ref_value['path'])
    C.need(ref_value['bytes']<=limit and path.is_file() and not path.is_symlink(),'BOUNDED_REGULAR_INPUT_REQUIRED')
    with path.open('rb') as stream:body=stream.read(limit+1)
    C.need(len(body)==ref_value['bytes'] and hashlib.sha256(body).hexdigest()==ref_value['sha256'],'PINNED_BODY_CHANGED')
    return json.loads(body)


def request_ref(proof_path,path):
    # Only small proof metadata is read before fresh admission, never task bodies.
    proof=json.loads(pathlib.Path(proof_path).read_text());request=proof['request'];wanted=str(pathlib.Path(path))
    hits=[item for key in ('source_references','data_references','deferred_authority_references')
        for item in request.get(key,[]) if item.get('path')==wanted]
    C.need(hits and all(item==hits[0] for item in hits),'LITERAL_INPUT_NOT_IN_ACTUAL_REQUEST')
    return hits[0]


def authorized(proof,references):
    request=proof['request'];allowed=[item for key in ('source_references','data_references','deferred_authority_references') for item in request.get(key,[])]
    for item in references:C.need(item in allowed,'TRANSITIVE_INPUT_NOT_AUTHORIZED:'+str(item.get('path')))


def admit(script,args,options,scope_key,scope,kind,required):
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2 import runtime
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.contract import PY
    script=pathlib.Path(script).absolute()
    C.need(pathlib.Path(sys.modules['__main__'].__file__).absolute()==script and pathlib.Path(sys.argv[0]).absolute()==script,'ACTUAL_PRIMARY_REQUIRED')
    argv=[PY,'-B',str(script)]
    for name in options:
        value=getattr(args,name.replace('-','_'));C.need(value.is_absolute() and '..' not in value.parts,'LITERAL_ABSOLUTE_CLI_REQUIRED')
        argv.extend(['--'+name,str(value)])
    catalog_ref=ref(HERE/'frozen_sources.json');catalog=C.load_catalog(catalog_ref)
    local=[ref(HERE/name) for name in FILES]
    provider_review_reference=request_ref(args.root_preflight,args.quota_provider_review)
    provider_references=Q.references(provider_review_reference)
    proof=runtime.require_startup(args.root_preflight,expected_scope_key=scope_key,expected_scope_parameters=scope,
        expected_execution_argv=argv,expected_source=script,expected_kind=kind,
        required_references=(*required,*local,*catalog['references'].values(),*catalog['inherited_v1_sources'],
            *catalog['inherited_v2_sources'],*catalog['inherited_v3_sources'],*C.count_evidence_references(catalog),
            *catalog['usability_semantics_provenance'],*provider_references))
    C.need(proof['request']['estimated_peak_output_bytes']>=CAP,'WHOLE8GIB_OUTPUT_REQUEST_REQUIRED')
    C.need(proof['request']['pilot'] is (kind=='conformer'),'HONEST_PREPARATION_OR_PILOT_REQUIRED')
    os.environ.update({key:'1' for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','BLIS_NUM_THREADS')})
    return proof,catalog,{'proof_path':str(args.root_preflight),'runner_source':ref(script),'execution_argv':argv,
        'proof_reference':ref(args.root_preflight),'output_root':str(args.output),'validated_parent_pid':os.getpid(),
        'validated_parent_start_ticks':int(pathlib.Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19]),
        'count_evidence_references':C.count_evidence_references(catalog),
        'usability_semantics_provenance':catalog['usability_semantics_provenance'],
        'quota_provider_review_reference':provider_review_reference,'quota_provider_references':provider_references}


def active_parent_continuation(admission,scope_key,scope,kind):
    """A worker continues its still-live admitted parent; not a fresh-age waiver.

    The main entry already consumed fresh proof before any data read. Heavy
    source hashing may precede worker creation. Bind that exact live parent,
    original proof bytes, boot/allocation and actual main/argv instead of falsely
    labeling the old proof fresh a second time.
    """
    proof=read(admission['proof_reference']);request=proof['request']
    parent=admission['validated_parent_pid'];C.need(os.getppid()==parent,'EXACT_ADMITTED_LIVE_PARENT_REQUIRED')
    path=pathlib.Path('/proc',str(parent),'stat');ticks=int(path.read_text().rsplit(')',1)[1].split()[19])
    C.need(ticks==admission['validated_parent_start_ticks'] and os.getuid()==1278==proof['uid']
        and pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()==proof['boot_id'], 'ADMITTED_PARENT_OR_BOOT_CHANGED')
    C.need(request['scope_key']==scope_key and request['scope_parameters']==scope and request['kind']==kind
        and str(proof['job_id'])==os.environ.get('SLURM_JOB_ID') and request['node']==socket.gethostname().split('.')[0]
        and os.environ.get('SLURM_CPUS_PER_TASK')=='16' and os.environ.get('SLURM_JOB_PARTITION')=='cpu'
        and os.environ.get('CUDA_VISIBLE_DEVICES')=='','SAME_ACTUAL_ADMITTED_CPU16_ALLOCATION_REQUIRED')
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.runtime import primary_binding
    main=pathlib.Path(sys.modules['__main__'].__file__).absolute()
    C.need(ref(main)==admission['runner_source'] and request['execution_argv']==admission['execution_argv'],'EXACT_ADMITTED_MAIN_SOURCE_AND_ARGV_REQUIRED')
    primary_binding(request,main,sys.argv[1:])
    C.need(admission['count_evidence_references'][0]==C.COUNT_CORRECTION_REFERENCE,'SAME_ROOT_COUNT_EVIDENCE_CONTINUATION_REQUIRED')
    C.need(admission['usability_semantics_provenance']==C.USABILITY_SEMANTICS_REFERENCES,'SAME_ORIGINAL_PRODUCER_DEFINITIONS_CONTINUATION_REQUIRED')
    authorized(proof,[*admission['count_evidence_references'],*admission['usability_semantics_provenance'],*admission['quota_provider_references']]);return proof


def new_output(path):
    path=pathlib.Path(path);C.need(path.is_absolute() and BASE in path.parents and path!=LEDGER
        and LEDGER not in path.parents and '..' not in path.parts and not path.exists()
        and not any(item.is_symlink() for item in (path,*path.parents)),'NEW_OWN_PILOT_OUTPUT_REQUIRED')
    path.mkdir(parents=True,mode=0o700,exist_ok=False);return path


def usage(roots):
    seen=set();total=0
    for root in roots:
        root=pathlib.Path(root)
        if not root.exists():continue
        for item in (root,*root.rglob('*')) if root.is_dir() else (root,):
            info=item.lstat();C.need(info.st_uid==os.getuid() and (stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode)),
                'OWN_REGULAR_OUTPUTS_AND_DIRECTORIES_ONLY')
            identity=(info.st_dev,info.st_ino)
            if identity not in seen:total+=info.st_size;seen.add(identity)
    return total


def write(path,body,roots,reserve=ADMIN_RESERVE):
    path=pathlib.Path(path);C.need(usage(roots)+len(body)+reserve<=CAP,'WHOLE_OUTPUT_CAP_PREWRITE')
    descriptor=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600)
    with os.fdopen(descriptor,'wb') as stream:stream.write(body);stream.flush();os.fsync(stream.fileno())
    value=ref(path);C.need(value['bytes']==len(body) and value['sha256']==hashlib.sha256(body).hexdigest(),'DURABLE_WRITE_READBACK_FAILED')
    return value


def json_new(path,value,roots):return write(path,C.canonical(value)+b'\n',roots)


def source_check(item):
    C.reference_shape(item);path=pathlib.Path(item['path'])
    C.need(path.is_file() and not path.is_symlink(),'REGULAR_SOURCE_REQUIRED')
    before=path.stat();actual=ref(path);after=path.stat()
    C.need(actual==item and (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)==
        (after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns),'FULL_SOURCE_SHA_OR_IDENTITY_CHANGED')
    return {'reference':item,'actual':actual,'device':after.st_dev,'inode':after.st_ino,'mtime_ns':after.st_mtime_ns,
        'uid':after.st_uid,'status':'ACTUAL_FULL_SHA_MATCH'}


def science_ast_proof():
    catalog=json.loads((HERE/'frozen_sources.json').read_text())
    inherited={pathlib.Path(item['path']).name:item for item in catalog['inherited_v1_sources']}
    inherited2={pathlib.Path(item['path']).name:item for item in catalog['inherited_v2_sources']}
    for name in ('core.py','test_core.py'):
        old=inherited2[name];new=ref(HERE/name)
        C.need(new['bytes']==old['bytes'] and new['sha256']==old['sha256'],'V2_COMPLETE_CORE_OR_TEN_TEST_SOURCE_BYTES_CHANGED:'+name)
    def functions(path):return {node.name:node for node in ast.parse(path.read_text()).body if isinstance(node,ast.FunctionDef)}
    old_contract=functions(C.pinned_small(inherited['contract.py']));new_contract=functions(HERE/'contract.py')
    old_core=functions(C.pinned_small(inherited['core.py']));new_core=functions(HERE/'core.py')
    names=['proposed_seed','select_real_second','expanded_orders','pilot32']
    for name in names:C.need(ast.dump(old_contract[name],include_attributes=False)==ast.dump(new_contract[name],include_attributes=False),'PURE_SCIENCE_AST_CHANGED:'+name)
    for name in ('_add_conformer','_raw_number','_embedding'):
        C.need(ast.dump(old_core[name],include_attributes=False)==ast.dump(new_core[name],include_attributes=False),'CORE_SCIENCE_AST_CHANGED:'+name)
    native={'science','AllChem','allchem'}
    def calls(node):
        selected=[item for item in ast.walk(node) if isinstance(item,ast.Call) and isinstance(item.func,ast.Attribute)
            and isinstance(item.func.value,ast.Name) and (item.func.value.id in native or
                item.func.value.id=='io' and item.func.attr=='geometry_sha')]
        return [ast.dump(item,include_attributes=False) for item in sorted(selected,key=lambda item:(item.lineno,item.col_offset))]
    C.need(calls(old_core['process_task'])==calls(new_core['process_task']),'REAL_GRAPH_STEREO_UFF_RMSD_CALL_AST_CHANGED')
    return {'status':'SCIENTIFIC_AST_UNCHANGED','pure_functions':names,'core_functions':['_add_conformer','_raw_number','_embedding'],
        'native_call_AST_count':len(calls(new_core['process_task'])),'v1_sources':catalog['inherited_v1_sources'],
        'v2_core_and_test_complete_bytes_unchanged':True,'count_authority_reference':catalog['count_correction_authority_reference']}


def test10():
    inheritance=science_ast_proof()
    from .test_core import N1GenerationBoundaries
    result=unittest.TestResult();suite=unittest.defaultTestLoader.loadTestsFromTestCase(N1GenerationBoundaries)
    suite.run(result)
    return {'status':'PASS' if result.testsRun==10 and result.wasSuccessful() and not(result.skipped or result.expectedFailures or result.unexpectedSuccesses) else 'FAIL',
        'tests_run':result.testsRun,'required':10,'failures':[{'test':item.id(),'traceback':detail} for item,detail in result.failures],
        'errors':[{'test':item.id(),'traceback':detail} for item,detail in result.errors],
        'skips':[{'test':item.id(),'reason':why} for item,why in result.skipped],
        'expected_failures':[{'test':item.id(),'traceback':detail} for item,detail in result.expectedFailures],
        'unexpected_successes':[item.id() for item in result.unexpectedSuccesses],'new_UFF_calls':0,'new_QM_calls':0,
        'v3_scientific_inheritance_before_tests':inheritance,
        'unmodified_fixture_absolute_import_namespace':'n1_pprime2_pilot_v2',
        'new_count_authority_and_aggregation_not_claimed_covered_by_original10':True}


def terminal_c0(accounting_ref,job_id):
    value=read(accounting_ref);C.need(value.get('schema')=='DATA_V1_PARENT_ACCOUNTING_CLOSURE_V1'
        and value.get('status')=='ACTUAL_PARENT_ACCOUNTING_CLOSED' and value.get('query_returncode')==0,'ACTUAL_PREPARE_ACCOUNTING_CLOSURE_REQUIRED')
    raw_ref=value['raw_sacct_reference'];C.reference_shape(raw_ref)
    raw_path=pathlib.Path(raw_ref['path']);C.need(ref(raw_path)==raw_ref and raw_ref['bytes']<=TASK_CAP,'SMALL_ACTUAL_SACCT_REQUIRED')
    rows=list(csv.DictReader(io.StringIO(raw_path.read_text()),delimiter='|'));actual={}
    for row in rows:
        jid=row.get('JobIDRaw',row.get('JobID',''))
        if jid.isdecimal():C.need(jid not in actual,'DUPLICATE_PARENT_SACCT');actual[jid]=row
    declared={str(row['job_id']):row for row in value['parents']}
    C.need(len(declared)==len(value['parents']),'DUPLICATE_DECLARED_PARENT_ACCOUNTING')
    C.need(set(actual)==set(declared) and str(job_id) in actual,'EXACT_ALL_ACCOUNTED_PARENT_SET_REQUIRED')
    total=0
    for jid,row in actual.items():
        other=declared[jid];C.need(row['State'].split()[0]==other['state'] and row['ExitCode']==other['exit_code']
            and int(row['AllocCPUS'])==int(other['alloc_cpus']) and int(row['ElapsedRaw'])==int(other['elapsed_raw_seconds']), 'ACTUAL_PARENT_ACCOUNTING_DIFFERS')
        C.need(row['State'].split()[0] in {'COMPLETED','FAILED','TIMEOUT','CANCELLED','OUT_OF_MEMORY','NODE_FAIL'},'ALL_PARENTS_TERMINAL_REQUIRED')
        C.need(int(row['AllocCPUS'])>=0 and int(row['ElapsedRaw'])>=0,'NONNEGATIVE_ACTUAL_ALLOCATED_COST_REQUIRED')
        total+=int(row['AllocCPUS'])*int(row['ElapsedRaw'])
    row=actual[str(job_id)];C.need(row['State']=='COMPLETED' and row['ExitCode']=='0:0' and int(row['AllocCPUS'])==16,'PREPARE_ACTUAL_C0_CPU16_REQUIRED')
    return {'accounting_reference':accounting_ref,'raw_sacct_reference':raw_ref,'all_declared_actual_core_seconds':total,'prepare_job_id':str(job_id)}


def claim(task,ledger,out,proof):
    ledger=pathlib.Path(ledger);C.need(ledger==LEDGER and not any(path.is_symlink() for path in (ledger,*ledger.parents)),'EXACT_SHARED_N1_ONCE_LEDGER_REQUIRED')
    ledger.mkdir(parents=True,exist_ok=True,mode=0o700);key=task['task_key']
    C.need(key==C.task_key(task['meta']['molecule_id']),'N1_GENERATION_ONCE_KEY_DIFFERS')
    row={'schema':'N1_PPRIME2_ONCE_ATTEMPT_STARTED_V2','task_key':key,'molecule_id':task['meta']['molecule_id'],
        'job_id':str(proof['job_id']),'uid':os.getuid(),'pid':os.getpid(),
        'pid_start_ticks':int(pathlib.Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19]),
        'boot_id':proof['boot_id'],'node':socket.gethostname(),'started_unix':time.time(),'output_root':str(out),
        'core_reference':ref(HERE/'core.py'),'seed':C.proposed_seed(task['meta']['molecule_id']),
        'automatic_retry':False,'common':False,'pilot_membership':False}
    return json_new(ledger/(key+'.json'),row,[out,ledger])


def reserve_task(task):
    # Finite JSON repr bound based on actual atom count and already bounded
    # source metadata; this is byte reservation, not a runtime/cost prediction.
    n=len(task['source_atomic_numbers']);baseline=len(C.canonical(task['existing_conformers'][0]));pointer=len(C.canonical(task['records'][0]))
    bound=(4<<20)+4096*n+4*baseline+16*pointer
    C.need(bound<=PACKET_CAP,'TASK_PACKET_RESERVATION_EXCEEDS_REVIEWED_CAP_NO_DISPATCH')
    return 3*bound  # packet plus immutable candidate/embedding/error checkpoints


def event_checkpoint(out,task,name,value):
    out=pathlib.Path(out);C.need(BASE in out.parents and out.exists(),'ACTUAL_OWN_EVENT_OUTPUT_REQUIRED')
    directory=out/'events'/task['task_key']
    C.need(not any(path.is_symlink() for path in (directory,*directory.parents)),'NO_EVENT_SYMLINK_ANCESTOR')
    directory.mkdir(parents=True,exist_ok=True,mode=0o700)
    C.need(not any(path.is_symlink() for path in (directory,*directory.parents)),'NO_EVENT_SYMLINKS')
    return json_new(directory/(name+'.json'),{'schema':'N1_ACTUAL_EVENT_CHECKPOINT_V2','task_key':task['task_key'],
        'molecule_id':task['meta']['molecule_id'],'job_id':os.environ['SLURM_JOB_ID'],'pid':os.getpid(),'uid':os.getuid(),
        'start_ticks':int(pathlib.Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19]),
        'boot_id':pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'node':socket.gethostname(),
        'observed_unix':time.time(),
        'value':value,'common':False,'pilot_membership':False},[out,LEDGER])


class EmbeddingJournal(list):
    """Instrument the unchanged helper's list protocol, with no new native call."""
    def __init__(self,out,task):super().__init__();self.out=out;self.task=task;self.closed=set()
    def append(self,event):
        self.flush_last();super().append(event)
        event_checkpoint(self.out,self.task,'embedding_%02d_started'%len(self),event)
    def flush_last(self):
        if self and len(self) not in self.closed:
            event_checkpoint(self.out,self.task,'embedding_%02d_observed'%len(self),self[-1]);self.closed.add(len(self))


def packet_new(out,task,packet,ledger):
    raw=C.canonical(packet)+b'\n';C.need(len(raw)<=PACKET_CAP,'MAX_PACKET_BYTES_EXCEEDED_FULL_EVENT_PACKET_NOT_TRUNCATED')
    compressed=gzip.compress(raw,mtime=0);path=out/'packets'/(hashlib.sha256(task['meta']['molecule_id'].encode()).hexdigest()+'.json.gz')
    result=write(path,compressed,[out,ledger])
    with gzip.GzipFile(fileobj=io.BytesIO(path.read_bytes()),mode='rb') as stream:
        body=stream.read(PACKET_CAP+1);C.need(len(body)<=PACKET_CAP and stream.read(1)==b'','BOUNDED_PACKET_EOF_REQUIRED')
    C.need(body==raw,'EXACT_JSON_GZIP_BYTE_READBACK_CHANGED')
    saved=json.loads(body);catalog=json.loads((HERE/'frozen_sources.json').read_text())
    original_io=C.module_from_pin('_n1_readback_original_io',catalog['references']['io'])
    C.need(saved['task_key']==task['task_key'] and saved['summary']['molecule_id']==task['meta']['molecule_id']
        and saved['common'] is False and saved['pilot_membership'] is False and saved['final_common_reference'] is None,'NO_PILOT_COMMON_RELEASE_OR_PACKET_ID_CHANGE')
    z=task['source_atomic_numbers'];old=saved['baseline_original_row']
    if saved['baseline_identity'] is not None:
        C.need(C.sha_value(old)==task['baseline_row_sha256'] and original_io.geometry_sha(z,old['coordinates'])==saved['baseline_identity']['geometry_sha256'],'BASELINE_FLOAT64_READBACK_CHANGED')
    for event in saved['candidate_optimizer_events']:
        if event['finite']:C.need(original_io.geometry_sha(z,event['coordinates'])==event['geometry_sha256'],'CANDIDATE_FLOAT64_READBACK_CHANGED')
    if saved['supplement'] is not None:
        extra=saved['supplement'];C.need(original_io.geometry_sha(z,extra['coordinates'])==extra['geometry_sha256']
            and extra['geometry_sha256']!=saved['baseline_identity']['geometry_sha256'],'SUPPLEMENT_FLOAT64_OR_IDENTITY_READBACK_CHANGED')
    return {'molecule_id':task['meta']['molecule_id'],'task_key':task['task_key'],'reference':result,
        'status':'ALL_PRESENT_GEOMETRIES_FLOAT64_SHA_READBACK','packet_status':saved['summary']['status'],
        'actual_candidate_events':len(saved['candidate_optimizer_events'])}


class Budget:
    """Actual observation -> STOP new dispatch -> natural drain; no science kill."""
    def __init__(self,proof,out,ledger=None,rss_cap=64<<30,*,quota_provider_review_reference):
        self.proof=proof;self.out=out;self.roots=[out]+([ledger] if ledger else []);self.started=time.monotonic()
        script=pathlib.Path(proof['request']['script_reference']['path']).read_text();logs=[]
        for line in script.splitlines():
            if not line.startswith('#SBATCH'):continue
            tokens=shlex.split(line[len('#SBATCH'):].strip())
            if not tokens:continue
            first=tokens[0]
            if first in {'--output','--error','-o','-e'} and len(tokens)==2:logs.append(tokens[1])
            elif first.startswith('--output=') or first.startswith('--error='):logs.append(first.split('=',1)[1])
        if not logs:logs=[str(pathlib.Path(proof['request']['workdir'])/('slurm-'+str(proof['job_id'])+'.out'))]
        for value in logs:
            value=value.replace('%j',str(proof['job_id'])).replace('%J',str(proof['job_id'])).replace('%x',proof['request']['job_name'])
            C.need('%' not in value and '$' not in value,'LITERAL_OBSERVABLE_STAGE_LOG_REQUIRED')
            path=pathlib.Path(value);C.need(path.is_absolute(),'ABSOLUTE_STAGE_LOG_REQUIRED')
            if path not in self.roots:self.roots.append(path)
        self.stop=None;self.samples=[];self.quota=[];self.rss_cap=rss_cap;self.next_quota=0
        self.peak_rss=0;self.minimum_available=None;self.minimum_quota_free=None
        self.wall_cutoff=max(0,proof['request']['wall_seconds']-600)
        self.quota_client=Q.Client(quota_provider_review_reference,proof['request']);self.observation_failure=None
    def observe(self,processes=(),reserve=0):
        try:
            available=next(int(row.split()[1])*1024 for row in pathlib.Path('/proc/meminfo').read_text().splitlines() if row.startswith('MemAvailable:'))
            pids=[os.getpid()]+[process.pid for process in processes if process.pid and process.is_alive()];rss=0
            for pid in pids:
                try:rss+=int(pathlib.Path('/proc',str(pid),'statm').read_text().split()[1])*os.sysconf('SC_PAGE_SIZE')
                except FileNotFoundError:continue
            row={'unix':time.time(),'owned_parent_worker_RSS':rss,'MemAvailable':available,'managed_bytes':usage(self.roots),'pids':pids}
            self.peak_rss=max(self.peak_rss,rss);self.minimum_available=available if self.minimum_available is None else min(self.minimum_available,available)
            if len(self.samples)<1024:self.samples.append(row)
            else:self.samples[-1]=row
            if rss>self.rss_cap or available<4<<30:self.stop=self.stop or 'MEMORY_STOP_NEW_DISPATCH'
            if row['managed_bytes']+reserve+ADMIN_RESERVE>CAP:self.stop=self.stop or 'STORAGE_RESERVE_STOP_NEW_DISPATCH'
            if time.monotonic()-self.started>=self.wall_cutoff:self.stop=self.stop or 'WALL_RESERVE_STOP_NEW_DISPATCH'
            prior=self.quota_client.last
            if prior is not None and (time.time()-prior['observed_unix_seconds']>Q.MAX_AGE
                    or time.time()>=prior['publisher_expires_unix_seconds']):self.next_quota=0
            if time.monotonic()>=self.next_quota:
                observation=self.quota_client.observe();free=observation['free_bytes']
                if len(self.quota)<1024:self.quota.append(observation)
                else:self.quota[-1]=observation
                self.minimum_quota_free=free if self.minimum_quota_free is None else min(self.minimum_quota_free,free)
                self.next_quota=time.monotonic()+60
                # Reserve the full task cap conservatively as well as this separate
                # finite metadata publisher. Local df is never quota evidence.
                if free-CAP-Q.CAP-reserve-ADMIN_RESERVE<200000000000:self.stop=self.stop or 'QUOTA200GB_STOP_NEW_DISPATCH'
        except Exception as exc:
            self.observation_failure={'error':repr(exc),'last_provider_evidence':self.quota_client.last}
            self.stop=self.stop or 'OBSERVATION_UNAVAILABLE:'+type(exc).__name__+': '+str(exc)
        return self.stop
    def report(self):return {'stop_new_dispatch':self.stop,'memory_samples':self.samples,'actual_quota_observations':self.quota,
        'algorithm_RSS_soft_cap_bytes':self.rss_cap,'minimum_MemAvailable_bytes':4<<30,'wall_dispatch_cutoff_seconds':self.wall_cutoff,
        'cost_1p5_policy':'REPORT_AND_CONTINUE_NO_ESTIMATE_STOP','explicit_science_signals_sent_by_producer':False,'natural_drain_on_dispatch_stop':True,
        'quota_provider_review_reference':self.quota_client.reference,'runtime_observation_failure':self.observation_failure,
        'quota_provider_policy':Q.POLICY,'whole_task_quota_reserve_bytes':CAP,'additional_provider_quota_reserve_bytes':Q.CAP,
        'managed_output_and_actual_log_paths':[str(path) for path in self.roots],'managed_bytes_observed':usage(self.roots),
        'sample_retention':'first1023_plus_latest; all observations still checked and extrema retained',
        'maximum_observed_sample_RSS':self.peak_rss,'minimum_observed_MemAvailable':self.minimum_available,'minimum_observed_quota_free':self.minimum_quota_free}


def prepare_input_references(formal_path,quota_provider_review_path):
    """Metadata CLI helper only: never open/hash a large dataset or LMDB."""
    formal_ref=ref(formal_path);C.need(formal_ref['bytes']<=1<<20,'SMALL_FORMAL_METADATA_ONLY')
    value=read(formal_ref);auth=read(value['roles_authority']);roles_ref=auth['source_role_manifest'];roles=read(roles_ref)
    source=read(value['formal_source_receipt']);sprime=read(value['sprime_manifest'])
    refs=[formal_ref,*[value[key] for key in ('per_molecule','roles_authority','formal_source_receipt','sprime_manifest')],roles_ref,auth['actual_closure']]
    refs.extend({key:row[key] for key in ('path','bytes','sha256')} for row in roles['outputs'] if '/molecule_roles/' in row['path'])
    refs.extend(row['reference'] for row in source['outputs'] if row['name']=='formal_population')
    refs.extend({key:row[key] for key in ('path','bytes','sha256')} for row in sprime['references'] if row['kind']=='conformers')
    catalog=C.load_catalog(ref(HERE/'frozen_sources.json'))
    provider_review_reference=ref(quota_provider_review_path);provider_references=Q.references(provider_review_reference)
    source_refs=[ref(HERE/name) for name in FILES]+list(catalog['references'].values())+catalog['inherited_v1_sources']
    source_refs+=catalog['inherited_v2_sources']+catalog['inherited_v3_sources']+C.count_evidence_references(catalog)
    source_refs+=catalog['usability_semantics_provenance']+provider_references
    sources={}
    for row in source_refs:
        C.need(row['path'] not in sources or sources[row['path']]==row,'CONFLICTING_SMALL_SOURCE_OR_PROVIDER_AUTHORITY_PINS')
        sources[row['path']]=row
    return {'schema':'N1_PREPARE_INPUT_LOCATORS_ONLY_V4','input_references':list({row['path']:row for row in refs}.values()),
        'source_references':list(sources.values()),
        'large_dataset_bodies_read':False,'LMDB_read':False,'new_UFF_calls':0,'new_QM_calls':0,
        'source_SHA_still_requires_actual_CPU_preparation':True}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description='Small metadata locators only, no science/large dataset read')
    parser.add_argument('--formal-config',type=pathlib.Path,required=True)
    parser.add_argument('--quota-provider-review',type=pathlib.Path,required=True)
    args=parser.parse_args();print(json.dumps(prepare_input_references(args.formal_config,args.quota_provider_review),ensure_ascii=False,allow_nan=False))
