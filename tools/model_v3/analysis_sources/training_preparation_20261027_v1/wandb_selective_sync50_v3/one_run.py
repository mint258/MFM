"""One exact staged SDK, official core replay, metadata-only cloud readback."""
from __future__ import annotations
import argparse
import contextlib
import math
import numbers
import os
from pathlib import Path
import resource
import subprocess
import sys
import time
from sync_common import *


def expected_remote(row):
    return dict(entity=row['routing']['entity'],project=row['routing']['project'],run_id=row['run_id'],
        state=row['expected_API_state'],history_rows=row['history_rows'],
        first_step=row['first_explicit_step'],last_step=row['last_explicit_step'])


def integer_step(value):
    require(not isinstance(value,bool) and isinstance(value,numbers.Real)
        and math.isfinite(value) and int(value)==value and abs(value)<=2**53,
        'Remote step is not a lossless explicit integer')
    return int(value)


def exact_missing_run(error,missing_type,comm_type):
    # Installed0.28.1 normalize.py retains the original exception in .exc.
    # Do not infer absence from generic communication/HTTP/auth failures,
    # text, context chains or a backend status alone.
    return type(error) is missing_type or (type(error) is comm_type
        and type(getattr(error,'exc',None)) is missing_type)


def error_types(error):
    # Deliberately omit str(error), args, messages, response bodies and URLs.
    inner=getattr(error,'exc',None)
    return dict(type=type(error).__name__,inner_type=None if inner is None else type(inner).__name__)


def project_remote_steps(rows,deadline,expected_rows):
    require(type(expected_rows) is int and 0<=expected_rows<=100000,'Original bounded history count required')
    count=0;first=last=None;previous=None
    for history in rows:
        require(time.monotonic()<deadline,'Cloud step readback reached finite deadline')
        require('_step' in history,'Cloud history lacks explicit step')
        step=integer_step(history['_step'])
        require(previous is None or step>previous,'Cloud steps duplicate or move backwards')
        if first is None:first=step
        last=previous=step;count+=1
        require(count<=expected_rows,'Cloud history exceeds original exact row budget')
    return dict(history_rows=count,first_step=first,last_step=last)


def snapshot_remote(api,row,deadline):
    from wandb.apis.public.runs import RunNotFoundError
    from wandb.errors import CommError
    api.flush();route='/'.join((row['routing']['entity'],row['routing']['project'],row['run_id']))
    try:run=api.run(route)
    except (RunNotFoundError,CommError) as error:
        if exact_missing_run(error,RunNotFoundError,CommError):return None
        raise
    require(run.id==row['run_id'] and run.entity==row['routing']['entity'] and run.project==row['routing']['project'],
        'Cloud route/runID conflicts with original RunRecord')
    # Actual read-only diagnosis after1410 proved keyed_step scans yield0
    # while the unkeyed HistoryScan retains the exact500 native steps.
    # Stream unkeyed rows; retain only _step locally. Never serialize/hash
    # the other fields, and never use sampled history for acceptance.
    steps=project_remote_steps(run.scan_history(keys=None,page_size=1000,min_step=0,use_cache=False),
        deadline,row['history_rows'])
    # Never write config, summary, metrics, credentials or history payloads.
    return dict(entity=run.entity,project=run.project,run_id=run.id,state=str(run.state).lower(),
        **steps)


