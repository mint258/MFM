"""New independent32 diagnostic;durable first-wave failures;no prod once."""
import argparse,concurrent.futures as cf,gzip,json,multiprocessing as mp,os,pathlib,stat,sys,time,traceback
from . import contract as C,runtime_io as R,edge as E
from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2 import runtime as A
from workflows.data_v1_final.conformers.portable_secondary_uff_v1.bridge import scientific_sha
SESSION=None;RUNNER=None;SCIENCE=None;BARRIER=None

def initialize(session,config,qa_sources,barrier,out,proof):
    global SESSION,RUNNER,SCIENCE,BARRIER
    SESSION=session;BARRIER=barrier;value=C.config(config);R.bind_io_context(out,value,proof,session)
    try:
        actual=R.continuation(session,check_sources=True);C.need(actual==proof,'WORKER_SAME_BOUND_STARTUP_PROOF')
        _,SCIENCE=R.load_science(value) # exact original object internally calls science.worker_init once
        C.need(C.ref(SCIENCE.__file__)==C.sources()['science'] and pathlib.Path(SCIENCE.SCIENCE.read.__code__.co_filename).absolute()==pathlib.Path(C.sources()['graph_stereo_rmsd']['path']),
            'ORIGINAL_SCIENCE_AND_LMDB_READ_FUNCTION_NOT_REPLACED')
        fixed={'run_pilot':'f7733b23602d9883159bbedc2ea712fb3054e9e7963950c6fd6c10c1f582868f','statistics_tools':'22422b92fde096a64c019683cf265514b99351b002fa8bc450f6eeaf932808ed'}
        for name,sha in fixed.items():C.need(qa_sources[name]['path']==str(C.ORIGINAL.HERE.parent/(name+'.py')) and qa_sources[name]['sha256']==sha,'EXACT_ORIGINAL_QA_RUN_ONE_AND_STATISTICS_SOURCES')
        stats=C.module('statistics_tools',qa_sources['statistics_tools']);RUNNER=C.module('run_pilot',qa_sources['run_pilot'])
        C.need(sys.modules['science'] is SCIENCE and sys.modules['statistics_tools'] is stats and R.SESSION is SESSION
            and R.OUT==pathlib.Path(out) and R.PROOF==proof and R.VALUE is value and SCIENCE.CONFIG is not None and SCIENCE.SCIENCE is not None,
            'EXPLICIT_ORIGINAL_RUNNER_SCIENCE_AND_PER_PROCESS_IO_WIRING')
        R.write_json_new(R.OUT/'errors'/('worker_initialized_%d.json'%os.getpid()),{'status':'INITIALIZED_NOT_INVOKED',
            'pid':os.getpid(),'pid_start_ticks':R.proc_ticks(os.getpid()),'job_id':session['job_id'],'science_reference':C.ref(SCIENCE.__file__),
            'run_pilot_reference':C.ref(RUNNER.__file__),'recipe_reference':value['recipe_config'],'original_loader_initialization_calls':1,
            'extra_science_worker_init_calls':0,'R_SESSION_PROOF_OUT_VALUE_bound':True,'scientific_runner_invoked':False})
    except BaseException as exc:
        R.write_json_new(R.OUT/'errors'/('worker_initialization_failed_%d.json'%os.getpid()),{'status':'INITIALIZATION_FAILED_NO_RUN_ONE',
            'pid':os.getpid(),'error':repr(exc),'traceback':traceback.format_exc(),'scientific_runner_invoked':False});raise

