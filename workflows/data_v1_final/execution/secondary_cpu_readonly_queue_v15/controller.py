"""Foreground Alpha login controller: one held submission, finite observation."""
from __future__ import annotations
import argparse,csv,fcntl,io,json,math,os,re,shlex,socket,subprocess,time,traceback
from pathlib import Path
from . import adapters
from secondary_cpu_queue_v1.common import (ROOT,ENDPOINT,UID,PACKAGE,POLICY,Heartbeat,need,event,now,canonical,sha,literal,
    read_small,ref,verify,load,write_new,source_review,authority,login,wall,fields,query,job_identity,
    free_cpus,storage_observation,effective_storage,self_identity,state)

TERMINAL={'COMPLETED','FAILED','TIMEOUT','CANCELLED','OUT_OF_MEMORY','NODE_FAIL','PREEMPTED','BOOT_FAIL','DEADLINE','REVOKED'}
CONTROL=ROOT/'control/secondary_cpu_queue'


def lock(path):
    path=literal(path);path.parent.mkdir(parents=True,exist_ok=True)
    fd=os.open(path,os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
    info=os.fstat(fd);need(info.st_uid==UID and info.st_nlink==1,'OWN_CONTROLLER_LOCK_REQUIRED')
    fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
    return fd


def atomic_text(path,text):
    path=literal(path);path.parent.mkdir(parents=True,exist_ok=True)
    need(len(text.encode())<=2*1024**2,'SMALL_ACTUAL_SCRIPT_REQUIRED')
    fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'w') as stream:stream.write(text);stream.flush();os.fsync(stream.fileno())
    return ref(path)


def script_for(request_path,node,name,seconds,python,log_path,scope_key):
    need(scope_key in adapters.PROTOCOLS,'EXACT_V15_TWO_DIAGNOSES_SCRIPT_SCOPE_REQUIRED')
    pythonpath=str(ROOT/'code')
    gate=[python,'-B','-m','secondary_cpu_queue_v1.gate','--request',str(request_path)]
    # These are the complete directives. No user body, environment or flag is appended.
    text='\n'.join(['#!/bin/bash','#SBATCH --job-name='+name,'#SBATCH --partition=cpu',
        '#SBATCH --nodelist='+node,'#SBATCH --nodes=1','#SBATCH --ntasks=1','#SBATCH --cpus-per-task=16',
        '#SBATCH --time='+wall(seconds),'#SBATCH --no-requeue','#SBATCH --chdir='+str(ROOT),
        '#SBATCH --output='+str(log_path),'set -euo pipefail',
        'export CUDA_VISIBLE_DEVICES="" PYTHONDONTWRITEBYTECODE=1',
        'export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1',
        'export PYTHONPATH='+shlex.quote(pythonpath),
        'cd '+shlex.quote(str(ROOT/'code')),'exec '+shlex.join(gate),''])
    need(not any(word in text for word in ('#SBATCH --mem','#SBATCH --exclusive','#SBATCH --gres','#SBATCH --gpu')),
         'GENERATED_SCRIPT_MUST_HAVE_NO_MEMORY_EXCLUSIVE_OR_GPU')
    return text,gate


