#!/bin/bash
#SBATCH --job-name=model_v3_remaining_Av2_routing_v6
#SBATCH --partition=all
#SBATCH --cpus-per-task=16
#SBATCH --time=02:00:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/model_v3_20261026/remaining_Av2_routing_v6_%j.log
set -euo pipefail
# One explicit old-job selector per Root submission; no loop, array or retry.
test "$#" -eq 1
export MODEL_V3_RECHECK_OLD_JOB="$1"
: "${MODEL_V3_GPU_PYTHON:?Root binds the declared original logical interpreter}"
: "${MODEL_V3_GPU_UUID:?Root fresh exact physical UUID admission}"
: "${MODEL_V3_EXPECTED_NODE:?Root fresh exact node admission}"
: "${MODEL_V3_PLAN_SHA256:?Root binds the final published PLAN.json raw SHA}"
: "${MODEL_V3_METHOD_PUBLICATION_PATH:?Actual new method publication}"
: "${MODEL_V3_METHOD_PUBLICATION_SHA256:?Actual publication raw SHA}"
: "${MODEL_V3_ROOT_ADMISSION_PATH:?Root semantic resource admission required}"
: "${MODEL_V3_ROOT_ADMISSION_SHA256:?Root admission raw SHA}"
: "${MODEL_V3_QUOTA_PATH:?Actual quota frame required}"
: "${MODEL_V3_QUOTA_SHA256:?Actual quota raw SHA}"
: "${MODEL_V3_HOLD_PATH:?Independent twoGiB one-job hold required}"
: "${MODEL_V3_HOLD_SHA256:?Hold raw SHA}"
CODE=/share/home/zixiao/descriptor_analysis/MFM_model_v3_A_acceptance_v2_candidate_v1
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=8 MKL_NUM_THREADS=8 OPENBLAS_NUM_THREADS=8
export PYTHONPATH="$CODE/current:$CODE/tools/model_v3:/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps"
export CUDA_VISIBLE_DEVICES="$MODEL_V3_GPU_UUID"
cd "$CODE"
# Stdlib source/metadata preflight then exec the ORIGINAL supervisor; no Torch here.
exec "$MODEL_V3_GPU_PYTHON" -u -B - <<'PY'
import hashlib, importlib.util, json, os, signal, socket, stat, subprocess, sys
from pathlib import Path
signal.alarm(180)
B=Path('/share/home/zixiao/descriptor_analysis'); N=B/'runs/model_v3_20261026'
HERE=N/'performance_remaining_Av2_20261029_routing_v6'; W=B/'MFM_model_v3_A_acceptance_v2_candidate_v1'
def need(ok,message):
    if not ok: raise ValueError(message)