def one(task,expected):
    key=expected['task_sha256'];started=None;invoked=False;returned=False;stage='CONTINUATION'
    try:
        R.continuation(SESSION);C.need(R.SESSION is SESSION and sys.modules['science'] is SCIENCE,'WORKER_CONTEXT_STILL_BOUND')
        BARRIER.wait(timeout=120);C.need(C.sha_value(task)==key,'SAME_ORIGINAL_TASK_BYTES');stage='START'
        started=R.write_json_new(R.OUT/'starts'/(key+'.json'),{'task_sha256':key,'molecule_id':task['meta']['molecule_id'],
            'pid':os.getpid(),'pid_start_ticks':R.proc_ticks(os.getpid()),'job_id':SESSION['job_id'],'diagnostic_only':True,'production_once_accessed':False})
        frames={};project=C.RUN.parents[1];stage='LMDB_FRAME'
        for row in task['records']:
            path=pathlib.Path(row['source_path']);path=path if path.is_absolute() else project/path
            C.need(project in path.parents and not any(p.is_symlink() for p in (path,*path.parents)),'ORIGINAL_TASK_LMDB_LOCATOR_ONLY')
            info=path.lstat();C.need(stat.S_ISREG(info.st_mode) and info.st_uid==1278,'OWN_ORIGINAL_LMDB_CONTAINER');frames[str(path)]=C.frame(info)
        stage='ORIGINAL_RUN_ONE';invoked=True;result=RUNNER.run_one(task);returned=True
        C.need(all(C.frame(pathlib.Path(p).stat())==v for p,v in frames.items()),'LMDB_FRAME_DURING_ORIGINAL_PAYLOAD_SHA_READER')
        stage='FULL_PACKET_WRITE';packet=save_packet(key,result);digest=scientific_sha(result)
        return {'molecule_id':task['meta']['molecule_id'],'task_sha256':key,'scientific_sha256':digest,
            'matches':digest==expected['scientific_sha256_excluding_elapsed_seconds'],'pid':os.getpid(),'pid_start_ticks':R.proc_ticks(os.getpid()),
            'LMDB_frames':frames,'native_return_observed':True,'original_runner_return_observed':True,'new_training_member':False,
            'actual_packet_reference':packet,'start_reference':started,'worker_initialization_reference':C.ref(R.OUT/'errors'/('worker_initialized_%d.json'%os.getpid()))}
    except BaseException as exc:
        R.write_json_new(R.OUT/'errors'/(key+'.json'),{'schema':'SPRIME_COMPAT_NO_DURABLE_MATCHED_PACKET_V2','molecule_id':task['meta']['molecule_id'],
            'task_sha256':key,'stage':stage,'start_reference':started,'scientific_runner_invoked':invoked,'original_runner_return_observed':returned,
            'internal_native_return_status':'OBSERVED_RUN_ONE_RETURN' if returned else 'UNKNOWN' if invoked else 'NOT_INVOKED_BY_THIS_WORKER',
            'error':repr(exc),'traceback':traceback.format_exc(),'production_once_accessed':False,'automatic_retry':False});raise

def save_packet(key,result):
    raw=C.canonical(result);C.need(len(raw)<=R.VALUE['packet_uncompressed_limit_bytes'],'COMPLETE_DIAGNOSTIC_PACKET_SOFTWARE_BOUND')
    compressed=gzip.compress(raw,mtime=0);C.need(len(compressed)<=R.VALUE['packet_compressed_limit_bytes'],'DIAGNOSTIC_FULL_PACKET_COMPRESSED_BOUND')
    ref=R.atomic_bytes(R.OUT/'packets'/(key+'.json.gz'),compressed,reservation_key=key)
    saved=R.read_packet(ref,R.VALUE);C.need(saved==result,'FULL_PACKET_ORIGINAL_READER_CRC_EOF_OBJECT_READBACK');return ref

