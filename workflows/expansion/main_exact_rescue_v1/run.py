"""Main UID1278 exact tail-FP rescue; explicit local build and closed nine-column scores."""
import argparse
import hashlib
import json
import multiprocessing as mp
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from . import common as C,workers
from .resource import Guard


def preflight(plan,transport,packed,builds,out):
    from ..exact_nn_inverted_cpp_v1 import benchmark as oracle_checks,backend
    from ..exact_nn_popcount_cpp_v1 import backend as old_backend
    env=os.environ.copy();env.update(EXACT_INVERTED_BUILD_MANIFEST=builds['new']['path'],EXACT_POPCOUNT_BUILD_MANIFEST=builds['old']['path'])
    entry=C.verify(plan['entry_reference'])
    with(out/'native_tests.stdout').open('xb')as stdout,(out/'native_tests.stderr').open('xb')as stderr:
        completed=subprocess.run([sys.executable,'-I','-B',str(entry),'workflows.expansion.exact_nn_inverted_cpp_v1.test_native','-v'],
            env=env,stdout=stdout,stderr=stderr,check=False)
    test_log=(out/'native_tests.stderr').read_text()
    C.need(completed.returncode==0 and 'Ran 10 tests'in test_log and test_log.rstrip().endswith('OK'),
        'All10 native tests must pass without skipped tests; retain failure logs')
    inputs=dict(fingerprints=transport.resolve(packed['fingerprints']),queries=transport.resolve(plan['test_queries_reference']),
                historical206=transport.resolve(plan['historical206_reference']))
    queries,history,stamp,_=oracle_checks.load_inputs(dict(inputs=inputs,ordered_query_identity_sha256=oracle_checks.IDENTITY_SHA))
    cap=plan['preflight_rss_cap_bytes'];old=new=None
    try:
        old=old_backend.load_reference(inputs['fingerprints']['path'],stamp,C.N,cap,build_manifest_reference=builds['old'])
        new=backend.load_reference(inputs['fingerprints']['path'],stamp,C.N,cap,build_manifest_reference=builds['new'])
        for row in queries:
            raw=bytes.fromhex(row['ecfp4_2048_hex']);expected=history[row['query_ordinal']]['native']
            oracle_checks.exact(old.nearest(raw),expected);oracle_checks.exact(new.nearest(raw),expected)
        return dict(native_test_suite='exact_nn_inverted_cpp_v1.test_native',native_tests=10,queries=64,
            all8_fields_and_F64_equal_local_old_and_historical206=True,full_reference_records_per_backend=C.N,
            inputs=inputs,ordered_query_identity_sha256=oracle_checks.IDENTITY_SHA,
            native_test_stdout_reference=C.reference(out/'native_tests.stdout'),native_test_stderr_reference=C.reference(out/'native_tests.stderr'),
            no_old_Node20_admit_or_benchmark_relabel=True)
    finally:
        if old is not None:old.close()
        if new is not None:new.close()


def query_batches(parts,transport,plan,guard,counts):
    import pyarrow.parquet as pq
    last={};batch=[]
    for part in parts:
        local=transport.resolve(part);path=C.verify(local);before=C.frame(path);file=pq.ParquetFile(path)
        C.need(file.metadata.num_rows==part['rows']and file.schema_arrow.names==['ecfp4_2048_hex']
            and str(file.schema_arrow.field('ecfp4_2048_hex').type)=='string','Original FP-only string Parquet/footer')
        bucket=part['physical_fp_bucket'];n=0
        for block in file.iter_batches(batch_size=8192,columns=['ecfp4_2048_hex']):
            for text in block.column(0).to_pylist():
                C.need(isinstance(text,str)and len(text)==512 and all(c in '0123456789abcdef'for c in text)
                    and text[0]==bucket and hashlib.md5(text.encode('ascii')).hexdigest()[0]in C.PREFIXES,
                    'Every exact canonical FP stays in original physical/MD5 tail domain')
                C.need(bucket not in last or last[bucket]<text,'Each physical bucket strictly sorted/distinct across every part')
                last[bucket]=text;batch.append(text);n+=1;counts[bucket]+=1
                if len(batch)>=plan['query_batch']:yield batch;batch=[];guard.check()
        C.need(n==part['rows']and C.frame(path)==before,'Whole unchanged input part EOF')
    if batch:yield batch