def rawref(path):
    p=Path(path); s=p.lstat()
    need(p.is_absolute() and p.resolve()==p and stat.S_ISREG(s.st_mode) and s.st_uid==1278
         and s.st_nlink==1 and s.st_size<=2<<20,'Owned bounded canonical source/metadata required')
    raw=p.read_bytes(); t=p.lstat()
    need(tuple(getattr(s,k) for k in ('st_dev','st_ino','st_size','st_mtime_ns'))==
         tuple(getattr(t,k) for k in ('st_dev','st_ino','st_size','st_mtime_ns')),'Metadata changed while read')
    return raw,dict(path=str(p),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
def bound(ref):
    raw,actual=rawref(ref['path']); need(actual==ref,'Frozen dependency differs: '+ref['path']); return raw
raw,planref=rawref(HERE/'PLAN.json')
need(planref['sha256']==os.environ['MODEL_V3_PLAN_SHA256'],'Root-bound plan differs')
plan=json.loads(raw); need(plan['schema']=='model_v3_remaining_six_A_cohort_v2_routing_execution_plan_v2' and plan['routing_version']==6,'Unknown plan')
rows=[r for r in plan['cases'] if r['old_job_id']==os.environ['MODEL_V3_RECHECK_OLD_JOB']]
need(len(plan['cases'])==6 and len(rows)==1,'Exactly one of six explicit rechecks required'); row=rows[0]
need(os.getuid()==1278 and os.environ.get('SLURM_JOB_ID') and os.environ.get('SLURM_CPUS_PER_TASK')=='16','Owned16CPU Slurm job required')
need(socket.gethostname().split('.')[0]==row['expected_node']==os.environ['MODEL_V3_EXPECTED_NODE'],'Admitted node differs')
need(os.environ['MODEL_V3_GPU_UUID']==row['gpu_uuid'] and os.environ['CUDA_VISIBLE_DEVICES']==row['gpu_uuid'],'Actual declared routing-v6 physical GPU differs; historical UUID is not overwritten')
need(os.environ['MODEL_V3_GPU_PYTHON']==row['logical_python'] and Path(sys.executable).resolve()==Path(row['logical_python']).resolve(),'Logical interpreter differs')
need(row['performance_execution_request'] is None and row['old500_reused'] is False,'No opt-in/profile or old500 reuse for these six cohorts')
for ref in plan['dependencies'].values(): bound(ref)
for name in ('original_configuration','original_supervisor','candidate_options'): bound(row[name])
old=json.loads(bound(row['original_configuration']))
need(old['candidate']==row['candidate'] and old['reference']==row['reference_options'] and old['model']==row['model']
     and old['data_version']==row['original_data_version'] and old['seed']==0 and old['input']=='native_s'
     and old['fixed_batches']==20 and old['trajectory_updates']==500,'Original cohort declaration differs')
need(json.loads(bound(row['candidate_options']))==row['candidate'],'Actual current option JSON differs')
need(old['data_version']['sampler']['max_padded_cost']==8000000 and old['data_version']['loader']['num_workers']==8
     and old['model']['backbone']['use_radius_mask'] is False,'Original input/cost/global path differs')
pubraw,pubref=rawref(os.environ['MODEL_V3_METHOD_PUBLICATION_PATH'])
need(pubref['sha256']==os.environ['MODEL_V3_METHOD_PUBLICATION_SHA256'],'Publication raw SHA differs')
pub=json.loads(pubraw); repo=pub.get('repository_full_name',pub.get('repository'))
need(repo=='mint258/MFM' and pub.get('repository',repo)==repo and pub['schema']=='model_v3_exact_tree_publication_actual_v1'
     and pub['branch']=='model-v3' and pub['public_branch_readback_verified'] is True
     and pub['public_Git_API_tree_readback_verified'] is True,'Actual exact-tree method publication required')
table={r['path']:r for r in pub['files']}; need(len(table)==len(pub['files']),'Duplicate public file names')
for name in plan['method_files']:
    body,_=rawref(HERE/name); blob=table[plan['method_prefix']+name]
    need(blob['type']=='blob' and blob['sha']==hashlib.sha1(b'blob '+str(len(body)).encode()+bytes([0])+body).hexdigest(),'Published method bytes differ')
policyref=plan['dependencies']['GPU_auto_memory_policy_source']
spec=importlib.util.spec_from_file_location('remaining_Av2_shared_GPU_memory_policy',policyref['path'])
memory_policy=importlib.util.module_from_spec(spec);spec.loader.exec_module(memory_policy)
memory_policy.verify_package(plan['dependencies']['GPU_auto_memory_policy_pins']['sha256'])
memory_policy.verify_publication(pubref)
# Reuse the proven same-source full115/2673P+3skip/publication validator, unchanged.
guardref=plan['dependencies']['existing_source_guard']; spec=importlib.util.spec_from_file_location('remaining_Av2_existing_source_guard',guardref['path'])
guard=importlib.util.module_from_spec(spec); spec.loader.exec_module(guard); guard.validate_sources()
git=B/'runs/model_v3_20261025/cpu_git_tools_v1/bin/git'; src=plan['current_source']
for args,expected in ((['rev-parse','HEAD'],src['local_commit']),(['rev-parse','HEAD^{tree}'],src['tree']),(['status','--porcelain=v1','--untracked-files=all'],'')):
    got=subprocess.run([str(git),'-C',str(W),*args],capture_output=True,text=True,timeout=120,check=True).stdout.strip()
    need(got==expected,'Actual current HEAD/tree/clean differs')
frames={}
for prefix in ('MODEL_V3_ROOT_ADMISSION','MODEL_V3_QUOTA','MODEL_V3_HOLD'):
    _,ref=rawref(os.environ[prefix+'_PATH']); need(ref['sha256']==os.environ[prefix+'_SHA256'],'Actual Root frame differs'); frames[prefix]=ref
# Frame integrity does not replace Root's fresh85%/quota/lock/reservation semantics.
out=Path(row['child_output']); record=Path(row['supervisor_record']); family=Path(row['family'])
need(family.resolve()==family and (HERE/'trials').resolve()==HERE/'trials' and family.resolve().is_relative_to((HERE/'trials').resolve()) and not out.exists() and not out.is_symlink()
     and not record.exists() and not record.is_symlink(),'Fresh independent one-use output required')
need(record.parent==out.parent and not record.is_relative_to(out),'Disjoint child/supervisor roots required')
for suffix in ('.jsonl','.storage.json'): need(not Path(str(record)+suffix).exists(),'Fresh supervisor sidecar required')
memory_raw=[]
def observe_memory(argv):
    result=subprocess.run(argv,capture_output=True,text=True,timeout=30)
    need(len(result.stdout)+len(result.stderr)<=2<<20,'Bounded memory observation required')
    item=dict(argv=argv,returncode=result.returncode,stdout=result.stdout,stderr=result.stderr);memory_raw.append(item)
    need(result.returncode==0,'Actual startup observation failed');return result.stdout
node_raw=observe_memory(['scontrol','show','node',row['expected_node']])
queue_raw=observe_memory(['squeue','-h','-w',row['expected_node'],'-o','%i|%u|%t|%m|%C'])
mem_raw=Path('/proc/meminfo').read_text()
memory=memory_policy.assess(node_raw,queue_raw,mem_raw,node=row['expected_node'],software_budget_bytes=64<<30,
    rss_limit_bytes=56<<30,registry_path=N/'native_S_profile_registered_reservations_v6.json',
    current_job_id=os.environ['SLURM_JOB_ID'],current_reservation_id='performance_remaining_Av2_routing_v6_'+row['old_job_id'])
job_raw=observe_memory(['scontrol','show','job','-o',os.environ['SLURM_JOB_ID']])
startup=dict(schema='model_v3_GPU_auto_memory_startup_actual_v1',job_id=os.environ['SLURM_JOB_ID'],memory=memory,
    raw_observations=memory_raw,actual_meminfo=mem_raw,actual_job_control=job_raw,
    actual_Slurm_memory_environment={k:v for k,v in os.environ.items() if k.startswith('SLURM_MEM_')},
    Slurm_memory_mode='automatic_default',fixed_memory_requested_bytes=None,finite_physical_guarantee_claimed=False)
startup_raw=(json.dumps(startup,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
need(len(startup_raw)<=2<<20,'Bounded actual startup memory record required')
with (Path(row['control'])/'GPU_auto_memory_startup_actual_v1.json').open('xb') as stream:
    stream.write(startup_raw);stream.flush();os.fsync(stream.fileno())
common=plan['common']; deps=plan['dependencies']; py=row['logical_python']
child=[py,'-u','-B','tools/model_v3/paired_a_acceptance.py','--candidate-options',row['candidate_options']['path'],
    '--reference-config',deps['reference_configuration']['path'],'--input','native_s','--seed','0','--workers','8',
    '--max-padded-cost','8000000','--expected-gpu',row['expected_gpu'],'--code-sha',src['local_commit'],
    '--prereg-sha',src['public_commit'],'--shard-snapshot-sha256',common['snapshot_sha256'],
    '--acceptance-version','v2','--acceptance-rule-document',deps['rule_document']['path'],
    '--acceptance-rule-document-sha256',deps['rule_document']['sha256'],'--acceptance-prereg-sha',plan['rules']['public_commit'],
    '--acceptance-rule-publication',deps['rule_publication']['path'],'--acceptance-rule-publication-sha256',deps['rule_publication']['sha256'],
    '--deterministic-controls','--output',str(out)]
command=[py,'-u','-B','tools/model_v3/run_supervised.py','--output-root',str(out),'--record',str(record),
    '--gpu-uuid',row['gpu_uuid'],'--wall-seconds','6900','--rss-limit-bytes','60129542144','--output-budget-bytes','2147483648',
    '--private-scratch-root','/tmp/mv3n_'+os.environ['SLURM_JOB_ID'],'--private-storage-budget-bytes','2147483648','--',*child]
print(json.dumps(dict(status='ACTUAL_SOURCE_AND_METADATA_PRECHECK_NO_NUMERIC_RESULT',old_job_id=row['old_job_id'],
    job_id=os.environ['SLURM_JOB_ID'],plan=planref,publication=pubref,Root_frames=frames,command=command),sort_keys=True),flush=True)
signal.alarm(0)
# No outer flock: paired_a_acceptance is the sole physical UUID-lock holder.
os.execv(py,command)
PY
