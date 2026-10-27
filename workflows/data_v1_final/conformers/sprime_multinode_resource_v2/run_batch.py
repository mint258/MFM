"""Exactly-once finite CPU wave: durable dispatch/start and child-owned packet IO."""
from __future__ import annotations
import argparse,concurrent.futures as cf,gzip,json,multiprocessing as mp,os,pathlib,sys,time,traceback
REPO=pathlib.Path(__file__).absolute().parents[4];sys.path.insert(0,str(REPO));sys.dont_write_bytecode=True
from workflows.data_v1_final.conformers.sprime_multinode_resource_v2 import contract as C,runtime_io as R

OPTIONS=('config','prepared','root-preflight','quota-reuse-review','output')
SCIENCE=None;SESSION=None;OUT=None;VALUE=None


def init_worker(config_reference,session,out):
    global SCIENCE,SESSION,OUT,VALUE
    proof=R.continuation(session,check_sources=True);VALUE=C.config(config_reference);OUT=pathlib.Path(out);R.OUT=OUT;R.VALUE=VALUE
    R.PROOF=proof;R.SESSION=session;SESSION=session;_,SCIENCE=R.load_science(VALUE)


def one(task,dispatch_reference):
    # Spawn initializer has loaded the exact recipe. This separate true worker
    # start is durable before any call to the unchanged process_task function.
    R.continuation(SESSION);dispatch=C.read(dispatch_reference);meta=task['meta'];key=meta['task_key']
    C.need(dispatch['task_sha256']==C.sha_value(task) and dispatch['task_key']==key,'ACTUAL_DISPATCH_TASK_BYTES_CHANGED')
    start={'schema':'SPRIME_ONCE_WORKER_STARTED_V3','dispatch_reference':dispatch_reference,'task_key':key,
        'task_sha256':C.sha_value(task),'molecule_id':meta['molecule_id'],'cohort':meta['cohort'],
        'seed':C.seed_for(meta['molecule_id'],meta['cohort']=='retry_once'),'job_id':SESSION['job_id'],
        'uid':os.getuid(),'node':R.socket.gethostname().split('.')[0],'pid':os.getpid(),'pid_start_ticks':R.proc_ticks(os.getpid()),
        'boot_id':SESSION['boot_id'],'observed_unix_seconds':time.time()}
    start_ref=R.write_json_new(OUT/'starts'/(key+'.json'),start)
    try:
        result=SCIENCE.process_task(task) # exact frozen scientific kernel, no wrapper science changes
        result['formal_start']=start
        C.need(result['summary']['molecule_id']==meta['molecule_id'] and result['summary']['seed']==start['seed'],
            'KERNEL_RESULT_MOLECULE_OR_SEED_CHANGED')
        raw=C.canonical(result);C.need(len(raw)<=VALUE['packet_uncompressed_limit_bytes'],'FULL_FAILED_OR_AUDIT_PACKET_TOO_LARGE')
        compressed=gzip.compress(raw,mtime=0);C.need(len(compressed)<=VALUE['packet_compressed_limit_bytes'],'COMPRESSED_PACKET_CAP_EXCEEDED')
        packet_ref=R.atomic_bytes(OUT/'packets'/(key+'.json.gz'),compressed,reservation_key=key)
        saved=R.read_packet(packet_ref,VALUE)
        C.need(saved==result,'PERSISTED_FULL_PACKET_READBACK_DIFFERS')
        return {'task_key':key,'molecule_id':meta['molecule_id'],'package_reference':dict(packet_ref,molecule_id=meta['molecule_id']),
            'start_reference':start_ref,'scientific_status':result['summary']['status']}
    except Exception as exc:
        error={'schema':'SPRIME_WORKER_NO_DURABLE_VALID_PACKET_V3','task_key':key,'molecule_id':meta['molecule_id'],
            'start_reference':start_ref,'error':repr(exc),'traceback':traceback.format_exc(),'science_result_observed':False,
            'scientific_status':None,'uncommitted_prefix_is_not_fabricated_as_packet':True}
        R.write_json_new(OUT/'errors'/(key+'.json'),error);raise


