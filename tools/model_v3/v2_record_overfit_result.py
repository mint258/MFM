"""Publish one closed diagnostic run's small metadata and actual new-work row."""
import argparse
import csv
import importlib.util
import io
import json
from pathlib import Path

REPO=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('model_metadata_disk',REPO/'current/phychem_mfm/phase1/v2_disk.py')
disk=importlib.util.module_from_spec(spec);spec.loader.exec_module(disk)


def write(path,data):
    path=Path(path);disk.require_capacity(disk.filesystem_status(path.parent),len(data),4)
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('wb') as file:
        disk.CheckedWriter(file,path.parent,len(data)).write(data)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--directory',required=True)
    p.add_argument('--job',required=True)
    p.add_argument('--gpu',required=True)
    p.add_argument('--terminal-state',choices=('COMPLETED',),required=True,
                   help='Actual parent state already read once on the login node')
    p.add_argument('--zero-attempt',action='append',default=[],help='Actual preflight jobID,candidate')
    a=p.parse_args();root=Path(a.directory)
    attempts=[v.split(',',1) for v in a.zero_attempt]
    summary=json.loads((root/'summary.json').read_text())
    table=REPO/'results/model_v3_v2_runs.csv'
    with table.open() as file:
        reader=csv.DictReader(file);columns=reader.fieldnames;rows=list(reader)
    seen={r['run_id'] for r in rows}
    for job,candidate in attempts:
        name=f'M2_DIAG_{candidate}_preflight_{job}'
        if name not in seen:
            row=dict.fromkeys(columns,'');row.update(run_id=name,stage=2,condition='PD',candidate=candidate,
                views='three',seed=0,molecules=1000,samples=0,updates=0,
                status='FAILED:DISK_PREFLIGHT_NO_TRAINING',slurm_job_id=job);rows.append(row)
    if root.name not in seen:
        process_updates=summary['process_updates']
        row=dict.fromkeys(columns,'');row.update(run_id=root.name,stage=2,condition='PD',
            candidate=summary['experiment']+'_clip'+str(summary['clip']),views='three',seed=0,
            molecules=1000,samples=process_updates*8,updates=process_updates,gpu_model=a.gpu,
            elapsed_seconds=summary['process_seconds'],peak_memory_bytes=summary['gpu_peak_bytes'],
            status=f"COMPLETED:{summary['status']}:MODEL_UPDATES_{summary['actual_updates']}:REUSED_{summary['reused_prefix_updates']}",
            slurm_job_id=a.job);rows.append(row)
    buffer=io.StringIO(newline='');writer=csv.DictWriter(buffer,fieldnames=columns,lineterminator='\n')
    writer.writeheader();writer.writerows(rows);write(table,buffer.getvalue().encode())
    write(REPO/'docs/model_v3/overfit_diagnosis'/f'{root.name}.json',(root/'summary.json').read_bytes())
    manifest_path=REPO/'docs/model_v3/M2_OVERFIT_DIAGNOSIS_DELIVERY.json'
    manifest=json.loads(manifest_path.read_text());files={r['path']:r for r in manifest['files']}
    prefix=1 if summary['reused_prefix_updates'] else 0
    if prefix and Path(summary['resume']).parent.name!='M2_overfit_4526238':
        raise ValueError('Declare the actual inherited history count for another predecessor')
    metric_points=process_updates//500+int(summary['actual_updates']%500!=0)+prefix
    records={'configuration.json':1,'summary.json':1,'final.pt':1,
             'losses.csv':process_updates,'per_head_history.csv':133*metric_points}
    for name,count in records.items():
        path=root/name;files[str(path)]=dict(path=str(path),bytes=path.stat().st_size,records=count)
    manifest['files']=list(files.values());manifest['status']='PARTIAL_DIAGNOSIS_IN_PROGRESS'
    manifest['running_jobs']=[j for j in manifest.get('running_jobs',[]) if str(j)!=a.job]
    manifest['closed_jobs']=sorted(set(manifest.get('closed_jobs',[])+[int(a.job)]))
    write(manifest_path,(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n').encode())
    print(json.dumps(dict(job=a.job,run=root.name,active_passed=summary['active_passed'],
        model_updates=summary['actual_updates'],new_updates=process_updates,metadata_published=True)),flush=True)


if __name__=='__main__':
    main()