def prepare(args):
    need(args.reviewer=='root','EXPLICIT_ROOT_CONTROLLER_INVOCATION_REQUIRED')
    review=source_review(args.controller_review);authorized=authority(args.authority);wall(args.wall_seconds)
    need(args.node in authorized.get('actual_cpu_nodes',authorized.get('target',{}).get('allowed_cpu_nodes',[])) and
         args.wall_seconds<=authorized['max_wall_seconds'],'EXACT_AUTHORIZED_CPU_NODE_AND_WALL_REQUIRED')
    need(re.fullmatch(r'[a-z][a-z0-9_]{0,95}',args.job_name),'NEW_SAFE_JOB_NAME_REQUIRED')
    output=literal(args.output)
    need(CONTROL in output.parents and not output.exists(),'NEW_CONTROLLER_OUTPUT_CHILD_REQUIRED')
    need(args.producer=='readonly','ONLY_EXACT_TWO_READONLY_DIAGNOSES_ALLOWED')
    adapter=adapters.readonly(args.input,args.deployment,args.node,args.wall_seconds)
    # Authority passed to the controller must be the exact actual producer authority.
    need(adapter['producer_authority_reference']==ref(args.authority),'CONTROLLER_AND_PRODUCER_AUTHORITY_DIFFERS')
    proof=literal(adapter['startup_proof_path']);ready=proof.with_suffix(proof.suffix+'.controller_ready.json')
    need(not proof.exists() and not ready.exists() and not Path(adapter['science_output']).exists(),'NEW_PROOF_AND_SCIENCE_OUTPUT_REQUIRED')
    need(Path(adapter['producer_argv'][0]).is_absolute(),'ABSOLUTE_VERIFIED_PRODUCER_PYTHON_REQUIRED')
    # This reads only Root storage-scope metadata, never a producer body.
    need(literal(args.storage_review)==adapters.STORAGE_SCOPE,'EXACT_CURRENT_DIAGNOSIS_SCOPE7_REQUIRED')
    load(args.storage_review)
    output.mkdir(parents=True,mode=0o700)
    request_path=output/'request.json';script=output/'job.sbatch'
    text,gate=script_for(request_path,args.node,args.job_name,args.wall_seconds,adapter['producer_argv'][0],output/'slurm_%j.out',adapter['scope_key'])
    script_ref=atomic_text(script,text)
    verified={r['path']:r for r in adapter['source_references']}
    for row in review['sources']:verified[row['target_locator']['path']]=row['target_locator']
    for path in (args.controller_review,args.authority,args.storage_review,args.input):verified[str(path)]=ref(path)
    if args.deployment is not None:verified[str(args.deployment)]=ref(args.deployment)
    request={'schema':'ROOT_SECONDARY_CPU_HELD_REQUEST_V1','endpoint':ENDPOINT,'uid':UID,'job_name':args.job_name,
        'node':args.node,'partition':'cpu','cpus':16,'wall_seconds':args.wall_seconds,'memory_policy':POLICY,
        'memory_requested':False,'exclusive_requested':False,'no_requeue':True,'created_at':now(),
        'kind':adapter['request_kind'],'pilot':adapter['pilot'],'scope_key':adapter['scope_key'],
        'scope_parameters':adapter['scope_parameters'],'stage':adapter['stage'],
        'scope_mode':adapter['scope_mode'],'performance_profile':adapter['performance_profile'],
        'controller_review_reference':ref(args.controller_review),'authority_reference':ref(args.authority),
        'storage_review_reference':ref(args.storage_review),'adapter':adapter,'script_reference':script_ref,
        'gate_argv':gate,'ready_path':str(ready),'verified_target_references':list(verified.values()),
        'producer_is_executed_only_after_login_controller_proof':True,'automatic_submission_retry':False,
        'data_body_hashes_or_scientific_acceptance_claimed':False}
    write_new(request_path,request)
    return output,request_path,request


def revalidate(request):
    need(request.get('schema')=='ROOT_SECONDARY_CPU_HELD_REQUEST_V1' and request.get('uid')==UID and
         request.get('endpoint')==ENDPOINT and request.get('cpus')==16 and request.get('memory_policy')==POLICY,
         'ACTUAL_OWN_SECONDARY_REQUEST_REQUIRED')
    wall(request['wall_seconds']);source_review(request['controller_review_reference']['path'])
    authority(request['authority_reference']['path'])
    for value in request['verified_target_references']:verify(value)
    verify(request['script_reference'])
    adapter=request['adapter']
    need(adapter['producer']=='readonly','ONLY_EXACT_TWO_READONLY_DIAGNOSES_ALLOWED')
    actual=adapters.readonly(adapter['input_reference']['path'],None,request['node'],request['wall_seconds'])
    need(request.get('kind')==adapter['request_kind']=='analysis' and request.get('pilot') is adapter['pilot']
        and request.get('scope_key')==adapter['scope_key'] and request.get('scope_parameters')==adapter['scope_parameters']
        and request.get('stage')==adapter['stage'] and request.get('scope_mode')==adapter['scope_mode']
        and request.get('performance_profile') is adapter['performance_profile'],'HONEST_PHASE_SPECIFIC_READONLY_REQUEST_REQUIRED')
    need(actual==adapter,'ROOT_REVIEWED_PRODUCER_METADATA_CHANGED')
    return True


