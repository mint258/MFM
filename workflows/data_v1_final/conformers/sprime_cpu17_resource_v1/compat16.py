"""Same original sixteen UFF tasks on actual Main17; no production once access."""
import argparse,concurrent.futures as cf,json,multiprocessing as mp,os,pathlib,re,stat,sys,traceback
from . import contract as C,runtime_io as R,quota_edge as E
from .probe import environment
from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2 import runtime as A
from workflows.data_v1_final.conformers.portable_secondary_uff_v1.bridge import scientific_sha
KEY='sprime_cpu17_original_uff16_qa_v1'
PARAMS={'node':'compute-0-17','controls':16,'original_LMDB_reader':True,'population_members_added':0,'production_once_accessed':False,
 'scientific_packet_SHA_excludes_only_elapsed':True,'maximum_workers':16,'candidate_cap':300,'new_QM_calls':0}
SESSION=None;RUNNER=None;BARRIER=None


def initialize(session,config,qa_sources,barrier):
    global SESSION,RUNNER,BARRIER
    SESSION=session;BARRIER=barrier;R.continuation(session,check_sources=True)
    _,science=R.load_science(C.config(config));C.verify_original_science(science)
    C.need(pathlib.Path(science.SCIENCE.read.__code__.co_filename).absolute()==pathlib.Path(C.sources()['graph_stereo_rmsd']['path']),
      'TRUE_ORIGINAL_LMDB_READER_NOT_REPLACED');C.module('statistics_tools',qa_sources['statistics_tools']);RUNNER=C.module('run_pilot',qa_sources['run_pilot'])
    C.need(pathlib.Path(RUNNER.run_one.__code__.co_filename)==pathlib.Path(qa_sources['run_pilot']['path']),'ORIGINAL_RUN_ONE_NOT_PORTABLE_BRIDGE')


