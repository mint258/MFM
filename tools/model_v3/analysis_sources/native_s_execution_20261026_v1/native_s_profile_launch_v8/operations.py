"""Single Root entry for metadata QA, bounded candidate preparation and profile.

Nothing is submitted, reserved or computed merely by importing this package.
Root invokes explicit subcommands; failed attempts and all originals survive.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import sys
import time
from common import *
sys.dont_write_bytecode=True

def protocol_proof(path,expected,pins):
    ref=binding(path);require(ref['sha256']==expected,'Protocol publication raw SHA differs')
    raw=read_ref(ref)
    if raw['schema']=='model_v3_Root_exact_tree_publication_receipt_v1':
        require(raw['repository']=='mint258/MFM' and raw['branch']=='model-v3'
            and raw['actual_readback']['model_v3']==raw['public_commit_sha'],
            'Protocol publication must have actual model-v3 readback')
        commit=raw['public_commit_sha']
        require(raw['actual_readback']['main']=='037546cd7f07b32dbb46bc21a69109dfd273f8da'
            and raw['formal_pretraining_authorized'] is False,'Main/formal boundary differs')
    else:
        require(raw['schema']=='model_v3_exact_tree_publication_receipt_v1' and raw['branch']=='model-v3'
            and raw['exact_tree_verified'] is True and raw['published_head_readback_verified'] is True,
            'Known actual protocol publication receipt required')
        commit=raw['github_commit_sha']
        require(raw['main_modified'] is False and raw['formal_pretraining_started'] is False,
            'Main/formal boundary differs')
    require(re.fullmatch('[0-9a-f]{40}',commit) and re.fullmatch('[0-9a-f]{40}',raw['tree_sha']),
        'Complete publication commit/tree required')
    published={row['sha256'] for row in raw['source_files']}
    require(binding(HERE/'source_pins.json')['sha256'] in published and all(row['sha256'] in published for row in pins['files']),
        'Publication source graph must contain every frozen launch package raw leaf')
    return ref


def snapshot_operations(directory,manifest,pins):
    """Actual unpublished operational bytes, never a publication receipt."""
    directory=Path(directory);require(not directory.exists(),'Fresh source snapshot required')
    directory.mkdir(mode=0o700,parents=True)
    entries=[]
    for name in [row['path'] for row in pins['files']]+['source_pins.json']:
        relative=Path(name)
        require(not relative.is_absolute() and '..' not in relative.parts,'Relative snapshot leaf required')
        source=binding(HERE/relative);raw=Path(source['path']).read_bytes()
        require(len(raw)==source['bytes'] and hashlib.sha256(raw).hexdigest()==source['sha256'],
            'Source changed while snapshotting')
        target=directory/relative;target.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
        with target.open('xb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
        copied=binding(target)
        require(copied['sha256']==source['sha256'] and copied['bytes']==source['bytes'],'Copied source differs')
        entries.append(dict(relative_path=relative.as_posix(),bytes=copied['bytes'],sha256=copied['sha256']))
    ref=write(directory/'MANIFEST.json',dict(schema='native_S_operational_source_snapshot_v2',
        status='UNPUBLISHED_CANDIDATE',original_source_manifest=manifest,files=entries,
        scientific_model_code_sha=CODE,scientific_model_prereg_sha=PUBLIC,
        published_operational_commit=None,usable_scientific_result=False,production_20k_allowed=False))
    verify_source_snapshot(ref,manifest)
    return ref


def verify_source_snapshot(reference,manifest):
    value=read_ref(reference);root=Path(reference['path']).parent
    require(value['schema']=='native_S_operational_source_snapshot_v2' and value['status']=='UNPUBLISHED_CANDIDATE'
        and value['original_source_manifest']==manifest and value['published_operational_commit'] is None
        and value['scientific_model_code_sha']==CODE and value['scientific_model_prereg_sha']==PUBLIC
        and value['usable_scientific_result'] is False and value['production_20k_allowed'] is False,
        'Unpublished source identity/scope differs')
    expected={str(Path(reference['path']))}
    for row in value['files']:
        relative=Path(row['relative_path'])
        require(not relative.is_absolute() and '..' not in relative.parts,'Snapshot path escaped')
        target=root/relative;ref=binding(target)
        require(ref['bytes']==row['bytes'] and ref['sha256']==row['sha256'] and str(target) not in expected,
            'Snapshot bytes/duplicate path differ')
        expected.add(str(target))
    entries=list(root.rglob('*'))
    require(not any(p.is_symlink() for p in entries),'Snapshot symlink refused')
    require({str(p) for p in entries if p.is_file()}==expected,'Unenumerated snapshot file')
    require(binding(root/'source_pins.json')['sha256']==manifest['sha256'],'Snapshot has another source manifest')
    return value

def launch_qa(job):
    raw=actual(['sacct','-X','-n','-P','-j',str(job),'--format=JobIDRaw,State,ExitCode']);require_C0(raw,job)
    path=OLD/f'frozen_units_{job}/native_s_profile_launch.json';value=read(path)
    before=value['source_hashes_before'];require(before and before==value['source_hashes_after']
        and value['returncode']==0 and value['sources_unchanged'] is True,'Actual launch QA failed or source changed')
    count=value['counts'];expected=read(HERE/'CPU_test_request.json')['expected_parameterized_cases_from_static_review']
    require(count['tests']==expected and count['failures']==count['errors']==count['skipped']==0,
        'Launch QA must actually pass without skips')
    _,pins=verify_package()
    require(before.get(str(HERE/'source_pins.json'))==binding(HERE/'source_pins.json')['sha256'] and
        all(before.get(str(HERE/row['path']))==row['sha256'] for row in pins['files']),
        'Actual launch QA did not bind the complete frozen package')
    supervisor=read(OLD/f'frozen_units_supervisor_{job}.json')
    require(supervisor['status']=='COMPLETED' and supervisor['exit_code']==0 and supervisor['first_failure'] is None,
        'Launch QA parent supervisor not C0')
    return dict(raw_sacct=raw,result=binding(path),supervisor=binding(OLD/f'frozen_units_supervisor_{job}.json'),
        passed=count['tests'],sources_before_after_sha256=digest(before))

def submit(args):
    import provenance,resources,root_phase
    root_identity();manifest,pins=verify_package(expected=args.pins_sha256)
    verify_package(V2,V2_PIN)
    if args.prepublication_operations:
        require(args.profile_launch_validation and args.qa_job is None
            and args.protocol_publication is None and args.protocol_sha256 is None,
            'Unpublished operations require explicit same-job validation and no fabricated publication/external C0')
        proof=None
    else:
        require(args.protocol_publication is not None and args.protocol_sha256 is not None,
            'Published mode requires actual operational publication proof')
        proof=protocol_proof(args.protocol_publication,args.protocol_sha256,pins)
    if args.profile_launch_validation:
        require(args.qa_job is None,'Inline mode cannot claim a separate QA parent C0')
        qa=dict(status='NOT_YET_EXECUTED',mode='PROFILE_LAUNCH_VALIDATION',independent_CPU_parent_C0_claimed=False)
    else:
        require(args.qa_job is not None,'Independent CPU_C0 mode requires actual source-bound QA parent')
        qa=launch_qa(args.qa_job)
    ready=read(args.candidate_ready);contract_ref=ready['contract'];contract=read_ref(contract_ref)
    require(ready['status']=='PROFILE_ONLY_RUNTIME_READY' and ready['production_20k_allowed'] is False,
        'Candidate-only prepared contract required')
    # Verify full actual candidate raw graph in a fresh child; no CUDA or data.
    check=actual([PYTHON,'-B',HERE/'candidate_probe.py','--contract',contract_ref['path']],
        env=runtime_environment(cpu=True),timeout=120)
    root_coverage=resources.observe()
    phase=Path(args.phase).absolute()
    require(phase.parent==N and not phase.exists(),'Fresh immediate N phase directory required')
    phase.mkdir(mode=0o700)
    (phase/'control').mkdir(mode=0o700)
    snapshot=snapshot_operations(phase/'control/operations_source',manifest,pins) if args.prepublication_operations else None
    # Import only after a fresh, canonical metadata contract has been checked.
    env=runtime_environment(cpu=True)
    config_cmd=actual([PYTHON,'-B',HERE/'candidate_probe.py','--contract',contract_ref['path'],
        '--configuration-output',phase/'control/configuration.json'],env=env,timeout=120)
    root_phase.reserve(phase,binding(phase/'control/configuration.json'),args.registry)
    template=HERE/'native_s_profile_gpu.sbatch'
    script=OLD/(phase.name+'_gpu.sbatch')
    require(not script.exists(),'New sbatch name required; preserve previous attempts')
    with script.open('xb') as stream:stream.write(template.read_bytes());stream.flush();os.fsync(stream.fileno())
    require(binding(script)['sha256']==binding(template)['sha256'],'Copied template bytes differ')
    frame=dict(schema='native_S_profile_Root_submit_v1',status='PREPARED',phase=str(phase),precision=args.precision,
        candidate_ready=binding(args.candidate_ready),candidate_contract=contract_ref,package_manifest=manifest,
        protocol_publication=proof,actual_launch_QA=qa,resource_observations=root_coverage,
        operational_source_status='UNPUBLISHED_CANDIDATE' if args.prepublication_operations else 'PUBLISHED_VERIFIED',
        operational_source_snapshot=snapshot,usable_scientific_result=False,
        launch_validation_mode='PROFILE_LAUNCH_VALIDATION' if args.profile_launch_validation else 'INDEPENDENT_CPU_C0',
        candidate_probe=check,configuration_preparation=config_cmd,registry=str(Path(args.registry).absolute()),
        copied_script=binding(script),created_unix=time.time(),nonce=os.urandom(16).hex(),
        model_code_sha=CODE,model_tree_sha=TREE,model_public_commit=PUBLIC,
        whole_job_output_budget_bytes=OUTER,private_storage_budget_bytes=PRIVATE,durable_lineage_cap_bytes=3<<30,
        full_Root_regression='ACTUAL_PASS',actual_full_runtime_verification=ready['actual_full_runtime_verification'],production_20k_allowed=False)
    argv=['sbatch','--parsable','--partition=all','--nodelist='+NODE,'--cpus-per-task=16','--mem=32G',
        '--time=00:20:00','--job-name=nativeS_prof_'+args.precision,'--output='+str(phase/'slurm_%j.log'),
        '--error='+str(phase/'slurm_%j.log'),str(script),str(phase),args.precision,manifest['sha256']]
    write(phase/'control/SUBMISSION_ATTEMPT.json',dict(frame=frame,actual_planned_sbatch_argv=argv,
        ambiguous_submission_must_not_be_retried=True))
    row=actual(argv,check=False)
    match=re.fullmatch(r'(\d+)(?:;[^\n]+)?\n?',row['stdout']) if row['returncode']==0 else None
    if match is None:
        write(phase/'control/SUBMISSION_REJECTED_OR_AMBIGUOUS.json',dict(actual_sbatch=row,
            status='HOLD_ROOT_RECONCILIATION',retained_finite_reservation=True));raise RuntimeError('Submission failed/ambiguous; no automatic retry')
    job=match[1]
    frame.update(status='SUBMITTED',actual_sbatch_job_id=job,actual_sbatch=row,actual_sbatch_argv=argv)
    write(phase/'control/submission.json',frame)
    print(json.dumps(dict(status='SUBMITTED',job_id=job,phase=str(phase),production_20k_allowed=False)),flush=True)
    # No detached unknown publisher: this bounded Root coordinator remains the
    # explicit owner. It publishes fresh account quota while the one job runs.
    start=time.monotonic();terminal=None
    while time.monotonic()-start<1800:
        root_phase.publish(phase,args.registry)
        query=actual(['squeue','-h','-j',job,'-o','%i|%t'],check=False)
        if query['returncode']==0 and not query['stdout'].strip():
            terminal=actual(['sacct','-X','-n','-P','-j',job,'--format=JobIDRaw,State,ExitCode'],check=False)
            if terminal['returncode']==0:
                state,code=terminal_rows(terminal,job)
                if state in ('COMPLETED','FAILED','TIMEOUT','CANCELLED','OUT_OF_MEMORY'):break
        time.sleep(20)
    require(terminal is not None,'Bounded Root feed coordinator ended without actual terminal; reservation retained')
    return close(phase,terminal=terminal,registry=args.registry)

def sdk_inputs(phase,job,result):
    management=Path(phase)/f'job_{job}'/'management';child=Path(phase)/f'job_{job}'/'child'
    ref=binding(child/'profile_result.json');value=read_ref(ref)
    if value.get('SDK_expectations') is None:return None
    expectations=value['SDK_expectations']
    for key,reference in expectations.items():
        require(binding(reference['path'],maximum=128<<20)==reference,'Actual SDK expectation raw reference changed')
    return write(management/'INDEPENDENT_SDK_INPUTS.json',dict(schema='native_S_evidence_inputs_v2',
        role='native_full_SDK_verifier',status='INPUTS_PREPARED_NOT_VERIFIED',artifacts=expectations,
        profile_result=ref,actual_terminal=result,expected_run_id=value['tracker_id'],expected_exit=0,
        purpose='PROFILE_ONLY_NO_B_ACCEPTANCE',production_20k_allowed=False,
        remaining=['actual_full_native_history_config_summary_tap','future_state_bound','dtype_certificate',
            'closed_output_source_graph','accounting_pressure_certificate','full_Root_regression_C0'],
        frozen_history_reader=binding(RUNTIME/'tools/model_v3/analysis_sources/archive_closed_v7/bounded_history_v7.py')))

def close(phase,*,terminal=None,registry=None):
    import root_phase
    root_identity();phase=Path(phase);frame=read(phase/'control/submission.json');job=frame['actual_sbatch_job_id']
    if terminal is None:terminal=actual(['sacct','-X','-n','-P','-j',job,'--format=JobIDRaw,State,ExitCode'])
    state,code=terminal_rows(terminal,job)
    require(state in ('COMPLETED','FAILED','TIMEOUT','CANCELLED','OUT_OF_MEMORY'),'Job not actually terminal')
    management=phase/f'job_{job}'/'management';supervisor_path=management/'supervisor.json'
    raw=write(management/'raw_terminal.json',terminal)
    exit_status,signal=map(int,code.split(':'));effective_exit=exit_status if signal==0 else 128+signal
    terminal_ref=write(management/'actual_terminal.json',dict(schema='native_S_actual_terminal_projection_v2',
        job_id=job,status=state,exit_code=effective_exit,raw_sacct=raw,
        exit_code_raw=code,profile_result=None if not (phase/f'job_{job}/child/profile_result.json').exists()
        else binding(phase/f'job_{job}/child/profile_result.json')))
    supervisor=read(supervisor_path) if supervisor_path.exists() else None
    ready=(supervisor is not None and str(supervisor['job_id'])==job and
        supervisor['remaining_recorded_processes_before_retirement']==[] and supervisor['private_storage_cleanup_errors']==[])
    # Publication/proof/SDK closure remains independent of unused-hold release.
    inputs=sdk_inputs(phase,job,terminal_ref) if state=='COMPLETED' and code=='0:0' else None
    status='PROFILE_OUTER_C0_SCIENCE_HOLD' if state=='COMPLETED' and code=='0:0' and ready and supervisor['status']=='COMPLETED' else 'FAILED_OR_CLOSURE_HOLD'
    qa_scope=None
    if (management/'inline_launch_QA.json').exists():
        from inline_qa import verdict
        qa=read(management/'inline_launch_QA.json')
        if status=='PROFILE_OUTER_C0_SCIENCE_HOLD':
            expected=read(HERE/'CPU_test_request.json')['expected_parameterized_cases_from_static_review']
            require(qa['status']==verdict(qa['returncode'],qa['counts'],qa['sources_before'],qa['sources_after'],expected)
                and qa['job_id']==job and qa['independent_CPU_parent_C0_claimed'] is False,
                'Actual inline QA scope/source differs')
            qa_scope=write(management/'launch_QA_scope_certificate.json',dict(schema='native_S_launch_QA_same_job_scope_v1',
                status='VERIFIED_METADATA_PREFLIGHT_AND_SAME_PROFILE_JOB_C0',actual_terminal=terminal_ref,
                original_inline_QA=binding(management/'inline_launch_QA.json'),independent_CPU_parent_C0_claimed=False,
                scope='launch_metadata_preflight_only; same_actual_GPU_model_profile_job; no_B_acceptance'))
    seal=None
    if ready and (management/'request.json').exists():
        root_phase.publish(phase,registry or frame['registry'])
        seal=actual([PYTHON,'-B',HERE/'finalize_profile.py','--phase',phase,'--terminal',terminal_ref['path']],
            env=runtime_environment(cpu=True,contract=frame['candidate_contract']['path']),timeout=120)
        with root_phase.registry_lock(registry or frame['registry']):
            registered=root_phase.registry_value(registry or frame['registry'])
            registered['reservations'][phase.name]['remaining_bytes']=0
            registered['reservations'][phase.name]['actual_Root_seal']=binding(management/'ROOT_LEDGER_SEAL.json')
            replace_feed(registry or frame['registry'],registered)
    result=write(management/'ROOT_PROFILE_CLOSURE.json',dict(schema='native_S_short_profile_Root_closure_v1',
        status=status,actual_terminal=terminal_ref,supervisor=None if supervisor is None else binding(supervisor_path),
        independent_SDK_inputs=inputs,unused_hold_release='ACTUAL_ROOT_LEDGER_SEALED' if seal else 'HOLD_NO_ACTUAL_SEAL',actual_seal=seal,
        same_job_launch_QA_scope=qa_scope,
        operational_source_status=frame['operational_source_status'],operational_source_snapshot=frame.get('operational_source_snapshot'),
        operational_publication=frame.get('protocol_publication'),usable_scientific_result=False,
        production_20k_allowed=False,scientific_acceptance=False,D5_authority=False))
    print(json.dumps(dict(status=status,closure=result,actual_terminal_state=state,actual_exit_code=code)),flush=True)
    return 0 if status=='PROFILE_OUTER_C0_SCIENCE_HOLD' else 1

def parser():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    q=sub.add_parser('candidate');q.add_argument('--output',type=Path,required=True);q.add_argument('--v2-job',required=True)
    q.add_argument('--git',default=str(OLD/'cpu_git_tools_v1/bin/git'))
    q=sub.add_parser('qa');q.add_argument('--pins-sha256',required=True)
    q=sub.add_parser('init-registry');q.add_argument('--registry',type=Path,required=True)
    q=sub.add_parser('submit')
    for name in ('phase','registry','candidate-ready'):q.add_argument('--'+name,type=Path,required=True)
    q.add_argument('--protocol-publication',type=Path);q.add_argument('--protocol-sha256')
    q.add_argument('--prepublication-operations',action='store_true')
    q.add_argument('--pins-sha256',required=True)
    q.add_argument('--qa-job');q.add_argument('--profile-launch-validation',action='store_true')
    q.add_argument('--precision',choices=('fp32','bf16'),required=True)
    q=sub.add_parser('close');q.add_argument('--phase',type=Path,required=True)
    return p

def main():
    a=parser().parse_args()
    if a.command=='qa':
        from cpu_qa import main as run_cpu_QA
        return run_cpu_QA(['--pins-sha256',a.pins_sha256])
    if a.command=='candidate':
        from provenance import build_candidate
        receipt=build_candidate(a.output,git=a.git,v2_job=a.v2_job,
            v2_result=OLD/f'frozen_units_{a.v2_job}/native_s_storage_v2_revised.json',
            v2_supervisor=OLD/f'frozen_units_supervisor_{a.v2_job}.json')
        print(json.dumps(receipt))
        return 0
    if a.command=='init-registry':
        from root_phase import initialize
        print(json.dumps(initialize(a.registry)));return 0
    if a.command=='submit':return submit(a)
    return close(a.phase)

if __name__=='__main__':raise SystemExit(main())