def submit_held(output,request_path,request):
    claims=CONTROL/'claims';claims.mkdir(parents=True,exist_ok=True)
    with (claims/(request['job_name']+'.json')).open('xb') as stream:
        stream.write(canonical({'queue_request_reference':ref(request_path),'created_at':now(),'automatic_retry':False}));stream.flush();os.fsync(stream.fileno())
    before=query(['squeue','-h','-u','alpha','-o','%i|%j|%T|%N'])
    need(all(len(parts)<2 or parts[1]!=request['job_name'] for parts in (line.split('|') for line in before['stdout'].splitlines())),
         'DUPLICATE_EXISTING_ALPHA_JOB_NAME_NO_SUBMISSION')
    env={key:value for key,value in os.environ.items() if not key.startswith('SBATCH_')}
    argv=['sbatch','--parsable','--hold','--no-requeue',request['script_reference']['path']]
    intent={'schema':'SECONDARY_CPU_SUBMISSION_INTENT_V1','endpoint':ENDPOINT,'uid':UID,'queue_request_reference':ref(request_path),
        'script_reference':request['script_reference'],'submission_argv':argv,'queue_before':before,
        'removed_sbatch_environment_keys':sorted(set(os.environ)-set(env)),'memory_requested':False,
        'exclusive_requested':False,'submission_always_held':True,'automatic_retry':False,'created_at':now()}
    write_new(output/'submission_intent.json',intent)
    event('PENDING_ACTUAL_HELD_SBATCH',job_name=request['job_name'])
    try:
        result=subprocess.run(argv,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=20,env=env)
    except subprocess.TimeoutExpired:
        write_new(output/'submission.json',{**intent,'status':'SUBMISSION_OUTCOME_UNKNOWN_NO_RETRY','job_id':None,
            'all_attempts_require_actual_endpoint_accounting':True})
        raise ValueError('ACTUAL_SBATCH_OUTCOME_UNKNOWN_ROOT_RECONCILIATION_REQUIRED_NO_RETRY')
    need(len(result.stdout.encode())+len(result.stderr.encode())<=2*1024**2,'SUBMISSION_METADATA_LIMIT')
    jid=result.stdout.strip().split(';')[0] if result.returncode==0 else None
    row={**intent,'sbatch_returncode':result.returncode,'stdout':result.stdout,'stderr':result.stderr,
        'job_id':jid,'status':'SUBMITTED_HELD' if result.returncode==0 and jid.isdecimal() else 'FAILED_OR_UNKNOWN_NO_RETRY',
        'all_attempts_require_actual_endpoint_accounting':True}
    write_new(output/'submission.json',row)
    need(result.returncode==0 and jid.isdecimal(),'ACTUAL_HELD_JOB_ID_UNAVAILABLE_NO_RETRY')
    ids=claims/'job_ids';ids.mkdir(exist_ok=True)
    write_new(ids/(jid+'.json'),{'job_id':jid,'submission_reference':ref(output/'submission.json'),'endpoint':ENDPOINT,'uid':UID})
    raw=query(['scontrol','show','job',jid,'--oneliner']);job_identity(request,raw['stdout'],jid,held=True)
    write_new(output/'held_verification.json',{'job_id':jid,'actual_query':raw,'exact_own_held_job_verified':True})
    return row


