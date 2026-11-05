"""One explicitly certified panel run, unchanged v3 official core transport."""
from __future__ import annotations
import argparse
import subprocess
import time
import sys
from pathlib import Path
V1=Path(__file__).absolute().parent.parent/'native_S10000_panel_SDK_sync_v1_source'
sys.path.insert(0,str(V1))
from panel_common import *
from overlay_metadata import verify_overlay
OVERLAY=Path(__file__).absolute().parent


def transport_argv(request_path,request_sha,output_root):
    require(isinstance(request_path,Path) and isinstance(output_root,Path)
        and type(request_sha) is str and re.fullmatch(r'[0-9a-f]{64}',request_sha),
        'Actual typedPath request/output and raw64SHA required')
    child=output_root/('run_0_'+RUN)
    return [str(PYTHON),'-B',str(HERE/'one_run_panel.py'),'--request',str(request_path),
        '--request-sha256',request_sha,'--run-id',RUN,'--output',str(child)]


def controls(request,row,transport):
    request_gate(request)
    bad={**request,'selected_run_ids':['not-this-run']}
    try:request_gate(bad)
    except ValueError:pass
    else:raise ValueError('Nonselected run negative accepted')
    control_row={**row,'routing':{'entity':row['native_RunRecord']['entity'],'project':row['native_RunRecord']['project']}}
    expected=transport.sync_argv(control_row,Path('/tmp/metadata_only/run-'+RUN+'.wandb'))
    actual_constructor=transport_argv(Path('/tmp/metadata_only/request.json'),'0'*64,Path('/tmp/metadata_only'))
    require(actual_constructor[-4:]==['--run-id',RUN,'--output','/tmp/metadata_only/run_0_'+RUN],
        'Production typedPath transport argv constructor differs')
    try:transport_argv(Path('/tmp/metadata_only/request.json'),'0'*64,'/tmp/metadata_only')
    except ValueError:pass
    else:raise ValueError('Untyped output root admitted by actual transport constructor')
    require('--sync-all' not in expected and expected.count('--id')==1 and expected[-2:]==[RUN,'/tmp/metadata_only/run-'+RUN+'.wandb']
        and expected[expected.index('--project')+1]=='phychem-model-v3','Only one exact original ID/project/file may be synced')
    require(transport.project_remote_steps(iter([{'_step':0},{'_step':1}]),time.monotonic()+2,2)
        ==dict(history_rows=2,first_step=0,last_step=1),'Existing remote parser mismatch')
    for values in ([{'_step':0},{'_step':0}],[{'_step':True}]):
        try:transport.project_remote_steps(iter(values),time.monotonic()+2,2)
        except ValueError:pass
        else:raise ValueError('Duplicate/bool remote-step negative accepted')
    return dict(scope='INLINE_METADATA_ONLY_NO_UPLOAD_TEST',count=4,
        checks=['actual_request_gate','nonselected_run_rejection','actual_typedPath_constructor_and_exact_official_one_file_argv','actual_unkeyed_step_parser_negatives'])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--request',type=Path,required=True);parser.add_argument('--request-sha256',required=True)
    parser.add_argument('--pins-sha256',required=True);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--overlay-pins-sha256',required=True)
    args=parser.parse_args();overlay=verify_overlay(args.overlay_pins_sha256)
    process=allocation();pin=verify(args.pins_sha256);raw=ref(args.request)
    require(raw['sha256']==args.request_sha256,'Actual request raw SHA differs')
    request=read(raw);request_gate(request)
    require(request['job_output']==str(args.output.absolute()) and args.output.absolute().parent==HERE.parent
        and not args.output.exists(),'Explicit fresh sync output required')
    args.output.mkdir(mode=0o700);started=time.monotonic();failure=None;record=None;intent=None;stage='load_transport'
    sources=[HERE/item['relative_path'] for item in read(pin)['files']]+[HERE/'source_pins.json',args.request]
    sources += [OVERLAY/item['relative_path'] for item in read(overlay)['files']]+[OVERLAY/'source_pins.json']
    before={str(p):ref(p) for p in sources}
    try:
        transport=load(ref(HERE/'one_run_panel.py'),'panel_exact_original_transport')
        # Proof-derived row before any auth/network, then actual authenticated
        # routing only inside the owned CPU allocation/private stdout capture.
        _,manifest=manifest_metadata();row=row_from_proof(manifest)
        stage='inline_metadata_controls'
        qa=write(args.output/'INLINE_METADATA_QA.json',controls(request,row,transport))
        stage='readonly_authenticated_eligible_row'
        _,eligible=eligible_rows();require(list(eligible)==[RUN],'One eligible panel run only')
        stage='construct_typed_transport_argv'
        argv=transport_argv(args.request,args.request_sha256,args.output)
        private=Path(os.environ['TMPDIR']);out=private/'panel_sync.stdout';err=private/'panel_sync.stderr'
        intent=write(args.output/'actual_invocation.json',dict(schema='native_S10000_panel_transport_intent_v2',
            status='INTENT_DURABLE_SUBPROCESS_START_NOT_YET_CONFIRMED',argv=argv,job_id=process['job_id'],
            stdout_path=str(out),stderr_path=str(err),prepared_unix=time.time(),execution_overlay=overlay,
            underlying_audit_transport_source_manifest=pin))
        stage='transport_subprocess_attempt'
        tick=time.monotonic()
        with out.open('xb') as stdout,err.open('xb') as stderr:
            completed=subprocess.run(argv,stdin=subprocess.DEVNULL,stdout=stdout,stderr=stderr,timeout=900)
        stage='transport_result_verification'
        invocation=write(args.output/'actual_invocation_result.json',dict(intent=intent,argv=argv,returncode=completed.returncode,
            elapsed_seconds=time.monotonic()-tick,stdout=ref(out,4<<20),stderr=ref(err,4<<20),
            job_id=process['job_id'],raw_contents_exported=False))
        item_ref=ref(args.output/('run_0_'+RUN)/'result.json');item=read(item_ref)
        require(completed.returncode==0 and item['status']=='SOURCE_AND_REMOTE_METADATA_VERIFIED'
            and item['run_id']==RUN and item['native_exit_code']==0,'Actual single transport/source/API readback failed')
        record={**{key:item[key] for key in ('run_id','native_exit_code','action','actual_remote_metadata')},
            'result':item_ref,'actual_invocation':invocation}
        request_gate(request);_,closed_manifest=manifest_metadata()
        require(row_from_proof(closed_manifest)==row,'Independent certificate/metadata changed during transport')
        stage='source_after'
        verify(args.pins_sha256);verify_overlay(args.overlay_pins_sha256)
        require(before=={str(p):ref(p) for p in sources},'Sync source/input changed')
    except BaseException as error:
        import traceback
        failure=dict(type=type(error).__name__,stage=stage,
            traceback_frames=[dict(file=f.filename,line=f.lineno,function=f.name)
                for f in traceback.extract_tb(error.__traceback__)[-32:]],
            reason='bounded_sync_overlay_failed; messages_args_locals_source_lines_credentials_metrics_not_exported')
    finally:
        after={str(p):ref(p) for p in sources}
        if after!=before:failure=failure or dict(type='SourceDrift',reason='source_after_differs')
        write(args.output/'RESULT.json',dict(schema='native_S10000_panel_selective_sync_result_v2',scope=SCOPE,
            status='SYNC_READBACK_CHILD_COMPLETED_PENDING_ROOT_C0' if failure is None else 'FAILED_HOLD_PRESERVED',
            actual_job_id=process['job_id'],actual_allocation=process,actual_argv=list(sys.orig_argv),
            requested_ids=[RUN],records=[] if record is None else [record],failure=failure,request=raw,source_manifest=pin,
            execution_overlay=overlay,underlying_certified_SDK_audit_source_manifest=pin,transport_intent=intent,
            source_refs_before=before,source_refs_after=after,elapsed_seconds=time.monotonic()-started,
            original_SDK_retained=True,raw_metrics_or_credentials_exported=False,scientific_acceptance=False,
            actual_outer_C0_not_self_asserted=True))
    return int(failure is not None)


if __name__=='__main__':raise SystemExit(main())
