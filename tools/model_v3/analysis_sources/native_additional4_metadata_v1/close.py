"""Read-only Root closure of1478/1482; SDK payload reads are forbidden."""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import socket
import xml.etree.ElementTree as ET

P=Path('/share/home/zixiao/descriptor_analysis');N=P/'runs/model_v3_20261026'
HERE=Path(__file__).absolute().parent
PY=P/'docs/phase1/evidence/stage43_5090_environment/install_4511929/venv/bin/python'
CASES=[dict(job='4521478',root=N/'native_closed3_sync_actual_v1',source=N/'native_closed3_sync_v1',
    driver='sync_selected_additional.py',child='one_run_additional.py',
    ids=['imuc199l','xswjijb6','jumhvnta']),
    dict(job='4521482',root=N/'native_fw6_sync_actual_v1',source=N/'native_closed_long_sync_v1',
    driver='sync_selected_long.py',child='one_run_long.py',ids=['fw6q26wr'])]
EXPECTED={'imuc199l':(21,0,20,0),'xswjijb6':(21,0,20,0),'jumhvnta':(725,0,724,1),'fw6q26wr':(1003,0,1002,0)}


def require(ok,message):
    if not ok:raise ValueError(message)


def identity(path):
    path=Path(path).absolute()
    require(not any(item.is_symlink() for item in (path,*path.parents)),'Symlink metadata/source rejected')
    info=path.lstat()
    require(stat.S_ISREG(info.st_mode) and info.st_uid==os.getuid() and info.st_nlink==1,'Owned ordinary single-link file required')
    return dict(path=str(path),bytes=info.st_size,device=info.st_dev,inode=info.st_ino,mtime_ns=info.st_mtime_ns)


def ref(path,cap=2<<20):
    path=Path(path).absolute()
    require(path.suffix not in {'.wandb','.jsonl','.pt','.pth','.npz','.npy','.lmdb'},'Payload read forbidden in Root metadata closure')
    before=identity(path);require(before['bytes']<=cap,'Small metadata byte cap exceeded')
    digest=hashlib.sha256(path.read_bytes()).hexdigest()
    require(identity(path)==before,'Metadata changed during hashing')
    return dict(path=str(path),bytes=before['bytes'],sha256=digest)


def bind(raw):
    require(ref(raw['path'])==raw,'Bound raw metadata reference differs')
    return raw


def read(value):
    raw=bind(value) if isinstance(value,dict) else ref(value)
    def pairs(items):
        result={}
        for key,item in items:
            require(key not in result,'Duplicate metadata key');result[key]=item
        return result
    return json.loads(Path(raw['path']).read_bytes(),object_pairs_hook=pairs,
        parse_constant=lambda _:(_ for _ in ()).throw(ValueError('Nonfinite metadata')))