def pending(output,jid,status,**details):
    # Append-only per-invocation receipt; no rewrite of old pending/terminal observations.
    name='status_'+str(time.time_ns())+'.json'
    write_new(output/name,{'schema':'SECONDARY_CPU_CONTROLLER_STATUS_V1','endpoint':ENDPOINT,'uid':UID,'job_id':jid,
        'status':status,'observed_at':now(),'automatic_retry_or_cancel':False,'all_actual_parent_costs_required':True,**details})
    event(status,job_id=jid,**details)
    return 2


def outstanding_caps(request_path,request):
    """Reserve all registered pending/active/unknown task caps on this mount."""
    total=request['adapter']['output_cap_bytes'];rows=[]
    for path in sorted((CONTROL/'claims').glob('*.json')):
        claim=load(path);reference=claim['queue_request_reference']
        if reference==ref(request_path):continue
        previous=load(verify(reference));folder=Path(reference['path']).parent;submission_path=folder/'submission.json'
        if not submission_path.exists():
            if not (folder/'submission_intent.json').exists():continue
            status='SUBMISSION_OUTCOME_UNKNOWN_NO_RECEIPT';actual=None
        else:
            sub=load(submission_path)
            if sub.get('sbatch_returncode') not in (None,0):continue
            jid=sub.get('job_id');actual=None
            if isinstance(jid,str) and jid.isdecimal():
                actual=query(['sacct','-j',jid,'--format=JobIDRaw,State','-n','-P'],allow_failure=True)
                parents=[line.split('|') for line in actual['stdout'].splitlines() if line.split('|')[0]==jid]
                if actual['returncode']==0 and len(parents)==1:
                    status=state(parents[0][1])
                    if status in TERMINAL:continue
                else:status='ACCOUNTING_PENDING_OR_UNAVAILABLE_CAP_NOT_RELEASED'
            else:status='SUBMISSION_OUTCOME_UNKNOWN_NO_GUESSED_ZERO_CAP'
        cap=previous['adapter']['output_cap_bytes'];need(type(cap) is int and cap>0,'REGISTERED_WHOLE_CAP_INVALID')
        total+=cap;rows.append({'queue_request_reference':reference,'whole_output_cap_bytes':cap,'status':status,'actual_accounting':actual})
    return total,{'current_task_whole_cap_bytes':request['adapter']['output_cap_bytes'],'other_registered_outstanding_tasks':rows,
                  'registered_whole_caps_bytes':total,'actual_terminal_parent_caps_not_reserved_twice_against_existing_disk_use':True}


