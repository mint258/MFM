"""Metadata-only actual CPU closure and prospective GPU probe contract."""
from concurrent.futures import ThreadPoolExecutor
import hashlib,json,os,socket,subprocess,time
from pathlib import Path
R=Path('/share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016')
assert os.getuid()==1278 and socket.gethostname().split('.')[0]=='sonmi'
def ref(path):
    p=Path(path);b=p.read_bytes();return dict(path=str(p),sha256=hashlib.sha256(b).hexdigest(),bytes=len(b))
def check(row):assert ref(row['path'])['sha256']==row['sha256']
def write(path,value):
    with path.open('x') as f:json.dump(value,f,indent=2,allow_nan=False);f.write('\n')
receipt=json.loads((R/'submission/atom_projection_cpu_v2.json').read_text());assert receipt['job_id']=='4515627'
raw=subprocess.run(['sacct','-j',receipt['job_id'],'-n','-X','-P','-o','JobIDRaw,State,ExitCode,ElapsedRaw,AllocCPUS'],stdin=subprocess.DEVNULL,capture_output=True,text=True,check=True,timeout=30)
rows=[x.strip().split('|') for x in raw.stdout.splitlines() if x.strip()];assert len(rows)==1
jid,state,exitcode,elapsed,cpus=rows[0];assert jid==receipt['job_id'] and state=='COMPLETED' and exitcode=='0:0' and int(cpus)>=16
parent=dict(JobIDRaw=jid,State=state,ExitCode=exitcode,ElapsedRaw=elapsed,AllocCPUS=cpus)
result=R/'validation/atom_projection_cpu_job4515627/result.json';qa=json.loads(result.read_text())
assert qa['status']=='ATOM_PROJECTION_CPU_C6_AND_LEGACY_PASS_NOT_ADOPTED' and qa['original_99_sources_unchanged']
with ThreadPoolExecutor(16) as pool:list(pool.map(check,qa['source_references']))
legacy=json.loads(Path(qa['legacy_reference']['path']).read_text());check(qa['legacy_reference'])
assert legacy['status']=='LEGACY_V2_BITEXACT_PASS' and legacy['compared_tensors']>0
closure=dict(status='ACTUAL_CPU_C6_AND_LEGACY_CLOSED_NOT_ADOPTED',captured_unix=time.time(),actual_parent=parent,
 actual_sacct_stdout=raw.stdout,submission_reference=ref(R/'submission/atom_projection_cpu_v2.json'),
 result_reference=ref(result),test_counts=qa['test_counts'],legacy_reference=qa['legacy_reference'],formal_training_authorized=False)
cpath=R/'configs/atom_projection_cpu_closure_v1.json';write(cpath,closure)
plan=json.loads((R/'configs/atom_projection_execution_plan_v1.json').read_text())
cfg=R/'source_v4/workflows/s_denoise/configs/A3_seed0_v3.json'
ptr=json.loads((R/'reports/A3_seed0_latest.json').read_text());check(ptr)
a3=json.loads(Path(ptr['path']).read_text());assert a3['status']=='D3_CONDITION_COMPLETE' and a3['optimizer_updates']==4000
check(a3['checkpoint'])
plan.update(status='PROSPECTIVE_GPU_EXECUTION_AND_DEVELOPMENT_OPTIMIZER_VALIDATION_NOT_ADOPTED',
 crossover_order=[False,True,True,False],timed_repeats=3,official_optimizer_updates=0,development_optimizer_updates=12,
 configuration=ref(cfg),trained_checkpoint=a3['checkpoint'],
 source_references=[ref(p) for p in [cpath,result,R/'analysis/atom_projection_gpu_v1.py',cfg,Path(ptr['path'])]],
 development_checkpoint_policy='Two updates on the same first/largest real batches per mode and message layer. Each weights_only checkpoint must restore model and optimizer in fresh objects, reproduce predictions and loss, and preserve state tensors exactly.',
 performance_only=False,benchmark_parameters_unchanged_before_development_optimizer_steps=True,
 admission='16CPU 32GiB bounded 20min node21, actual idle second 5090 with shared UUID lock; all-user memory plus new allocation <=85% RealMemory',
 output_cap_bytes=2*(1<<30),host_RSS_cap_GiB=26,wall_seconds=1000)
write(R/'configs/atom_projection_gpu_plan_v1.json',plan)
print(json.dumps(dict(status='CPU_ACTUAL_C0_CLOSED_GPU_PLAN_READY_NOT_ADOPTED',actual_parent=parent,legacy_tensors=legacy['compared_tensors'],closure=ref(cpath))))