def collect_waves(pool,tasks,expected,observe,runner=one,reservation_bytes=None,progress=None):
    """Reserve complete wave before submit;drain every future;never dispatch after failure."""
    progress={} if progress is None else progress
    results=progress.setdefault('results',[]);errors=progress.setdefault('errors',[]);submitted=progress.setdefault('submitted',[]);completed_waves=progress.setdefault('completed_waves',[])
    n=reservation_bytes if reservation_bytes is not None else R.VALUE['packet_compressed_limit_bytes']+(1<<20)
    for first in range(0,len(tasks),16):
        if errors or any(not r['matches'] for r in results) or observe() is not None:break
        wave=tasks[first:first+16];C.need(len(wave)==16,'COMPLETE_FIXED16_WAVE_REQUIRED')
        try:
            for task in wave:R.reserve(R.OUT,expected[task['meta']['molecule_id']]['task_sha256'],n)
        except BaseException as exc:
            error={'stage':'RESERVE_BEFORE_THIS_WAVE_SUBMISSION','wave_first':first,'error':repr(exc),'traceback':traceback.format_exc(),
                'submitted_in_this_wave':0,'previous_results_retained':len(results)};errors.append(error)
            R.write_json_new(R.OUT/'errors'/('reserve_wave_%d.json'%first),error);break
        active={}
        for task in wave:
            mid=task['meta']['molecule_id'];key=expected[mid]['task_sha256']
            try:
                R.write_json_new(R.OUT/'dispatch'/(key+'.json'),{'molecule_id':mid,'task_sha256':key,'wave_first':first,
                    'status':'DIAGNOSTIC_INTENT_BEFORE_SUBMIT','production_once_accessed':False})
                active[pool.submit(runner,task,expected[mid])]=task;submitted.append(mid)
            except BaseException as exc:
                error={'stage':'SUBMISSION_OUTCOME_UNKNOWN_NO_RETRY','molecule_id':mid,'task_sha256':key,'error':repr(exc),'traceback':traceback.format_exc()}
                errors.append(error);R.write_json_new(R.OUT/'errors'/('parent-'+key+'.json'),error);break
        while active:
            observe();done,_=cf.wait(active,timeout=1,return_when=cf.FIRST_COMPLETED)
            for future in done:
                task=active.pop(future);mid=task['meta']['molecule_id'];key=expected[mid]['task_sha256']
                try:results.append(future.result())
                except BaseException as exc:
                    error={'stage':'RETURN_WITHOUT_VALID_MATCHED_PACKET','molecule_id':mid,'task_sha256':key,'error':repr(exc),'traceback':traceback.format_exc(),
                        'internal_native_return_status':'UNKNOWN_UNLESS_WORKER_EVIDENCE_OBSERVED','no_retry':True}
                    errors.append(error);R.write_json_new(R.OUT/'errors'/('parent-'+key+'.json'),error)
        completed_waves.append(first)
        # A first-wave failure or mismatch stops here;all submitted futures have drained.
        if errors or any(not r['matches'] for r in results) or observe() is not None:break
    return results,errors,{'submitted_molecule_ids':submitted,'submitted_count':len(submitted),'drained_wave_starts':completed_waves,
        'first_wave_failure_stops_second_wave':bool(errors or any(not r['matches'] for r in results)),'automatic_retry':False,'signals_sent':0}

# Synthetic IO workers never initialize science or invoke UFF/QM;no project DATA.
def synthetic_initialize(out,value,proof,barrier):
    global BARRIER
    BARRIER=barrier;R.bind_io_context(out,value,proof,{'synthetic_IO_only':True})
    C.need(R.VALUE is value and R.PROOF==proof and R.OUT==pathlib.Path(out) and R.SESSION['synthetic_IO_only'] is True
        and proof['uid']==os.getuid()==1278 and proof['request']['scope_key']=='sprime_multinode_resource_source3_v2','REAL_SOURCE3_SYNTHETIC_CHILD_IO_CONTEXT')
