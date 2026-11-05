"""One pilot or at most3 explicit sequential sync/readback runs; no dispatcher."""
from __future__ import annotations
import argparse
import os
from pathlib import Path
import subprocess
import time
import sys
import xml.etree.ElementTree as ET
from sync_common import *


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--request',type=Path,required=True);p.add_argument('--request-sha256',required=True)
    p.add_argument('--pins-sha256',required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();process=allocation();manifest=verify(a.pins_sha256)
    request_ref=ref(a.request);require(request_ref['sha256']==a.request_sha256,'Request raw SHA differs')
    request=read(request_ref);request_gate(request);_,rows=eligible_rows()
    selected=request['selected_run_ids']
    require(request['source_manifest']==manifest and request['job_output']==str(a.output.absolute())
        and len(selected)==len(set(selected)) and all(key in rows for key in selected)
        and 1<=len(selected)<=(1 if request['mode']=='pilot' else 3), 'Explicit bounded request/output differs')
    require(not a.output.exists(),'Fresh sync job output required');a.output.mkdir(mode=0o700)
    # Meaningful metadata tests accompany the real sync CPU task, not another
    # small QA parent. Fixtures use normal failed-retention cleanup.
    sources=[HERE/row['relative_path'] for row in read(manifest)['files']]+[HERE/'source_pins.json',a.request]
    before={str(path):ref(path)['sha256'] for path in sources}
    start=time.monotonic();records=[];failure=None
    try:
        xml=a.output/'metadata4.xml'
        qa=subprocess.run([str(PYTHON),'-B','-m','pytest',str(HERE/'test_sync_metadata.py'),'-q',
            '-p','no:cacheprovider','-o','tmp_path_retention_policy=failed',
            '--basetemp='+str(a.output/'metadata_tmp'),'--junitxml='+str(xml)],
            stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=60)
        require(len(qa.stdout)+len(qa.stderr)<=1<<20,'Metadata QA console exceeds1MiB')
        suites=list(ET.parse(xml).getroot().iter('testsuite'))
        counts={name:sum(int(s.get(name,0)) for s in suites) for name in ('tests','failures','errors','skipped')}
        write(a.output/'metadata_QA.json',dict(returncode=qa.returncode,counts=counts,XML=ref(xml),
            stdout_bytes=len(qa.stdout),stderr_bytes=len(qa.stderr),raw_values_exported=False))
        require(qa.returncode==0 and counts==dict(tests=4,failures=0,errors=0,skipped=0),'Exact metadata4 zero-skip QA failed')
        for index,key in enumerate(selected):
            require(time.monotonic()-start<request['child_seconds']-900,'Insufficient finite window for another one-run sync')
            argv=[str(PYTHON),'-B',str(HERE/'one_run.py'),'--request',str(a.request),
                '--request-sha256',a.request_sha256,'--run-id',key,'--output',str(a.output/f'run_{index}_{key}')]
            private=Path(os.environ['TMPDIR']);out=private/f'sync_child_{index}.stdout';err=private/f'sync_child_{index}.stderr'
            tick=time.monotonic()
            with out.open('xb') as stdout,err.open('xb') as stderr:
                result=subprocess.run(argv,stdin=subprocess.DEVNULL,stdout=stdout,stderr=stderr,
                    env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'},timeout=900)
            invocation=write(a.output/f'run_{index}_invocation.json',dict(argv=argv,returncode=result.returncode,
                elapsed_seconds=time.monotonic()-tick,stdout=ref(out,4<<20),stderr=ref(err,4<<20),
                raw_contents_exported=False,job_id=process['job_id']))
            path=a.output/f'run_{index}_{key}'/'result.json'
            require(path.exists(),'Run child did not publish metadata result')
            item=read(path);item_ref=ref(path)
            require(result.returncode==0 and item['status']=='SOURCE_AND_REMOTE_METADATA_VERIFIED',
                'One-run sync/readback failed; later selected runs not attempted')
            records.append({**{name:item[name] for name in ('run_id','native_exit_code','action','actual_remote_metadata')},
                'result':item_ref,'actual_invocation':invocation})
        require(before=={str(path):ref(path)['sha256'] for path in sources},'Sync source/request changed during job')
    except BaseException as error:
        failure=dict(type=type(error).__name__,reason='bounded_sync_or_metadata_gate_failed; inspect referenced_metadata_only')
    write(a.output/'RESULT.json',dict(schema='model_v3_selective_sync_job_result_v1',
        status='SYNC_READBACK_CHILD_COMPLETED_PENDING_ROOT_C0' if failure is None else 'FAILED_HOLD_PRESERVED',
        mode=request['mode'],records=records,requested_ids=selected,failure=failure,
        source_manifest=manifest,request=request_ref,job_id=process['job_id'],actual_allocation=process,
        elapsed_seconds=time.monotonic()-start,source_hashes_before=before,
        source_hashes_after={str(path):ref(path)['sha256'] for path in sources},
        original_SDKs_retained=True,raw_metrics_or_keys_exported=False,scientific_acceptance=False,
        actual_outer_C0_not_self_asserted=True))
    return int(failure is not None)


if __name__=='__main__':raise SystemExit(main())
