"""Independent bounded original32 replays;no production once or new training."""
import argparse,concurrent.futures as cf,gzip,json,multiprocessing as mp,os,pathlib,stat,time,traceback
from . import contract as C,runtime_io as R,edge as E
from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2 import runtime as A
from workflows.data_v1_final.conformers.portable_secondary_uff_v1.bridge import scientific_sha
SESSION=None;RUNNER=None;BARRIER=None
def initialize(session,config,qa_sources,barrier,out,proof):
    global SESSION,RUNNER,BARRIER
    SESSION=session;BARRIER=barrier;R.continuation(session,check_sources=True);R.OUT=pathlib.Path(out);R.PROOF=proof;R.VALUE=C.config(config);_,science=R.load_science(R.VALUE)
    C.need(C.ref(science.__file__)==C.sources()['science'] and pathlib.Path(science.SCIENCE.read.__code__.co_filename).absolute()==pathlib.Path(C.sources()['graph_stereo_rmsd']['path']),
        'ORIGINAL_SCIENCE_AND_LMDB_READ_FUNCTION_NOT_REPLACED')
    fixed={'run_pilot':'f7733b23602d9883159bbedc2ea712fb3054e9e7963950c6fd6c10c1f582868f','statistics_tools':'22422b92fde096a64c019683cf265514b99351b002fa8bc450f6eeaf932808ed'}
    for name,sha in fixed.items():C.need(qa_sources[name]['path']==str(C.ORIGINAL.HERE.parent/(name+'.py')) and qa_sources[name]['sha256']==sha,'EXACT_ORIGINAL_QA_RUN_ONE_AND_STATISTICS_SOURCES')
    C.module('statistics_tools',qa_sources['statistics_tools']);RUNNER=C.module('run_pilot',qa_sources['run_pilot'])
def one(task,expected):
    R.continuation(SESSION);BARRIER.wait(timeout=120);C.need(C.sha_value(task)==expected['task_sha256'],'SAME_ORIGINAL_TASK_BYTES')
    key=expected['task_sha256'];R.write_json_new(R.OUT/'starts'/(key+'.json'),{'task_sha256':key,'molecule_id':task['meta']['molecule_id'],
        'pid':os.getpid(),'pid_start_ticks':R.proc_ticks(os.getpid()),'job_id':SESSION['job_id'],'diagnostic_only':True,'production_once_accessed':False})
    frames={};project=C.RUN.parents[1]
    for r in task['records']:
        path=pathlib.Path(r['source_path']);path=path if path.is_absolute() else project/path
        C.need(project in path.parents and not any(p.is_symlink() for p in (path,*path.parents)),'ORIGINAL_TASK_LMDB_LOCATOR_ONLY')
        info=path.lstat();C.need(stat.S_ISREG(info.st_mode) and info.st_uid==1278,'OWN_ORIGINAL_LMDB_CONTAINER');frames[str(path)]=C.frame(info)
    result=RUNNER.run_one(task)
    C.need(all(C.frame(pathlib.Path(p).stat())==v for p,v in frames.items()),'LMDB_FRAME_DURING_ORIGINAL_PAYLOAD_SHA_READER')
    raw=C.canonical(result);C.need(len(raw)<=R.VALUE['packet_uncompressed_limit_bytes'],'COMPLETE_DIAGNOSTIC_PACKET_SOFTWARE_BOUND')
    compressed=gzip.compress(raw,mtime=0);C.need(len(compressed)<=R.VALUE['packet_compressed_limit_bytes'],'DIAGNOSTIC_FULL_PACKET_COMPRESSED_BOUND')
    packet=R.atomic_bytes(R.OUT/'packets'/(key+'.json.gz'),compressed,reservation_key=key)
    with gzip.open(packet['path'],'rb') as saved:readback=saved.read(R.VALUE['packet_uncompressed_limit_bytes']+1)
    C.need(readback==raw,'FULL_DIAGNOSTIC_PACKET_GZIP_CRC_EOF_BYTE_READBACK');digest=scientific_sha(result)
    return {'molecule_id':task['meta']['molecule_id'],'task_sha256':C.sha_value(task),'scientific_sha256':digest,'matches':digest==expected['scientific_sha256_excluding_elapsed_seconds'],
        'pid':os.getpid(),'pid_start_ticks':R.proc_ticks(os.getpid()),'LMDB_frames':frames,'native_return_observed':True,'new_training_member':False,'actual_packet_reference':packet}
