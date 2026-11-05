"""One native old/new full-augmented-reference check before the original coverage body."""
from concurrent.futures import ProcessPoolExecutor
import hashlib,json,multiprocessing,os,pathlib,resource,struct,time
from ..alpha_runtime_v1 import common as Q
from ..alpha_runtime_v1.guard import Guard
from ..exact_nn_cached_v1.engine import file_frame
from ..exact_nn_inverted_production_v1 import authority as fast_authority
from .general_workers import target_contract

def checked(value,n):
    Q.need(type(value['score'])is float and all(type(value[k])is int for k in ('reference_molecules','evaluated_references','strictly_bound_pruned_references','reference_ordinal','score_numerator','score_denominator')),'Native integer counters and binary64 scalar types')
    Q.need(value['reference_molecules']==n and value['evaluated_references']+value['strictly_bound_pruned_references']==n,'Every actual reference counted')
    Q.need(0<=value['reference_ordinal']<n and 0<=value['score_numerator']<=value['score_denominator']<=2048 and value['score_denominator']>0,'Original integer result domain')
    Q.need(struct.pack('<d',value['score'])==struct.pack('<d',value['score_numerator']/value['score_denominator']),'Exact original binary64 division')
    return value

def equal(old,new,n):
    checked(old,n);checked(new,n)
    Q.need(set(old)==set(new) and all(old[k]==new[k]for k in old if k!='score') and struct.pack('<d',old['score'])==struct.pack('<d',new['score']),'All native fields/firstordinal/counters/F64 must agree')

def query_cases(real,fetch,n,base_n):
    Q.need(len(real)==64 and n>base_n>1,'Actual prior64 plus full reference boundary cases')
    cases=[('original64_%02d'%i,raw)for i,raw in enumerate(real)]
    for index in (0,1,base_n-1,base_n,base_n+1,n-1):cases.append(('actual_reference_ordinal_'+str(index),fetch(index)))
    cases.extend((('zero',bytes(256)),('ones',bytes([255])*256),('alternating55',bytes([85])*256),('alternatingaa',bytes([170])*256)))
    cases.extend(('repeat_'+name,raw)for name,raw in cases[:6])
    Q.need(len(cases)==80 and all(isinstance(raw,bytes)and len(raw)==256 for _,raw in cases),'80 complete raw2048-bit cases')
    return cases

def _probe(kind,path,frame,n,cap,build,cases):
    if kind=='old':
        from ..exact_nn_popcount_cpp_v1 import backend
    elif kind=='fast':
        from ..exact_nn_inverted_cpp_v1 import backend
    else:raise ValueError('Explicit native implementation')
    start=time.perf_counter();cpu=time.process_time()
    reference=backend.load_reference(path,frame,n,cap,build_manifest_reference=build)
    Q.need(reference.reference_records_loaded==n,'Full private augmented reference, never a subset')
    rows=[]
    for name,raw in cases:
        value=checked(reference.nearest(raw),n)
        rows.append(dict(case=name,result=value))
    return dict(kind=kind,pid=os.getpid(),uid=os.getuid(),reference_records_loaded=reference.reference_records_loaded,implementation=reference.implementation,load_RSS_bytes=reference.load_rss_bytes,peak_RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,wall_seconds=time.perf_counter()-start,process_CPU_seconds=time.process_time()-cpu,rows=rows)

