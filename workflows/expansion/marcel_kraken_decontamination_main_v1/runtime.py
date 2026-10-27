"""Same-fd whole SHA -> bounded stream -> EOF/SHA/fstat; fresh central CPU guard."""
import hashlib,os,stat,sys
from pathlib import Path
from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2 import runtime as R
from workflows.expansion.marcel_drugs_keys_main_v1.runtime import Budget,Writer
from . import contract as C,projection as P
Q=C.Q


def frame(s):return (s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns,s.st_uid)


def rows(ref,check,progress=None):
    C.data_reference(ref);path=Path(ref['path'])
    Q.need(not any(p.is_symlink() for p in (path,*path.parents)),'NO_DATA_SYMLINK')
    initial=path.lstat();Q.need(stat.S_ISREG(initial.st_mode) and initial.st_uid==1278 and initial.st_size==ref['bytes'],'REAL_MAIN_OWNED_EXACT_SOURCE_BYTES')
    with path.open('rb') as stream:
        before=os.fstat(stream.fileno());Q.need(frame(initial)==frame(before),'SAME_OPENED_SOURCE_FD')
        h=hashlib.sha256();size=0
        for block in iter(lambda:stream.read(1<<20),b''):
            check();h.update(block);size+=len(block)
            if progress is not None:progress.update(phase='WHOLE_SOURCE_SHA_BEFORE_ROWS',source=path.name,source_bytes_hashed=size)
        Q.need(size==ref['bytes'] and h.hexdigest()==ref['sha256'] and frame(os.fstat(stream.fileno()))==frame(before),'WHOLE_SOURCE_SHA_AND_STABLE_FD')
        stream.seek(0);h=hashlib.sha256();size=0;count=0
        while True:
            check();raw=stream.readline((8<<20)+1)
            if not raw:break
            Q.need(len(raw)<=8<<20 and raw.endswith(b'\n'),'BOUNDED_COMPLETE_JSONL_LINE_NO_PREFIX_ACCEPTANCE')
            offset=size;h.update(raw);size+=len(raw);value=P.strict_json(raw);Q.need(type(value) is dict,'ONE_JSON_OBJECT_PER_LINE')
            yield value,{'source_reference':ref,'line_ordinal':count,'offset_bytes':offset,'line_bytes':len(raw),'line_sha256':hashlib.sha256(raw).hexdigest()}
            count+=1
        Q.need(size==ref['bytes'] and h.hexdigest()==ref['sha256'] and stream.tell()==ref['bytes']
            and frame(os.fstat(stream.fileno()))==frame(before)==frame(path.lstat()),'EXACT_SECOND_EOF_SHA_AND_UNCHANGED_SOURCE_FRAME')


def admit(args,plan,parents):
    Q.need(plan['schema']=='MARCEL_KRAKEN_DECONTAMINATION_PLAN_V1' and plan['scope_parameters']==C.PARAMETERS
        and plan['output_cap_bytes']==C.CAP and type(plan['wall_seconds']) is int and 600<=plan['wall_seconds']<=1800
        and plan['wall_seconds']%60==0,'EXACT_FINITE_ADAPTER_SCOPE')
    argv=[Q.PY,'-B','-m',C.MODULE,'--plan',str(args.plan),'--startup-proof',str(args.startup_proof)]
    proof=R.require_startup(args.startup_proof,expected_scope_key=C.KEY,expected_scope_parameters=C.PARAMETERS,expected_execution_argv=argv,
        expected_source=C.HERE/'run.py',expected_kind='analysis',required_references=[Q.pin(args.plan),*parents,plan['cost_decision_reference']])
    req=proof['request'];authority=C.meta(req['queue_authority_reference'])
    Q.need(req['node'] in {'compute-0-'+str(n) for n in authority['allowed_nodes']['analysis']} and proof['uid']==1278
        and req['cpus']==16 and req['kind']=='analysis' and req['pilot'] is False and req['memory_policy']=='SLURM_DEFAULT_UNSPECIFIED'
        and req['wall_seconds']==plan['wall_seconds'] and req['estimated_peak_output_bytes']==req['stage_output_cap_bytes']==C.CAP
        and req['data_references']==plan['data_references'] and not req.get('deferred_authority_references')
        and proof['account_free_bytes']-C.CAP>=200000000000,'FRESH_MAIN_ANALYSIS16_NO_MEM_EXACT3DATA_512MIB_PLUS200GB')
    review=C.meta(req['scope']['review']);Q.need(req['scope']['mode']=='BOUNDED_METADATA_PREPARATION'
        and review['identity_only_all_native_variants_authorized'] is True and review['global_pool_release_authorized'] is False,'ROOT_EXACT_IDENTITY_PROJECTION_ONLY_REVIEW')
    cost=C.meta(plan['cost_decision_reference']);Q.need(cost['status']=='USER_AUTHORIZED' and cost['on_overrun']=='REPORT_AND_CONTINUE'
        and cost['scientific_quality_thresholds_unchanged'] is True,'ORIGINAL_COST_AND_QUALITY_AUTHORITY')
    for path in [*(C.HERE/n for n in C.FILES),*C.OLD]:Q.need(Q.pin(path) in req['source_references'],'EVERY_ADAPTER_AND_FROZEN_PRODUCER_SOURCE')
    for name,module in list(sys.modules.items()):
        path=getattr(module,'__file__',None)
        if name.startswith('workflows.expansion') and path and Path(path).suffix=='.py':Q.need(Q.pin(path) in req['source_references'],'ACTUAL_IMPORTED_EXPANSION_SOURCE:'+name)
    Q.need(Path(sys.modules['__main__'].__file__).absolute()==C.HERE/'run.py' and sys.argv==[str(C.HERE/'run.py'),*argv[4:]],'EXACT_NEW_PRIMARY_AND_FULL_ARGV')
    return proof
