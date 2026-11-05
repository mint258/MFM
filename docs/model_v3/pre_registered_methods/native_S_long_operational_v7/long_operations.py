"""Root-only prepare/validate/dryrun/submit-next for the frozen native B plan.

Importing performs no filesystem mutation, reservation, Slurm or model action.
"""
from __future__ import annotations
import argparse
from contextlib import contextmanager
from copy import deepcopy
import fcntl
import json
import os
from pathlib import Path
import re
import time
from long_common import *


@contextmanager
def lock(phase):
    with (Path(phase)/'control/.dispatch.lock').open('a') as stream:
        fcntl.flock(stream,fcntl.LOCK_EX|fcntl.LOCK_NB);yield


def draft(phase,runtime_ready,registry,pins_sha):
    root_identity();manifest,_=verify(pins_sha)
    phase=Path(phase).absolute();require(phase.parent==N and not phase.exists(),'Fresh immediate N lineage required')
    ready_ref=binding(runtime_ready);ready=read_ref(ready_ref);contract_ref=ready['contract']
    require(ready['schema']=='native_S_launch_candidate_ready_v1'
        and ready['status']=='PROFILE_ONLY_RUNTIME_READY' and ready['production_20k_allowed'] is False,
        'Original profile-only READY scope must remain false; it is not science admission')
    require(binding(contract_ref['path'])==contract_ref,'READY raw contract reference changed')
    contract,_=import_runtime(contract_ref['path'],metadata_only=True)
    phase.mkdir(mode=0o700);(phase/'control').mkdir();(phase/'logs').mkdir();(phase/'slots').mkdir()
    (phase/'lineages').mkdir();(phase/'control/attempts').mkdir();(phase/'control/leases').mkdir()
    value=dict(schema='native_S_long_draft_v1',status='METADATA_ONLY_WAITING_ACTUAL_READINESS_C0',
        phase=str(phase),package_manifest=manifest,runtime_ready=ready_ref,runtime_contract=contract_ref,
        registry=str(Path(registry).absolute()),policy=policy(),plan=binding(HERE/'long_policy.json'),
        scientific_code_sha=CODE,scientific_prereg_sha=PUBLIC,production_allowed=False,
        quota_reserved=False,future_state_unknown_is_zero=False,
        observed_runtime_flags=dict(READY_status=ready['status'],READY_production_20k_allowed=ready['production_20k_allowed'],
            contract_status=contract['status'],contract_production_20k_allowed=contract['production_20k_allowed'],
            meaning='verbatim observed independent layers; neither grants this DRAFT science admission'))
    return write(phase/'control/DRAFT.json',value)


def evidence_sources(profile):
    mapping=dict(sdk_verifier='native_SDK_verification',future_state='future_state_certificate',
        precision_verifier='selective_precision_certificate',closed_census='closed_output_census',
        accounting_runner='accounting_certificate')
    result={}
    for role,key in mapping.items():
        refs=[read_ref(profile['measurements'][mode][key])['producer_source'] for mode in ('fp32','bf16')]
        require(refs[0]==refs[1],'Both precision proofs must use the same actual source for '+role)
        require(binding(refs[0]['path'])==refs[0],'Actual evidence producer source changed')
        result[role]=refs[0]
    readers=[read_ref(profile['measurements'][mode]['native_SDK_verification'])['history_reader_source']
        for mode in ('fp32','bf16')]
    require(readers[0]==readers[1],'Both precision proofs must use the same actual bounded reader')
    require(binding(readers[0]['path'])==readers[0],'Actual bounded reader source changed')
    result['sdk_history_reader']=readers[0]
    return result


