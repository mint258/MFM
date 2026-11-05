"""Explicit two-failed-run SDK transport; old v3 one-file body remains unchanged."""
from __future__ import annotations
import argparse
import subprocess
import time
import traceback
from failed_common import *


def transport_argv(request_path,request_sha,output_root,key,index):
    require(isinstance(request_path,Path) and isinstance(output_root,Path) and key in {r['run_id'] for r in proof_rows(manifest_metadata()[1])}
        and type(index) is int and 0<=index<3 and re.fullmatch(r'[0-9a-f]{64}',request_sha),'Typed explicit original transport constructor required')
    return [str(PYTHON),'-B',str(HERE/'one_run_failed.py'),'--request',str(request_path),
        '--request-sha256',request_sha,'--run-id',key,'--output',str(output_root/f'run_{index}_{key}')]


def controls(request,rows,transport):
    request_gate(request);key=request['selected_run_ids'][0];row=rows[key];header=row['native_RunRecord']
    argv=transport_argv(Path('/tmp/metadata/request.json'),'0'*64,Path('/tmp/metadata'),key,0)
    require(argv[-4:]==['--run-id',key,'--output','/tmp/metadata/run_0_'+key],'Actual typed Path constructor mismatch')
    def reject(call):
        try:call()
        except ValueError:return
        raise ValueError('Metadata negative accepted')
    reject(lambda:transport_argv(Path('/tmp/request'),'0'*64,'/tmp/untyped',key,0))
    reject(lambda:transport_argv(Path('/tmp/request'),'0'*64,Path('/tmp/metadata'),'outside',0))
    candidate={**row,'routing':dict(entity=header['entity'],project=header['project'])}
    command=transport.sync_argv(candidate,Path('/tmp/metadata/run-'+key+'.wandb'))
    require('--sync-all' not in command and command[-2:]==[key,'/tmp/metadata/run-'+key+'.wandb']
        and command[command.index('--project')+1]=='mfm_model_v3_development','Original one-file/project flags changed')
    require(transport.project_remote_steps(iter([{'_step':1},{'_step':2}]),time.monotonic()+2,2)
        ==dict(history_rows=2,first_step=1,last_step=2),'Original unkeyed step parser changed')
    require(transport.project_remote_steps(iter(()),time.monotonic()+2,0)
        ==dict(history_rows=0,first_step=None,last_step=None),'Original zero-history readback changed')
    reject(lambda:transport.project_remote_steps(iter([{'_step':1}]),time.monotonic()+2,0))
    reject(lambda:transport.project_remote_steps(iter([{'_step':True}]),time.monotonic()+2,2))
    reject(lambda:transport.project_remote_steps(iter([{'_step':1},{'_step':1}]),time.monotonic()+2,2))
    return dict(scope='INLINE_METADATA_ONLY_NO_AUTH_OR_UPLOAD_TEST',count=4,
        checks=['actual_typedPath_constructor','untyped_and_unselected_rejected','exact_one_file_project_flags','actual_remote_step_parser_negatives'])


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--request',type=Path,required=True);p.add_argument('--request-sha256',required=True)
    p.add_argument('--pins-sha256',required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();process=allocation();pin=verify(a.pins_sha256);request_ref=ref(a.request)
    require(request_ref['sha256']==a.request_sha256,'Actual request raw SHA differs');request=read(request_ref);request_gate(request)
    require(a.output.absolute().parent==HERE.parent and request['job_output']==str(a.output.absolute()) and not a.output.exists(),
        'Explicit fresh output required');a.output.mkdir(mode=0o700)
    started=time.monotonic();records=[];failure=None;stage='metadata';intent=None
    _,manifest=manifest_metadata();rows={r['run_id']:r for r in proof_rows(manifest)}
    files=[HERE/r['relative_path'] for r in read(pin)['files']]+[HERE/'source_pins.json',a.request]
    before={str(path):ref(path) for path in files}
    try:
        transport=load(ref(HERE/'one_run_failed.py'),'A5_failed_exact_original_v3_transport')
        write(a.output/'INLINE_METADATA_QA.json',controls(request,rows,transport))
        for index,key in enumerate(request['selected_run_ids']):
            require(time.monotonic()-started<request['child_seconds']-900,'Original finite batch window cannot admit another900s child')
            argv=transport_argv(a.request,a.request_sha256,a.output,key,index)
            private=Path(os.environ['TMPDIR']);stdout=private/f'A5_failed_{index}.stdout';stderr=private/f'A5_failed_{index}.stderr'
            intent=write(a.output/f'run_{index}_intent.json',dict(status='INTENT_DURABLE_START_NOT_CONFIRMED',argv=argv,
                stdout_path=str(stdout),stderr_path=str(stderr),job_id=process['job_id'],created_unix=time.time()))
            stage='transport_'+key;tick=time.monotonic()
            with stdout.open('xb') as out,stderr.open('xb') as err:
                completed=subprocess.run(argv,stdin=subprocess.DEVNULL,stdout=out,stderr=err,timeout=900)
            invocation=write(a.output/f'run_{index}_invocation.json',dict(intent=intent,argv=argv,returncode=completed.returncode,
                elapsed_seconds=time.monotonic()-tick,stdout=ref(stdout,4<<20),stderr=ref(stderr,4<<20),job_id=process['job_id'],raw_contents_exported=False))
            raw=ref(a.output/f'run_{index}_{key}'/'result.json');result=read(raw)
            require(completed.returncode==0 and result['status']=='SOURCE_AND_REMOTE_METADATA_VERIFIED'
                and result['run_id']==key and result['native_exit_code']==1,'Actual exact transport/readback did not complete')
            records.append({**{k:result[k] for k in ('run_id','native_exit_code','action','actual_remote_metadata')},'result':raw,'actual_invocation':invocation})
        stage='source_after';request_gate(request);verify(a.pins_sha256)
        require(before=={str(path):ref(path) for path in files},'Source/input drift during explicit sync')
    except BaseException as error:
        failure=dict(type=type(error).__name__,stage=stage,frames=[dict(file=f.filename,line=f.lineno,function=f.name)
            for f in traceback.extract_tb(error.__traceback__)[-32:]],reason='No_exception_messages_credentials_or_metric_values_exported')
    finally:
        write(a.output/'RESULT.json',dict(schema='A5_failed_sync_result_v1',scope=SCOPE,
            status='SYNC_READBACK_CHILD_COMPLETED_PENDING_ROOT_C0' if failure is None else 'FAILED_HOLD_PRESERVED',
            actual_job_id=process['job_id'],actual_argv=list(sys.orig_argv),request=request_ref,source_manifest=pin,
            requested_ids=request['selected_run_ids'],records=records,failure=failure,last_intent=intent,
            source_refs_before=before,source_refs_after={str(path):ref(path) for path in files},
            actual_outer_C0_not_self_asserted=True,elapsed_seconds=time.monotonic()-started,original_SDKs_retained=True,scientific_acceptance=False))
    return int(failure is not None)


if __name__=='__main__':raise SystemExit(main())
