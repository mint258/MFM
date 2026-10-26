"""Unregistered existing334 software-control16 replay; never production population."""
from __future__ import annotations
import argparse,concurrent.futures as futures,gzip,hashlib,json,multiprocessing as mp,os,time
from pathlib import Path
from . import bridge
from .contract import canonical,sha,need,read_small,ref,load,prep_metadata,startup,CONTROL_MODE

BARRIER=None
ENDPOINT=None


def initialize(deployment,barrier):
    global BARRIER,ENDPOINT
    BARRIER=barrier;ENDPOINT=deployment['endpoint_id']
    bridge.install_sources(deployment,initialize_science=True)


def one(item):
    envelope,expected=item;BARRIER.wait(timeout=120)
    task=bridge.bind_envelope(envelope,expected)
    frame=Path('/proc/self/stat').read_text()
    identity={'pid':os.getpid(),'uid':os.getuid(),'job_id':os.environ['SLURM_JOB_ID'],
        'endpoint_id':ENDPOINT,'start_ticks':int(frame[frame.rfind(')')+2:].split()[19])}
    result=bridge.STATE['runner'].run_one(task)
    return result,identity,bridge.scientific_sha(result),bridge.STATE['actual_versions']


def envelopes(locator,expected,max_bytes):
    path=Path(locator['path']);need(path.is_absolute() and not any(p.is_symlink() for p in (path,*path.parents)),
                                 'LITERAL_LOCAL_PORTABLE_INPUT_REQUIRED')
    rows={};digest=hashlib.sha256();total=0
    with path.open('rb') as stream:
        before=os.fstat(stream.fileno())
        need(before.st_uid==os.getuid() and before.st_size==locator['bytes']<=max_bytes,'BOUNDED_OWNED_INPUT_SIZE')
        while True:
            raw=stream.readline((64<<20)+1)
            if not raw:break
            need(len(raw)<=64<<20 and raw.endswith(b'\n'),'BOUNDED_COMPLETE_JSONL_LINE_REQUIRED')
            total+=len(raw);digest.update(raw);need(total<=max_bytes,'PORTABLE_INPUT_CAP')
            envelope=json.loads(raw);mid=envelope['task']['meta']['molecule_id']
            need(mid in expected and mid not in rows,'UNKNOWN_OR_DUPLICATE_PORTABLE_TASK')
            bridge.bind_envelope(envelope,expected[mid]);rows[mid]=envelope
        after=os.fstat(stream.fileno())
    bridge.STATE.pop('payloads',None)
    need((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)==(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns)
         and total==locator['bytes'] and digest.hexdigest()==locator['sha256'] and set(rows)==set(expected),
         'EXACT_MAIN_PREPARED_GOLDEN16_INPUT_CHANGED_OR_INCOMPLETE')
    return rows