def validate(phase,profile_path):
    root_identity();phase=Path(phase);drafted=read(phase/'control/DRAFT.json');verify(drafted['package_manifest']['sha256'])
    require(not (phase/'control/VALIDATED.json').exists(),'Immutable validation already exists')
    contract,adapter=import_runtime(drafted['runtime_contract']['path'])
    profile_ref=binding(profile_path);profile=read_ref(profile_ref)
    # The actual1331/1332 profile files remain authoritative raw sources;
    # readiness adds bound SDK/future/accounting postprocessing, not new GPU work.
    raw=[read_ref(profile['measurements'][mode]['profile_result']) for mode in ('fp32','bf16')]
    require(raw[0]['native_sources']==raw[1]['native_sources'] and raw[0]['runtime']==raw[1]['runtime'],
        'Both measured precisions must share source and physical environment')
    base=read(N/'native_S_profile_fp32_v8/control/configuration.json')
    config=deepcopy(base);config['purpose']=adapter.SCIENCE;config.pop('profile_updates',None)
    config['long_run_policy']=policy();config['evidence_sources']=evidence_sources(profile)
    config['Root_runtime_pin']=adapter.runtime_pin(contract)
    native_member=dict(scope=adapter.SCOPE,plan=adapter.PLAN,seed=0,precision='fp32',code_sha=CODE,prereg_sha=PUBLIC,
        sources=raw[0]['native_sources'],runtime=raw[0]['runtime'])
    request=dict(native_member=native_member,long_run=dict(profile=profile_ref))
    storage,_=adapter.load_runtime(drafted['runtime_contract']['path'])
    # Existing V2 validates all actual raw invocations, parent C0, CP bounds,
    # SDK config/history/summary, full-pressure accounting and source refs.
    adapter.validate_profile(request,config,storage,False)
    cfg=write(phase/'control/configuration.json',config)
    roots=write(phase/'control/initial_roots_long.json',initial_roots(phase))
    return write(phase/'control/VALIDATED.json',dict(schema='native_S_long_validation_v1',
        status='ACTUAL_READINESS_VERIFIED_NO_RESERVATION_OR_TRAINING',configuration=cfg,
        profile=profile_ref,initial_roots=roots,native_member_template=native_member,
        runtime_contract=drafted['runtime_contract'],registry=drafted['registry'],
        package_manifest=drafted['package_manifest'],all_four_start_at_seed_u0=True,
        profile_checkpoint_used_as_prefix=False,scientific_acceptance=False))


def prepare_root_registry(phase,validated):
    """Predeclare every finite output slot, including pre-model failed jobs.

    Uses the frozen serialization/write-once APIs. The first actual NativeLedger
    constructor revalidates these same immutable records before any update.
    No fake allocation/admission or compute terminal is manufactured here.
    """
    import root_phase
    phase=Path(phase);control=phase/'control'
    if not (control/'principal.json').exists():root_phase.reserve(phase,validated['configuration'],validated['registry'])
    _,adapter=import_runtime(validated['runtime_contract']['path']);storage,_=adapter.load_runtime()
    limits=read_ref(validated['configuration'])['long_run_policy'];root=phase/'ledger'
    root.mkdir(mode=0o700,exist_ok=True)
    for name in ('records','index','roots','feeds','lineages'):(root/name).mkdir(exist_ok=True)
    storage.write_once(root/'PRINCIPAL.json',dict(schema='model_v3_durable_ledger_v1',
        reservation_principal=binding(control/'principal.json'),policy=limits))
    rows=[dict(path=str(root),kind='management',type='directory',must_exist=True),
        *read_ref(validated['initial_roots'])['roots']]
    require(len(rows)<=limits['managed_roots'],'Predeclared output roots exceed finite policy')
    paths=[Path(row['path']) for row in rows]
    require(all(path.is_relative_to(phase) for path in paths),'New output root escaped its lineage')
    require(len(set(paths))==len(paths) and not any(a!=b and (a.is_relative_to(b) or b.is_relative_to(a))
        for a in paths for b in paths),'Predeclared roots overlap')
    for row in rows:
        key=storage.canonical_hash(dict(path=row['path']))
        storage.write_once(root/'roots'/(key+'.json'),row)
    require(storage.owned_bytes(root)<=limits['metadata_bytes'],'Prepared root metadata exceeds512MiB')
    return binding(control/'principal.json')


def closed_attempts(phase):
    phase=Path(phase);result=[]
    for path in sorted((phase/'control/attempts').glob('slot_*.submitted.json')):
        ref=binding(path);frame=read_ref(ref);layout=slot_layout(phase,frame['slot'])
        closure_path=layout['management']/'ROOT_LONG_SEGMENT_CLOSURE.json'
        require(closure_path.exists(),'Submitted/live/ambiguous attempt requires actual Root close before another submit')
        closure=read(closure_path)
        require(closure['submission']==ref,'Actual attempt closure binds another submission')
        result.append((frame,closure,binding(closure_path)))
    # A written intent without an unambiguous submitted receipt consumes the
    # slot and blocks automatic resubmission until Root reconciles reality.
    intents=list((phase/'control/attempts').glob('slot_*.intent.json'))
    require(len(intents)==len(result),'Unresolved submission intent; no automatic replay')
    return result


