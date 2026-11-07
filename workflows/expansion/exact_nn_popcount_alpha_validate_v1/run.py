"""Guarded benchmark-only build/small suites/fullCommon64 paired validation."""
import argparse
from concurrent.futures import ProcessPoolExecutor
import importlib
import json
import multiprocessing
import os
from pathlib import Path
import struct
import subprocess
import sys
from ..alpha_runtime_v1 import common as Q,profile
from ..alpha_runtime_v1.guard import Guard
from ..exact_nn_cached_v1 import engine as old,run as original_run
from ..exact_nn_cached_v1 import coverage,contracts
from ..exact_nn_popcount_cpp_v1 import build as native_build,backend as native
from ..portable_sources_v1.transport import bind_plan
from . import inputs,workers

MODULE='workflows.expansion.exact_nn_popcount_alpha_validate_v1.run'


def query_stamp(path):
    return Q.frame(path),Path(path).lstat().st_ctime_ns


def resources(plan):
    Q.need(plan['workers']==16 and plan['worker_rss_cap_bytes']==2<<30 and plan['parent_rss_cap_bytes']==8<<30
        and plan['software_rss_budget_bytes']==40<<30 and plan['minimum_node_available_bytes']==24<<30,
        'Exact reviewed16 workers*2GiB+8GiBparent=40GiB and24GiB node reserve')
    b=inputs.read(plan['reviewed_storage_budget_reference'])
    Q.need(b['schema']=='ROOT_ALPHA_ALL_FUTURE_STORAGE_BUDGET_V2'and b['reviewer']=='root'
        and b['endpoint']==Q.ENDPOINT and b['uid']==1264 and b['quota_root']==plan['quota_authority']['quota_root']=='/gfshome/alpha'
        and b['scope_total_caps_bytes']['reports']==plan['output_cap_bytes']==5000000000
        and b['other_future_reserved_bytes_for_each_scope']['reports']==plan['other_future_reserved_bytes']
        and b['minimum_free_after_all_future_bytes']==plan['minimum_free_bytes']==200000000000
        and plan['output_scope_root']=='/gfshome/alpha/pubchem_expansion_20261103/reports',
        'Actual Root reports aggregate budget, all-future reserve/floor, never old hardcoded future credit')


def admission(plan_path,proof_path):
    plan=Q.load(plan_path);proof=Q.load(proof_path);request=proof['request']
    Q.need(plan['schema']=='ALPHA_EXACT_POPCOUNT_VALIDATION_PLAN_V1'and plan['scope_key']==request['scope_key']=='popcount_cpp_validation_v1',
        'Independent benchmark plan, not a production engine entry')
    Q.need(all(r['bytes']<=2<<20 for r in plan['code_references']),'No scientific data disguised as source pins')
    actual=profile.admit(plan,minimum_workers=16);argv=plan['execution_argv']
    Q.need(proof['endpoint']==plan['endpoint']==Q.ENDPOINT and proof['uid']==os.getuid()==actual['uid']==1264
        and str(proof['job_id'])==actual['job_id']==os.environ.get('SLURM_JOB_ID')
        and proof['boot_id']==Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        and request['producer_plan_reference']==Q.reference(plan_path)and request['execution_argv']==argv
        and len(argv)==9 and argv[0]==sys.executable and argv[1:3]==['-I','-B']and argv[4]==MODULE
        and argv[5:]==sys.argv[1:]==['--plan',str(plan_path),'--startup-proof',str(proof_path)],
        'Actual Alpha profile/boot/job/exact plan and guarded module argv')
    paths=[*Path(__file__).parent.glob('*.py'),*Path(native.__file__).parent.glob('*.py'),
        Path(native.__file__).parent/'kernel.c',Path(argv[3])]
    refs=[Q.reference(p)for p in paths]
    Q.need(all(r in plan['code_references']and r in request['source_references']for r in refs),'Every actual harness/prototype/entry source pinned')
    resources(plan);memory=original_run.allocation_guard(plan)
    return plan,actual,memory,refs


def source_bindings(bound,plan,proof):
    result={}
    for name,origins in bound['original_source_references'].items():
        module=importlib.import_module('workflows.expansion.exact_nn_cached_v1.'+name.removesuffix('.py'))
        ref=Q.reference(module.__file__)
        Q.need((ref['bytes'],ref['sha256'])==(origins[0]['bytes'],origins[0]['sha256'])
            and ref in plan['code_references']and ref in proof['request']['source_references'],
            'Actual imported original code must match historical200 body: '+name)
        result[name]=dict(origin_references=origins,execution_reference=ref)
    return result


