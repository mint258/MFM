"""Independent wpgg metadata closure; fixed additional4 remains untouched."""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import importlib.util
import json
import os
from pathlib import Path
import socket
import subprocess
import sys

HERE=Path(__file__).absolute().parent
BASE=HERE.parent/'native_additional4_metadata_v1'
spec=importlib.util.spec_from_file_location('frozen_additional4_metadata_support',BASE/'close.py')
support=importlib.util.module_from_spec(spec);sys.modules[spec.name]=support;spec.loader.exec_module(support)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--evidence-root',type=Path,required=True);p.add_argument('--pins-sha256',required=True);a=p.parse_args()
    s=support
    s.require(os.getuid()==1278 and socket.gethostname()=='sonmi','Actual Root sonmi metadata execution required')
    source=s.ref(HERE/'source_pins.json');s.require(source['sha256']==a.pins_sha256,'WPGG metadata source differs')
    own=s.read(source)
    for leaf in own['files']:
        actual=s.ref(HERE/leaf['relative_path'])
        s.require((actual['bytes'],actual['sha256'])==(leaf['bytes'],leaf['sha256']),'WPGG metadata source changed')
    for raw in own['source_dependencies']:s.bind(raw)
    s.require(not a.output.exists() and not a.evidence_root.exists(),'Fresh independent wpgg evidence/output required')
    argv=['sacct','-X','-n','-P','-j','4521511','--format=JobIDRaw,State,ExitCode,ElapsedRaw,AllocCPUS']
    done=subprocess.run(argv,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=45)
    s.require(done.returncode==0 and len(done.stdout)+len(done.stderr)<=1<<20,'Actual1511 accounting command failed')
    fields=done.stdout.strip().split('|')
    s.require(len(fields)==5 and fields[:3]==['4521511','COMPLETED','0:0'] and fields[3].isdigit()
        and fields[4]=='16','Exact actual1511 C0/16CPU missing')
    a.evidence_root.mkdir(mode=0o700,parents=True)
    raw=s.write(a.evidence_root/'raw_sacct.json',dict(argv=argv,returncode=0,stdout=done.stdout,stderr=done.stderr))
    accounting=dict(job_id='4521511',state='COMPLETED',exit_code='0:0',elapsed_seconds=int(fields[3]),allocated_cpus=16,raw_sacct=raw)
    case=dict(job='4521511',root=s.N/'native_wpgg_sync_actual_v1',source=s.N/'native_closed_long_sync_v1',
        driver='sync_selected_long.py',child='one_run_long.py',ids=['wpggfu9n'])
    job=s.close_case(case,accounting,{'wpggfu9n':(1002,2005,3006,0)})
    result=s.write(a.output,dict(schema='native_wpgg_sync_Root_closure_v1',status='ROOT_CLOSED_C0_METADATA_VERIFIED',
        created_UTC=datetime.now(timezone.utc).isoformat(),source_manifest=source,jobs=[job],records=job['records'],accepted_count=1,
        SDK_current_independent_rehash=False,SDK_bytes_read_or_decoded_by_Root=False,
        SDK_hash_evidence='actual_sync_worker_before_after_and_staged_copy; Root current stat only',
        marker_hash_scope='worker equality only for historical marker hashes; current small marker ref observed separately',
        cloud_API_requeried_by_Root=False,fixed50_or_additional4_modified=False,
        actual_scope='wpggfu9n_only_rows1002_steps2005_to3006_native_exit0',scientific_acceptance=False,active_runs_included=False))
    print(json.dumps(dict(result=result,status='ROOT_CLOSED_C0_METADATA_VERIFIED',accepted_count=1,SDK_bytes_read=False)))
    return 0


if __name__=='__main__':raise SystemExit(main())
