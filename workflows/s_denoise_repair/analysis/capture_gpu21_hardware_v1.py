"""Bounded read-only hardware evidence inside this exact owned allocation."""
import csv,hashlib,json,os
from pathlib import Path
import socket,subprocess,time
ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016')
assert os.getuid()==1278 and os.environ['SLURM_JOB_ID']=='4515578' and socket.gethostname().split('.')[0]=='compute-0-21'
command=['nvidia-smi','--query-gpu=index,uuid,name,memory.total','--format=csv,noheader,nounits']
raw=subprocess.check_output(command,stdin=subprocess.DEVNULL,text=True,timeout=20)
rows=list(csv.reader(raw.splitlines()));assert len(rows)==2
assert all(x[2].strip()=='NVIDIA GeForce RTX 5090' and int(x[3])>=30000 for x in rows)
doc=dict(status='ACTUAL_COMPUTE21_TWO_MATCHED_RTX5090_GPUS',uid=1278,host=socket.gethostname(),job_id=os.environ['SLURM_JOB_ID'],timestamp=time.time(),
    command=command,raw_stdout=raw,raw_stdout_sha256=hashlib.sha256(raw.encode()).hexdigest(),
    gpus=[dict(index=int(x[0]),uuid=x[1].strip(),model=x[2].strip(),total_MiB=int(x[3])) for x in rows],
    source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),no_model_or_dataset_execution=True,
    hardware_count_is_not_a_gpu_reservation=True)
p=ROOT/'control/hardware_snapshots/gpu21_two_5090_v1.json';p.parent.mkdir(exist_ok=True)
with p.open('x') as stream:json.dump(doc,stream,indent=2);stream.write('\n')
print('GPU21_HARDWARE_SNAPSHOT_WRITTEN')