def queries(bound,plan,historical,receipt):
    bind_plan(plan)
    m=coverage.validate_reference(Q.verify(bound['reference_manifest_reference']),'before')
    Q.need(m['molecules']==inputs.N,'Entire accepted1196122 reference required')
    q=inputs.read(bound['baseline_receipt_reference'])
    expected_path=Path(q['projection']['path']);source_stamp=query_stamp(expected_path)
    source=contracts.baseline_query(q,actual_review_reference=bound['baseline_review_reference'],receipt_reference=bound['baseline_receipt_reference'])
    Q.need(source==expected_path and query_stamp(source)==source_stamp,'Full fixed1M source changed during initial body binding')
    selected=[(i,row,raw)for i,row,raw,size in original_run.rows(source,64,old.file_frame(source))]
    import pyarrow.parquet as pq
    import pyarrow.dataset as ds
    member=Q.verify(q['sample_membership'])
    Q.need(pq.ParquetFile(member).metadata.num_rows==1000000,'Full frozen membership Parquet1M required')
    rows=ds.dataset(str(member),format='parquet').to_table(columns=['sample_ordinal','cid','full_key'],filter=ds.field('sample_ordinal')<64).to_pylist()
    rows.sort(key=lambda x:x['sample_ordinal'])
    Q.need([(r['sample_ordinal'],r['cid'],r['full_key'])for r in rows]==[(i,row['cid'],row['full_key'])for i,row,raw in selected],
        'Same actual frozen64 membership identities and ordinals')
    digest=inputs.historical_queries(selected,historical,receipt)
    return m,selected,digest,source,source_stamp


def test_suite(module,out,entry,guard):
    target=out/(module.rsplit('.',1)[-1]+'_suite.json')
    cmd=[sys.executable,'-I','-B',entry,'workflows.expansion.exact_nn_popcount_alpha_validate_v1.suite','--module',module,'--output',str(target)]
    guard.check()
    with (target.with_suffix('.stdout')).open('xb')as stdout,(target.with_suffix('.stderr')).open('xb')as stderr:
        result=subprocess.run(cmd,stdout=stdout,stderr=stderr,check=False)
    guard.check();Q.need(result.returncode==0,'Actual native boundary suite failed; retain logs')
    data=Q.load(target);Q.need(data['success']and data['failures']==data['errors']==data['skips']==0,'No skipped/failed native suite accepted')
    return Q.reference(target)