def observe(output,request_path,request,submission,max_seconds):
    jid=submission['job_id'];need(isinstance(jid,str) and jid.isdecimal(),'ACTUAL_EXISTING_JOB_ID_REQUIRED')
    need(submission['queue_request_reference']==ref(request_path) and submission.get('sbatch_returncode')==0,
         'EXACT_EXISTING_SUBMISSION_REQUEST_REQUIRED')
    revalidate(request)
    proof_path=Path(request['adapter']['startup_proof_path']);ready_path=Path(request['ready_path'])
    if ready_path.exists():
        ready=load(ready_path)
        need(ready['job_id']==jid and ready['queue_request_reference']==ref(request_path) and ready['proof_reference']==ref(proof_path),
             'EXISTING_OWN_READY_PROOF_CHANGED')
        event('EXISTING_PROOF_ALREADY_PUBLISHED_NO_RETRY',job_id=jid);return 0
    need(not proof_path.exists(),'PARTIALLY_PUBLISHED_PROOF_REQUIRES_ROOT_RECONCILIATION')
    raw=query(['scontrol','show','job',jid,'--oneliner']);job=fields(raw['stdout'])
    if job.get('JobState')=='PENDING' and job.get('Reason')=='JobHeldUser':
        job_identity(request,raw['stdout'],jid,held=True)
        cpus=free_cpus(request)
        if cpus['free_cpus']<16:return pending(output,jid,'PENDING_HELD_WAIT_FREE_CPU',cpu_observation=cpus)
        observed=storage_observation()
        reserved,reservations=outstanding_caps(request_path,request)
        try:effective=effective_storage(observed,request['storage_review_reference']['path'],reserved,reservation_evidence=reservations)
        except ValueError as exc:
            if str(exc).startswith('WAIT_EFFECTIVE_FREE'):return pending(output,jid,'PENDING_HELD_WAIT_EFFECTIVE_FREE',error=str(exc))
            raise
        admission=write_new(output/('held_admission_'+str(time.time_ns())+'.json'),
            {'job_id':jid,'cpu_observation':cpus,'storage_observation':observed,'effective_storage':effective,
             'memory_admission_evaluated':False,'other_jobs_modified':False})
        # Recheck exact same own held job after resource queries, immediately before release.
        before_release=query(['scontrol','show','job',jid,'--oneliner']);job_identity(request,before_release['stdout'],jid,held=True)
        sequence=str(time.time_ns())
        write_new(output/('release_intent_'+sequence+'.json'),{'job_id':jid,'queue_request_reference':ref(request_path),
            'held_admission_reference':admission,'held_readback':before_release,'only_this_exact_owned_job':True})
        released=query(['scontrol','release',jid])
        write_new(output/('release_result_'+sequence+'.json'),released)
    started=time.monotonic();last_probe_error=None
    while time.monotonic()-started<max_seconds:
        current=query(['scontrol','show','job',jid,'--oneliner']);job=fields(current['stdout']);state=job.get('JobState','UNKNOWN')
        if state in TERMINAL:
            account=query(['sacct','-j',jid,'--format=JobIDRaw,State,ExitCode,ElapsedRaw,AllocCPUS,NodeList,Partition,TotalCPU,MaxRSS','-n','-P'],allow_failure=True)
            return pending(output,jid,'TERMINAL_BEFORE_PROOF_ACCOUNT_PARENT_AND_STEPS',actual_job=current,actual_accounting=account)
        if state=='RUNNING':
            job_identity(request,current['stdout'],jid)
            remote=['env','PYTHONDONTWRITEBYTECODE=1','PYTHONPATH='+str(ROOT/'code'),request['adapter']['producer_argv'][0],
                '-B','-m','secondary_cpu_queue_v1.probe','--request',str(request_path),'--job-id',jid]
            probe_started=time.monotonic()
            answer=query(['ssh','-n','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','ConnectTimeout=8',
                request['node'],shlex.join(remote)],allow_failure=True,timeout=55)
            if answer['returncode']!=0:
                last_probe_error=answer;event('PENDING_ACTUAL_GATE_METADATA',job_id=jid)
            else:
                probe=json.loads(answer['stdout'])
                need(probe['schema']=='SECONDARY_CPU_ACTUAL_TARGET_METADATA_V1' and probe['uid']==UID and
                     probe['node']==request['node'] and probe['job_id']==jid and probe['queue_request_reference']==ref(request_path) and
                     type(probe['observed_unix_seconds']) in (int,float) and math.isfinite(probe['observed_unix_seconds']) and
                     0<=time.monotonic()-probe_started<=90,'FRESH_ACTUAL_TARGET_PROBE_REQUIRED')
                revalidate(request)
                reserved,reservations=outstanding_caps(request_path,request)
                storage=effective_storage(probe['storage'],request['storage_review_reference']['path'],reserved,reservation_evidence=reservations)
                need(0<=time.monotonic()-probe_started<=90,'FRESH_ACTUAL_TARGET_STORAGE_REQUIRED')
                # Bind the actual RUNNING snapshot after the probe to avoid signing a stopped/replaced job.
                fresh=query(['scontrol','show','job',jid,'--oneliner']);actual=job_identity(request,fresh['stdout'],jid)
                storage_ref=write_new(output/'actual_target_storage.json',probe['storage'])
                probe_ref=write_new(output/'actual_target_probe.json',probe)
                running_ref=write_new(output/'actual_running_job.json',fresh)
                controller={'schema':'SECONDARY_LOGIN_CONTROLLER_PROOF_ORIGIN_V1','endpoint':ENDPOINT,'uid':UID,
                    'hostname':socket.gethostname().split('.')[0],'pid':os.getpid(),
                    'login_boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
                    'queue_request_reference':ref(request_path),'submission_reference':ref(output/'submission.json'),
                    'controller_source_review_reference':request['controller_review_reference'],'actual_script_reference':request['script_reference'],
                    'actual_login_controller_process':self_identity(),
                    'actual_gate_probe_reference':probe_ref,'actual_running_metadata_reference':running_ref,
                    'proof_is_not_created_by_scientific_worker':True,'scientific_data_bodies_read':False}
                proof=adapters.startup_proof(request,jid,fresh['stdout'],actual,probe,storage,storage_ref,controller)
                proof['target_probe_observed_unix_seconds']=probe['observed_unix_seconds']
                proof['root_login_observed_unix_seconds']=fresh['observed_unix_seconds']
                elapsed=time.monotonic()-probe_started;need(0<=elapsed<=90,'NO_STALE_PROOF_PUBLICATION')
                proof['root_login_probe_query_to_publication_monotonic_seconds']=elapsed
                proof['freshness_basis']='Compute observed_unix_seconds unchanged; login query-start-to-publication monotonic upper bound90s. Consumer compute120s/acquisition300s gates unchanged.'
                proof_reference=write_new(proof_path,proof)
                need(0<=time.monotonic()-probe_started<=90,'NO_STALE_READY_PUBLICATION')
                ready_reference=write_new(ready_path,{'job_id':jid,'proof_reference':proof_reference,'queue_request_reference':ref(request_path)})
                write_new(output/'proof_publication.json',{'job_id':jid,'proof_reference':proof_reference,'ready_reference':ready_reference,
                    'actual_terminal_parent_cost_pending':True,'science_or_download_acceptance_granted':False})
                event('ACTUAL_ALPHA_STARTUP_PROOF_PUBLISHED',job_id=jid,proof_reference=proof_reference)
                return 0
        else:event('PENDING_ACTUAL_ALPHA_JOB',job_id=jid,state=state,reason=job.get('Reason'))
        time.sleep(min(5,max(0,max_seconds-(time.monotonic()-started))))
    return pending(output,jid,'PENDING_FINITE_OBSERVATION_DEADLINE_NO_CANCEL',last_probe_error=last_probe_error,
        note='No service remains. Root may resume this same job; a running gate itself has a120s finite limit.')