def validate_slot(plan,proof,out):
    return R.validate_slot(plan,proof,out)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in OPTIONS:p.add_argument('--'+name,type=pathlib.Path,required=True)
    args=p.parse_args();value,proof,session,config_ref=R.admit(__file__,args,'run',OPTIONS)
    prepared_ref=R.input_ref(args.root_preflight,args.prepared);prepared=C.read(prepared_ref)
    C.need(prepared['schema']==C.SCHEMAS['prepared'] and prepared['status']=='ORIGINAL_BATCH_INPUTS_READY_NOT_GENERATED'
        and prepared['config']==config_ref and prepared['kernel_sha256']==C.KERNEL_SHA,'EXACT_CLOSED_PREPARED_BATCH_REQUIRED')
    R.authorized(proof,[prepared['plan'],prepared['tasks']]);plan=C.read(prepared['plan'])
    C.need(plan['status']=='BOUNDED_WAVE_FROZEN_IMPORTS_CLOSED' and plan['config']==config_ref,'ACTUAL_FROZEN_WAVE_REQUIRED')
    R.authorized(proof,[plan['draft'],plan['root_review'],plan['pilot_imports']]);C.approve_wave(plan['draft'],C.read(plan['draft']),plan['root_review'],config_ref)
    slot,concurrency=validate_slot(plan,proof,args.output)
    C.need(slot['batch_id']==prepared['batch']['batch_id'],'PREPARED_BATCH_DIFFERS_FROM_APPROVED_SLOT')
    imports=C.read(plan['pilot_imports']);C.need(len(imports)==320 and all(C.read(C.ref(C.ledger_path(r['task_key'])))==r for r in imports),'IMPORTS_NOT_DURABLY_CLOSED')
    with C.pinned(prepared['tasks'],C.CAP).open() as stream:tasks=[json.loads(line) for line in stream]
    C.need(len(tasks)==prepared['molecules']==slot.get('molecules',prepared['batch']['molecules'])
        and len({t['meta']['task_key'] for t in tasks})==len(tasks),'EXACT_UNIQUE_SLOT_TASKS_REQUIRED')
    C.need(all(not C.ledger_path(t['meta']['task_key']).exists() for t in tasks),'ONCE_KEYS_ALREADY_CONSUMED_OR_UNKNOWN')
    out=R.new_output_directory(args.output,value);budget=R.Budget(proof,session,value,out);R.VALUE=value
    C.need(budget.observe() is None,'FRESH_SHARED_ACCOUNT_QUOTA_REQUIRED_BEFORE_SCIENCE_DISPATCH');budget.start_monitor()
    R.write_json_new(out/'execution_binding.json',{'schema':'SPRIME_FORMAL_CPU_BATCH_V3','plan':prepared['plan'],
        'prepared':prepared_ref,'request_reference':proof['request_reference'],'root_preflight':session['proof_reference'],
        'job_id':str(proof['job_id']),'batch_id':slot['batch_id'],'config':config_ref,'concurrency':concurrency,
        'scope':'listed finite wave only','actual_parent_terminal_claimed':False})
    index=0;active={};results=[];errors=[]
    with cf.ProcessPoolExecutor(max_workers=16,mp_context=mp.get_context('spawn'),initializer=init_worker,
            initargs=(config_ref,session,str(out))) as pool:
        while active or index<len(tasks):
            budget.observe(list(pool._processes.values()))
            while budget.stop is None and len(active)<16 and index<len(tasks):
                task=tasks[index]
                try:
                    dispatch_ref=R.dispatch(task,prepared_ref,prepared['plan'],proof,out)
                    future=pool.submit(one,task,dispatch_ref);active[future]=task;index+=1
                except Exception as exc:
                    errors.append({'task_key':task['meta']['task_key'],'dispatch_error':repr(exc)})
                    budget.stop=budget.stop or 'DISPATCH_OR_STORAGE_ERROR';break
            if not active:break
            done,_=cf.wait(active,timeout=1,return_when=cf.FIRST_COMPLETED)
            for future in done:
                task=active.pop(future)
                try:
                    record=future.result();results.append(record)
                    if record['scientific_status']=='IMPLEMENTATION_ERROR':budget.stop=budget.stop or 'IMPLEMENTATION_ERROR_STOP_NEW_DISPATCH'
                except Exception as exc:
                    errors.append({'task_key':task['meta']['task_key'],'error':repr(exc)});budget.stop=budget.stop or 'WORKER_UNKNOWN_OR_IMPLEMENTATION_ERROR'
    budget.close_monitor()
    R.write_json_new(out/'receipt.json',{'schema':'SPRIME_FORMAL_CPU_BATCH_RECEIPT_V3',
        'status':'PRODUCER_EXIT_REQUIRES_INDEPENDENT_TERMINAL_CLOSE','plan':prepared['plan'],'prepared':prepared_ref,
        'job_id':str(proof['job_id']),'config':config_ref,'durable_completed':results,'errors':errors,'budget':budget.report(),
        'full_forecast_core_hours':None,'cost_1p5_stop':False,'automatic_retry':False,'signals_sent':False,
        'parent_C0_or_scientific_PASS_claimed':False,'common_frozen':False})
    return 0 if not errors else 3


if __name__=='__main__':
    failure=None
    try:outcome=main()
    except BaseException as exc:
        failure={'error':repr(exc),'traceback':__import__('traceback').format_exc()};raise
    finally:R.finish_resource_entry(failure)
    raise SystemExit(outcome)