def execute(plan_path,proof_path):
    plan,actual,memory,refs=admission(plan_path,proof_path)
    guard=Guard(plan);out=Path(plan['output_directory']);previous_tmp=os.environ.get('TMPDIR');previous_build=os.environ.get('EXACT_POPCOUNT_BUILD_MANIFEST')
    try:
        out.mkdir(parents=True,exist_ok=False);temporary=out/'temporary';temporary.mkdir();os.environ['TMPDIR']=str(temporary)
        bound=inputs.read(plan['inputs_reference']);historical,receipt=inputs.validate_bound(bound)
        bindings=source_bindings(bound,plan,Q.load(proof_path));Q.write(out/'actual_input_bindings.json',bound)
        old.enforce_rss(plan['parent_rss_cap_bytes']);guard.check()
        build_ref=native_build.build(Path('/usr/bin/gcc'),out/'build')
        old.enforce_rss(plan['parent_rss_cap_bytes']);guard.check()
        os.environ['EXACT_POPCOUNT_BUILD_MANIFEST']=build_ref['path']
        tests=[test_suite(name,out,plan['execution_argv'][3],guard)for name in (
            'workflows.expansion.exact_nn_popcount_cpp_v1.test_native','workflows.expansion.exact_nn_cached_v1.test_exact')]
        m,selected,digest,query_path,original_query_stamp=queries(bound,plan,historical,receipt)
        Q.write(out/'queries64.json',[dict(query_ordinal=i,query=row,fingerprint_sha256=historical['results'][i]['fingerprint_sha256'])for i,row,raw in selected])
        path=Path(m['fingerprints']['path']);frame=old.file_frame(path)
        ctx=multiprocessing.get_context('spawn');barrier=ctx.Barrier(16);counter=ctx.Value('i',0)
        worker_refs=[x['execution_reference']for x in bindings.values()]+[Q.reference(native.__file__)]+refs
        guard.check();ready=[];paired=[];pids=[]
        with ProcessPoolExecutor(max_workers=16,mp_context=ctx,initializer=workers.initialize,
                initargs=(str(path),frame,inputs.N,plan['worker_rss_cap_bytes'],build_ref,counter,barrier,worker_refs))as pool:
            warmups=[pool.submit(workers.ready)for i in range(16)]
            for future in warmups:ready.append(future.result());guard.check()
            Q.need(len({r['worker_pid']for r in ready})==16 and sorted(r['slot']for r in ready)==list(range(16))
                and all(r['reference_molecules']==r['original_decode_calls']==r['native_records_loaded']==inputs.N for r in ready),
                'All16 actual workers load both complete references, no subset/cache hit')
            Q.write(out/'worker_readiness.json',ready)
            batches=[pool.submit(workers.batch,[(i,raw)for i,row,raw in selected[start:start+4]])for start in range(0,64,4)]
            for future in batches:
                data=future.result();pids.append(data['worker_pid']);paired.extend(data['results']);guard.check()
        paired.sort(key=lambda r:r['query_ordinal'])
        Q.need(len(paired)==64 and [r['query_ordinal']for r in paired]==list(range(64))and len(set(pids))==16,'Every64 query once, exactly4 per actual worker')
        history={r['query_ordinal']:r for r in historical['results']}
        for row in paired:
            old_result=row['original'];old_fields=history[row['query_ordinal']]['result']
            Q.need(row['fingerprint_sha256']==history[row['query_ordinal']]['fingerprint_sha256']
                and {k:old_result[k]for k in old_fields}==old_fields
                and struct.pack('<d',old_result['score'])==struct.pack('<d',old_fields['score']),
                'Historical200 fields/F64/fingerprint bindings must all match current oracle')
        Q.need(query_stamp(query_path)==original_query_stamp,'Full fixed1M projection changed during benchmark')
        Q.verify(m['fingerprints']);Q.verify(m['keys'])
        for ref in refs+[r['execution_reference']for r in bindings.values()]:Q.verify(ref)
        old.enforce_rss(plan['parent_rss_cap_bytes']);guard.sample();guard.check()
        metrics=Q.write(out/'measurements.json',dict(schema='ALPHA_FULL_COMMON_POPCOUNT_PAIRED64_MEASUREMENTS_V1',workers=ready,paired_queries=paired,
            old_first_queries=32,native_first_queries=32,old_first_load_workers=8,native_first_load_workers=8,
            QueryCache_used=False,prefix64_population_representativeness_claimed=False,speedup_or_ETA_claimed=False))
        return Q.write(out/'receipt.json',dict(schema='ALPHA_EXACT_POPCOUNT_PRIVATE_COPY_VALIDATION_BENCHMARK_V1',
            status='BENCHMARK_PENDING_ROOT_ACTUAL_C0_REVIEW',inputs_reference=plan['inputs_reference'],build_manifest_reference=build_ref,
            native_small_suites=tests,original_source_bindings=bindings,reference_molecules=inputs.N,measured_queries=64,
            actual_parent=actual,source_references=refs,plan_reference=Q.reference(plan_path),startup_proof_reference=Q.reference(proof_path),
            query_identity_sha256=digest,all8_fields_and_F64_bits_equal=True,all_historical200_fields_and_F64_bits_equal=True,
            measurements_reference=metrics,runtime=guard.receipt(),startup_memory=memory,full_1M_NN_complete=False,
            production_backend_adopted=False,cache_reuse_or_training_authorized=False,full_population_speed_or_ETA_claimed=False))
    finally:
        if previous_tmp is None:os.environ.pop('TMPDIR',None)
        else:os.environ['TMPDIR']=previous_tmp
        if previous_build is None:os.environ.pop('EXACT_POPCOUNT_BUILD_MANIFEST',None)
        else:os.environ['EXACT_POPCOUNT_BUILD_MANIFEST']=previous_build
        guard.close()


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',required=True,type=Path);p.add_argument('--startup-proof',required=True,type=Path)
    a=p.parse_args();execute(a.plan,a.startup_proof)


if __name__=='__main__':main()
