"""Root metadata-only closure and next-three listing; no submission/retry."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

HERE=Path(__file__).absolute().parent
V3=HERE.parent/'wandb_selective_sync50_v3'
sys.path.insert(0,str(V3))
from sync_common import ref,bind,read,write,require,verify,root_only,PYTHON,request_gate
from one_run import expected_remote,sync_argv

V3_SHA='4e97d0f413564ace06555067e828bb7109334573c5e43338426cdecf083609c3'


def check_job(result_path,source,rows):
    result_ref=ref(result_path);value=read(result_ref);job=str(value['job_id'])
    root=Path(result_ref['path']).parent
    require(job.isdigit() and value['schema']=='model_v3_selective_sync_job_result_v1'
        and value['status']=='SYNC_READBACK_CHILD_COMPLETED_PENDING_ROOT_C0'
        and value['failure'] is None and value['source_manifest']==source,
        'Actual completed frozen-v3 result required')
    request_ref=value['request'];request=read(request_ref);request_gate(request)
    require(request['source_manifest']==source and request['job_output']==str(root)
        and value['requested_ids']==request['selected_run_ids']
        and value['mode']==request['mode'] and value['mode'] in ('pilot','batch')
        and 1<=len(value['records'])<=(1 if value['mode']=='pilot' else 3)
        and [r['run_id'] for r in value['records']]==value['requested_ids']
        and len(set(value['requested_ids']))==len(value['requested_ids']),
        'Exact original request/population/one-to-three record binding differs')
    before=value['source_hashes_before'];after=value['source_hashes_after']
    pins=read(source)
    expected={str(V3/f['relative_path']):f['sha256'] for f in pins['files']}
    expected.update({source['path']:source['sha256'],request_ref['path']:request_ref['sha256']})
    require(before==after==expected,'Actual source/request before-after scope or hashes differ')
    for path,sha in after.items():require(ref(path)['sha256']==sha,'Completed source/request changed')
    sup_ref=ref(root.parent/(root.name+'.supervisor.json'));sup=read(sup_ref)
    expected_command=[str(PYTHON),'-u','-B',str(V3/'sync_selected.py'),'--request',request_ref['path'],
        '--request-sha256',request_ref['sha256'],'--pins-sha256',source['sha256'],'--output',str(root)]
    require(str(sup['job_id'])==job and sup['status']=='COMPLETED' and sup['exit_code']==0
        and sup['first_failure'] is None and sup['remaining']==[] and sup['command']==expected_command
        and sup['private_storage']['first_sampling_failure'] is None,
        'Actual same-job supervisor/source/process/private closure required')
    dependency_sources={item['path']:item['sha256'] for item in read(V3/'dependencies.json')['files']}
    require(len(sup['sources_sha256'])==4 and all(dependency_sources.get(path)==sha
        for path,sha in sup['sources_sha256'].items()),'Actual supervisor runtime source pins differ')
    qa_ref=ref(root/'metadata_QA.json');qa=read(qa_ref);bind(qa['XML'])
    require(qa['returncode']==0 and qa['counts']==dict(tests=4,failures=0,errors=0,skipped=0),
        'Actual four metadata tests zero-skip closure missing')
    accepted=[]
    for index,record in enumerate(value['records']):
        key=record['run_id'];require(key in rows,'Run outside fixed50')
        row=rows[key];wanted=expected_remote(row);sub_ref=record['result'];sub=read(sub_ref)
        require(sub_ref==ref(root/f'run_{index}_{key}'/'result.json')
            and sub['schema']=='model_v3_one_WandB_sync_readback_v1'
            and sub['status']=='SOURCE_AND_REMOTE_METADATA_VERIFIED' and sub['failure'] is None
            and sub['run_id']==key and sub['native_exit_code']==row['native_exit_code']==record['native_exit_code']
            and sub['source_manifest']==source and sub['original_source']==row['SDK_raw_ref']
            and sub['source_hash_before_after_equal'] is True and sub['original_sync_marker_unchanged'] is True
            and sub['expected_remote_metadata']==sub['actual_remote_metadata']==record['actual_remote_metadata']==wanted
            and sub['action']==record['action'], 'Per-run source/state/count/step readback binding differs')
        inv_ref=record['actual_invocation'];inv=read(inv_ref)
        child_argv=[str(PYTHON),'-B',str(V3/'one_run.py'),'--request',request_ref['path'],
            '--request-sha256',request_ref['sha256'],'--run-id',key,'--output',str(root/f'run_{index}_{key}')]
        require(inv_ref==ref(root/f'run_{index}_invocation.json') and inv['argv']==child_argv
            and inv['returncode']==0 and str(inv['job_id'])==job,'Actual successful one-run invocation differs')
        if sub['action']=='SYNCED_EXACT_COPY_AND_API_VERIFIED':
            stage=sub['staged_SDK'];raw=row['SDK_raw_ref'];command=sub['official_core_command']
            require(stage['bytes']==raw['bytes'] and stage['sha256']==raw['sha256']
                and Path(stage['path']).is_relative_to(root/f'run_{index}_{key}'/'stage')
                and command['returncode']==0 and command['timeout'] is False
                and command['argv']==sync_argv(row,stage['path']), 'Exact staged official CLI receipt differs')
        else:
            require(sub['action']=='REMOTE_ALREADY_MATCHED_NO_REPLAY'
                and sub['official_core_command'] is None and sub['staged_SDK'] is None,
                'Only exact-copy replay or already-matched no-replay is admitted')
        require(key!='4sgxpx8j' or sub['action']=='REMOTE_ALREADY_MATCHED_NO_REPLAY',
            '1410 already-uploaded4sg must not be replayed')
        accepted.append(dict(run_id=key,job_id=job,action=sub['action'],result=sub_ref,invocation=inv_ref))
    return dict(job_id=job,result=result_ref,supervisor=sup_ref,metadata_QA=qa_ref,
        mode=value['mode'],records=accepted)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--completed',type=Path,nargs='+',required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--pins-sha256',required=True)
    p.add_argument('--raw-sacct',type=Path,help='Optional actual argv/returncode/stdout/stderr JSON for the exact listed jobs')
    a=p.parse_args();root_only();pin=ref(HERE/'source_pins.json')
    require(pin['sha256']==a.pins_sha256,'Closure helper manifest differs')
    own=read(pin)
    for leaf in own['files']:
        actual=ref(HERE/leaf['relative_path'])
        require((actual['bytes'],actual['sha256'])==(leaf['bytes'],leaf['sha256']),'Closure helper source changed')
    source=verify(V3_SHA);manifest=read(V3/'explicit50.json');rows={r['run_id']:r for r in manifest['runs']}
    require(len(a.completed)<=50 and len(set(a.completed))==len(a.completed),'Explicit bounded unique completed list required')
    jobs=[check_job(path,source,rows) for path in a.completed]
    ids=[item['job_id'] for item in jobs];require(len(ids)==len(set(ids)),'Completed jobs duplicated')
    argv=['sacct','-X','-n','-P','-j',','.join(ids),'--format=JobIDRaw,State,ExitCode']
    if a.raw_sacct:raw=read(a.raw_sacct);raw_ref=ref(a.raw_sacct)
    else:
        tick=time.time();done=subprocess.run(argv,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=45)
        raw=dict(argv=argv,returncode=done.returncode,stdout=done.stdout,stderr=done.stderr,
            started_unix=tick,completed_unix=time.time());raw_ref=None
    require(raw['argv']==argv and type(raw['returncode']) is int and raw['returncode']==0,
        'Actual exact Root terminal command/return code required')
    terminal=[line.strip() for line in raw['stdout'].splitlines() if line.strip()]
    require(len(terminal)==len(ids) and set(terminal)=={job+'|COMPLETED|0:0' for job in ids},
        'Every explicitly supplied parent must be actually COMPLETED0:0')
    a.output.mkdir(mode=0o700,parents=True,exist_ok=False)
    if raw_ref is None:raw_ref=write(a.output/'raw_sacct.json',raw)
    accepted={r['run_id'] for item in jobs for r in item['records']}
    remaining=[r['run_id'] for r in manifest['runs'] if r['run_id'] not in accepted]
    pilots=[item for item in jobs if item['mode']=='pilot' and len(item['records'])==1]
    require(pilots,'Explicit actual-C0 pilot must remain in the closure input')
    pilot=pilots[0]
    next_ids=remaining[:3]
    next_argv=None
    if next_ids:
        next_argv=[str(PYTHON),'-B',str(V3/'prepare_sync.py'),'--mode','batch','--runs',*next_ids,
            '--output','ROOT_CHOOSE_FRESH_PLAN','--job-output','ROOT_CHOOSE_FRESH_JOB_OUTPUT',
            '--pins-sha256',source['sha256'],'--pilot-result',pilot['result']['path'],
            '--pilot-supervisor',pilot['supervisor']['path'],'--pilot-job',pilot['job_id']]
    report=dict(schema='model_v3_sync50_actual_Root_closure_and_next_v1',
        status='EXPLICIT_COMPLETED_PARENTS_C0_AND_METADATA_VERIFIED',source_manifest=pin,
        frozen_sync_source=source,fixed50=ref(V3/'explicit50.json'),raw_actual_sacct=raw_ref,jobs=jobs,
        accepted_count=len(accepted),accepted_run_ids=[r['run_id'] for r in manifest['runs'] if r['run_id'] in accepted],
        remaining_count=len(remaining),next_run_ids=next_ids,next_prepare_argv_TEMPLATE_ONLY=next_argv,
        already_uploaded_must_not_replay=[key for key in next_ids if key=='4sgxpx8j'],
        original_SDK_payloads_opened=False,network_or_API_called=False,sbatch_called=False,
        auto_retry=False,science_acceptance=False)
    written=write(a.output/'CLOSURE_AND_NEXT.json',report)
    print(json.dumps(dict(result=written,accepted_count=len(accepted),remaining_count=len(remaining),next_run_ids=next_ids)))
    return 0


if __name__=='__main__':raise SystemExit(main())
