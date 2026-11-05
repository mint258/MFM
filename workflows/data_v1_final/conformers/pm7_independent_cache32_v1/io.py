"""Fresh central-v2 admission and bounded own IO; no queue or old runtime patch."""
from __future__ import annotations
import argparse,gzip,hashlib,json,os,pathlib,socket,sys,unittest
from . import contract as C,inheritance as H
from workflows.data_v1_final.conformers.formal_cpu_auto_v3 import contract as F,runtime_io as R
from workflows.data_v1_final.conformers.n1_pprime2_pilot_v4 import io as V
from workflows.data_v1_final.conformers.formal_cpu_auto_prepare_mapping_v1 import mapping as M
HERE=pathlib.Path(__file__).absolute().parent
ref=V.ref;read=V.read;source_check=V.source_check;authorized=V.authorized;request_ref=V.request_ref


def sources():
    return [*[ref(HERE/n) for n in C.FILES],*H.sources(ref),*[ref(F.HERE/n) for n in R.FILES],*F.sources().values(),
        *[ref(M.HERE/n) for n in ('__init__.py','mapping.py','prepare_batch.py')]]


def admit(script,args,options,stage):
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2 import runtime
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.contract import PY
    script=pathlib.Path(script).absolute();argv=[PY,'-B',str(script)]
    C.need(pathlib.Path(sys.modules['__main__'].__file__).absolute()==script and pathlib.Path(sys.argv[0]).absolute()==script,'ACTUAL_CACHE_PRIMARY_REQUIRED')
    required=[]
    for name in options:
        path=getattr(args,name.replace('-','_'));C.need(path.is_absolute() and '..' not in path.parts,'LITERAL_CACHE_CLI_LOCATORS')
        argv.extend(['--'+name,str(path)])
        if name not in {'root-preflight','output'}:required.append(request_ref(args.root_preflight,path))
    quota_ref=request_ref(args.root_preflight,args.quota_reuse_review);reuse,Q,resources=R.quota_reuse(quota_ref,F.sources())
    proof=runtime.require_startup(args.root_preflight,expected_scope_key='pm7_independent_cache32_v1_'+stage,
        expected_scope_parameters=C.scope(stage),expected_execution_argv=argv,expected_source=script,expected_kind='analysis',
        required_references=(*required,*sources(),*resources))
    request=proof['request'];C.need(request['node']=='compute-0-13' and request['cpus']==16 and request['pilot'] is False
        and request['memory_policy']=='SLURM_DEFAULT_UNSPECIFIED' and request['scope']['mode']=='BOUNDED_METADATA_PREPARATION'
        and request['estimated_peak_output_bytes']>=C.CAP and 1200<=request['wall_seconds']<=172800,'EXACT_CPU16_NODE13_NO_MEM_BOUNDED_ANALYSIS')
    os.environ.update({k:'1' for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','BLIS_NUM_THREADS')})
    session={'proof_reference':ref(args.root_preflight),'main_source':ref(script),'execution_argv':argv,'parent_pid':os.getpid(),
        'parent_start_ticks':R.proc_ticks(os.getpid()),'boot_id':proof['boot_id'],'job_id':str(proof['job_id']),
        'quota_reuse_review_reference':quota_ref,'output_root':str(args.output),'source_references':sources()}
    return proof,session


def new_output(path):
    C.need(C.BASE in path.parents and not path.exists() and not any(p.is_symlink() for p in (path,*path.parents)),'NEW_OWN_CACHE_OUTPUT_ONLY')
    path.mkdir(parents=True,exist_ok=False,mode=0o700);R.fsync_dir(path.parent);return path


def budget(proof,session,out):
    # Public resource monitor only; never set R.OUT/PROOF/VALUE or replace APIs.
    return R.Budget(proof,session,{'stop_dispatch_before_wall_seconds':600,'algorithm_rss_soft_cap_bytes':64<<30,'minimum_MemAvailable_bytes':4<<30},out)


def write(path,body,out):
    C.need(pathlib.Path(out) in pathlib.Path(path).parents and len(body)<=C.CAP,'OWN_FINITE_OUTPUT_ONLY')
    with R.lock(out):
        C.need(R.disk_bytes(out)+len(body)+(64<<20)<=C.CAP,'WHOLE_CACHE_OUTPUT_CAP_PREWRITE')
        fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'wb') as stream:stream.write(body);stream.flush();os.fsync(stream.fileno())
        R.fsync_dir(pathlib.Path(path).parent)
    result=ref(path);C.need(result['bytes']==len(body) and result['sha256']==hashlib.sha256(body).hexdigest(),'EXACT_DURABLE_OUTPUT_READBACK')
    return result


def json_new(path,value,out):return write(path,C.canonical(value)+b'\n',out)


def parquet(path,table,out):
    import pyarrow as pa,pyarrow.parquet as pq
    sink=pa.BufferOutputStream();pq.write_table(table,sink,compression='zstd',row_group_size=4096)
    return write(path,sink.getvalue().to_pybytes(),out)


def fixtures(out):
    source=H.proof();source_ref=json_new(out/'source_inheritance.json',source,out)
    from .test_cache import CacheBoundaries
    result=unittest.TestResult();unittest.defaultTestLoader.loadTestsFromTestCase(CacheBoundaries).run(result)
    ok=result.testsRun==8 and result.wasSuccessful() and not(result.skipped or result.expectedFailures or result.unexpectedSuccesses)
    report={'status':'PASS' if ok else 'FAIL','tests_run':result.testsRun,'expected_tests':8,
        'failures':[{'test':t.id(),'traceback':error} for t,error in result.failures],
        'errors':[{'test':t.id(),'traceback':error} for t,error in result.errors],
        'skips':[str(r) for r in result.skipped],'unexpected_successes':[str(r) for r in result.unexpectedSuccesses],
        'expected_failures':[str(r) for r in result.expectedFailures],'source_inheritance_reference':source_ref,
        'executed_before_actual_scientific_bodies':True,'new_UFF_calls':0,'new_QM_calls':0}
    reference=json_new(out/'fixtures8.json',report,out);C.need(ok,'ALL8_BOUNDARIES_BEFORE_BODY');return reference


def plan(reference,proof):
    value=read(reference);C.need(value['schema']=='ROOT_PM7_INDEPENDENT_CACHE32_PLAN_V1' and value['status']=='APPROVED_BOUNDED32_NOT_FULL'
        and value['reviewer']=='root' and value['endpoint']=='202.38.247.57:22' and value['uid']==1278 and value['molecules']==32
        and value['golden']==16 and value['independent']==16 and value['hof_mode'] in {'CANONICAL_VERIFIED','GEOMETRY_ONLY_UNVERIFIED'}
        and value['full_execution_authorized'] is False and value['common'] is False,'ROOT_EXPLICIT_CACHE32_SOURCE_PLAN')
    required=[value[k] for k in ('formal_source','per_molecule','golden_prepared','golden_profile_receipt','golden_manifest','mapping_review','hof_authority_review')]
    authorized(proof,required);C.need(value['formal_source']==M.EXPECTED,'ONLY_ORIGINAL_FORMAL_SOURCE')
    return value


def formal_source(value,proof,out):
    review=read(value['mapping_review']);receipt=read(review['formal_source_receipt']);prior=read(review['prior_cpu_source_validation'])
    authorized(proof,[review[k] for k in ('formal_source_receipt','prior_cpu_source_validation','same_storage_mapping','quota_provider_review')])
    C.need(review['schema']=='ROOT_SPRIME_NODE13_SOURCE_MOUNT_MAPPING_V1' and review['status']=='APPROVED_EXACT_CANONICAL_SOURCE_MAPPING'
        and review['reviewer']=='root' and review['node']==proof['request']['node']=='compute-0-13' and review['uid']==1278
        and review['endpoint']=='202.38.247.57:22' and review['canonical_reference']==value['formal_source']==M.EXPECTED,
        'ACTUAL_EXACT_NODE13_SOURCE_MOUNT_REVIEW')
    C.need(receipt['status']=='ALL_BOUND_INPUTS_SHA_VERIFIED' and prior['status']=='ALL_ACTUAL_SOURCE_SHA_VERIFIED'
        and prior['runtime']['job_id']=='4521417','ORIGINAL_INPUT_AND_REAL_PRIOR_CPU_VALIDATION')
    rows=[r for r in receipt['outputs'] if r['name']=='formal_population'];matches=[r for r in prior['inputs'] if r['reference']==value['formal_source']]
    C.need(len(rows)==len(matches)==1 and rows[0]['reference']==value['formal_source'] and rows[0]['after']==review['historical_frame']
        and matches[0]['actual']==value['formal_source'] and matches[0]['status']=='ACTUAL_FULL_SHA_MATCH'
        and matches[0]['inode']==rows[0]['after']['inode'] and matches[0]['mtime_ns']==rows[0]['after']['mtime_ns']
        and matches[0]['uid']==1278,'EXACT_CURRENT_AND_HISTORICAL_CANONICAL_INPUT')
    path=pathlib.Path(value['formal_source']['path']);before=path.stat()
    C.need(M.source_frame(before)==M.expected_frame(rows[0]['after']) and before.st_dev==matches[0]['device'],'ONLY_OBSERVED_NODE13_DEVICE_TRANSLATION')
    source_check(value['formal_source']);after=path.stat();C.need(M.stable_frame(before)==M.stable_frame(after),'CURRENT_SOURCE_FRAME_CHANGED_DURING_FULL_SHA')
    json_new(out/'actual_formal_source.json',{'reference':value['formal_source'],'historical_frame':rows[0]['after'],
        'current_frame':dict(zip(('device','inode','size','mtime_ns','uid'),M.stable_frame(after))),'actual_CPU_whole_SHA_verified':True},out)


def continuation(session):
    proof=read(session['proof_reference']);request=proof['request']
    C.need(os.getppid()==session['parent_pid'] and R.proc_ticks(os.getppid())==session['parent_start_ticks']
        and os.getuid()==1278 and str(os.environ.get('SLURM_JOB_ID'))==session['job_id']==str(proof['job_id'])
        and pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()==session['boot_id']
        and socket.gethostname().split('.')[0]==request['node']=='compute-0-13' and os.environ.get('SLURM_CPUS_PER_TASK')=='16'
        and request['memory_policy']=='SLURM_DEFAULT_UNSPECIFIED' and request['execution_argv']==session['execution_argv']
        and ref(session['main_source']['path'])==session['main_source'],'SAME_LIVE_ADMITTED_PARENT_NOT_OLD_PROOF_AGE_WAIVER')
    for reference in session['source_references']:C.need(ref(reference['path'])==reference,'ADMITTED_CACHE_SOURCE_CHANGED')
    return proof


def packet(path,value,out):
    raw=C.canonical(value);C.need(len(raw)<=C.PACKET_CAP,'FULL_CACHE_PACKET_SOFTWARE_CAP_NO_TRUNCATION')
    reference=write(path,gzip.compress(raw,mtime=0),out)
    C.need(read_packet(reference)==value,'EXACT_FULL_PACKET_GZIP_FLOAT64_READBACK');return reference


def read_packet(reference):
    source_check(reference)
    with gzip.open(reference['path'],'rb') as stream:
        raw=stream.read(C.PACKET_CAP+1);C.need(len(raw)<=C.PACKET_CAP and stream.read(1)==b'','BOUNDED_GZIP_EOF_CRC')
    value=json.loads(raw);pc=H.profile_common()
    for row in value.get('pm7',[]):C.need(pc.IO.geometry_sha(value['atomic_numbers'],row['coordinates'])==row['geometry_sha256'],'CACHE_FLOAT64_GEOMETRY_SHA_CHANGED')
    return value


def input_locators(plan_path,quota_path,prepared_path=None,accounting_path=None):
    """Login metadata only. Never open/hash task/packet/Parquet/LMDB bodies."""
    C.need(plan_path.stat().st_size<=1<<20,'SMALL_ROOT_PLAN_HEADER_ONLY');plan_ref=ref(plan_path);value=read(plan_ref)
    C.need(value['schema']=='ROOT_PM7_INDEPENDENT_CACHE32_PLAN_V1','EXACT_METADATA_PLAN_SCHEMA')
    source=sources()+[plan_ref,value['mapping_review'],value['hof_authority_review']];data=[]
    data.extend(value[k] for k in ('formal_source','per_molecule','golden_prepared','golden_profile_receipt','golden_manifest'))
    mapping=read(value['mapping_review']);source.extend(mapping[k] for k in ('formal_source_receipt','prior_cpu_source_validation','same_storage_mapping','quota_provider_review'))
    quota_ref=ref(quota_path);reuse,Q,quota_refs=R.quota_reuse(quota_ref,F.sources());source.extend(quota_refs)
    hof=read(value['hof_authority_review'])
    if value['hof_mode']=='CANONICAL_VERIFIED':
        source.append(hof['projection_receipt_reference']);data.append(hof['latest_owner_reference'])
        projection=read(hof['projection_receipt_reference']);data.extend(projection[k] for k in ('catalog','verification','source_files'))
    if prepared_path is not None:
        C.need(prepared_path.name=='prepared.json' and prepared_path.stat().st_size<=1<<20,'SMALL_ACTUAL_PREPARED_HEADER_ONLY')
        prepared_ref=ref(prepared_path);prepared=read(prepared_ref);data.extend([prepared_ref,prepared['source_authority_reference']])
        data.extend(r['task_reference'] for r in prepared['tasks']);data.extend(r['reference'] for r in prepared['golden_packet_references'])
    if accounting_path is not None:
        C.need(accounting_path.stat().st_size<=1<<20,'SMALL_ACCOUNTING_METADATA_ONLY')
        account_ref=ref(accounting_path);account=read(account_ref);source.extend([account_ref,account['raw_sacct_reference']])
    def unique(rows):
        result={}
        for row in rows:
            reference={k:row[k] for k in ('path','bytes','sha256')};path=reference['path']
            C.need(path not in result or result[path]==reference,'CONFLICTING_METADATA_LOCATOR_PINS');result[path]=reference
        return result
    smap=unique(source);dmap=unique(data)
    C.need(not(set(smap)&set(dmap)),'SOURCE_AND_SCIENTIFIC_DATA_REFS_MUST_BE_DISJOINT')
    return {'schema':'PM7_CACHE32_INPUT_LOCATORS_ONLY_V1','source_references':list(smap.values()),'data_references':list(dmap.values()),
        'scientific_bodies_opened_or_hashed_on_login':False,'native_LMDB_authority':'canonical pointer path/real_index/per-record payload SHA; no invented whole-LMDB hash',
        'full_execution_authorized':False}


if __name__=='__main__':
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.shared import on_login
    on_login()
    p=argparse.ArgumentParser(description='Small plan/header locators only; no cache/science execution')
    for name in ('plan','quota-reuse-review','prepared','prepare-accounting'):p.add_argument('--'+name,type=pathlib.Path,required=name in {'plan','quota-reuse-review'})
    args=p.parse_args();print(json.dumps(input_locators(args.plan,args.quota_reuse_review,args.prepared,args.prepare_accounting),sort_keys=True))
