"""Typed one-row-per-paired-experiment parent accounting; not a speed table."""
import csv
import hashlib
import json
from pathlib import Path
import subprocess
BASE=Path('/share/home/zixiao/descriptor_analysis');RUNS=BASE/'runs/model_v3_20261025';REPO=BASE/'MFM_model_v3'
folders={j:'a_native_control_'+j for j in ['4520405','4520410','4520411','4520438']}
folders.update({'4520457':'A_a06_fused_4520457','4520486':'A_a00_control_4520486','4520525':'A_a05_compile_4520525','4520546':'A_a01_backbone_off_4520546','4520549':'A_a03_head_off_4520549','4520589':'A_a07_tf32_4520589','4520590':'A_a02_distance_off_4520590'})
argv=['sacct','-X','-n','-P','-j',','.join(sorted(folders)),'--format=JobIDRaw,State,ExitCode,ElapsedRaw,AllocCPUS']
raw=subprocess.check_output(argv,text=True,timeout=45);accounting={r.split('|')[0]:r.split('|') for r in raw.splitlines() if r}
if set(accounting)!=set(folders):raise ValueError('Actual exact parent set required')
rows=[];sources=[]
for job,folder in sorted(folders.items()):
    path=RUNS/folder/'configuration.json';content=path.read_bytes();cfg=json.loads(content);a=accounting[job]
    snapshot=cfg.get('original_shard_snapshot_prejob_sha256') or cfg['data_version']['original_shard_snapshot']['sha256']
    rows.append(dict(run_id='A_'+job,stage='2',config_sha256=cfg['configuration_sha256'],code_sha=cfg['code_sha'],
        data_version='native_S_snapshot_'+snapshot,seed=cfg['seed'],gpu_model=cfg['gpu_name'],elapsed_seconds=int(a[3]),
        status=a[1],preregistration_sha=cfg['prereg_sha'],gpu_uuid=cfg['gpu_uuid'],allocated_cpu_seconds=int(a[3])*int(a[4]),allocated_gpu_seconds=int(a[3])))
    sources.append(dict(job_id=job,configuration=dict(path=str(path),bytes=len(content),sha256=hashlib.sha256(content).hexdigest())))
root=REPO/'docs/model_v3/results'
with (root/'A_actual_paired_parent_runs.csv').open('x',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
value=dict(schema='model_v3_A_actual_paired_parent_summary_v1',granularity='one actual paired-experiment Slurm parent, not one SDK; reference/candidate SDK evidence remains separate',
    allocated_gpu_seconds_are_utilization=False,paired_wall_is_speedup=False,pending_job_4520456_excluded=True,
    raw_sacct=dict(argv=argv,stdout=raw,stdout_sha256=hashlib.sha256(raw.encode()).hexdigest()),sources=sources)
with (root/'A_actual_paired_parent_source_bindings.json').open('x') as f:json.dump(value,f,indent=2);f.write('\n')
for n in ['A_actual_paired_parent_runs.csv','A_actual_paired_parent_source_bindings.json']:(root/n).chmod(0o644)
print(json.dumps(dict(status='ACTUAL_TYPED_PAIRED_PARENT_SUMMARY_PREPARED',rows=len(rows))))
