#!/bin/bash
#SBATCH --job-name=remaining_Av2_fresh_R1
#SBATCH --partition=all
#SBATCH --cpus-per-task=16
#SBATCH --time=02:00:00
set -euo pipefail
: "${SLURM_JOB_ID:?Actual Root-owned GPU job}"
: "${MODEL_V3_R1_PACKAGE:?Frozen source package}"
: "${MODEL_V3_R1_PACKAGE_SHA:?Frozen pins SHA}"
: "${MODEL_V3_R1_BOUND_COHORT:?Server CPython exact cohort binding}"
: "${MODEL_V3_R1_BOUND_COHORT_SHA:?Actual binding SHA}"
: "${MODEL_V3_R1_ADMISSION:?Fresh Root admission}"
: "${MODEL_V3_R1_ADMISSION_SHA:?Actual Root admission SHA}"
: "${MODEL_V3_R1_GPU_UUID:?Exact physical UUID}"
: "${MODEL_V3_R1_NODE:?Exact admitted node}"
export CUDA_VISIBLE_DEVICES="$MODEL_V3_R1_GPU_UUID" PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=8 MKL_NUM_THREADS=8 OPENBLAS_NUM_THREADS=8
B=/share/home/zixiao/descriptor_analysis
CODE=$B/MFM_model_v3_A_acceptance_v2_candidate_v1
PY=$B/docs/phase1/evidence/stage43_5090_environment/install_4511929/venv/bin/python
export PYTHONPATH="$CODE/current:$CODE/tools/model_v3:$B/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps"
cd "$CODE"
"$PY" -u -B - <<'PY'
import importlib.util,json,os,signal,socket,stat,subprocess,time
from pathlib import Path
signal.alarm(180)
pkg=Path(os.environ['MODEL_V3_R1_PACKAGE'])
spec=importlib.util.spec_from_file_location('remaining_R1_admission',pkg/'admission.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
pins=m.verify_package(os.environ['MODEL_V3_R1_PACKAGE_SHA'])
ref=m.reference(os.environ['MODEL_V3_R1_BOUND_COHORT']);m.need(ref['sha256']==os.environ['MODEL_V3_R1_BOUND_COHORT_SHA'],'Actual bound cohort SHA differs')
b=m.bound(ref);m.need(b['schema']=='model_v3_remaining_Av2_R1_precise_cohort_binding_v1' and b['source_package']==pins
    and b['exact_server_CPython_integer_copy'] is True and b['old_or_cross_UUID_timing_reused'] is False,'Actual exact current cohort required')
m.verify_method(b['method_publication']);q=m.qualify(b['cohort'],b['qualification_input']);case=q['case'];declared=q['declared']
for key in case:m.need(m.exact(case[key],b['case'][key]),'Server exact original cohort binding differs: '+key)
m.need(m.exact(q['numeric_configuration'],b['numeric_configuration']) and b['case']['R1_family']==declared['family']
    and b['case']['R1_series_id']==declared['series_id'],'Actual numeric/family binding differs')
position=b['position'];m.need(type(position) is int and 1<=position<=4 and b['role']==m.ROLES[position-1],'Actual ABBA role/position differs')
node=case['expected_node'];gpu=case['gpu_uuid'];job=os.environ['SLURM_JOB_ID']
m.need(os.getuid()==os.geteuid()==1278 and socket.gethostname().split('.')[0]==os.environ.get('SLURMD_NODENAME')==node==os.environ['MODEL_V3_R1_NODE']
    and os.environ.get('SLURM_CPUS_PER_TASK')=='16' and os.environ['CUDA_VISIBLE_DEVICES']==os.environ['MODEL_V3_R1_GPU_UUID']==gpu
    and not any(k.startswith('SBATCH_') for k in os.environ),'Actual owned16CPU/node/UUID; no inherited SBATCH override required')
cgroup=Path('/proc/self/cgroup').read_text();m.need('/job_'+job+'/' in cgroup or cgroup.rstrip().endswith('/job_'+job),'Actual kernel job cgroup required')
family=Path(declared['family'])/('member_'+str(position));out=family/'child';record=family/'supervisor.json'
m.need(family.resolve()==family and not out.exists() and not record.exists(),'Fresh actual member child/supervision required')
for suffix in ('.jsonl','.storage.json'):m.need(not Path(str(record)+suffix).exists(),'Fresh original supervision sidecars required')
control=family/'control';initial=0
for path in control.iterdir():
    info=path.lstat();m.need(stat.S_ISREG(info.st_mode) and info.st_uid==1278 and info.st_nlink==1 and not path.is_symlink(),'Only current ordinary control metadata/stdio permitted')
    initial+=info.st_size
m.need(initial<=8<<20,'Root control metadata must fit original management/finalization allowance')
ad=m.reference(os.environ['MODEL_V3_R1_ADMISSION']);m.need(ad['sha256']==os.environ['MODEL_V3_R1_ADMISSION_SHA'],'Actual admission SHA differs');frame=m.bound(ad)
m.need(frame['schema']=='model_v3_remaining_Av2_R1_auto_Root_admission_v1' and frame['source_package']==pins and frame['bound_cohort']==ref
    and frame['node']==node and frame['gpu_uuid']==gpu and frame['method_publication']==b['method_publication']
    and 0<=time.time()-frame['captured_unix']<=120,'Original120s Root resource/metadata binding required')
api=m.policy();raw=[]
def capture(argv):
    r=subprocess.run(argv,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=30)
    m.need(len(r.stdout)+len(r.stderr)<=2<<20,'Small live resource observation required')
    raw.append(dict(argv=argv,returncode=r.returncode,stdout=r.stdout,stderr=r.stderr));m.need(r.returncode==0,'Actual worker controller failure: HOLD');return r.stdout
node_raw=capture(['scontrol','show','node',node]);queue_raw=capture(['squeue','-h','-w',node,'-o','%i|%u|%t|%m|%C']);mem_raw=Path('/proc/meminfo').read_text()
assessment=api.assess(node_raw,queue_raw,mem_raw,node=node,software_budget_bytes=64<<30,rss_limit_bytes=56<<30,
    registry_path=m.N/'native_S_profile_registered_reservations_v6.json',current_job_id=job,current_reservation_id=b['reservation_id'])
job_control=capture(['scontrol','show','job','-o',job])
startup=dict(schema='model_v3_GPU_auto_memory_startup_actual_v1',job_id=job,memory=assessment,raw_observations=raw,actual_meminfo=mem_raw,
    actual_job_control=job_control,actual_Slurm_memory_environment={k:v for k,v in os.environ.items() if k.startswith('SLURM_MEM_')},
    Slurm_memory_mode='automatic_default',fixed_memory_requested_bytes=None,finite_physical_guarantee_claimed=False)
body=(json.dumps(startup,sort_keys=True,indent=2,allow_nan=False)+'\n').encode();m.need(len(body)<=2<<20,'Small startup record required')
with (control/'GPU_auto_memory_startup_actual_v1.json').open('xb') as stream:stream.write(body);stream.flush();os.fsync(stream.fileno())
routing=m.bound(m.read(pkg/'dependencies.json')['raw_refs']['routing_plan']);py=case['logical_python'];deps=routing['dependencies']
child=[py,'-u','-B','tools/model_v3/single_a_benchmark.py','--candidate-options',case['candidate_options']['path'],
    '--reference-config',deps['reference_configuration']['path'],'--input','native_s','--seed','0','--workers','8','--max-padded-cost','8000000',
    '--expected-gpu',case['expected_gpu'],'--code-sha',m.CODE,'--prereg-sha',m.PUBLIC,'--shard-snapshot-sha256',routing['common']['snapshot_sha256'],
    '--role',b['role'],'--abba-position',str(position),'--series-id',declared['series_id'],'--deterministic-controls','--output',str(out)]
# All six R2 cohorts have NO integration declaration. Do not add a manual wrapper,
# padding, checkpoint profile, target regrouping or a replacement execution policy.
command=[py,'-u','-B','tools/model_v3/run_supervised.py','--output-root',str(out),'--record',str(record),'--gpu-uuid',gpu,
    '--wall-seconds','6900','--rss-limit-bytes','60129542144','--output-budget-bytes','2147483648',
    '--private-scratch-root','/tmp/mv3n_'+job,'--private-storage-budget-bytes','2147483648','--',*child]
print(json.dumps(dict(status='ACTUAL_CURRENT_NUMERIC_AND_SDK_METADATA_QUALIFIED_NOT_R1_ACCEPTANCE',cohort=b['cohort'],position=position,
    source_package=pins,bound_cohort=ref,Root_admission=ad,command=command)),flush=True)
signal.alarm(0)
# No outer flock: only original single_a_benchmark owns the shared UUID lock.
os.execv(py,command)
PY