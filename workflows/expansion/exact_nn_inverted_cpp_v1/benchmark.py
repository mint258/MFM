"""Isolated full-Common/prefix64 paired benchmark; no production adoption."""
import argparse
import hashlib
import io
import json
import multiprocessing as mp
import os
from pathlib import Path
import socket
import stat
import struct
import subprocess
import sys
import time
import traceback

N=1196122
CAP=3<<30
FIELDS={'score','reference_ordinal','score_numerator','score_denominator','evaluated_references',
        'strictly_bound_pruned_references','reference_molecules','searched_popcount_groups'}
IDENTITY_SHA='f61f6a5f8f5effece3dfa24dc6d48172d77e072e165e5652103d2b68204e4854'
TEST_SCRIPT='''import importlib, json, pathlib, sys, unittest
sys.path.insert(0, sys.argv[1])
module=importlib.import_module('workflows.expansion.exact_nn_inverted_cpp_v1.test_native')
suite=unittest.defaultTestLoader.loadTestsFromModule(module)
result=unittest.TextTestRunner(verbosity=2).run(suite)
value=dict(tests=result.testsRun,errors=len(result.errors),failures=len(result.failures),skips=len(result.skipped),passed=result.wasSuccessful())
pathlib.Path(sys.argv[2]).write_text(json.dumps(value,sort_keys=True)+'\\n')
sys.exit(0 if result.testsRun==10 and result.wasSuccessful() and not result.skipped else 1)
'''


def need(value,message):
    if not value:raise ValueError(message)


def frame(s):return(s.st_dev,s.st_ino,s.st_uid,s.st_mode,s.st_size,s.st_mtime_ns,s.st_ctime_ns)


def reference(path):
    path=Path(path).resolve(strict=True);before=path.lstat()
    need(stat.S_ISREG(before.st_mode)and before.st_uid==1278,'Own actual Main regular input/source')
    digest=hashlib.sha256()
    with path.open('rb')as stream:
        need(frame(os.fstat(stream.fileno()))==frame(before),'Same input FD')
        for block in iter(lambda:stream.read(8<<20),b''):digest.update(block)
        after=os.fstat(stream.fileno())
    need(frame(before)==frame(after)==frame(path.lstat()),'Input changed during full SHA')
    return dict(path=str(path),bytes=before.st_size,sha256=digest.hexdigest())


def verify(ref):
    need(reference(ref['path'])=={key:ref[key]for key in('path','bytes','sha256')},'Actual whole input SHA/bytes differs')
    return Path(ref['path'])


def write(path,value):
    with Path(path).open('x',encoding='utf-8')as stream:
        json.dump(value,stream,sort_keys=True,separators=(',',':'),allow_nan=False);stream.write('\n')


def available():
    fields={line.split(':',1)[0]:line.split(':',1)[1].strip()for line in Path('/proc/meminfo').read_text().splitlines()}
    return int(fields['MemAvailable'].split()[0])*1024


def rss(pid=None):
    path=Path('/proc')/str(pid or os.getpid())/'status'
    try:
        fields={line.split(':',1)[0]:line.split(':',1)[1].strip()for line in path.read_text().splitlines()if ':'in line}
        return dict(current_bytes=int(fields.get('VmRSS','0 kB').split()[0])*1024,
                    high_water_bytes=int(fields.get('VmHWM','0 kB').split()[0])*1024)
    except FileNotFoundError:return None


def admit():
    need(sys.platform.startswith('linux')and sys.flags.isolated and sys.flags.dont_write_bytecode,
         'Actual Linux Python -I -B required')
    need(os.getuid()==1278 and socket.gethostname().split('.')[0]=='compute-0-20'
         and os.environ.get('SLURM_JOB_ID')and int(os.environ.get('SLURM_CPUS_PER_TASK','0'))==16
         and len(os.sched_getaffinity(0))>=16,'Actual Main UID1278/compute-0-20/Slurm16CPU allocation')
    need(not any(os.environ.get(key)for key in('SLURM_JOB_GPUS','SLURM_STEP_GPUS')),'No GPU allocation/computation')
    return dict(uid=os.getuid(),node=socket.gethostname(),job_id=os.environ['SLURM_JOB_ID'],
                allocated_CPUs=16,affinity=sorted(os.sched_getaffinity(0)),python=sys.executable,version=sys.version)


def exact(value,expected):
    need(set(value)==set(expected)==FIELDS and value==expected
         and struct.pack('<d',value['score'])==struct.pack('<d',expected['score']),
         'All eight original fields and binary64 score must match')