def sync_argv(row,staged):
    # All options below are verified in the installed0.28.1 cli.py. False TB,
    # unchanged mark_synced=True and no legacy/append/clean/glob/skip-console
    # keep the official beta/core reroute condition true. Only one FILE path.
    return [str(PYTHON),'-B','-m','wandb','sync','--yes','--no-sync-tensorboard','--include-offline',
        '--entity',row['routing']['entity'],'--project',row['routing']['project'],
        '--id',row['run_id'],str(staged)]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--request',type=Path,required=True);parser.add_argument('--request-sha256',required=True)
    parser.add_argument('--run-id',required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();allocation()
    request_ref=ref(args.request);require(request_ref['sha256']==args.request_sha256,'Request changed')
    request=read(request_ref);manifest=verify(request['source_manifest']['sha256']);_,rows=eligible_rows()
    request_gate(request)
    require(args.run_id in request['selected_run_ids'] and args.run_id in rows,'Run outside explicit frozen request')
    row=rows[args.run_id];args.output.mkdir(mode=0o700,parents=True,exist_ok=False)
    expected=expected_remote(row);failure=None;result=None;stage='source_binding';started=time.monotonic()
    source=row['SDK_raw_ref'];marker=Path(source['path']+'.synced')
    require(not marker.is_symlink(),'Original sync marker must not be a link')
    before_marker=ref(marker) if marker.exists() else None
    marker_unchanged=None
    command_result=None;staged_ref=None;action=None
    private=Path(os.environ['TMPDIR'])/('selective_sync_'+row['run_id']);private.mkdir(mode=0o700)
    env={**os.environ,'WANDB_MODE':'online','WANDB_BASE_URL':'https://api.wandb.ai',
        'WANDB_CACHE_DIR':str(private/'cache'),'WANDB_DATA_DIR':str(private/'data'),
        'WANDB_CONFIG_DIR':str(private/'config'),'WANDB_DIR':str(private),'WANDB_SILENT':'true',
        'WANDB_CONSOLE':'off','WANDB_ANONYMOUS':'never','WANDB_ERROR_REPORTING':'false'}
    os.environ.update({key:value for key,value in env.items() if key.startswith('WANDB_')})
    try:
        bind(source,128<<20)
        for installed in read(HERE/'installed_sources.json')['files']:
            current=ref(installed['original'])
            require(current['bytes']==installed['bytes'] and current['sha256']==installed['sha256'],
                'Installed W&B code differs from source-reviewed0.28.1')
        import wandb
        require(wandb.__version__=='0.28.1','Exact installed W&B0.28.1 required')
        # API library console streams are private too; evidence stores only
        # their hashes/counts. No exception text or object repr is exported.
        with (
            (private/'API.stdout').open('x') as api_out,
            (private/'API.stderr').open('x') as api_err,
            contextlib.redirect_stdout(api_out),
            contextlib.redirect_stderr(api_err),
        ):
            stage='remote_API_construction';api=wandb.Api(overrides=dict(entity=row['routing']['entity'],project=row['routing']['project']),timeout=30)
            require(api.settings['base_url']=='https://api.wandb.ai','Unexpected cloud destination')
            stage='remote_run_lookup'
            before=snapshot_remote(api,row,time.monotonic()+180)
            if before is not None:
                require(before==expected,'Existing remote namespace/history/state conflict; no replay/append/repair')
                result=before;action='REMOTE_ALREADY_MATCHED_NO_REPLAY'
            else:
                # A matched pre-existing pilot proves presence, not this
                # method's failed-exit replay. Never silently extrapolate that.
                gate=request.get('pilot_gate')
                if request['mode']=='batch':
                    require(gate is not None,'Actual reviewed pilot gate required')
                    if row['native_exit_code']==1:
                        require(gate['native_exit_code']==1 and gate['actual_replay_verified'] is True,
                            'Failed-exit core replay not yet verified by an actual single-run pilot')
                stage='copy_exact_SDK'
                original_parent=Path(source['path']).parent.name
                require(original_parent.startswith('offline-run-'),'Original offline run-directory identity required')
                staged=args.output/'stage'/original_parent/Path(source['path']).name
                staged_ref=copy_exact(source,staged)
                argv=sync_argv(row,staged)
                stage='official_core_sync';out=private/'CLI.stdout';err=private/'CLI.stderr'
                def limits():resource.setrlimit(resource.RLIMIT_FSIZE,(4<<20,4<<20))
                tick=time.monotonic()
                timeout_failure=None;completed=None
                with out.open('xb') as stdout,err.open('xb') as stderr:
                    try:
                        completed=subprocess.run(argv,stdin=subprocess.DEVNULL,stdout=stdout,stderr=stderr,cwd=private,
                            env=env,timeout=request['CLI_timeout_seconds'],preexec_fn=limits)
                    except subprocess.TimeoutExpired as error:timeout_failure=error
                command_result=dict(argv=argv,returncode=None if completed is None else completed.returncode,
                    timeout=timeout_failure is not None,elapsed_seconds=time.monotonic()-tick,
                    stdout=ref(out,4<<20),stderr=ref(err,4<<20),raw_output_contents_exported=False)
                if timeout_failure is not None:raise timeout_failure
                require(completed.returncode==0,'Official core CLI returned nonzero')
                stage='cloud_post_replay_verification';deadline=time.monotonic()+request['API_verification_seconds']
                while True:
                    result=snapshot_remote(api,row,deadline)
                    if result==expected:break
                    require(time.monotonic()+10<deadline,'Cloud failed-exit/history/step readback differs; method held')
                    time.sleep(10)
                action='SYNCED_EXACT_COPY_AND_API_VERIFIED'
                require(ref(staged,128<<20)==staged_ref,'Staged SDK body was rewritten')
        bind(source,128<<20)
        require((ref(marker) if marker.exists() else None)==before_marker,'Original sync marker changed')
    except BaseException as error:
        failure=dict(**error_types(error),stage=stage,
            reason='bounded_operation_failed_or_metadata_mismatch; no_credentials_or_metric_values_exported')
    finally:
        # Shutdown only this process's SDK transport; never create/finish a run
        # or call a remote state/config/summary mutation API.
        if 'wandb' in sys.modules and callable(getattr(sys.modules['wandb'],'teardown',None)):
            try:sys.modules['wandb'].teardown()
            except BaseException as error:
                failure=failure or dict(type=type(error).__name__,stage='transport_close',reason='transport_close_failed')
        source_unchanged=False
        try:
            bind(source,128<<20);source_unchanged=True
            marker_unchanged=not marker.is_symlink() and (ref(marker) if marker.exists() else None)==before_marker
            require(marker_unchanged,'Original marker changed')
        except BaseException as error:
            failure=failure or dict(type=type(error).__name__,stage='source_after_hash',reason='source_or_marker_changed')
        write(args.output/'result.json',dict(schema='model_v3_one_WandB_sync_readback_v1',
            status='SOURCE_AND_REMOTE_METADATA_VERIFIED' if failure is None else 'FAILED_HOLD_PRESERVED',
            run_id=row['run_id'],native_exit_code=row['native_exit_code'],original_source=source,
            source_hash_before_after_equal=source_unchanged,original_sync_marker_unchanged=marker_unchanged,
            staged_SDK=staged_ref,action=action,expected_remote_metadata=expected,actual_remote_metadata=result,
            official_core_command=command_result,failure=failure,elapsed_seconds=time.monotonic()-started,
            source_manifest=manifest,metric_values_exported=False,API_keys_exported=False,
            original_SDK_repaired_or_deleted=False,scientific_acceptance=False))
    return int(failure is not None)


if __name__=='__main__':raise SystemExit(main())