def account(output):
    """Endpoint-owned parent plus steps. Never infer zero cost for missing evidence."""
    output=literal(output);request_path=output/'request.json';request=load(request_path);submission=load(output/'submission.json')
    need(submission.get('queue_request_reference')==ref(request_path) and submission.get('sbatch_returncode')==0 and
         isinstance(submission.get('job_id'),str) and submission['job_id'].isdecimal(),'KNOWN_ACTUAL_SUBMISSION_REQUIRED_NO_GUESSED_JOB_ID')
    jid=submission['job_id'];result=query(['sacct','-j',jid,
        '--format=JobIDRaw,User,UID,State,ExitCode,ElapsedRaw,AllocCPUS,NodeList,Partition,TotalCPU,MaxRSS','-P'])
    rows=list(csv.DictReader(io.StringIO(result['stdout']),delimiter='|'));parents=[row for row in rows if row.get('JobIDRaw')==jid]
    need(len(parents)==1 and parents[0].get('UID')==str(UID) and parents[0].get('Partition')=='cpu',
         'EXACT_ALPHA_ACCOUNTING_PARENT_OWNER_REQUIRED')
    parent=parents[0];elapsed=int(parent['ElapsedRaw']);cpus=int(parent['AllocCPUS'])
    need(elapsed>=0 and 0<=cpus<=16,'ACTUAL_ACCOUNTING_ALLOCATION_INVALID')
    stamp=str(time.time_ns());raw_reference=atomic_text(output/('sacct_'+stamp+'.txt'),result['stdout'])
    evidence={'schema':'SECONDARY_CPU_ACTUAL_ACCOUNTING_EVIDENCE_V1','endpoint':ENDPOINT,'uid':UID,
        'query_returncode':result['returncode'],'command_argv':result['argv'],'raw_sacct_reference':raw_reference,
        'observed_at':result['observed_at'],'job_id':jid,'queue_request_reference':ref(request_path),
        'actual_parent':parent,'actual_terminal':state(parent['State']) in TERMINAL,
        'allocated_core_seconds_observed':elapsed*cpus,'elapsed_zero_is_integer_floor_not_true_zero_claim':True,
        'steps_preserved_without_double_counting':[row for row in rows if row.get('JobIDRaw','').startswith(jid+'.')],
        'failed_and_startup_only_parents_are_in_scope':True,'science_acceptance_claimed':False}
    reference=write_new(output/('accounting_'+stamp+'.json'),evidence)
    event('ACTUAL_ALPHA_PARENT_AND_STEPS_RECORDED',job_id=jid,evidence_reference=reference,
          actual_terminal=evidence['actual_terminal'],allocated_core_seconds_observed=elapsed*cpus)
    return 0