def main():
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('plan','root-preflight','output'):p.add_argument('--'+k,type=pathlib.Path,required=True)
    a=p.parse_args();ref=C.ref(a.plan);plan=E.meta(ref);n=C.node(plan['node']);argv=[C.Q.PY,'-B','-m',C.MODULE+'.compat32','--plan',str(a.plan),'--root-preflight',str(a.root_preflight),'--output',str(a.output)]
    proof=A.require_startup(a.root_preflight,expected_scope_key='sprime_multinode_resource_compat32_v1',expected_scope_parameters=C.parameters('compat32',n),expected_execution_argv=argv,
        expected_source=__file__,expected_kind='conformer',required_references=[ref,*C.own_sources(),*plan['source_references']])
    C.need(proof['request']['node']==n and proof['request']['pilot'] is True and proof['request']['estimated_peak_output_bytes']==4<<30
        and proof['request']['wall_seconds']==14400,'EXACT32_DIAGNOSTIC_CPU16_4G_4H')
    E.source3(plan['source3_reference']);binding=E.binding(plan['node_binding_reference'],active=True);C.need(binding['node']==n and E.environment()==binding['environment'],'ACTUAL_PER_NODE_PROBE_ENV_MATCH')
    closure,prep=E.preparation_closure(plan['qa_preparation_closure_reference'])
    C.need(prep['status']=='ORIGINAL32_TASKS_AND_BASELINES_CLOSED_NO_UFF' and len(prep['expected'])==32,'REAL_C0_PREPARED32_NOT_NEW_TASK_SELECTION')
    R.authorized(proof,[prep['tasks_reference']]);tasks=[json.loads(raw) for raw in C.pinned(prep['tasks_reference'],C.CAP).read_bytes().splitlines()]
    expected={r['molecule_id']:r for r in prep['expected']};C.need(len(tasks)==32 and {t['meta']['molecule_id'] for t in tasks}==set(expected),'EXACT32_TASK_SET')
    auth=E.meta(plan['diagnostic_authorization_reference']);C.root(auth,'ROOT_SPRIME_NODE_INDEPENDENT32_QA_V1','APPROVED_DIAGNOSTIC_REPLAY_ONLY')
    C.need(auth['node']==n and auth['qa_preparation_closure_reference']==plan['qa_preparation_closure_reference'] and auth['maximum_replays']==32
        and auth['production_once_access_authorized'] is False and auth['new_training_members']==0,'INDEPENDENT_DIAGNOSTIC_INTENT_NOT_PRODUCTION_RETRY')
    intent_key=C.sha_value([n,plan['diagnostic_authorization_reference'],prep['tasks_reference']]);intent=C.DIAG/'diagnostic_intents'/(intent_key+'.json')
    intent.parent.mkdir(parents=True,exist_ok=True);R.exclusive_raw(intent,C.canonical({'job_id':str(proof['job_id']),'node':n,'maximum_replays':32,'original_tasks_reference':prep['tasks_reference'],
        'authorization_reference':plan['diagnostic_authorization_reference'],'production_once_accessed':False})+b'\n')
    value=C.config(plan['config_reference']);out=R.new_output_directory(a.output,value);R.PROOF=proof;R.VALUE=value
    session={'proof_reference':C.ref(a.root_preflight),'main_source':C.ref(__file__),'execution_argv':argv,'parent_pid':os.getpid(),'parent_start_ticks':R.proc_ticks(os.getpid()),
        'boot_id':proof['boot_id'],'job_id':str(proof['job_id']),'node':n,'quota_reuse_review_reference':plan['quota_reuse_review_reference']};R.SESSION=session
    budget=R.Budget(proof,session,value,out);results=[];errors=[]
    try:
        C.need(budget.observe() is None,'ORIGINAL_BUDGET_BEFORE32_DIAGNOSTIC_REPLAYS');budget.start_monitor();ctx=mp.get_context('spawn');barrier=ctx.Barrier(16)
        with cf.ProcessPoolExecutor(max_workers=16,mp_context=ctx,initializer=initialize,initargs=(session,plan['config_reference'],plan['qa_sources'],barrier,str(out),proof)) as pool:
            for first in (0,16):
                if budget.observe(list((pool._processes or {}).values())) is not None:break
                active={}
                for t in tasks[first:first+16]:
                    key=C.sha_value(t);R.reserve(out,key,value['packet_compressed_limit_bytes']+(1<<20));active[pool.submit(one,t,expected[t['meta']['molecule_id']])]=t
                while active:
                    budget.observe(list((pool._processes or {}).values()));done,_=cf.wait(active,timeout=1,return_when=cf.FIRST_COMPLETED)
                    for f in done:
                        t=active.pop(f)
                        try:results.append(f.result())
                        except Exception as exc:errors.append({'molecule_id':t['meta']['molecule_id'],'error':repr(exc)})
    finally:
        budget.close_monitor();passed=len(results)==32 and all(r['matches'] for r in results) and len({r['pid'] for r in results})==16 and not errors and budget.stop is None
        R.write_json_new(out/'receipt.json',{'schema':'ACTUAL_MAIN_SPRIME_NODE_COMPAT32_V1','status':'EXACT32_ORIGINAL_SCIENTIFIC_SHA_MATCH' if passed else 'INCOMPLETE_OR_MISMATCH_HOLD',
            'job_id':str(proof['job_id']),'node':n,'uid':1278,'plan_reference':ref,'startup_proof_reference':C.ref(a.root_preflight),'node_binding_reference':plan['node_binding_reference'],
            'qa_preparation_reference':closure['receipt_reference'],'qa_preparation_closure_reference':plan['qa_preparation_closure_reference'],'completed':len(results),'matched':sum(r['matches'] for r in results),
            'results':results,'errors':errors,'budget':budget.report(),'environment':E.environment(),'source_references':C.own_sources(),'production_once_accessed':False,'new_training_members':0,
            'new_QM_calls':0,'scientific_recipe_changed':False,'whole_LMDB_SHA_not_originally_available_not_claimed':True,'automatic_native_retry':False})
    return 0 if passed else 3
if __name__=='__main__':raise SystemExit(main())