def next_member(phase,*,allow_failed=False):
    attempts=closed_attempts(phase)
    failed=[row for row in attempts if row[1]['status']!='OUTER_C0_SEGMENT_CLOSED_SDK_PENDING']
    require(len(attempts)<108 and len(failed)<=12,'Finite long attempt/failure envelope exhausted')
    if attempts and attempts[-1][1]['status']!='OUTER_C0_SEGMENT_CLOSED_SDK_PENDING':
        require(allow_failed,'Previous actual failure retained; explicit Root --retry-failed required')
    for seed,precision in MEMBERS:
        good=[row for row in attempts if (row[0]['seed'],row[0]['precision'])==(seed,precision)
            and row[1]['status']=='OUTER_C0_SEGMENT_CLOSED_SDK_PENDING']
        update=good[-1][1]['optimizer_updates'] if good else 0
        if update==20000:continue
        require(len(failed)<12,'No unused finite failure slot remains for another launch')
        require(len([row for row in attempts if row[1]['status']=='OUTER_C0_SEGMENT_CLOSED_SDK_PENDING'])<96,
            'Finite successful segment allowance exhausted')
        return dict(seed=seed,precision=precision,start_update=update,target_update=endpoint(update),
            previous=None if not good else good[-1][2],
            resume_checkpoint=None if not good else good[-1][1]['checkpoint_directory'],
            resume_output_root=None if not good else good[-1][0]['child_root'],slot=len(attempts)+1)
    return dict(status='ALL_FOUR_20000_UPDATES_COMPLETE_PENDING_LOG_NUMERIC_GATES',scientific_acceptance=False)


def source_snapshot(management,manifest):
    from long_worker import snapshot
    _,pins=verify(manifest['sha256']);return snapshot(management,manifest,pins)