def memory_available():
    rows={}
    for line in Path('/proc/meminfo').read_text().splitlines():
        fields=line.split()
        if fields[0] in ('MemAvailable:','MemTotal:'):rows[fields[0].rstrip(':')]=int(fields[1])*1024
    need(set(rows)=={'MemAvailable','MemTotal'} and 0<=rows['MemAvailable']<=rows['MemTotal'],'ACTUAL_MEMAVAILABLE_REQUIRED')
    return rows


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('deployment-map','startup-proof','output'):parser.add_argument('--'+name,type=Path,required=True)
    a=parser.parse_args();deployment=json.loads(read_small(a.deployment_map.absolute()))
    proof,recipe=startup(deployment,a.deployment_map,a.startup_proof,a.output)
    prep=load(deployment['main_preparation_target_locator']);expected=prep_metadata(prep)
    need(prep['endpoint_id']==deployment['endpoint_id'],'MAIN_QA_EXPORT_MUST_BE_FOR_THIS_SECONDARY_ENDPOINT')
    rows=envelopes(deployment['tasks_target_locator'],expected,deployment['max_input_bytes'])
    need(memory_available()['MemAvailable']>=deployment['soft_min_mem_available_bytes'],'SOFT_MEMAVAILABLE_STOP_NEW_DISPATCH')
    output=a.output.absolute();root=Path(deployment['target']['deployment_root'])
    need(root/'outputs' in output.parents and not output.exists(),'NEW_SECONDARY_OUTPUT_REQUIRED')
    spool=root/'attempt_spool';spool.mkdir(parents=True,exist_ok=True)
    need(not any(p.is_symlink() for p in (spool,*spool.parents)),'LITERAL_LOCAL_ATTEMPT_SPOOL_REQUIRED')
    token=spool/(sha(prep['slice_id'].encode())+'.json')
    with token.open('xb') as stream:
        stream.write(canonical({'slice_id':prep['slice_id'],'endpoint_id':deployment['endpoint_id'],
            'job_id':str(proof['job_id']),'mode':CONTROL_MODE,'molecule_ids':sorted(rows),
            'this_is_not_the_main_authoritative_once_ledger':True,'population_members_added':0}));stream.flush();os.fsync(stream.fileno())
    common,runner=bridge.install_sources(deployment,initialize_science=False)
    common.new_output_directory(output,recipe);(output/'reproduction').mkdir()
    executions=[];errors=[];samples=[];denied=False;started=time.monotonic()
    context=mp.get_context('spawn');barrier=context.Barrier(16)
    with futures.ProcessPoolExecutor(max_workers=16,mp_context=context,initializer=initialize,initargs=(deployment,barrier)) as pool:
        active={pool.submit(one,(rows[mid],expected[mid])):mid for mid in sorted(rows)}
        while active:
            try:
                sample=memory_available();sample['observed_monotonic']=time.monotonic()
                denied=denied or sample['MemAvailable']<deployment['soft_min_mem_available_bytes']
            except Exception as exc:
                denied=True;sample={'observed_monotonic':time.monotonic(),'metric_invalid':True,'error':repr(exc)[:1000]}
            samples.append(sample)
            done,_=futures.wait(active,timeout=.5,return_when=futures.FIRST_COMPLETED)
            for future in done:
                mid=active.pop(future)
                try:
                    result,identity,signature,versions=future.result()
                    need(result['summary']['molecule_id']==mid and identity['uid']==deployment['target']['uid'] and
                         identity['endpoint_id']==deployment['endpoint_id'] and str(identity['job_id'])==str(proof['job_id']),
                         'ACTUAL_SECONDARY_WORKER_SCOPE_IDENTITY_CHANGED')
                    package=runner.persist_result(output,mid,result,recipe['max_output_bytes'])
                    exact=signature==expected[mid]['scientific_sha256_excluding_elapsed_seconds']
                    executions.append({'molecule_id':mid,'task_sha256':expected[mid]['task_sha256'],'worker_identity':identity,
                        'packet_reference':package,'scientific_sha256_excluding_elapsed_seconds':signature,
                        'actual_versions':versions,'main_golden_exact_match':exact})
                    if not exact:errors.append({'molecule_id':mid,'error':'MAIN_SECONDARY_GOLDEN_SCIENCE_DRIFT'})
                except Exception as exc:errors.append({'molecule_id':mid,'error':repr(exc)[:2000]})
    complete=len(executions)==16 and len({(r['worker_identity']['pid'],r['worker_identity']['start_ticks']) for r in executions})==16 and not errors and not denied
    memory_path=output/'memory_evidence.json.gz';memory_raw=gzip.compress(canonical(samples),mtime=0)
    common.prewrite_guard(memory_path,len(memory_raw))
    with memory_path.open('xb') as stream:stream.write(memory_raw);stream.flush();os.fsync(stream.fileno())
    memory_reference={'path':str(memory_path),'bytes':len(memory_raw),'sha256':sha(memory_raw)}
    receipt={'schema':'SECONDARY_PORTABLE_UFF_CONTROL16_RECEIPT_V1','mode':CONTROL_MODE,
        'status':'CONTROL16_EXACT_SCIENCE_MATCH_REQUIRES_MAIN_SOFTWARE_ACCEPTANCE' if complete else 'CONTROL16_INCOMPLETE_OR_DRIFT_NO_AUTOMATIC_RETRY',
        'endpoint_id':deployment['endpoint_id'],'uid':os.getuid(),'job_id':str(proof['job_id']),'node':proof['node'],
        'deployment_map_reference':ref(a.deployment_map),'startup_proof_reference':ref(a.startup_proof),
        'main_preparation_reference':deployment['main_preparation_target_locator'],'attempt_token':ref(token),
        'executions':executions,'errors':errors,'soft_memavailable_denial':denied,'memory_evidence_reference':memory_reference,
        'actual_target_scientific_sources_verified_byte_identical':True,'original_pickle_bytes_reencoded_as_numbers':False,
        'actual_worker_count':len({r['worker_identity']['pid'] for r in executions}),'elapsed_seconds':time.monotonic()-started,
        'formal_generation_authorized':False,'main_unified_acceptance_granted':False,'automatic_retry':False,
        'original334_software_qa_controls_replayed':len(executions),'two_missing_replayed':False,'population_members_added':0,
        'current_main_recovery_2plus14_scope_changed':False,'main_lmdb_or_once_ledger_opened':False,'signals_sent':False,
        'torch_build_identical_to_main_claimed':False,
        'main_torch_version_provenance':deployment['main_torch_version_provenance'],
        'actual_cost':'PENDING_ROOT_SECONDARY_ENDPOINT_TERMINAL_SACCT_NOT_MAIN_JOB_ID'}
    common.write_json_new(output/'secondary_receipt.json',receipt)
    print(json.dumps({'status':receipt['status'],'endpoint_id':deployment['endpoint_id'],'closed':len(executions)}))
    return 0 if complete else 1


if __name__=='__main__':raise SystemExit(main())
