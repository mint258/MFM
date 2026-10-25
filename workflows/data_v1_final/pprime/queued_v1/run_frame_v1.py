"""Run unchanged frame QM then unchanged evaluator in a strict Root allocation."""
from __future__ import annotations
import argparse,datetime,hashlib,json,os,pathlib,re,socket,subprocess,sys,traceback
ROOT=pathlib.Path('/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025')
PROJECT=ROOT.parent.parent
PY='/share/home/zixiao/.conda/envs/chemprop/bin/python'

def need(ok,message):
    if not ok:raise ValueError(message)

def ref(path):
    path=pathlib.Path(path);h=hashlib.sha256()
    with path.open('rb') as f:
        before=os.fstat(f.fileno())
        for block in iter(lambda:f.read(1024**2),b''):h.update(block)
        after=os.fstat(f.fileno())
    need((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)==(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns),'FILE_CHANGED_DURING_REF')
    return {'path':str(path),'bytes':before.st_size,'sha256':h.hexdigest()}

def load(path):return json.loads(pathlib.Path(path).read_text())

def write_new(path,obj):
    with pathlib.Path(path).open('x',encoding='utf-8') as f:json.dump(obj,f,indent=2,ensure_ascii=False,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan',type=pathlib.Path,required=True);parser.add_argument('--root-preflight',type=pathlib.Path,required=True)
    a=parser.parse_args();plan=load(a.plan);proof=load(a.root_preflight);request=proof['request']
    need(plan['schema']=='PPRIME_VECTOR_FRAME_STRICT_QUEUE_PLAN_V1' and plan['expected_calls']==72 and plan['production_membership'] is False,'EXACT_ISOLATED_FRAME_PLAN_REQUIRED')
    node=socket.gethostname().split('.')[0]
    need(os.name=='posix' and os.getuid()==1278 and os.environ.get('SLURM_JOB_ID','').isdecimal() and node in plan['allowed_nodes'],'REAL_OWNER_SLURM_CPU14_TO19_REQUIRED')
    need(os.environ.get('SLURM_JOB_PARTITION')=='cpu' and int(os.environ.get('SLURM_CPUS_PER_TASK','0'))==16
         and int(os.environ.get('SLURM_MEM_PER_NODE','0'))>=64*1024,'ACTUAL_CPU16_MEMORY64G_REQUIRED')
    need(os.environ.get('CUDA_VISIBLE_DEVICES')=='' and all(os.environ.get(k)=='1' for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS')),'CPU_ONLY_ONE_THREAD_WORKERS_REQUIRED')
    need(request['kind']=='qm' and request['pilot'] is True and request['cpus']==16 and request['memory_gib']==64
         and request['wall_seconds']==7200 and request['node']==node and not request.get('resource_policy') and not request.get('memory_basis'),'STRICT_NEW_ORDINARY_QM_REQUEST_REQUIRED')
    need(proof['uid']==1278 and request['root_review']['status']=='APPROVED','NEW_ROOT_EXECUTION_ADMISSION_REQUIRED')
    age=datetime.datetime.now(datetime.timezone.utc).timestamp()-datetime.datetime.fromisoformat(proof['observed_at']).timestamp()
    need(0<=age<=3600,'FRESH_EXECUTION_PROOF_REQUIRED_NOT_QUEUE_TIME_PROOF')
    sources=request['source_references'];by_path={p['path']:p for p in sources}
    need(by_path.get(str(a.plan))==ref(a.plan) and by_path.get(str(pathlib.Path(__file__).absolute()))==ref(pathlib.Path(__file__).absolute()),'ACTUAL_PLAN_AND_WRAPPER_MUST_BE_PINNED')
    need(str(a.root_preflight)==plan['execution_intent_path'],'EXACT_EXECUTION_INTENT_PATH_REQUIRED')
    for pin in plan['source_references']:
        need(by_path.get(pin['path'])==pin and ref(pin['path'])==pin,'REVIEWED_FRAME_SOURCE_CHANGED:'+pin['path'])
    for job in proof['existing_jobs_all_users']:
        values=re.findall(r'(?:^|\s)MinMemory(?:Node|CPU)=([^\s]+)',job['metadata'])
        need(len(values)==1 and not re.fullmatch(r'0[KMGTP]?',values[0]),'FOREIGN_UNBOUNDED_MEMORY_BLOCKS_FRAME_QM')
    real=re.search(r'(?:^|\s)RealMemory=(\d+)(?:\s|$)',proof['node_metadata'])
    need(real and proof['committed_memory_mib']+64*1024<=.85*int(real[1]),'ALL_USER_DECLARED_MEMORY85_REQUIRED')
    need(proof['account_free_bytes']-plan['estimated_peak_output_bytes']>=plan['quota_reserve_bytes'],'WHOLE_QUEUE_OUTPUT_RESERVE_REQUIRED')
    prefix=pathlib.Path(plan['output_prefix']);out=pathlib.Path(plan['run_output']);evaluation=pathlib.Path(plan['evaluation_output'])
    need(prefix.parent==ROOT/'artifacts/vector_frame_audit' and out==prefix/'run' and not prefix.exists(),'NEW_FRAME_OUTPUT_ONLY_NO_RETRY')
    prefix.mkdir(mode=0o700)
    write_new(prefix/'queue_start.json',{'status':'FRAME_QM_OUTCOME_UNKNOWN_UNTIL_CLOSED','plan':ref(a.plan),'root_preflight':ref(a.root_preflight),
        'job_id':os.environ['SLURM_JOB_ID'],'node':node,'production_membership':False,'automatic_retry':False})
    c=plan['config']['path'];pilot=plan['pilot_config']['path'];prepared=pathlib.Path(plan['prepared']['path'])
    qm_argv=[PY,'-B',plan['original_source']['path'],'--execute','--config',c,'--pilot-config',pilot,
        '--prepared',str(prepared.parent),'--prepared-sha256',plan['prepared']['sha256'],'--root-preflight',str(a.root_preflight),'--output',str(out)]
    eval_argv=[PY,'-B',plan['original_evaluator']['path'],'--config',c,'--run',str(out),'--output',str(evaluation)]
    records=[];error=None;qm_code=eval_code=None;closed=report=None
    try:
        # Only process CWD changes: the frozen engine uses PROJECT-relative reproduction assets.
        qm_code=subprocess.run(qm_argv,cwd=PROJECT,stdin=subprocess.DEVNULL).returncode
        if (out/'run_closed.json').is_file():
            closed=load(out/'run_closed.json')
            eval_code=subprocess.run(eval_argv,cwd=PROJECT,stdin=subprocess.DEVNULL).returncode
            if evaluation.is_file():report=load(evaluation)
            for pin in closed['results']:
                need(ref(pin['path'])==pin,'CLOSED_FRAME_RESULT_CHANGED')
                records.append(load(pin['path']))
    except Exception as exc:error={'type':type(exc).__name__,'message':str(exc),'traceback':traceback.format_exc()}
    pids=sorted({r['pid'] for r in records});calls=sum(r.get('QM_call_attempted') is True for r in records)
    raw_durable=sum(r.get('raw_reference',{}).get('raw_call_durable') is True for r in records)
    parsed_complete=sum(r.get('status')=='CONTROL_CALL_RETAINED_AND_PARSED' for r in records)
    supported=(error is None and qm_code==eval_code==0 and closed and len(records)==72 and calls==72 and len(pids)==16
        and raw_durable==parsed_complete==72 and closed['all_workers_joined'] is True and not closed['execution_errors'] and report
        and report['status']==plan['required_frame_status'] and not report['contradictions'] and not report['incomplete'])
    receipt={'schema':'PPRIME_QUEUED_FRAME_ACTUAL_EXECUTION_V1',
        'status':'ACTUAL_FRAME_CONTROLS_PASS_WITH_LIMITS' if supported else 'ACTUAL_FRAME_NOT_ACCEPTED_KEEP_RAW_AND_REPORT_ROOT',
        'job_id':os.environ['SLURM_JOB_ID'],'node':node,'plan':ref(a.plan),'root_preflight':ref(a.root_preflight),
        'qm_argv':qm_argv,'evaluation_argv':eval_argv,'working_directory':str(PROJECT),'qm_returncode':qm_code,'evaluation_returncode':eval_code,
        'actual_cases_closed':len(records),'QM_calls_attempted':calls,'actual_worker_pids':pids,
        'frame_evaluation_status':report.get('status') if report else None,
        'execution_closure':ref(out/'run_closed.json') if (out/'run_closed.json').is_file() else None,
        'evaluation':ref(evaluation) if evaluation.is_file() else None,'error':error,'production_membership':False,
        'actual_durable_raw_calls':raw_durable,'actual_independently_parsed_cases':parsed_complete,
        'all72_output_raw_retained':raw_durable==72,'source_recipe_or_keywords_changed':False,
        'signals_sent':False,'automatic_retry':False,'all_corpus_frames_verified':False,'2000_pilot_or_full_release':False,
        'actual_parent_cost':'Root must attach actual terminal sacct parent, including failures and wrapper/evaluation startup; worker seconds are not allocated cost.'}
    write_new(plan['queue_receipt_output'],receipt)
    print(json.dumps({'status':receipt['status'],'receipt':ref(plan['queue_receipt_output']),'actual_cases_closed':len(records),'QM_calls_attempted':calls}))
    return 0 if supported else 3
if __name__=='__main__':sys.exit(main())
