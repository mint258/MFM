"""Retire only reconstructible raw H of the three CLOSED3M diagnostics.

No model/array is loaded, no hash or statistic is recomputed. Final NPZ draws,
predictions, manifests, checkpoints, failed partials and all other runs remain.
"""
import argparse
import json
import os
from pathlib import Path
import re
import socket
import stat
import time
from types import SimpleNamespace
from storage_20261122 import CONTROL,REPO,write,claim_current
from finetune_extension_20261124 import query


def checked_file(path,root):
    path,root=Path(path),Path(root)
    if not path.is_relative_to(root) or path.resolve()!=path or root.resolve()!=root:
        raise ValueError('Scratch retirement path escaped its canonical owned root')
    observed=path.lstat()
    if (not stat.S_ISREG(observed.st_mode) or observed.st_uid!=os.getuid()
            or observed.st_nlink!=1):
        raise ValueError('Only one regular owned scratch inode may retire')
    return dict(path=str(path),device=observed.st_dev,inode=observed.st_ino,
        bytes=observed.st_size,allocated_bytes=observed.st_blocks*512,mtime_ns=observed.st_mtime_ns)


def retire_one(row,root):
    path=Path(row['path'])
    current=checked_file(path,root)
    if current!=row:
        raise ValueError('Closed scratch changed after the retirement plan')
    path.unlink()


def plan():
    read=lambda p:json.loads(Path(p).read_text())
    rows=[]
    proofs=[]
    for run in ('S_B0_s0_3M','S_G1_s0_3M','S_R1_s0_3M'):
        diagnostic=CONTROL/'training'/run/'diagnostic_readouts'
        for stage in ('curve_gpu','curve_statistics','geometry_gpu','geometry_statistics'):
            path=diagnostic/(stage+'_status.json')
            proof=read(path)
            expected='GPU_DIAGNOSTIC_COMPLETE_WAITING_CPU' if stage.endswith('_gpu') else 'COMPLETE'
            if (proof.get('run')!=run or proof.get('samples')!=3000000
                    or proof.get('status')!=expected or not proof.get('owned_descendants_exited')):
                raise ValueError('A diagnostic producer/consumer is not actually closed')
            raw=query(['/usr/bin/sacct','-X','-n','-P','-j',str(proof['job_id']),
                '--format=State,ExitCode'],SimpleNamespace(requested=False)).strip()
            if raw!='COMPLETED|0:0':
                raise ValueError('Diagnostic allocation is not actual C0')
            proofs.append(dict(path=str(path),job_id=proof['job_id'],actual_state=raw))
        delivered=REPO/'results/s_recipe/representations'/run
        if read(delivered/'summary.json').get('status')!='COMPLETE':
            raise ValueError('Final geometry statistics have not been delivered')
        for layer in range(1,7):
            if (delivered/('layer_'+str(layer)+'_bootstrap.npz')).stat().st_size<=0:
                raise ValueError('Retain all original delivered molecular draw artifacts')
        layer_root=CONTROL/'scratch/readout_features'/run/'endpoint_layers'
        for layer in range(1,7):
            for dataset in ('expansionrx','cyp_isoform','qm9'):
                path=layer_root/str(layer)/(dataset+'.pt')
                if path.exists() or path.is_symlink():
                    rows.append(checked_file(path,layer_root))
        geometry_root=CONTROL/'scratch/representations'/run
        manifest=read(geometry_root/'manifest.json')
        for filename in manifest['chunks']:
            path=Path(filename)
            if not re.fullmatch(r'chunk_[0-9]+\.pt',path.name) or path.parent!=geometry_root:
                raise ValueError('Raw H manifest references a noncanonical scratch chunk')
            rows.append(checked_file(path,geometry_root))
    if len({row['path'] for row in rows})!=len(rows):
        raise ValueError('Scratch retirement plan repeated an inode path')
    return dict(schema='S_CLOSED_DIAGNOSTIC_H_RETIREMENT_V1',files=rows,proofs=proofs,
        allocated_bytes=sum(row['allocated_bytes'] for row in rows),
        no_scientific_recalculation=True,final_results_and_failed_partials_retained=True)


def execute():
    if socket.gethostname().split('.')[0] not in {'compute-0-'+str(i) for i in range(8,20)} or os.environ.get('CUDA_VISIBLE_DEVICES'):
        raise ValueError('Use the finite admitted CPU metadata stage')
    directory=CONTROL/'diagnostic_scratch_retirement_20261124'
    if (directory/'COMPLETE.json').exists():
        return
    directory.mkdir(exist_ok=True)
    source=directory/'plan.json'
    if not source.exists():
        write(source,plan())
    value=json.loads(source.read_text())
    from cpu_execution_20261126 import stop_new_work_epoch
    stop_at=stop_new_work_epoch()
    removed=0
    for row in value['files']:
        if time.time()>=stop_at:
            raise SystemExit(75)
        path=Path(row['path'])
        if path.exists() or path.is_symlink():
            retire_one(row,CONTROL/'scratch')
            removed+=1
    result=dict(status='COMPLETE',plan=str(source),planned_files=len(value['files']),
        removed_files_this_attempt=removed,released_allocated_bytes=value['allocated_bytes'],
        final_statistics_and_predictions_unchanged=True,failed_partials_preserved=True)
    write(directory/'COMPLETE.json',result)
    claim_current()
    write(REPO/'results/s_recipe/closed_diagnostic_scratch_retirement_20261124.json',result)
    print(json.dumps(result),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--execute',action='store_true',required=True)
    p.parse_args()
    execute()