def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='action',required=True)
    prepare_parser=sub.add_parser('submit')
    prepare_parser.add_argument('--producer',choices=('readonly',),required=True)
    for name in ('input','authority','storage-review','controller-review','output'):
        prepare_parser.add_argument('--'+name,type=Path,required=True)
    prepare_parser.add_argument('--deployment',type=Path)
    for name in ('node','job-name','reviewer'):prepare_parser.add_argument('--'+name,required=True)
    prepare_parser.add_argument('--wall-seconds',type=int,required=True)
    prepare_parser.add_argument('--max-poll-seconds',type=int,default=90)
    resume=sub.add_parser('resume');resume.add_argument('--output',type=Path,required=True);resume.add_argument('--max-poll-seconds',type=int,default=90)
    storage=sub.add_parser('storage-evidence');storage.add_argument('--output',type=Path,required=True)
    accounting=sub.add_parser('account');accounting.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();login()
    with Heartbeat():
        if args.action=='storage-evidence':
            evidence=storage_observation();reference=write_new(args.output,evidence)
            event('ACTUAL_STORAGE_OBSERVED_NO_QUOTA_ADMISSION_CLAIM',evidence_reference=reference);return 0
        if args.action=='account':return account(args.output)
        need(type(args.max_poll_seconds) is int and 5<=args.max_poll_seconds<=1200,'FINITE_MAX20MIN_FOREGROUND_POLL_REQUIRED')
        fd=lock(CONTROL/'controller.lock');output=None
        try:
            if args.action=='submit':
                output,request_path,request=prepare(args);submission=submit_held(output,request_path,request)
            else:
                output=literal(args.output);request_path=output/'request.json';request=load(request_path);submission=load(output/'submission.json')
            return observe(output,request_path,request,submission,args.max_poll_seconds)
        except Exception as exc:
            if output is not None:
                write_new(output/('controller_error_'+str(time.time_ns())+'.json'),{'endpoint':ENDPOINT,'uid':UID,
                    'error':str(exc),'type':type(exc).__name__,'traceback':traceback.format_exc(),
                    'automatic_cancel_or_retry':False,'all_actual_submission_outcomes_and_costs_require_root_accounting':True})
            event('CONTROLLER_STOPPED_NO_CANCEL_OR_RETRY',error=str(exc));raise
        finally:os.close(fd)


if __name__=='__main__':raise SystemExit(main())