def write(path,value):
    raw=(json.dumps(value,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
    require(len(raw)<=2<<20,'Metadata output cap exceeded')
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('xb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
    return ref(path)


def marker_now(sdk_path):
    marker=Path(str(sdk_path)+'.synced')
    require(not marker.is_symlink(),'Original/stage marker link rejected')
    return dict(exists=marker.exists(),current_ref=ref(marker,65536) if marker.exists() else None)


def close_case(case,accounting,expected_counts=None):
    expected_counts=EXPECTED if expected_counts is None else expected_counts
    root=case['root'];source=case['source'];job=case['job']
    result_ref=ref(root/'RESULT.json');result=read(result_ref);sup_ref=ref(root.parent/(root.name+'.supervisor.json'));sup=read(sup_ref)
    require(result['schema']=='model_v3_selective_sync_job_result_v1'
        and result['status']=='SYNC_READBACK_CHILD_COMPLETED_PENDING_ROOT_C0' and result['failure'] is None
        and str(result['job_id'])==job and result['requested_ids']==case['ids']
        and [r['run_id'] for r in result['records']]==case['ids'],'Actual exact job result/IDs differ')
    bind(result['source_manifest']);pins=read(result['source_manifest'])
    require(result['source_manifest']==ref(source/'source_pins.json'),'Actual job source manifest differs')
    for leaf in pins['files']:
        current=ref(source/leaf['relative_path'])
        require((current['bytes'],current['sha256'])==(leaf['bytes'],leaf['sha256']),'Frozen source changed')
    request_ref=result['request'];request=read(request_ref);manifest=read(request['eligible_manifest'])
    require(request['source_manifest']==result['source_manifest'] and request['job_output']==str(root)
        and request['selected_run_ids']==case['ids'],'Request/source/output differs')
    source_before=result['source_hashes_before'];source_after=result['source_hashes_after']
    require(source_before==source_after and source_after,'Actual source before/after differs or is empty')
    current_hashes={path:ref(path)['sha256'] for path in source_after}
    require(current_hashes==source_after,'Current small-source/proof/manifest hashes differ from actual job')
    command=[str(PY),'-u','-B',str(source/case['driver']),'--request',request_ref['path'],
        '--request-sha256',request_ref['sha256'],'--pins-sha256',result['source_manifest']['sha256'],'--output',str(root)]
    require(str(sup['job_id'])==job and sup['status']=='COMPLETED' and sup['exit_code']==0
        and sup['first_failure'] is None and sup['remaining']==[] and sup['command']==command
        and sup['private_storage']['first_sampling_failure'] is None,'Actual same-job supervisor/process closure differs')
    supervisor_current={path:ref(path)['sha256'] for path in sup['sources_sha256']}
    require(supervisor_current==sup['sources_sha256'],'Current supervisor implementation source differs')
    qa_ref=ref(root/'metadata_QA.json');qa=read(qa_ref);bind(qa['XML'])
    require(qa['returncode']==0 and qa['counts']==dict(tests=4,failures=0,errors=0,skipped=0),'Actual4 inline metadata QA missing')
    suites=list(ET.parse(qa['XML']['path']).getroot().iter('testsuite'))
    xml_counts={key:sum(int(s.get(key,0)) for s in suites) for key in ('tests','failures','errors','skipped')}
    require(xml_counts==qa['counts'],'Inline actual XML counts differ')
    rows={row['run_id']:row for row in manifest['runs']};records=[]
    for ordinal,record in enumerate(result['records']):
        key=record['run_id'];n,first,last,exit_code=expected_counts[key];row=rows[key]
        sub_ref=record['result'];sub=read(sub_ref);inv_ref=record['actual_invocation'];inv=read(inv_ref)
        require(sub_ref==ref(root/f'run_{ordinal}_{key}'/'result.json')
            and inv_ref==ref(root/f'run_{ordinal}_invocation.json'),'Exact per-run receipt path differs')
        expected=dict(entity='mint_leaf258',project='mfm_model_v3_development',run_id=key,
            state='failed' if exit_code else 'finished',history_rows=n,first_step=first,last_step=last)
        require(sub['schema']=='model_v3_one_WandB_sync_readback_v1' and sub['status']=='SOURCE_AND_REMOTE_METADATA_VERIFIED'
            and sub['failure'] is None and sub['source_manifest']==result['source_manifest']
            and sub['run_id']==key and sub['native_exit_code']==record['native_exit_code']==exit_code
            and sub['expected_remote_metadata']==sub['actual_remote_metadata']==record['actual_remote_metadata']==expected
            and sub['source_hash_before_after_equal'] is True and sub['original_sync_marker_unchanged'] is True
            and sub['action']==record['action']=='SYNCED_EXACT_COPY_AND_API_VERIFIED',
            'Actual exact source/marker/state/count/step/API readback evidence differs')
        require((row['history_rows'],row['first_explicit_step'],row['last_explicit_step'],row['native_exit_code'])==(n,first,last,exit_code)
            and row['SDK_raw_ref']==sub['original_source'],'Proof-derived manifest differs')
        child=[str(PY),'-B',str(source/case['child']),'--request',request_ref['path'],
            '--request-sha256',request_ref['sha256'],'--run-id',key,'--output',str(root/f'run_{ordinal}_{key}')]
        require(inv['argv']==child and inv['returncode']==0 and str(inv['job_id'])==job,'Actual one-run process receipt differs')
        raw=sub['original_source'];staged=sub['staged_SDK'];cli=sub['official_core_command']
        require(raw['bytes']==staged['bytes'] and raw['sha256']==staged['sha256']
            and Path(staged['path']).is_relative_to(root/f'run_{ordinal}_{key}'/'stage')
            and cli['returncode']==0 and cli['timeout'] is False,'Actual exact-copy official CLI receipt differs')
        argv=[str(PY),'-B','-m','wandb','sync','--yes','--no-sync-tensorboard','--include-offline',
            '--entity',expected['entity'],'--project',expected['project'],'--id',key,staged['path']]
        require(cli['argv']==argv,'Official single-file core CLI argv differs')
        source_stat=identity(raw['path']);stage_stat=identity(staged['path'])
        require(source_stat['bytes']==raw['bytes'] and stage_stat['bytes']==staged['bytes'],'Current stat size differs')
        records.append(dict(run_id=key,url='https://wandb.ai/'+expected['entity']+'/'+expected['project']+'/runs/'+key,
            sync_job_id=job,actual_remote_metadata=expected,native_exit_code=exit_code,action=sub['action'],
            result=sub_ref,actual_invocation=inv_ref,original_SDK_raw_ref_from_sync_job=raw,
            staged_SDK_raw_ref_from_sync_job=staged,worker_SDK_before_after_hash_equal=True,
            Root_current_SDK_bytes_read=False,Root_current_SDK_independent_SHA_verified=False,
            current_original_SDK_stat_only=source_stat,current_stage_SDK_stat_only=stage_stat,
            worker_original_marker_before_after_equal=True,worker_marker_individual_hashes_exported=False,
            current_original_marker=marker_now(raw['path']),current_stage_marker=marker_now(staged['path']),
            Root_current_vs_worker_marker_SHA_compared=False,cloud_API_requeried_by_Root=False,
            source_scope=row.get('original_scope',row.get('scope')),scientific_acceptance=False))
    return dict(job_id=job,actual_terminal=accounting,result=result_ref,supervisor=sup_ref,inline_QA=qa_ref,
        inline_QA_XML=qa['XML'],source_before_after_and_current_equal=True,current_source_hashes=current_hashes,
        current_supervisor_source_hashes=supervisor_current,records=records)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--evidence-root',type=Path,required=True);p.add_argument('--pins-sha256',required=True);a=p.parse_args()
    require(os.getuid()==1278 and socket.gethostname()=='sonmi','Actual Root sonmi metadata execution required')
    source=ref(HERE/'source_pins.json');require(source['sha256']==a.pins_sha256,'Closure source manifest differs')
    for leaf in read(source)['files']:
        actual=ref(HERE/leaf['relative_path'])
        require((actual['bytes'],actual['sha256'])==(leaf['bytes'],leaf['sha256']),'Closure implementation changed')
    require(not a.output.exists() and not a.evidence_root.exists(),'Fresh closure/evidence output required')
    argv=['sacct','-X','-n','-P','-j','4521478,4521482','--format=JobIDRaw,State,ExitCode,ElapsedRaw,AllocCPUS']
    done=subprocess.run(argv,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=45)
    require(done.returncode==0 and len(done.stdout)+len(done.stderr)<=1<<20,'Actual accounting command failed')
    terminal={}
    for line in done.stdout.splitlines():
        if not line.strip():continue
        fields=line.strip().split('|');require(len(fields)==5 and fields[0] not in terminal,'Accounting row malformed/duplicated')
        job,state,code,seconds,cpus=fields
        require(job in {'4521478','4521482'} and state=='COMPLETED' and code=='0:0'
            and seconds.isdigit() and cpus=='16','Every actual parent must be C0/16CPU')
        terminal[job]=dict(job_id=job,state=state,exit_code=code,elapsed_seconds=int(seconds),allocated_cpus=16)
    require(set(terminal)=={'4521478','4521482'},'Missing explicit actual accounting parent')
    a.evidence_root.mkdir(mode=0o700,parents=True)
    raw=write(a.evidence_root/'raw_sacct.json',dict(argv=argv,returncode=done.returncode,stdout=done.stdout,stderr=done.stderr))
    jobs=[close_case(case,{**terminal[case['job']],'raw_sacct':raw}) for case in CASES]
    records=[r for job in jobs for r in job['records']]
    require({r['run_id'] for r in records}==set(EXPECTED) and len(records)==4,'Exact additional4 population required')
    result=write(a.output,dict(schema='native_additional4_sync_Root_closure_v1',
        status='ROOT_CLOSED_C0_METADATA_VERIFIED',created_UTC=datetime.now(timezone.utc).isoformat(),
        source_manifest=source,jobs=jobs,records=records,accepted_count=4,
        expected_history_rows=[21,21,725,1003],failed_native_state_preserved=['jumhvnta'],
        SDK_current_independent_rehash=False,SDK_bytes_read_or_decoded_by_Root=False,
        SDK_hash_evidence='actual_sync_worker_before_after_and_staged_copy; Root current stat only',
        marker_hash_scope='worker compared before/after refs but did not export individual marker SHA; Root now observation separate',
        cloud_API_requeried_by_Root=False,fixed50_or_first3_sources_modified=False,
        original_failed_training_status_unchanged=True,scientific_acceptance=False,active_runs_included=False))
    print(json.dumps(dict(result=result,status='ROOT_CLOSED_C0_METADATA_VERIFIED',accepted_count=4,
        run_ids=[r['run_id'] for r in records],SDK_bytes_read=False)))
    return 0


if __name__=='__main__':raise SystemExit(main())