def synthetic_one(task,expected):
    key=expected['task_sha256'];BARRIER.wait(timeout=120)
    R.write_json_new(R.OUT/'starts'/(key+'.json'),{'molecule_id':task['meta']['molecule_id'],'synthetic_IO_only':True,'pid':os.getpid()})
    if task.get('synthetic_failure'):
        R.write_json_new(R.OUT/'errors'/(key+'.json'),{'synthetic_deliberate_failure':True,'native_invoked':False});raise ValueError('SYNTHETIC_FIRST_WAVE_FAILURE')
    import hashlib,struct
    mid=task['meta']['molecule_id'];numbers=[6,1,1];coords=[[1.25,-2.5,3.125],[2.,-2.5,3.125],[1.25,-1.75,3.125]]
    atom=hashlib.sha256(struct.pack('<3q',*numbers)).hexdigest();anchor='synthetic_anchor'
    result={'summary':{'molecule_id':mid,'atom_order_sha256':atom,'source_record_id':anchor},'synthetic_IO_only':True,'pid':os.getpid(),
        'conformers':[{'molecule_id':mid,'sprime_conf_idx':0,'below_dedup_threshold':False,'status':'SUCCESS','converged':True,
            'atomic_numbers':numbers,'coordinates':coords,'atom_order_sha256':atom,'source_record_id':anchor,'geometry_sha256':R.common().geometry_sha(numbers,coords),
            'uff_energy_kcal_mol':0.125,'origin':'accepted_sprime','original_sprime_conf_idx':0}]}
    ref=save_packet(key,result)
    return {'molecule_id':task['meta']['molecule_id'],'pid':os.getpid(),'matches':True,'actual_packet_reference':ref,'io_context_bound':R.SESSION['synthetic_IO_only'] is True}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('plan','root-preflight','output'):p.add_argument('--'+k,type=pathlib.Path,required=True)
    a=p.parse_args();ref=C.ref(a.plan);plan=E.meta(ref);n=C.node(plan['node']);argv=[C.Q.PY,'-B','-m',C.MODULE+'.compat32','--plan',str(a.plan),'--root-preflight',str(a.root_preflight),'--output',str(a.output)]
    proof=A.require_startup(a.root_preflight,expected_scope_key='sprime_multinode_resource_compat32_v2',expected_scope_parameters=C.parameters('compat32',n),expected_execution_argv=argv,
        expected_source=__file__,expected_kind='conformer',required_references=[ref,*C.own_sources(),*plan['source_references']])
    C.need(proof['request']['node']==n and proof['request']['pilot'] is True and proof['request']['estimated_peak_output_bytes']==C.CAP
        and proof['request']['wall_seconds']==14400,'EXACT32_DIAGNOSTIC_CPU16_8G_4H')
    E.source3(plan['source3_reference']);binding=E.binding(plan['node_binding_reference'],active=True);C.need(binding['node']==n and E.environment()==binding['environment'],'ACTUAL_PER_NODE_PROBE_ENV_MATCH')
    closure,prep=E.preparation_closure(plan['qa_preparation_closure_reference'])
    C.need(prep['status']=='ORIGINAL32_TASKS_AND_BASELINES_CLOSED_NO_UFF' and len(prep['expected'])==32,'REAL_C0_NEW_PREPARED32')
    exclusion=E.exclusions(plan['excluded_mid_authority_reference']);C.need(prep['excluded_mid_authority_reference']==plan['excluded_mid_authority_reference'],'SAME_ROOT_EXACT_OLD16_EXCLUSION')
    R.authorized(proof,[prep['tasks_reference']]);tasks=[json.loads(raw) for raw in C.pinned(prep['tasks_reference'],C.CAP).read_bytes().splitlines()]
    expected={r['molecule_id']:r for r in prep['expected']};C.need(len(tasks)==32 and {t['meta']['molecule_id'] for t in tasks}==set(expected)
        and not set(expected)&set(exclusion['excluded_molecule_ids']),'EXACT32_NEW_TASK_SET_NO_OLD_STARTED_MID')
    auth=E.meta(plan['diagnostic_authorization_reference']);C.root(auth,'ROOT_SPRIME_NODE_INDEPENDENT32_QA_V2','APPROVED_DIAGNOSTIC_REPLAY_ONLY')
    C.need(auth['node']==n and auth['qa_preparation_closure_reference']==plan['qa_preparation_closure_reference'] and auth['maximum_replays']==32
        and auth['excluded_mid_authority_reference']==plan['excluded_mid_authority_reference'] and auth['production_once_access_authorized'] is False and auth['new_training_members']==0,
        'EXPLICIT_NEW_ROOT_INTENT_NOT_OLD16_RETRY')
    intent_key=C.sha_value([n,plan['diagnostic_authorization_reference'],prep['tasks_reference']]);intent=C.DIAG/'diagnostic_intents'/(intent_key+'.json')
    intent.parent.mkdir(parents=True,exist_ok=True);R.exclusive_raw(intent,C.canonical({'job_id':str(proof['job_id']),'node':n,'maximum_replays':32,'original_tasks_reference':prep['tasks_reference'],
        'authorization_reference':plan['diagnostic_authorization_reference'],'excluded_mid_authority_reference':plan['excluded_mid_authority_reference'],'production_once_accessed':False})+b'\n')
    value=C.config(plan['config_reference']);C.need(C.compatibility_minimum_cap(value)<=C.CAP,'COMPLETE32_RESERVATION_AND_ADMIN_WITHIN8G')
    out=R.new_output_directory(a.output,value)
    session={'proof_reference':C.ref(a.root_preflight),'main_source':C.ref(__file__),'execution_argv':argv,'parent_pid':os.getpid(),'parent_start_ticks':R.proc_ticks(os.getpid()),
        'boot_id':proof['boot_id'],'job_id':str(proof['job_id']),'node':n,'quota_reuse_review_reference':plan['quota_reuse_review_reference']}
    R.bind_io_context(out,value,proof,session);budget=None;results=[];errors=[];collection={};progress={};failure=None
    try:
        budget=R.Budget(proof,session,value,out)
        C.need(budget.observe() is None,'ORIGINAL_BUDGET_BEFORE32_DIAGNOSTIC_REPLAYS');budget.start_monitor();ctx=mp.get_context('spawn');barrier=ctx.Barrier(16)
        with cf.ProcessPoolExecutor(max_workers=16,mp_context=ctx,initializer=initialize,initargs=(session,plan['config_reference'],plan['qa_sources'],barrier,str(out),proof)) as pool:
            results,errors,collection=collect_waves(pool,tasks,expected,lambda:budget.observe(list((pool._processes or {}).values())),progress=progress)
    except BaseException as exc:
        results=progress.get('results',results);errors=progress.get('errors',errors)
        collection={'submitted_molecule_ids':progress.get('submitted',[]),'submitted_count':len(progress.get('submitted',[])),'drained_wave_starts':progress.get('completed_waves',[]),'aborted_with_preserved_partial_parent_collections':True}
        failure={'error':repr(exc),'traceback':traceback.format_exc(),'existing_results_and_errors_retained':True}
    finally:
        if budget is not None:budget.close_monitor()
        passed=budget is not None and len(results)==32 and all(r['matches'] for r in results) and len({r['pid'] for r in results})==16 and not errors and failure is None and budget.stop is None
        R.write_json_new(out/'receipt.json',{'schema':'ACTUAL_MAIN_SPRIME_NODE_COMPAT32_V2','status':'EXACT32_ORIGINAL_SCIENTIFIC_SHA_MATCH' if passed else 'INCOMPLETE_OR_MISMATCH_HOLD',
            'job_id':str(proof['job_id']),'node':n,'uid':1278,'plan_reference':ref,'startup_proof_reference':C.ref(a.root_preflight),'node_binding_reference':plan['node_binding_reference'],
            'qa_preparation_reference':closure['receipt_reference'],'qa_preparation_closure_reference':plan['qa_preparation_closure_reference'],
            'excluded_mid_authority_reference':plan['excluded_mid_authority_reference'],'completed':len(results),'matched':sum(r['matches'] for r in results),
            'results':results,'errors':errors,'collection':collection,'top_level_failure':failure,'budget':budget.report() if budget is not None else None,'environment':E.environment(),'source_references':C.own_sources(),
            'production_once_accessed':False,'new_training_members':0,'new_QM_calls':0,'scientific_recipe_changed':False,'whole_LMDB_SHA_not_originally_available_not_claimed':True,
            'automatic_native_retry':False,'old16_native_return_status':'UNKNOWN_PRESERVED_NO_REPLAY','minimum32_resource_envelope_bytes':C.compatibility_minimum_cap(value)})
    return 0 if passed else 3
if __name__=='__main__':raise SystemExit(main())