def one(task,expected):
    R.continuation(SESSION);BARRIER.wait(timeout=120)
    C.need(C.sha_value(task)==expected['task_sha256'],'UNCHANGED_ORIGINAL_QA_TASK_BYTES')
    # Only pointers in this byte-identical frozen original task are followed.
    # No whole-LMDB hash existed in the original authority; none is invented.
    before={};project=C.RUN.parents[1]
    for row in task['records']:
        C.need(isinstance(row['record_payload_sha256'],str) and re.fullmatch('[0-9a-f]{64}',row['record_payload_sha256']),
          'ORIGINAL_RECORD_PAYLOAD_SHA_REQUIRED')
        p=pathlib.Path(row['source_path']);p=p if p.is_absolute() else project/p
        C.need(p.is_absolute() and project in p.parents and '..' not in p.parts
          and not any(x.is_symlink() for x in (p,*p.parents)),'ONLY_ORIGINAL_PROJECT_EXACT_TASK_POINTER_PATH')
        info=p.lstat();C.need(stat.S_ISREG(info.st_mode) and info.st_uid==1278,'OWN_REGULAR_ORIGINAL_LMDB_POINTER_CONTAINER')
        before[str(p)]=E.frame(info)
    result=RUNNER.run_one(task)
    C.need(all(E.frame(pathlib.Path(text).stat())==f and not any(x.is_symlink() for x in (pathlib.Path(text),*pathlib.Path(text).parents)) for text,f in before.items()),'LMDB_FRAME_CHANGED_DURING_ORIGINAL_READ')
    C.need(result['summary']['status']=='SUCCESS','QA_TASK_NOT_SUCCESS')
    digest=scientific_sha(result)
    return {'molecule_id':task['meta']['molecule_id'],'task_sha256':C.sha_value(task),'scientific_sha256':digest,
      'matches':digest==expected['scientific_sha256_excluding_elapsed_seconds'],'LMDB_frames':before,
      'LMDB_frame_after_equal':True,'pid':os.getpid(),'pid_start_ticks':R.proc_ticks(os.getpid())}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('plan','root-preflight','output'):p.add_argument('--'+k,type=pathlib.Path,required=True)
    a=p.parse_args();pr=C.ref(a.plan);plan=E.meta(pr);prep=E.meta(plan['controls_preparation_reference']);expected=E.PC.prep_metadata(prep)
    argv=[E.Q.PY,'-B','-m',C.MODULE+'.compat16','--plan',str(a.plan),'--root-preflight',str(a.root_preflight),'--output',str(a.output)]
    required=[pr,plan['controls_preparation_reference'],plan['node17_binding_reference'],plan['quota_reuse_review_reference'],prep['tasks_reference'],
      *C.own_sources(),*plan['source_references'],*plan['qa_sources'].values(),plan['qa_authority_reference'],
      prep['original_complete_packages_reference'],prep['original_audit_reference'],prep['partial_audit_monitor_closure_reference'],
      prep['root_preflight_reference'],prep['root_control_authorization_reference'],prep['qa_slice_marker_reference'],prep['selection_report_reference']]
    proof=A.require_startup(a.root_preflight,expected_scope_key=KEY,expected_scope_parameters=PARAMS,expected_execution_argv=argv,
      expected_source=__file__,expected_kind='conformer',required_references=required)
    C.need(proof['request']['node']==C.NODE and proof['request']['cpus']==16 and proof['request']['wall_seconds']==C.QA_WALL
      and plan['mode']=='compat16' and plan['source_references']==C.own_sources(),'EXACT_ORIGINAL16_FIXED_NODE17_QA')
    C.source_inverse_proof();binding=E.binding(plan['node17_binding_reference'])
    C.need(environment()==binding['environment'],'ACTUAL_MAIN_ENVIRONMENT_MUST_MATCH_OWN17_PROBE')
    value=C.config(plan['config_reference']);out=R.new_output_directory(a.output,value)
    session={'proof_reference':C.ref(a.root_preflight),'main_source':C.ref(__file__),'execution_argv':argv,
      'parent_pid':os.getpid(),'parent_start_ticks':R.proc_ticks(os.getpid()),'boot_id':proof['boot_id'],'job_id':str(proof['job_id'])}
    budget=R.Budget(proof,{'quota_reuse_review_reference':plan['quota_reuse_review_reference']},value,out)
    results=[];errors=[]
    try:
        C.need(budget.observe() is None,'ORIGINAL_QUOTA_MEMORY_BEFORE_QA_DATA');budget.start_monitor()
        from workflows.data_v1_final.conformers.portable_secondary_uff_v1.prepare_existing_controls import select_metadata
        C.need(C.ref(select_metadata.__code__.co_filename) in proof['request']['source_references']
          and pathlib.Path(select_metadata.__code__.co_filename).absolute()==C.REPO/'workflows/data_v1_final/conformers/portable_secondary_uff_v1/prepare_existing_controls.py',
          'ORIGINAL_FIXED_SELECTION_SOURCE_PIN_REQUIRED')
        from .test_binding import data_frame
        baseline_path=C.pinned(prep['original_complete_packages_reference'],C.CAP)
        C.need(not any(x.is_symlink() for x in (baseline_path,*baseline_path.parents)),'NO_BASELINE_METADATA_SYMLINK')
        with baseline_path.open('rb') as source:
            before=data_frame(prep['original_complete_packages_reference'],os.fstat(source.fileno()));closed=json.load(source)
            C.need(data_frame(prep['original_complete_packages_reference'],os.fstat(source.fileno()))==before
              and data_frame(prep['original_complete_packages_reference'],baseline_path.stat())==before
              and not any(x.is_symlink() for x in (baseline_path,*baseline_path.parents)),'ORIGINAL334_METADATA_FRAME_CHANGED')
        audit=E.meta(prep['original_audit_reference']);monitor=E.meta(prep['partial_audit_monitor_closure_reference'])
        C.need(len(closed)==334 and len({x['molecule_id'] for x in closed})==334 and audit['status']=='PARTIAL_PILOT_NOT_ACCEPTED_FOR_FORMAL'
          and audit['original_parent_state']=='TIMEOUT' and monitor['job_id']=='4520527'
          and monitor['status']=='COMPLETED_NO_MEMORY_DENIAL' and monitor['durable_evidence_exported'] is True,'ACTUAL_ORIGINAL334_BASELINE_AUTHORITY')
        chosen,selection=select_metadata(closed)
        C.need([x['molecule_id'] for x in chosen]==prep['molecule_ids'] and len(chosen)==16,'SAME_ORIGINAL_FIXED16_SELECTION_NOT_NEW_SAMPLING')
        for row in chosen:
            old=expected[row['molecule_id']]
            C.need(row['reference']==old['baseline_packet_reference'] and row['file_identity']==old['baseline_file_identity'],
              'EXACT_EXISTING334_BASELINE_PACKET_AND_FRAME_PROVENANCE')
        tasks={};path=C.pinned(prep['tasks_reference'],1<<30)
        C.need(not any(x.is_symlink() for x in (path,*path.parents)),'NO_TASK_SOURCE_SYMLINK')
        with path.open('rb') as stream:
            task_frame=data_frame(prep['tasks_reference'],os.fstat(stream.fileno()))
            while True:
                line=stream.readline((64<<20)+1)
                if not line:break
                C.need(len(line)<=64<<20,'BOUNDED_ORIGINAL_CONTROL_ENVELOPE')
                envelope=json.loads(line);task=envelope['task'];mid=task['meta']['molecule_id']
                C.need(mid in expected and mid not in tasks and C.sha_value(task)==expected[mid]['task_sha256'],
                  'EXACT_ORIGINAL16_NOT_NEW_SELECTION_OR_RECORD_RECODING');tasks[mid]=task
            C.need(data_frame(prep['tasks_reference'],os.fstat(stream.fileno()))==task_frame
              and data_frame(prep['tasks_reference'],path.stat())==task_frame
              and not any(x.is_symlink() for x in (path,*path.parents)),'TASK_SOURCE_FRAME_CHANGED')
        C.need(set(tasks)==set(expected) and len(tasks)==16,'ALL_SAME16_ORIGINAL_CONTROLS')
        context=mp.get_context('spawn');barrier=context.Barrier(16)
        with cf.ProcessPoolExecutor(max_workers=16,mp_context=context,initializer=initialize,
          initargs=(session,plan['config_reference'],plan['qa_sources'],barrier)) as pool:
            # One fixed batch only. Budget STOP prevents dispatch; running tasks drain.
            C.need(budget.observe() is None,'ORIGINAL_BUDGET_BEFORE_EXACT_QA16_DISPATCH')
            active={pool.submit(one,tasks[mid],expected[mid]):mid for mid in prep['molecule_ids']}
            while active:
                budget.observe(list(pool._processes.values()))
                done,_=cf.wait(active,timeout=1,return_when=cf.FIRST_COMPLETED)
                for future in done:
                    mid=active.pop(future)
                    try:results.append(future.result())
                    except Exception as exc:errors.append({'molecule_id':mid,'error':repr(exc)})
    except BaseException as exc:
        errors.append({'error':repr(exc),'traceback':traceback.format_exc()});raise
    finally:
        budget.close_monitor();passed=len(results)==16 and all(r['matches'] for r in results) and len({r['pid'] for r in results})==16 and not errors and budget.stop is None
        receipt={'schema':'MAIN17_ORIGINAL_UFF_CONTROL16_RECEIPT_V1','status':'EXACT16_ORIGINAL_SCIENTIFIC_SHA_MATCH' if passed else 'QA_INCOMPLETE_OR_DRIFT_HOLD',
          'node':C.NODE,'uid':1278,'job_id':str(proof['job_id']),'plan_reference':pr,'startup_proof_reference':C.ref(a.root_preflight),
          'node17_binding_reference':plan['node17_binding_reference'],'control_ids':prep['molecule_ids'],'results':results,
          'completed':len(results),'matched':sum(r['matches'] for r in results),'errors':errors,'budget':budget.report(),
          'environment':environment(),'source_references':C.own_sources(),'population_members_added':0,'production_once_accessed':False,
          'new_QM_calls':0,'whole_LMDB_SHA':'WHOLE_LMDB_SHA_NOT_ORIGINALLY_AVAILABLE_NOT_CLAIMED',
          'transitive_input_authority':'EXACT_ORIGINAL16_TASK_POINTERS_AND_ACTUAL334_BASELINES','original_LMDB_reader_used':True,'numeric_tolerance_added':False,'automatic_retry':False}
        C.need(len(C.canonical(receipt))<2<<20,'SMALL_QA_RECEIPT');R.write_json_new(out/'receipt.json',receipt)
    return 0 if passed else 3


if __name__=='__main__':raise SystemExit(main())