def after_equivalence(plan,proof,output):
    Q.need(plan['reference_role']=='after' and proof['request']['producer_plan_reference']==Q.reference(pathlib.Path(output).parent/'plan.json'),'Actual bound after coverage startup')
    packed=Q.load(Q.verify(plan['reference_manifest']))
    fast,_=fast_authority.adopted(plan['backend_adoption_reference'])
    Q.need(plan['comparison_backend_adoption_reference']==fast['previous_backend_adoption_reference'],'The comparator remains the original old206 implementation')
    old=Q.load(Q.verify(plan['comparison_backend_adoption_reference']))
    Q.need(old['reference_manifest_reference']==fast['reference_manifest_reference'],'Both native kernels share original full196 prefix')
    n=target_contract(packed,plan['reference_manifest'],'after',fast['reference_manifest_reference'])
    Q.need(n==3696122 and packed['added_molecules']==2500000,'Every added graph regardless of UFF outcome')
    alpha=Q.load(Q.verify(fast['alpha_result_reference']));query_ref=alpha['inputs']['queries']
    Q.need(query_ref['bytes']<=1<<20,'Bounded already-proven original query metadata')
    raw=Q.verify(query_ref).read_bytes();source=[json.loads(line)for line in raw.splitlines()]
    Q.need(len(source)==64 and [r['query_ordinal']for r in source]==list(range(64)),'Same native equivalence original ordered64')
    real=[bytes.fromhex(r['ecfp4_2048_hex'])for r in source]
    comparison_build=alpha['builds']['old']
    old=dict(old,build_manifest_reference=comparison_build)
    scope=pathlib.Path(plan['output_scope_root']);scope.mkdir(parents=True,exist_ok=True)
    guard=Guard(plan)
    try:
        path=Q.verify(packed['fingerprints']);keys=Q.verify(packed['keys']);frame=file_frame(path);key_frame=file_frame(keys)
        with path.open('rb')as stream:
            def fetch(index):
                stream.seek(index*256);return stream.read(256)
            cases=query_cases(real,fetch,n,1196122)
        results=[]
        context=multiprocessing.get_context('spawn')
        for kind,adoption in (('old',old),('fast',fast)):
            with ProcessPoolExecutor(max_workers=1,mp_context=context)as pool:
                result=pool.submit(_probe,kind,str(path),frame,n,4<<30,adoption['build_manifest_reference'],cases).result()
            guard.check();results.append(result)
        left,right=results
        Q.need(len(left['rows'])==len(right['rows'])==80,'Every original/boundary/repeated case present')
        with keys.open('rb')as stream:
            for one,two in zip(left['rows'],right['rows']):
                Q.need(one['case']==two['case'],'Identical ordered cases')
                equal(one['result'],two['result'],n)
                stream.seek(one['result']['reference_ordinal']*28);key=stream.read(28).decode('ascii').rstrip('\n')
                Q.need(len(key)==27,'Actual complete ordinal-key map')
                one['nearest_reference_key']=two['nearest_reference_key']=key
        Q.need(file_frame(path)==frame and file_frame(keys)==key_frame,'Packed reference and key map unchanged')
        Q.need(right['peak_RSS_bytes']+(256<<20)<=plan['worker_rss_cap_bytes'],'Measured full-reference native peak plus256MiB must fit each production worker')
        guard.sample();guard.check()
        return Q.write(output,dict(schema='AUGMENTED_FULL_REFERENCE_NATIVE_EQUIVALENCE_V1',status='PASS',actual_job_id=os.environ['SLURM_JOB_ID'],uid=os.getuid(),endpoint=Q.ENDPOINT,node=proof['node'],boot_id=proof['boot_id'],producer_plan_reference=proof['request']['producer_plan_reference'],full_augmented_reference=plan['reference_manifest'],reference_molecules=n,added_molecules=2500000,old_backend_adoption_reference=plan['comparison_backend_adoption_reference'],fast_before_native_equivalence_reference=plan['backend_adoption_reference'],comparison_build_reference=comparison_build,comparison_source_identity_proven_by_existing_native_descriptor=True,query_source_reference=query_ref,query_cases=80,original_real_queries=64,remaining_cases='6 actual reference prefix/suffix boundaries,4 bit edges,6 repeated real queries',all_native_fields_and_F64_equal=True,results=results,resource_observation=guard.receipt(),full_fixed1M_speed_or_ETA_claimed=False,original64_population_representativeness_claimed=False,QueryCache_used=False,new_Root_approval_required=False))
    finally:guard.close()