def submit_next(phase,pins_sha,*,retry_failed=False):
    import resources,quota_publish
    root_identity();phase=Path(phase);manifest,_=verify(pins_sha)
    validated=read(phase/'control/VALIDATED.json')
    adoption_ref=binding(phase/'control/OPERATIONAL_ADOPTION_v7.json');adoption=read_ref(adoption_ref)
    require(adoption['schema']=='native_S_long_operational_adoption_v7' and adoption['authority']=='ROOT_ACTUAL'
        and adoption['original_validation']==binding(phase/'control/VALIDATED.json')
        and adoption['original_package']==validated['package_manifest'] and adoption['package_manifest']==manifest
        and adoption['principal']==binding(phase/'control/principal.json')
        and adoption['counters_reset'] is False and adoption['numerical_science_config_data_seed_precision_unchanged'] is True,
        'Explicit operational-only adoption of exact original validated science is required')
    for name in ('configuration','profile','initial_roots','runtime_contract','registry'):
        require(adoption[name]==validated[name],'Operational adoption changed original science/evidence/root identity')
    read_ref(adoption['original_failed_closure'])
    read_ref(adoption['prior_operational_adoption'])
    read_ref(adoption['failed_v5_operational_adoption'])
    read_ref(adoption['failed_v5_package_manifest'])
    # This reference binds a plain-text traceback, not a JSON document.
    log_ref=adoption['failed_v5_coordinator_stdout']
    require(binding(log_ref['path'])==log_ref,'Retained failed-v5 log raw bytes changed')
    read_ref(adoption['failed_v6_operational_adoption'])
    read_ref(adoption['failed_v6_package_manifest'])
    log_ref=adoption['failed_v6_coordinator_stdout']
    require(binding(log_ref['path'])==log_ref,'Retained failed-v6 log raw bytes changed')
    require(adoption['failed_v6_no_fresh_lease_intent_submission_or_slot'] is True,
        'Explicit failed-v6 pre-SB history reconciliation required')
    require(adoption['failed_v5_no_fresh_lease_intent_submission_or_slot'] is True,
        'Explicit failed-v5 pre-SB history reconciliation required')
    qa=adoption['actual_CPU_QA']
    require(qa['status']=='ACTUAL_C0_30_METADATA_TESTS_SOURCE_CLOSED'
        and qa['counts']==dict(tests=30,failures=0,errors=0,skipped=0)
        and read_ref(qa['summary'])['status']=='PASS'
        and read_ref(qa['unit_result'])['counts']==qa['counts'],
        'Actual v7 full CPU metadata QA adoption required')
    require(phase==N/'native_S_B20k_v3' and binding(phase/'control/quota_descriptor_v7.json')==adoption['quota_feed_descriptor'],
        'Exact existing B phase and actual v7 quota descriptor required')
    with lock(phase):
        step=next_member(phase,allow_failed=retry_failed)
        if 'status' in step:return step
        resources_now=resources.observe()
        principal=prepare_root_registry(phase,validated)
        slot=step['slot'];layout=slot_layout(phase,slot)
        require(not layout['root'].exists(),'Fresh finite attempt slot required')
        # A new immutable lease belongs to this attempt; no old evidence path
        # is overwritten. Only the declared quota feed is mutable.
        # Validate/publish every current hold before any new lease or intent.
        quota_publish.publish(phase,validated['registry'],adoption['quota_feed_descriptor'])
        lease=quota_publish.prepare_lease(phase,slot,adoption)
        script=OLD/(phase.name+f'_slot_{slot:03d}.sbatch')
        require(not script.exists(),'Fresh named sbatch copy required')
        with script.open('xb') as stream:stream.write((HERE/'long_gpu.sbatch').read_bytes());stream.flush();os.fsync(stream.fileno())
        submission_path=phase/'control/attempts'/f'slot_{slot:03d}.submitted.json'
        argv=['sbatch','--parsable','--partition=all','--nodelist='+NODE,'--cpus-per-task=16','--mem=32G',
            '--time=02:00:00','--job-name=nativeS_B_'+step['precision'],
            '--output='+str(layout['log']),'--error='+str(layout['log']),str(script),str(phase),str(submission_path),manifest['sha256']]
        frame=dict(schema='native_S_long_Root_submission_v1',status='INTENT',phase=str(phase),**step,
            segment_id=f'nativeS_B_slot_{slot:03d}',child_root=str(layout['child']),management_root=str(layout['management']),
            package_manifest=manifest,operational_adoption=adoption_ref,
            configuration=validated['configuration'],principal=principal,
            initial_roots=validated['initial_roots'],profile=validated['profile'],runtime_contract=validated['runtime_contract'],
            registry=validated['registry'],quota_feed_descriptor=adoption['quota_feed_descriptor'],
            native_member={**validated['native_member_template'],
                'seed':step['seed'],'precision':step['precision']},lease=lease,
            resource_observations=resources_now,script=binding(script),actual_sbatch_argv=argv,
            science_code_sha=CODE,science_prereg_sha=PUBLIC,scientific_acceptance=False)
        write(phase/'control/attempts'/f'slot_{slot:03d}.intent.json',frame)
        row=actual(argv,check=False)
        token=row['stdout'].split(';',1)[0].strip()
        require(row['returncode']==0 and re.fullmatch('[1-9][0-9]*',token),
            'Ambiguous/failed sbatch: preserve intent/hold; Root must reconcile, never automatic retry')
        frame.update(status='SUBMITTED',actual_sbatch_job_id=token,actual_sbatch=row)
        submission=write(submission_path,frame)
        print(json.dumps(dict(status='SUBMITTED',job_id=token,submission=submission)),flush=True)
        # Bounded Root coordinator for this actual2h allocation. A long pending
        # job is not cancelled or falsely closed; expired authority fails safe.
        deadline=time.monotonic()+7800;terminal=None
        while time.monotonic()<deadline:
            quota_publish.publish(phase,validated['registry'],adoption['quota_feed_descriptor'])
            query=actual(['squeue','-h','-j',token,'-o','%i|%t'],check=False)
            if query['returncode']==0 and not query['stdout'].strip():
                raw=actual(['sacct','-X','-n','-P','-j',token,'--format=JobIDRaw,State,ExitCode'],check=False)
                if raw['returncode']==0:
                    state,_=terminal_rows(raw,token)
                    if state in ('COMPLETED','FAILED','TIMEOUT','CANCELLED','OUT_OF_MEMORY'):
                        terminal=raw;break
            time.sleep(20)
        require(terminal is not None,'Root coordinator deadline: retain active/unknown intent and reservation')
        return close(phase,submission_path,terminal=terminal)


