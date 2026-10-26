"""CPU16 replay of original two missing tasks and fourteen controls; Slurm memory omitted."""
from __future__ import annotations
import argparse,concurrent.futures as cf,json,multiprocessing as mp,os,re,sys,time
from pathlib import Path
ORIGINAL_RECOVERY_DIR=Path(__file__).parent.parent/'recovery_v1'
sys.path.insert(0,str(ORIGINAL_RECOVERY_DIR))
from workflows.data_v1_final.conformers.recovery_auto_memory_v1.resource_runtime import (
    generation_admit,RecoverySampler,memory_evidence_metadata,related_cost_lower_bound)
from recovery_common import (IO,PARENT,MISSING,bind_inputs,load_plan,
    packet_reader,read_packet,require,scientific_sha,task_sha,expected_seed)
BARRIER=None

def init_worker(recipe,barrier):
    global BARRIER
    BARRIER=barrier
    import science
    science.worker_init(recipe)

def one(item):
    BARRIER.wait(timeout=120) # exactly16 independent worker PIDs enter before any task starts
    from run_pilot import run_one
    task,role=item
    frame=Path('/proc/self/stat').read_text()
    identity={'pid':os.getpid(),'start_ticks':int(frame[frame.rfind(')')+2:].split()[19]),
              'job_id':os.environ['SLURM_JOB_ID'],'uid':os.getuid()}
    result=run_one(task) # unchanged original task/config/seed/scientific function
    return role,task['meta']['molecule_id'],result,identity

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--plan',type=Path,required=True);p.add_argument('--approval',type=Path,required=True)
    p.add_argument('--root-preflight',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--resource-binding',type=Path,required=True)
    a=p.parse_args();value=load_plan(a.plan,approved=True)
    runtime,proof=generation_admit(a.plan,value,a.root_preflight,a.approval,
        resource_binding_path=a.resource_binding,output=a.output)
    require(not a.output.exists(),'NEW_RECOVERY_OUTPUT_REQUIRED_NO_RETRY')
    audit,closed,tasks=bind_inputs(value)
    require(IO.reference(value['partial_audit_report']['path']) in proof['request']['source_references'],
            'PARTIAL_AUDIT_AUTHORITY_NOT_PINNED')
    # Original334 paths are read only. Results are never copied over old packages.
    controls={r['molecule_id']:r for r in closed if r['molecule_id'] in value['replay_control_ids']}
    validator=packet_reader();expected={}
    for mid,row in controls.items():
        packet,_=read_packet(row['reference'],tasks[mid],validator)
        expected[mid]=scientific_sha(packet)
    config=IO.load_config(value['recipe_config']['path'])
    for name in MISSING:
        require(not Path(audit['pilot_output_directory'],'reproduction',
            __import__('hashlib').sha256(name.encode()).hexdigest()+'.json.gz').exists(),
            'MISSING_SOURCE_PACKAGE_NOW_EXISTS_REAUDIT_REQUIRED')
    out=IO.new_output_directory(a.output,value)
    (out/'reproduction').mkdir();(out/'controls').mkdir();(out/'controls/reproduction').mkdir()
    from live_memory_policy_32g_v1 import MemoryMonitor
    from run_pilot import persist_result
    monitor=MemoryMonitor(RecoverySampler(runtime['job_id'],proof));monitor.start()
    rows=[];errors=[];cost_gate_observed=False;started=time.monotonic()
    items=[(tasks[mid],'missing_original_task_reexecution') for mid in sorted(MISSING)]
    items += [(tasks[mid],'independent_same_seed_replay_control') for mid in value['replay_control_ids']]
    try:
        require(monitor.allow_dispatch(),'ALGORITHM_SOFT_MEMORY_DISPATCH_GUARD_DENIED')
        context=mp.get_context('spawn');barrier=context.Barrier(16)
        with cf.ProcessPoolExecutor(max_workers=16,mp_context=context,initializer=init_worker,
                initargs=(value['recipe_config']['path'],barrier)) as pool:
            active={pool.submit(one,item):item for item in items}
            while active:
                observed_related_core_seconds=related_cost_lower_bound(proof)
                if not cost_gate_observed and observed_related_core_seconds>1.5*230400:
                    cost_gate_observed=True
                    IO.write_json_new(out/'COST_GATE_STOP_NEW_DISPATCH.json',
                        {'reason':'ALL_RELATED_ACTUAL_COST_LOWER_BOUND_OVER_ORIGINAL_GATE','stop_new_dispatch':True,
                         'action':'Root report user;existing16 molecules drain naturally;no further submission',
                         'observed_all_related_core_seconds_lower_bound':observed_related_core_seconds})
                # All16 tasks were independently reviewed at startup. Any later
                # denial stops new dispatch; existing molecules drain naturally.
                done,_=cf.wait(active,timeout=.5,return_when=cf.FIRST_COMPLETED)
                for future in done:
                    item=active.pop(future);mid=item[0]['meta']['molecule_id']
                    try:
                        role,actual,result,identity=future.result()
                        require(actual==mid and role==item[1],'WORKER_TASK_ROLE_CHANGED')
                        dest=out if mid in MISSING else out/'controls'
                        ref=persist_result(dest,mid,result,value['max_output_bytes'])
                        packet,detail=read_packet(ref,tasks[mid],validator)
                        require(packet['summary']['seed']==expected_seed(tasks[mid]),'ORIGINAL_DETERMINISTIC_SEED_CHANGED')
                        signature=scientific_sha(packet)
                        equal=None if mid in MISSING else signature==expected[mid]
                        row={'molecule_id':mid,'role':role,'package_reference':ref,
                            'original_task_sha256':task_sha(tasks[mid]),'worker_identity':identity,
                            'scientific_sha256_excluding_summary_elapsed_seconds':signature,
                            'same_seed_control_exact_match':equal,'detail':detail,
                            'seed':result['summary']['seed'],'new_logical_retry':False,
                            'additional_physical_execution':True}
                        rows.append(row)
                        if equal is False:errors.append({'molecule_id':mid,'error':'EXACT_SAME_SEED_REPLAY_DRIFT'})
                    except Exception as exc:errors.append({'molecule_id':mid,'error':repr(exc)})
                if done:
                    IO.write_json_new(out/f'progress_{len(rows):02d}_{len(errors):02d}.json',
                        {'closed_physical_executions':len(rows),'expected_physical_executions':16,
                         'missing_original_tasks_closed':sum(r['molecule_id'] in MISSING for r in rows),
                         'resource_denial':monitor.first_denial,'original1p5_cost_gate_observed':cost_gate_observed})
    except Exception as exc:errors.append({'stage':'startup_or_executor','error':repr(exc)})
    finally:monitor.stop()
    workers={(r['worker_identity']['pid'],r['worker_identity']['start_ticks']) for r in rows}
    missing_rows=[r for r in rows if r['molecule_id'] in MISSING]
    control_rows=[r for r in rows if r['molecule_id'] not in MISSING]
    require(len(rows)<=16 and len(missing_rows)<=2 and len(control_rows)<=14,'PHYSICAL_EXECUTION_SCOPE_OVERFLOW')
    complete=(len(rows)==16 and len(workers)==16 and len(missing_rows)==2 and len(control_rows)==14 and
              all(r['same_seed_control_exact_match'] is True for r in control_rows) and
              not errors and monitor.first_denial is None and not monitor.thread.is_alive())
    from run_pilot_live_memory_32g_v1 import save_gzip_new
    save_gzip_new(out/'memory_evidence.json.gz',memory_evidence_metadata(monitor))
    IO.write_json_new(out/'physical_executions.json',sorted(rows,key=lambda r:r['molecule_id']))
    IO.write_json_new(out/'errors.json',errors)
    receipt={'schema':'SPRIME_MISSING_RECOVERY_EXECUTION_RECEIPT_V1',
        'status':'RECOVERY_PHYSICAL_EXECUTIONS_COMPLETE_REQUIRES_NEW_CLOSURE' if complete else 'RECOVERY_INCOMPLETE_NO_RETRY',
        'runtime':runtime,'plan_reference':IO.reference(a.plan),'approval_reference':IO.reference(a.approval),
        'root_preflight':IO.reference(a.root_preflight),'partial_audit_report':value['partial_audit_report'],
        'resource_binding_reference':IO.reference(a.resource_binding),
        'memory_policy':'SLURM_DEFAULT_UNSPECIFIED','slurm_memory_requested':False,
        'original_job_id':'4520364','original_parent_state':'TIMEOUT','original_timeout_retained':True,
        'new_missing_packages':[r['package_reference'] for r in missing_rows],
        'controls_are_not_new_population_members':True,'replay_controls':14,'configured_workers':16,
        'actual_completed_worker_identities':len(workers),'physical_executions_closed':len(rows),
        'new_logical_retries':0,'new_seeds':0,'resource_denial':monitor.first_denial,
        'monitor_thread_closed':not monitor.thread.is_alive(),'signals_sent':False,
        'original1p5_estimate_gate_observed_requires_user_report':cost_gate_observed,
        'elapsed_seconds':time.monotonic()-started,'budget_is_allocation_ceiling_not_runtime_forecast':True,
        'outputs':[IO.reference(out/n) for n in ('physical_executions.json','errors.json','memory_evidence.json.gz')],
        'scientific_recipe_changed':False,'old334_recomputed_for_population':False,
        'formal_generation_authorized':False,'pilot_accepted_for_planning':False,
        'actual_cost_status':'ROOT_MUST_ATTACH_REAL_TERMINAL_PARENT_SACCT_INCLUDING_ORIGINAL_TIMEOUT'}
    IO.write_json_new(out/'recovery_receipt.json',receipt)
    print(json.dumps({'status':receipt['status'],'closed':len(rows),'actual_workers':len(workers)}))
    return 0 if complete else 1
if __name__=='__main__':raise SystemExit(main())