def execute(plan_path):
    from ..exact_nn_inverted_cpp_v1 import build as new_build
    from ..exact_nn_popcount_cpp_v1 import build as old_build
    from ..exact_nn_cached_v1 import engine
    import pyarrow as pa
    import pyarrow.parquet as pq
    plan_ref=C.reference(plan_path);plan=C.body(plan_ref);node=socket.gethostname().split('.')[0]
    C.need(plan['schema']=='MAIN_EXACT_FP_RESCUE_PLAN_V1'and os.getuid()==1278 and node==plan['expected_node'] and node in ('compute-0-16','compute-0-21')
        and sys.flags.isolated and sys.flags.dont_write_bytecode and os.environ.get('SLURM_JOB_ID')
        and int(os.environ.get('SLURM_CPUS_PER_TASK','0'))>=plan['workers']
        and not any(os.environ.get(k)for k in ('SLURM_JOB_GPUS','SLURM_STEP_GPUS')),'Actual Main21 CPU-only isolated allocation')
    C.need(type(plan['workers'])is int and 16<=plan['workers']<=len(os.sched_getaffinity(0))
        and type(plan['query_batch'])is int and 1<=plan['query_batch']<=4096,'Bounded actual allocated workers/query batch')
    C.need(plan['workers']*plan['worker_rss_cap_bytes']+plan['parent_rss_cap_bytes']<=plan['software_rss_budget_bytes'],
           'All worker caches/parent fit actual software allowance')
    sources=[C.reference(p)for p in Path(__file__).parent.glob('*.py')]
    sources+=[C.reference(Path(m.__file__).parent/name)for m in(new_build,old_build)for name in m.SOURCES]
    from ..exact_nn_inverted_cpp_v1 import benchmark
    sources+=[C.reference(engine.__file__),C.reference(benchmark.__file__),
        C.reference(Path(new_build.__file__).parent/'test_native.py'),plan['entry_reference']]
    C.need(all(r in plan['code_references']for r in sources),'Every actual Main adapter/Core5/oracle/entry source pinned')
    out=Path(plan['output_directory']);C.need(out.is_absolute()and out.is_relative_to(plan['scratch_root'])and plan['scratch_root']in ('/tmp/zixiao_pubchem_rescue_20261104','/dev/shm/zixiao_pubchem_rescue_20261104')and not out.exists()
        and not any(p.is_symlink()for p in(out,*out.parents)),'Fresh own Main node-local scratch, never Node20 path assumption')
    out.mkdir(mode=0o700,parents=True);stop=mp.get_context('spawn').Event();guard=Guard(plan,stop);started=time.monotonic()
    try:
        transport=C.Transport(plan['transport_reference'],C.ALPHA,C.MAIN,1278)
        exported=C.body(transport.resolve(plan['origin_export_manifest_reference']))
        C.native_closed(exported['actual'],transport.resolve(plan['origin_export_native_sacct_reference']),1264,parent_required=False)
        C.need(exported['reference_manifest_reference']==plan['reference_manifest_reference'], 'Same original196 origin reference')
        packed=C.body(transport.resolve(plan['reference_manifest_reference']))
        C.need(packed['schema']=='expansion_exact_ecfp4_reference_v1'and packed['status']=='COMPLETE'
            and packed['molecules']==C.N and packed['fingerprint_recipe']==engine.RECIPE and packed['targets_present']is False,
            'All original1196122 reference ordinals/recipe, never a sampled reference')
        parts=C.exported_parts(exported,transport);fp=transport.resolve(packed['fingerprints']);keys_ref=transport.resolve(packed['keys'])
        C.need(fp['bytes']==C.N*256 and keys_ref['bytes']==C.N*28,'Complete reference byte widths')
        keys=C.verify(keys_ref).read_bytes()
        builds=dict(new=new_build.build(Path(plan['compiler']),out/'build_new'),old=old_build.build(Path(plan['compiler']),out/'build_old'))
        pre=preflight(plan,transport,packed,builds,out);C.write_new(out/'preflight.json',pre);guard.check()
        counts={b:0 for b in '0123456789abcdef'};written={b:0 for b in counts};buffers={b:[]for b in counts};outputs=[];ready=[]
        journal_path=out/'closed_scores.jsonl'
        with journal_path.open('xb')as journal,(out/'workers.jsonl').open('x')as metrics:
            def loaded(value):
                C.need(value['reference_records_loaded']==C.N,'No partial worker reference')
                ready.append(value);metrics.write(json.dumps(dict(event='READY',**value))+'\n');metrics.flush()
            def flush(bucket):
                values=buffers[bucket]
                if not values:return
                folder=out/'scores'/bucket;folder.mkdir(parents=True,exist_ok=True)
                path=folder/('part_%06d.parquet'%len(outputs));pq.write_table(pa.Table.from_pylist(values),path,compression='zstd')
                with path.open('rb')as stream:os.fsync(stream.fileno())
                ref=dict(C.reference(path),rows=len(values),fp_bucket=bucket);outputs.append(ref)
                journal.write(json.dumps(ref,sort_keys=True).encode()+b'\n');journal.flush();os.fsync(journal.fileno())
                written[bucket]+=len(values);buffers[bucket]=[];guard.check()
            batches=query_batches(parts,transport,plan,guard,counts)
            for result in workers.exact_batches(C.verify(fp),builds['new'],batches,plan,stop,loaded):
                for text,value in result.pop('results'):
                    index=value['reference_ordinal'];key=keys[index*28:index*28+27].decode('ascii')
                    row=dict(ecfp4_2048_hex=text,nearest_v1_key=key,nearest_v1_tanimoto=value.pop('score'),**value)
                    buffers[text[0]].append(row)
                    if len(buffers[text[0]])>=4096:flush(text[0])
                metrics.write(json.dumps(result)+'\n');metrics.flush();guard.check()
            for bucket in buffers:flush(bucket)
            journal.flush();os.fsync(journal.fileno());metrics.flush();os.fsync(metrics.fileno())
        C.need(counts==written==exported['per_bucket_counts']and sum(written.values())==exported['distinct_fingerprints']
            and len(ready)==plan['workers']and len({v['pid']for v in ready})==plan['workers'], 'Every exported distinct FP and all full workers exactly covered')
        transport.finish();guard.check()
        actual=dict(endpoint=C.MAIN,uid=1278,node=node,job_id=os.environ['SLURM_JOB_ID'],python=sys.executable,
                    version=sys.version,allocated_CPUs=int(os.environ['SLURM_CPUS_PER_TASK']),boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip())
        result=C.write_new(out/'manifest.json',dict(schema='MAIN_EXACT_FP_RESCUE_SCORES_V1',status='COMPLETE',actual=actual,
            origin_export_manifest_reference=plan['origin_export_manifest_reference'],origin_export_native_sacct_reference=plan['origin_export_native_sacct_reference'],transport_reference=plan['transport_reference'],
            source_filter_reference=exported['source_filter_reference'],reference_manifest_reference=plan['reference_manifest_reference'],
            md5_hex_text_prefixes=C.PREFIXES,per_bucket_counts=written,distinct_fingerprints=sum(written.values()),
            parts_catalog_reference=dict(C.reference(journal_path),rows=len(outputs)),part_count=len(outputs),closed_score_journal_reference=C.reference(journal_path),builds=builds,preflight_reference=C.reference(out/'preflight.json'),
            reference_fingerprints_origin=packed['fingerprints'],reference_keys_origin=packed['keys'],local_fingerprints=fp,local_keys=keys_ref,
            worker_ready=ready,resource_observation=guard.receipt(),resource_plan=plan_ref,source_references=sources,
            wall_seconds=time.monotonic()-started,reference_molecules=C.N,nearest_similarity_exact=True,
            full_pool_release_claimed=False,Alpha_UID_or_execution_claimed=False))
        guard.close();return result
    except BaseException:
        stop.set();raise
    finally:
        guard.done.set();guard.thread.join()


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',required=True,type=Path)
    execute(p.parse_args().plan)


if __name__=='__main__':main()