def close(phase,submission_path,*,terminal=None):
    root_identity();phase=Path(phase);submission=binding(submission_path);frame=read_ref(submission)
    job=frame['actual_sbatch_job_id'];layout=slot_layout(phase,frame['slot']);management=layout['management']
    management.mkdir(mode=0o700,parents=True,exist_ok=True)
    if terminal is None:terminal=actual(['sacct','-X','-n','-P','-j',job,'--format=JobIDRaw,State,ExitCode'])
    state,code=terminal_rows(terminal,job)
    require(state in ('COMPLETED','FAILED','TIMEOUT','CANCELLED','OUT_OF_MEMORY'),'Only actual terminal jobs can close')
    raw=write(management/'Root_raw_terminal.json',terminal)
    exit_code,signal=map(int,code.split(':'));effective=exit_code if not signal else 128+signal
    terminal_ref=write(management/'actual_terminal.json',dict(schema='native_S_actual_terminal_projection_v2',
        job_id=job,status=state,exit_code=effective,exit_code_raw=code,raw_sacct=raw))
    supervisor_path=management/'supervisor.json';sup=read(supervisor_path) if supervisor_path.exists() else None
    process_closed=(sup is not None and str(sup['job_id'])==job and
        sup['remaining_recorded_processes_before_retirement']==[] and sup['private_storage_cleanup_errors']==[])
    good=(state=='COMPLETED' and code=='0:0' and process_closed and sup['status']=='COMPLETED'
        and sup['exit_code']==0 and sup['first_failure'] is None)
    checkpoint=None;updates=frame['start_update'];member_ref=None;failure=None
    if good:
        status=read(layout['child']/'run_status.json');member_ref=binding(layout['child']/'member_result.json');member=read_ref(member_ref)
        require(status['failure'] is None and status['cleanup_errors']==[]
            and frame['start_update']<member['optimizer_updates']<=frame['target_update'],
            'Actual C0 child did not publish advancing clean NativeCore result')
        updates=member['optimizer_updates'];matches=[]
        for marker in layout['child'].glob('checkpoint_u*/COMPLETE.json'):
            header=read(marker)
            if header['optimizer_updates']==updates:matches.append(marker.parent)
        require(len(matches)==1,'Unique COMPLETE checkpoint at committed endpoint required')
        checkpoint=str(matches[0]);require(read(matches[0]/'COMPLETE.json')['payload_bytes']<=384<<20,'Bounded safe CP required')
        require(len(list((layout['child']/'wandb').glob('offline-run-*/run-*.wandb')))==1,'One closed SDK required per segment')
    else:failure=dict(actual_Slurm_state=state,actual_Slurm_exit=code,process_private_closed=process_closed)
    seal=None
    if process_closed and (management/'request.json').exists():
        import quota_publish
        require(frame['package_manifest']==binding(HERE/'source_pins.json'),
            'v7 close cannot rewrite an old operational attempt')
        quota_publish.publish(phase,frame['registry'],frame['quota_feed_descriptor'])
        observation=actual([PYTHON,'-B',HERE/'long_seal.py','--phase',phase,'--submission',submission_path,
            '--terminal',terminal_ref['path']],env=environment(cpu=True,contract=frame['runtime_contract']['path']),timeout=300)
        seal=write(management/'Root_seal_execution.json',observation)
    result=write(management/'ROOT_LONG_SEGMENT_CLOSURE.json',dict(schema='native_S_long_segment_Root_closure_v1',
        status='OUTER_C0_SEGMENT_CLOSED_SDK_PENDING' if good and seal is not None else 'FAILED_OR_STORAGE_HOLD',
        submission=submission,actual_terminal=terminal_ref,supervisor=None if sup is None else binding(supervisor_path),
        optimizer_updates=updates,checkpoint_directory=checkpoint,member_result=member_ref,storage_seal=seal,
        failure=failure,scientific_acceptance=False,D5_authority=False,
        native_full_SDK_readback_and_four_curve_numeric_gates='REQUIRED_BEFORE_B_ACCEPTANCE'))
    return dict(status=read_ref(result)['status'],closure=result)


def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='mode',required=True)
    p=sub.add_parser('prepare')
    for name in ('phase','runtime-ready','registry'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--pins-sha256',required=True)
    p=sub.add_parser('validate');p.add_argument('--phase',type=Path,required=True);p.add_argument('--profile',type=Path,required=True)
    p=sub.add_parser('dryrun');p.add_argument('--phase',type=Path,required=True);p.add_argument('--retry-failed',action='store_true')
    p=sub.add_parser('submit-next');p.add_argument('--phase',type=Path,required=True);p.add_argument('--pins-sha256',required=True)
    p.add_argument('--retry-failed',action='store_true')
    p=sub.add_parser('close');p.add_argument('--phase',type=Path,required=True);p.add_argument('--submission',type=Path,required=True)
    args=parser.parse_args()
    if args.mode=='prepare':result=draft(args.phase,args.runtime_ready,args.registry,args.pins_sha256)
    elif args.mode=='validate':result=validate(args.phase,args.profile)
    elif args.mode=='dryrun':result=dict(next=next_member(args.phase,allow_failed=args.retry_failed),will_submit=False,
        actual_readiness_validated=(args.phase/'control/VALIDATED.json').exists(),
        finite_reservation_created=(args.phase/'control/principal.json').exists())
    elif args.mode=='submit-next':result=submit_next(args.phase,args.pins_sha256,retry_failed=args.retry_failed)
    else:result=close(args.phase,args.submission)
    print(json.dumps(result,sort_keys=True))
    return 1 if isinstance(result,dict) and result.get('status')=='FAILED_OR_STORAGE_HOLD' else 0


if __name__=='__main__':raise SystemExit(main())
