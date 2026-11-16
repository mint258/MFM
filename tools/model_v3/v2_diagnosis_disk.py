"""Actual-node model guard; debit D6 allocations already counted in quota used."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import socket
import stat
import subprocess
import time

ROOT=Path('/share/home/zixiao/descriptor_analysis')
spec=importlib.util.spec_from_file_location('tested_model_disk_observer',ROOT/'MFM_model_v3/tools/model_v3/v2_watch_disk.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
CONTROL=ROOT/'runs/data_v1_20261025/control/window2_20261105'
D6=Path('/lfshome/zixiao/data_v1_20261025/D6_full_v31_20261105_v1')


def d6_published(final=None):
    final=Path(final) if final is not None else ROOT/'runs/data_v1_20261025/artifacts/export/D6_full_v31_20261105_v1/compact/manifest.json'
    if not final.is_file():
        return False
    value=json.loads(final.read_text())
    return bool(value.get('split_roots') and value.get('molecules'))


def remaining_nfs_other(final=None):
    # Final ID-map allocation is already in quota used after formal publication.
    return 23_179_869_184+(0 if d6_published(final) else 93_589_934_592)


def remaining_d6():
    if d6_published():
        return 0
    admission=json.loads((CONTROL/'D6_node20_shared_candidate_20261108_v1/admission.json').read_text())
    if admission.get('status')!='ADMITTED':
        raise OSError('D6 future allocation is not admitted/known')
    base=admission['already_allocated_raw_LMDB_bytes']
    future=admission['lustre_raw_or_final_peak_bytes']
    if any(type(x) is not int or x<0 for x in (base,future)):
        raise OSError('D6 allocation forecast is unknown')
    roots=(D6/'write_scratch_node20_candidate_20261108_v1',D6/'shared_compact')
    allocated=sum(path.stat().st_blocks*512 for root in roots for role in ('TRAIN','FULL')
                  if (path:=root/role/'data.mdb').is_file())
    if allocated<base:
        # A new storage phase must get its actual owner forecast before debit.
        raise OSError('D6 allocated base is not present in the bound locations')
    return max(0,future-(allocated-base))


def model_growth_forecast(*, base=Path('/lfshome/zixiao/model_v31_20261105'), registry=None):
    # One global forecast, including explicitly registered follow-on outputs.
    base=Path(base).resolve()
    registry=Path(registry) if registry is not None else ROOT/'runs/model_v31_20261105/model_output_budget.json'
    roots=list(base.glob('M2_DIAG_*'));peak=100_000_000_000
    if registry.is_file():
        record=json.loads(registry.read_text())
        if (record.get('schema')!='MODEL_OUTPUT_BUDGET_V1' or type(record.get('total_peak_bytes')) is not int
                or record['total_peak_bytes']<=0 or not isinstance(record.get('roots'),list)):
            raise OSError('Model output allocation registry is unknown')
        peak=record['total_peak_bytes']
        for name in record['roots']:
            root=Path(name).resolve()
            if root.parent!=base or (root.exists() and not root.is_dir()):
                raise OSError('Registered model output is not a direct owned output directory')
            roots.append(root)
    seen=set();allocated=0
    for path in (p for root in roots if root.is_dir() for p in root.rglob('*')):
        try:
            info=path.lstat()
        except FileNotFoundError:
            # Live pytest temporary files may naturally close/disappear.
            continue
        if stat.S_ISREG(info.st_mode):
            identity=(info.st_dev,info.st_ino)
            if identity not in seen:
                seen.add(identity);allocated+=info.st_blocks*512
    return allocated,max(2_000_000_000,peak-allocated)


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--output',required=True)
    p.add_argument('--node',required=True)
    p.add_argument('--job',required=True,type=int)
    p.add_argument('--state',required=True)
    p.add_argument('--once',action='store_true')
    a=p.parse_args()
    if os.getuid()!=1278 or socket.gethostname().split('.')[0]!=a.node:
        raise ValueError('Actual owning node/UID required')
    quota_lustre=CONTROL/'lustre_quota_available_v2_20261107.json'
    quota_nfs=CONTROL/'share_quota_available_v3.json'
    def save(value):
        value.update(pid=os.getpid(),observed_at=time.time(),node=a.node,jobs=[a.job])
        pending=Path(a.state+'.next');pending.write_text(json.dumps(value)+'\n');pending.replace(a.state)
    def signal(argv,**kwargs):
        # Persist before STOP also stops this job's observer process.
        try:
            save(dict(status='DISK_PAUSED',reason='Actual disk/quota admission failed; own job STOP requested'))
            print('MODEL_DISK_PAUSE',flush=True)
        finally:
            result=subprocess.run(argv,**kwargs)
        return result
    while True:
        try:
            future=remaining_d6()
            other=future+6_000_000_000
            model_allocated,model_remaining=model_growth_forecast()
            nfs_other=remaining_nfs_other()
        except (OSError,ValueError,KeyError,TypeError):
            if a.once:
                raise
            future=None
            other=-1  # Existing tested quota guard refuses unknown forecasts.
            nfs_other=-1
            model_allocated=None;model_remaining=100_000_000_000
        if a.once:
            m.require_capacity(m.filesystem_status('/'),0,0)
            m.require_capacity(m.filesystem_status(a.output),model_remaining,10000)
            m.require_capacity(m.filesystem_status(ROOT/'runs/model_v31_20261105'),67108864,1000)
            print(json.dumps(dict(D6_remaining_forecast=future,model_allocated_bytes=model_allocated,
                model_remaining_forecast=model_remaining,
                lustre=m.quota_headroom(quota_lustre,'/lfshome',model_remaining,other),
                nfs=m.quota_headroom(quota_nfs,'/share',67108864,nfs_other))),flush=True)
            return
        checks=[m.check_and_protect(a.output,[a.job],node=a.node,growth_bytes=model_remaining,
                    quota_reference=quota_lustre,quota_filesystem='/lfshome',quota_concurrent_bytes=other,run=signal),
                m.check_and_protect(ROOT/'runs/model_v31_20261105',[a.job],node=a.node,growth_bytes=67108864,
                    quota_reference=quota_nfs,quota_filesystem='/share',quota_concurrent_bytes=nfs_other,run=signal)]
        paused=any(c['status']=='DISK_PAUSED' for c in checks)
        save(dict(status='DISK_PAUSED' if paused else 'OBSERVING',D6_remaining_forecast=future,
            model_allocated_bytes=model_allocated,model_remaining_forecast=model_remaining,nfs_other_forecast=nfs_other,checks=checks))
        time.sleep(5)


if __name__=='__main__':
    main()
