"""Actual QA1398 gate, then exec unchanged readiness v1. No queue/controller."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import xml.etree.ElementTree as ET

BASE=Path('/share/home/zixiao/descriptor_analysis')
NEW=BASE/'runs/model_v3_20261026'
FROZEN=NEW/'native_S_supplemental_readiness_v2'
QA={"path":"/share/home/zixiao/descriptor_analysis/runs/model_v3_20261026/native_S_QA55_actual1398_v1.json","bytes":1739,"sha256":"5e3e693b3106f78ec3548c6405acefc9aa0e662ac91cfe2b8730c1ea5c285db9"}
PINS={"path":"/share/home/zixiao/descriptor_analysis/runs/model_v3_20261026/native_S_supplemental_readiness_v2/source_pins_v1.json","bytes":1402,"sha256":"ee354d99908b19efc87b1bbc551d4abbd254a7035a22372f8220bd0e7e63bdce"}
REQUEST={"path":"/share/home/zixiao/descriptor_analysis/runs/model_v3_20261026/native_S_readiness_request_v2.json","bytes":7127,"sha256":"6b28a7654bd4d64e47263ab771074413111696d38cb2a29f69970e01369730d0"}
ORIGINAL={"path":"/share/home/zixiao/descriptor_analysis/runs/model_v3_20261026/native_S_supplemental_readiness_v2/readiness.sbatch","bytes":1531,"sha256":"83a73ea7a331aff02200c660c0a274d971099130e8cd511efcbfb885e116a6c5"}


def require(ok,message):
    if not ok:raise ValueError(message)


def bind(value):
    require(re.fullmatch(r'[0-9a-f]{64}',value['sha256']) is not None,'Declared SHA must be64 machine hexadecimal characters')
    path=Path(value['path']);before=path.stat()
    require(path.is_absolute() and path==path.resolve(strict=True) and path.is_file()
        and before.st_uid==os.getuid() and before.st_nlink==1 and before.st_size==value['bytes']<=4<<20,
        'Bounded owned physical metadata required')
    raw=path.read_bytes();after=path.stat()
    require((before.st_ino,before.st_size,before.st_mtime_ns)==(after.st_ino,after.st_size,after.st_mtime_ns)
        and hashlib.sha256(raw).hexdigest()==value['sha256'],'Raw metadata/source binding differs')
    return raw


def read(value):return json.loads(bind(value))


def check():
    proof=read(QA);pins=read(PINS);request=read(REQUEST);bind(ORIGINAL)
    require(proof['schema']=='model_v3_actual_QA55_C0_metadata_v1' and proof['job_id']=='4521398','Actual new QA1398 proof required')
    raw=proof['raw_sacct'];expected=['sacct','-X','-n','-P','-j','4521398',
        '--format=JobIDRaw,User,State,ExitCode,ElapsedRaw,AllocCPUS,NodeList']
    require(raw['argv']==expected and raw['returncode']==0,'Actual successful QA1398 sacct capture required')
    lines=raw['stdout'].strip().splitlines();fields=lines[0].split('|') if len(lines)==1 else []
    require(len(fields)==7 and fields[:4]==['4521398','zixiao','COMPLETED','0:0']
        and int(fields[5])>=16 and fields[6]=='compute-0-13','QA1398 raw parent is not actual CPU C0')
    unit,summary,supervisor,original=(read(proof[key]) for key in ('unit','summary','supervisor','request'))
    require(proof['request']['sha256']=='61b4cbc5ee0a96d5193b14600c167ab81a6605a8112a6e624b473ef9b82b4a5a','Original frozen v55 source request required')
    counts=dict(tests=0,failures=0,errors=0,skipped=0)
    root=ET.fromstring(bind(proof['xml']))
    for suite in root.iter('testsuite'):
        for key in counts:counts[key]+=int(suite.attrib.get(key,0))
    expected_counts=dict(tests=55,failures=0,errors=0,skipped=0)
    require(counts==expected_counts and unit['counts']==expected_counts and unit['returncode']==0
        and unit['source_hashes_before']==unit['source_hashes_after']==original['tasks'][0]['sources']
        and summary['status']=='PASS' and summary['job_id']=='4521398' and summary['units']==[unit]
        and summary['request_sha256']==proof['request']['sha256'],'Actual zero-skip XML/result/source identity differs')
    require(supervisor['job_id']=='4521398' and supervisor['status']=='COMPLETED' and supervisor['exit_code']==0
        and supervisor['first_failure'] is None and supervisor['retirement'] is None and supervisor['remaining']==[],
        'Actual QA1398 supervision/process closure required')
    for row in pins['files']:
        bind(dict(path=str(FROZEN/row['relative_path']),bytes=row['bytes'],sha256=row['sha256']))
    require(request['scope']=='NATIVE_S_PROFILE_READINESS_ONLY' and request['supervisor_seconds']==1500
        and request['RSS_bytes']==12<<30 and request['output_private_joint_bytes']==2<<30,'Original workload budgets must remain frozen')
    return request


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--validate-only',action='store_true');args=parser.parse_args()
    request=check()
    if args.validate_only:
        print(json.dumps(dict(valid=True,actual_QA_job='4521398',no_SDK_CP_or_compute=True,
            old_expired_1334_not_used_as_C0=True,original_workload_unchanged=True)));return 0
    job=os.environ.get('SLURM_JOB_ID','');node=socket.gethostname();group=Path('/proc/self/cgroup').read_text()
    require(job.isdigit() and job!='4521398' and node==os.environ.get('MODEL_V3_EXPECTED_NODE')
        and re.fullmatch(r'compute-0-(?:2|[8-9]|1[0-9])',node)
        and os.environ.get('SLURM_JOB_PARTITION')=='cpu' and os.environ.get('SLURM_CPUS_PER_TASK')=='16'
        and os.environ.get('SLURM_MEM_PER_NODE')=='16384'
        and re.search(r'(?:^|/)job[_/-]'+re.escape(job)+r'(?:/|$)',group,re.M),'Actual own CPU16/16GiB Slurm/kernel allocation required')
    expected=dict(MODEL_V3_READINESS_SOURCE_PINS=PINS['path'],MODEL_V3_READINESS_SOURCE_PINS_SHA=PINS['sha256'],
        MODEL_V3_READINESS_REQUEST=REQUEST['path'],MODEL_V3_READINESS_REQUEST_SHA=REQUEST['sha256'],
        MODEL_V3_READINESS_OUTPUT=request['output_root'])
    require(all(os.environ.get(key)==value for key,value in expected.items()),'Direct bindings must preserve original pins/request/output')
    require(not Path(request['output_root']).exists(),'Original readiness output must be fresh')
    print(json.dumps(dict(schema='native_S_readiness_direct_entry_observation_v1',job_id=job,uid=os.getuid(),
        node=node,cgroup=group,actual_QA1398=QA,original_source=ORIGINAL,original_request=REQUEST,
        queue_publisher_or_expired_peer_not_consulted=True,own_C0_not_asserted=True)),flush=True)
    os.chdir(BASE)
    os.execve('/bin/bash',['/bin/bash',ORIGINAL['path']],{**os.environ,'CUDA_VISIBLE_DEVICES':'','PYTHONDONTWRITEBYTECODE':'1'})


if __name__=='__main__':raise SystemExit(main())