def load_inputs(config):
    from ..exact_nn_cached_v1 import engine
    refs=config['inputs'];path=verify(refs['fingerprints'])
    need(refs['fingerprints']['bytes']==N*256,'Entire1196122-reference fingerprint file, no subset')
    query_path=verify(refs['queries']);history_path=verify(refs['historical206'])
    need(refs['queries']['bytes']<=1<<20 and refs['historical206']['bytes']<=2<<20,'Bounded exact64 query/history metadata')
    raw=query_path.read_bytes();need(raw.endswith(b'\n')and hashlib.sha256(raw).hexdigest()==refs['queries']['sha256'],'Closed exact query JSONL')
    queries=[json.loads(line)for line in raw.splitlines()]
    need(len(queries)==64 and [row['query_ordinal']for row in queries]==list(range(64)),'Exact original ordered prefix64')
    digest=hashlib.sha256()
    for i,row in enumerate(queries):
        text=row['ecfp4_2048_hex'];need(len(text)==512 and all(c in'0123456789abcdef'for c in text),'Original2048-bit lowercase hex')
        digest.update(json.dumps([i,row['cid'],row['full_key'],bytes.fromhex(text).hex()],separators=(',',':')).encode()+b'\n')
    need(digest.hexdigest()==config['ordered_query_identity_sha256']==IDENTITY_SHA,'Exact original206 ordered identity/FP membership')
    historical_raw=history_path.read_bytes()
    need(hashlib.sha256(historical_raw).hexdigest()==refs['historical206']['sha256'],'Same freshly read historical206 metadata bytes')
    historical=json.loads(historical_raw);need(historical['schema']=='ALPHA_FULL_COMMON_POPCOUNT_PAIRED64_MEASUREMENTS_V1','Original206 paired native measurements')
    rows=historical['paired_queries'];need(len(rows)==64 and {r['query_ordinal']for r in rows}==set(range(64)),'Every historical206 query once')
    history={row['query_ordinal']:row for row in rows}
    for row in queries:
        old=history[row['query_ordinal']];raw=bytes.fromhex(row['ecfp4_2048_hex'])
        need(hashlib.sha256(raw).hexdigest()==old['fingerprint_sha256'],'Original206 FP identity')
        exact(old['native'],old['original'])
        need(struct.pack('<d',old['native']['score']).hex()==old['score_bits'],'Original206 native F64 score bits')
    return queries,history,engine.file_frame(path),frame(path.stat())


def call(method,raw):
    wall=time.perf_counter_ns();cpu=time.process_time_ns();value=method(raw)
    return value,dict(wall_nanoseconds=time.perf_counter_ns()-wall,process_CPU_nanoseconds=time.process_time_ns()-cpu)


def worker(slot,config,builds,queries,history,expected_frame,native_frame,out,barrier,stop):
    path=Path(out);old=new=None
    try:
        actual=admit()
        from ..exact_nn_cached_v1 import engine
        from ..exact_nn_popcount_cpp_v1 import backend as previous
        from . import backend as inverted
        baseline=rss();loads={};objects={}
        order=('old','new')if slot%2==0 else('new','old')
        for name in order:
            need(not stop.is_set(),'Peer/resource failure before reference load')
            module=previous if name=='old'else inverted
            began=time.perf_counter_ns();cpu=time.process_time_ns()
            objects[name]=module.load_reference(config['inputs']['fingerprints']['path'],expected_frame,N,CAP,
                build_manifest_reference=builds[name])
            loads[name]=dict(wall_nanoseconds=time.perf_counter_ns()-began,process_CPU_nanoseconds=time.process_time_ns()-cpu,
                rss=rss(),reference_records_loaded=objects[name].reference_records_loaded,
                storage_statistics=objects[name].native_statistics)
            engine.enforce_rss(CAP)
        old=objects['old'];new=objects['new']
        write(path/('worker_%02d_load.json'%slot),dict(slot=slot,pid=os.getpid(),actual=actual,
            load_order=order,baseline_rss=baseline,loads=loads,rss_after_both=rss(),all1196122_reference_records_loaded_per_backend=True))
        barrier.wait()
        comparisons=0;profiled=0
        with(path/('worker_%02d_queries.jsonl'%slot)).open('x',encoding='utf-8')as stream:
            for row in queries[slot::16]:
                index=row['query_ordinal'];raw=bytes.fromhex(row['ecfp4_2048_hex']);expected=history[index]['native']
                for repeat in range(config['repeats']):
                    need(not stop.is_set(),'Peer/resource failure before query')
                    order=('old','new')if(index+repeat)%2==0 else('new','old')
                    results={};timings={}
                    for name in order:
                        result,timing=call(old.nearest if name=='old'else new.nearest,raw)
                        results[name]=result;timings[name]=timing
                    exact(results['old'],expected);exact(results['new'],expected);exact(results['new'],results['old'])
                    engine.enforce_rss(CAP);comparisons+=1
                    value=dict(slot=slot,pid=os.getpid(),query_ordinal=index,repeat=repeat,execution_order=order,
                        cid=row['cid'],full_key=row['full_key'],fingerprint_sha256=hashlib.sha256(raw).hexdigest(),
                        results=results,timing=timings,score_bits=struct.pack('<d',results['new']['score']).hex(),rss=rss(),
                        all8_fields_and_F64_equal_old206_and_paired_old_backend=True)
                    stream.write(json.dumps(value,sort_keys=True,separators=(',',':'))+'\n');stream.flush()
                # One separately timed profile call per query, outside paired
                # performance measurements; all posting work is explicitly kept.
                (result,work),timing=call(new.nearest_with_work,raw);exact(result,expected);profiled+=1
                write(path/('worker_%02d_query_%02d_postings.json'%(slot,index)),dict(query_ordinal=index,work=work,
                    profiling_call_timing=timing,result=result,extra_profile_call_excluded_from_paired_timings=True))
        need(frame(Path(config['inputs']['fingerprints']['path']).stat())==native_frame,'Reference changed during paired benchmark')
        write(path/('worker_%02d_complete.json'%slot),dict(slot=slot,pid=os.getpid(),comparisons=comparisons,
            separate_profile_calls=profiled,rss=rss(),status='COMPLETE_ALL_ASSIGNED_QUERIES_MATCH'))
    except BaseException:
        stop.set()
        try:barrier.abort()
        except BaseException:pass
        write(path/('worker_%02d_error.json'%slot),dict(slot=slot,pid=os.getpid(),traceback=traceback.format_exc(),partials_preserved=True))
        raise
    finally:
        if old is not None:old.close()
        if new is not None:new.close()


