"""One explicitly certified panel run, unchanged v3 official core transport."""
from __future__ import annotations
import argparse
import subprocess
import time
from panel_common import *


def controls(request,row,transport):
    request_gate(request)
    bad={**request,'selected_run_ids':['not-this-run']}
    try:request_gate(bad)
    except ValueError:pass
    else:raise ValueError('Nonselected run negative accepted')
    control_row={**row,'routing':{'entity':row['native_RunRecord']['entity'],'project':row['native_RunRecord']['project']}}
    expected=transport.sync_argv(control_row,Path('/tmp/metadata_only/run-'+RUN+'.wandb'))
    require('--sync-all' not in expected and expected.count('--id')==1 and expected[-2:]==[RUN,'/tmp/metadata_only/run-'+RUN+'.wandb']
        and expected[expected.index('--project')+1]=='phychem-model-v3','Only one exact original ID/project/file may be synced')
    require(transport.project_remote_steps(iter([{'_step':0},{'_step':1}]),time.monotonic()+2,2)
        ==dict(history_rows=2,first_step=0,last_step=1),'Existing remote parser mismatch')
    for values in ([{'_step':0},{'_step':0}],[{'_step':True}]):
        try:transport.project_remote_steps(iter(values),time.monotonic()+2,2)
        except ValueError:pass
        else:raise ValueError('Duplicate/bool remote-step negative accepted')
    return dict(scope='INLINE_METADATA_ONLY_NO_UPLOAD_TEST',count=4,
        checks=['actual_request_gate','nonselected_run_rejection','exact_official_one_file_argv','actual_unkeyed_step_parser_negatives'])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--request',type=Path,required=True);parser.add_argument('--request-sha256',required=True)
    parser.add_argument('--pins-sha256',required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();process=allocation();pin=verify(args.pins_sha256);raw=ref(args.request)
    require(raw['sha256']==args.request_sha256,'Actual request raw SHA differs')
    request=read(raw);request_gate(request)
    require(request['job_output']==str(args.output.absolute()) and args.output.absolute().parent==HERE.parent
        and not args.output.exists(),'Explicit fresh sync output required')
    args.output.mkdir(mode=0o700);started=time.monotonic();failure=None;record=None
    sources=[HERE/item['relative_path'] for item in read(pin)['files']]+[HERE/'source_pins.json',args.request]
    before={str(p):ref(p) for p in sources}
    try:
        transport=load(ref(HERE/'one_run_panel.py'),'panel_exact_original_transport')
        # Proof-derived row before any auth/network, then actual authenticated
        # routing only inside the owned CPU allocation/private stdout capture.
        _,manifest=manifest_metadata();row=row_from_proof(manifest)
        qa=write(args.output/'INLINE_METADATA_QA.json',controls(request,row,transport))
        _,eligible=eligible_rows();require(list(eligible)==[RUN],'One eligible panel run only')
        argv=[str(PYTHON),'-B',str(HERE/'one_run_panel.py'),'--request',str(args.request),
            '--request-sha256',args.request_sha256,'--run-id',RUN,'--output',str(args.output/'run_0_'+RUN)]
        private=Path(os.environ['TMPDIR']);out=private/'panel_sync.stdout';err=private/'panel_sync.stderr'
        tick=time.monotonic()
        with out.open('xb') as stdout,err.open('xb') as stderr:
            completed=subprocess.run(argv,stdin=subprocess.DEVNULL,stdout=stdout,stderr=stderr,timeout=900)
        invocation=write(args.output/'actual_invocation.json',dict(argv=argv,returncode=completed.returncode,
            elapsed_seconds=time.monotonic()-tick,stdout=ref(out,4<<20),stderr=ref(err,4<<20),
            job_id=process['job_id'],raw_contents_exported=False))
        item_ref=ref(args.output/('run_0_'+RUN)/'result.json');item=read(item_ref)
        require(completed.returncode==0 and item['status']=='SOURCE_AND_REMOTE_METADATA_VERIFIED'
            and item['run_id']==RUN and item['native_exit_code']==0,'Actual single transport/source/API readback failed')
        record={**{key:item[key] for key in ('run_id','native_exit_code','action','actual_remote_metadata')},
            'result':item_ref,'actual_invocation':invocation}
        request_gate(request);_,closed_manifest=manifest_metadata()
        require(row_from_proof(closed_manifest)==row,'Independent certificate/metadata changed during transport')
        verify(args.pins_sha256)
        require(before=={str(p):ref(p) for p in sources},'Sync source/input changed')
    except BaseException as error:
        failure=dict(type=type(error).__name__,reason='bounded_single_panel_sync_failed; inspect owned private metadata, no secrets exported')
    finally:
        after={str(p):ref(p) for p in sources}
        if after!=before:failure=failure or dict(type='SourceDrift',reason='source_after_differs')
        write(args.output/'RESULT.json',dict(schema='native_S10000_panel_selective_sync_result_v1',scope=SCOPE,
            status='SYNC_READBACK_CHILD_COMPLETED_PENDING_ROOT_C0' if failure is None else 'FAILED_HOLD_PRESERVED',
            actual_job_id=process['job_id'],actual_allocation=process,actual_argv=list(sys.orig_argv),
            requested_ids=[RUN],records=[] if record is None else [record],failure=failure,request=raw,source_manifest=pin,
            source_refs_before=before,source_refs_after=after,elapsed_seconds=time.monotonic()-started,
            original_SDK_retained=True,raw_metrics_or_credentials_exported=False,scientific_acceptance=False,
            actual_outer_C0_not_self_asserted=True))
    return int(failure is not None)


if __name__=='__main__':raise SystemExit(main())
