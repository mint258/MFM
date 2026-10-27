"""New metadata/runtime adapter; public frozen resource and packet APIs only."""
from __future__ import annotations
import gzip,hashlib,json,os,pathlib,socket,sys,unittest
from . import contract as C
from workflows.data_v1_final.conformers.pm7_independent_cache32_v1 import io as P,inheritance as H
from workflows.data_v1_final.conformers.pm7_hof_augmentation32_v1 import contract as HC
R=P.R;F=P.F;ref=P.ref;read=P.read;authorized=P.authorized;source_check=P.source_check;request_ref=P.request_ref


def sources():
    rows=[*[ref(C.HERE/n) for n in C.FILES],*P.sources(),*[ref(HC.HERE/n) for n in HC.FILES]]
    result={}
    for r in rows:
        r=C.reference(r);C.need(r['path'] not in result or result[r['path']]==r,'SOURCE_PIN_CONFLICT');result[r['path']]=r
    return [result[k] for k in sorted(result)]


def admit(script,args):
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2 import runtime
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.contract import PY
    script=pathlib.Path(script).absolute();argv=[PY,'-B',str(script)];required=[]
    C.need(pathlib.Path(sys.modules['__main__'].__file__).absolute()==script and pathlib.Path(sys.argv[0]).absolute()==script,'ACTUAL_POPULATION_PRIMARY')
    for name in C.OPTIONS:
        p=getattr(args,name.replace('-','_'));C.need(p.is_absolute() and '..' not in p.parts,'LITERAL_FULL_ARGV')
        argv+=['--'+name,str(p)]
        if name not in {'root-preflight','output'}:required.append(request_ref(args.root_preflight,p))
    plan_ref=request_ref(args.root_preflight,args.plan);plan=read(plan_ref)
    C.need(plan['schema']==C.SCHEMA and plan['status']==C.STATUS and plan['reviewer']=='root'
        and plan['endpoint']=='202.38.247.57:22' and plan['uid']==1278 and plan['common'] is False
        and plan['full_cache_release'] is False and plan['ledger_root']==str(C.LEDGER),'ROOT_EXACT_BATCH_NOT_COMMON_RELEASE')
    selected=C.selection(plan['selection']);quota=request_ref(args.root_preflight,args.quota_reuse_review)
    reuse,Q,resources=R.quota_reuse(quota,F.sources())
    C.need(reuse['additional_PM7_batch_output_cap_bytes']==C.CAP
        and reuse['whole_wave_output_reserve_bytes']>=reuse['preserved_previous_reserve_bytes']+C.CAP,'NEW64GIB_RESERVE_PRESERVES_PREVIOUS_OUTPUTS')
    own=sources();required.extend([*own,*plan['metadata_source_references'],*plan['data_references'],*resources])
    proof=runtime.require_startup(args.root_preflight,expected_scope_key=C.SCOPE,expected_scope_parameters=C.scope(selected),
        expected_source=script,expected_execution_argv=argv,expected_kind='analysis',required_references=required)
    req=proof['request'];C.need(req['node']=='compute-0-13' and req['cpus']==16 and req['pilot'] is False
        and req['memory_policy']=='SLURM_DEFAULT_UNSPECIFIED' and req['scope']['mode']=='BOUNDED_METADATA_PREPARATION'
        and req['estimated_peak_output_bytes']==C.CAP and 1200<=req['wall_seconds']<=172800,'FRESH_CPU16_NODE13_NO_MEM_FINITE64GIB')
    os.environ.update({k:'1' for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','BLIS_NUM_THREADS')})
    os.environ['CUDA_VISIBLE_DEVICES']=''
    session={'proof_reference':ref(args.root_preflight),'main_source':ref(script),'execution_argv':argv,'parent_pid':os.getpid(),
        'parent_start_ticks':R.proc_ticks(os.getpid()),'boot_id':proof['boot_id'],'job_id':str(proof['job_id']),
        'quota_reuse_review_reference':quota,'output_root':str(args.output),'source_references':own,'source_fingerprint':C.digest(own)}
    return plan,plan_ref,proof,session


def new_output(path):
    C.need(C.BASE in path.parents and not path.exists() and not any(p.is_symlink() for p in (path,*path.parents)),'NEW_OWN_BATCH_OUTPUT')
    path.mkdir(parents=True,exist_ok=False,mode=0o700)
    for name in ('tasks','starts','molecules','finished','progress'):(path/name).mkdir()
    C.LEDGER.mkdir(parents=True,exist_ok=True,mode=0o700)
    C.need(not C.LEDGER.is_symlink() and C.LEDGER.stat().st_uid==1278,'OWN_LITERAL_GLOBAL_CACHE_LEDGER')
    return path


def usage(out):
    path=out/'usage.json'
    return json.loads(path.read_text())['charged_bytes'] if path.exists() else 0


def charge_locked(out,amount,final=False):
    used=usage(out)+amount+4096;C.need(used+(0 if final else C.RESERVE)<=C.CAP,'WHOLE_BATCH64GIB_PREWRITE_STOP')
    tmp=out/('usage.'+str(os.getpid())+'.tmp')
    with tmp.open('xb') as f:f.write(C.canonical({'charged_bytes':used}));f.flush();os.fsync(f.fileno())
    os.replace(tmp,out/'usage.json');R.fsync_dir(out)


def write(path,body,out,final=False):
    path=pathlib.Path(path);C.need(out in path.parents and len(body)<=P.C.PACKET_CAP,'BOUNDED_NEW_OWN_OUTPUT')
    C.need(not final or path.name in {'receipt.json','molecule_catalog.jsonl.gz','parent_errors.jsonl.gz','resource_observations.json.gz'},'RESERVE_ONLY_FOR_FINAL_METADATA')
    with R.lock(out):
        charge_locked(out,len(body),final);fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'wb') as f:f.write(body);f.flush();os.fsync(f.fileno())
        R.fsync_dir(path.parent)
    actual=ref(path);C.need(actual['bytes']==len(body) and actual['sha256']==hashlib.sha256(body).hexdigest(),'DURABLE_SHA_READBACK');return actual


def json_new(path,v,out,final=False):return write(path,C.canonical(v)+b'\n',out,final)


def append_progress(path,v,out):
    body=C.canonical(v)+b'\n';C.need(len(body)<=32768 and out in path.parents,'BOUNDED_RECORD_EVENT')
    with R.lock(out):
        charge_locked(out,len(body));fd=os.open(path,os.O_WRONLY|os.O_APPEND|os.O_CREAT|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'ab') as f:f.write(body);f.flush();os.fsync(f.fileno())


def claim(key,value,out):
    path=C.LEDGER/(key+'.json');raw=C.canonical(value)+b'\n';C.need(len(raw)<=8192,'SMALL_CACHE_CLAIM')
    with R.lock(out):
        charge_locked(out,len(raw)) # Charge external immutable bytes before creating them.
        try:fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        except FileExistsError:return None
        with os.fdopen(fd,'wb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
        R.fsync_dir(C.LEDGER)
    return ref(path)


def packet(path,value,out):
    raw=C.canonical(value);C.need(len(raw)<=P.C.PACKET_CAP,'INHERITED_PACKET_SOFTWARE_LIMIT_NO_TRUNCATION')
    r=write(path,gzip.compress(raw,mtime=0),out);C.need(P.read_packet(r)==value,'EXACT_FLOAT64_AND_GZIP_READBACK');return r


def fixtures(out):
    inheritance=json_new(out/'source_inheritance.json',H.proof(),out)
    from workflows.data_v1_final.conformers.pm7_independent_cache32_v1.test_cache import CacheBoundaries
    from workflows.data_v1_final.conformers.pm7_hof_augmentation32_v1.test_derive import DerivedBoundaries
    from .test_boundaries import BatchBoundaries
    suite=unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromTestCase(t) for t in (CacheBoundaries,DerivedBoundaries,BatchBoundaries))
    result=unittest.TestResult();suite.run(result)
    ok=result.testsRun==17 and result.wasSuccessful() and not(result.skipped or result.expectedFailures or result.unexpectedSuccesses)
    value={'status':'PASS' if ok else 'FAIL','tests_run':result.testsRun,'expected':17,'source_inheritance':inheritance,
        'errors':[(t.id(),e) for t,e in result.errors],'failures':[(t.id(),e) for t,e in result.failures],
        'skipped':list(map(str,result.skipped)),'before_all_scientific_bodies':True,'new_QM_calls':0,'new_UFF_calls':0}
    r=json_new(out/'fixtures17.json',value,out);C.need(ok,'ALL17_BEFORE_SCIENTIFIC_BODY');return r