def run(config_path,output):
    actual=admit();config_path=Path(config_path);need(config_path.stat().st_size<=2<<20,'Small explicit benchmark config')
    config_ref=reference(config_path);config_raw=config_path.read_bytes()
    need(hashlib.sha256(config_raw).hexdigest()==config_ref['sha256'],'Same actual benchmark config bytes')
    config=json.loads(config_raw);need(config['schema']=='MAIN_FULL_COMMON_INVERTED_BENCHMARK_CONFIG_V1'
        and config['repeats']in(1,3)and config['compiler']=='/usr/bin/cc','Explicit paired benchmark/actual compiler/repeats1or3')
    need(Path(config['import_root']).is_absolute()and Path(config['import_root']).resolve()==Path(__file__).resolve().parents[3],
         'Actual full source import root, not an implicit/fake namespace')
    out=Path(output);need(out.is_absolute()and not out.exists(),'Fresh absolute benchmark output; keep previous attempts')
    out.mkdir(mode=0o700,parents=True);started=time.perf_counter_ns();cpu=time.process_time_ns()
    processes=[];stop=None;barrier=None
    try:
        need(available()>=80<<30,'Initial actual MemAvailable>=48GiB workers+8GiB parent+24GiB reserve')
        queries,history,expected_frame,native_frame=load_inputs(config)
        from . import build as new_build
        from ..exact_nn_popcount_cpp_v1 import build as old_build
        from ..exact_nn_cached_v1 import engine
        source_paths={Path(__file__),Path(__file__).with_name('README_benchmark.md'),Path(engine.__file__)}
        for module in(new_build,old_build):
            source_paths.update(Path(module.__file__).parent/name for name in module.SOURCES)
        source_paths.add(Path(__file__).with_name('test_native.py'))
        sources=[reference(path)for path in sorted(source_paths)]
        write(out/'inputs_and_sources.json',dict(config_reference=reference(config_path),actual=actual,inputs=config['inputs'],
            ordered_query_identity_sha256=IDENTITY_SHA,source_references=sources,source_commit_completeness_claimed=False))
        builds=dict(new=new_build.build(Path(config['compiler']),out/'build_new'),old=old_build.build(Path(config['compiler']),out/'build_old'))
        environment=os.environ.copy();environment.update(EXACT_INVERTED_BUILD_MANIFEST=builds['new']['path'],EXACT_POPCOUNT_BUILD_MANIFEST=builds['old']['path'])
        with(out/'native_tests.stdout').open('xb')as stdout,(out/'native_tests.stderr').open('xb')as stderr:
            tests=subprocess.run([sys.executable,'-I','-B','-c',TEST_SCRIPT,config['import_root'],str(out/'native_tests.json')],
                env=environment,stdout=stdout,stderr=stderr,check=False)
        need(tests.returncode==0,'Actual10 native/RDKit-oracle tests failed; logs preserved, no benchmark COMPLETE')
        test_result=json.loads((out/'native_tests.json').read_text())
        need(test_result==dict(tests=10,errors=0,failures=0,skips=0,passed=True),'Exactly10 actual native tests with no skip')
        need(available()>=80<<30,'Actual memory admission rechecked immediately before16 full-cache workers')
        context=mp.get_context('spawn');barrier=context.Barrier(16);stop=context.Event()
        for slot in range(16):
            process=context.Process(target=worker,args=(slot,config,builds,queries,history,expected_frame,native_frame,str(out),barrier,stop))
            process.start();processes.append(process)
        peak_tree=0;peak_parent=0;minimum_available=available();resource_failure=None
        while any(process.is_alive()for process in processes):
            parent=rss()['current_bytes'];values=[rss(process.pid)for process in processes]
            tree=parent+sum(value['current_bytes']for value in values if value is not None);free=available()
            peak_tree=max(peak_tree,tree);peak_parent=max(peak_parent,parent);minimum_available=min(minimum_available,free)
            if parent>8<<30 or tree>56<<30 or free<24<<30 or any(value and value['current_bytes']>CAP for value in values):
                resource_failure=dict(parent_rss=parent,tree_rss=tree,available=free);stop.set();barrier.abort()
            for process in processes:process.join(timeout=.05)
            time.sleep(.1)
        for process in processes:process.join()
        write(out/'worker_accounting.json',dict(workers=[dict(pid=p.pid,exitcode=p.exitcode)for p in processes],
            peak_observed_tree_RSS_bytes=peak_tree,peak_observed_parent_RSS_bytes=peak_parent,
            minimum_observed_MemAvailable_bytes=minimum_available,resource_failure=resource_failure))
        need(resource_failure is None and len(processes)==16 and len({p.pid for p in processes})==16
             and all(p.exitcode==0 for p in processes),'All16 actual private-cache workers completed within actual memory budgets')
        rows=[]
        for slot in range(16):
            complete=json.loads((out/('worker_%02d_complete.json'%slot)).read_text())
            need(complete['comparisons']==4*config['repeats']and complete['separate_profile_calls']==4,'Every assigned query/repeat/profile once')
            rows.extend(json.loads(line)for line in(out/('worker_%02d_queries.jsonl'%slot)).read_text().splitlines())
        need(len(rows)==64*config['repeats']and {(r['query_ordinal'],r['repeat'])for r in rows}
             =={(i,r)for i in range(64)for r in range(config['repeats'])},'Complete exact64 query/repeat membership')
        for row in rows:
            exact(row['results']['new'],history[row['query_ordinal']]['native']);exact(row['results']['old'],row['results']['new'])
        need([reference(path)for path in sorted(source_paths)]==sources,'Physical source changed during benchmark')
        need(frame(Path(config['inputs']['fingerprints']['path']).stat())==native_frame,'Full reference source frame changed')
        paired={name:dict(calls=len(rows),wall_nanoseconds=sum(r['timing'][name]['wall_nanoseconds']for r in rows),
            process_CPU_nanoseconds=sum(r['timing'][name]['process_CPU_nanoseconds']for r in rows))for name in('old','new')}
        artifacts=[reference(path)for path in sorted(out.glob('*'))if path.is_file()]
        result=dict(schema='MAIN_FULL_COMMON_INVERTED_PAIRED64_BENCHMARK_V1',status='COMPLETE',actual=actual,
            reference_molecules_per_backend_per_worker=N,workers=16,query_identities=64,repeats=config['repeats'],
            comparisons=64*config['repeats'],separate_new_profile_calls=64,builds=builds,native_tests=test_result,
            paired_call_totals=paired,whole_benchmark_wall_nanoseconds=time.perf_counter_ns()-started,
            parent_process_CPU_nanoseconds=time.process_time_ns()-cpu,
            inputs=config['inputs'],ordered_query_identity_sha256=IDENTITY_SHA,source_references=sources,artifacts=artifacts,
            historical206_all8_fields_and_F64_match=True,current_old_new_all8_fields_and_F64_match=True,
            prefix64_population_representativeness_claimed=False,full_pool_speed_or_ETA_claimed=False,
            QueryCache_used=False,production_API_or_adoption_changed=False,source_commit_completeness_claimed=False,
            old_and_new_load_order_alternates_by_worker=True,paired_call_order_alternates_by_query_and_repeat=True)
        write(out/'result.json',result);return result
    except BaseException:
        if stop is not None:stop.set()
        if barrier is not None:
            try:barrier.abort()
            except BaseException:pass
        for process in processes:process.join()
        write(out/'failure.json',dict(status='FAILED_NOT_COMPLETE',traceback=traceback.format_exc(),partial_logs_preserved=True))
        raise


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--config',required=True,type=Path);parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args();result=run(args.config,args.output);print(json.dumps(dict(status=result['status'],output=str(args.output))))


if __name__=='__main__':main()
