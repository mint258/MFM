"""Pure source, numerical-gate, sequential-closure and resource checks for A01 ABBA."""
from __future__ import annotations

from decimal import Decimal
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import time
import uuid

BASE=Path('/share/home/zixiao/descriptor_analysis')
REPO=BASE/'MFM_model_v3_a_checkpoint'
PUBLIC_REPO=BASE/'MFM_model_v3'
RUNS=BASE/'runs/model_v3_20261025'
HERE=BASE/'runs/model_v3_20261026/A01_4090_ABBA_v1'
GATE=RUNS/'A_a01_backbone_off_4520456'
CODE='8ece64c685fe287d6863fbbe2f6f52006632a5cc'
PREREG='61658a4c1f472de035601dbedc17809315774784'
OPTIONS_SHA='d3bb101a8e5417fcbe998c39f97698e6902a9b06851a343aa0a0e4830ef0e8d4'
GPU='GPU-ec788ed1-7da1-8f93-bb23-b4fdb2018b02'
NODE='compute-0-20'
PYTHON=Path('/share/home/zixiao/.conda/envs/chemprop/bin/python')
GIT=RUNS/'cpu_git_tools_v1/bin/git'
LOCK=BASE/'docs/phase1/evidence/stage46_shared_gpu_launch/.own_gpu_uuid_locks'/(GPU+'.lock')
ORDER=('reference','candidate','candidate','reference')
SERIES='A01_4090_backbone_off_ABBA_v1'
MEMORY_MIB=65536
OUTPUT_BUDGET=PRIVATE_BUDGET=2<<30
JOB_WALL=1200
SUPERVISOR_WALL=1100
RSS_LIMIT=56<<30
PUBLISHED_PREFIX='tools/model_v3/analysis_sources/A01_4090_ABBA_v1/'
PROTOCOL_PATH='configs/model_v3/a01_4090_abba_v1.json'
CAP=32<<20


def require(ok,message):
    if not ok: raise ValueError(message)


def encoded(value):
    return (json.dumps(value,sort_keys=True,indent=2,ensure_ascii=False,allow_nan=False)+'\n').encode()


def canonical(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()


def strict_json(raw):
    def pairs(items):
        result={}
        for key,value in items:
            require(key not in result,'Duplicate JSON key'); result[key]=value
        return result
    def nonfinite(value): raise ValueError('Nonfinite JSON: '+value)
    value=json.loads(raw,object_pairs_hook=pairs,parse_constant=nonfinite)
    def finite(item):
        if type(item) is float: require(math.isfinite(item),'Nonfinite JSON number')
        elif type(item) is dict:
            for child in item.values(): finite(child)
        elif type(item) is list:
            for child in item: finite(child)
    finite(value); return value


def ref(path,cap=CAP):
    path=Path(path)
    require(path.is_absolute() and '..' not in path.parts and path==path.resolve(strict=True),'Physical absolute file required')
    before=path.lstat(); require(stat.S_ISREG(before.st_mode) and before.st_size<=cap,'Bounded ordinary metadata/source file required')
    digest=hashlib.sha256(); size=0
    with os.fdopen(os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0)),'rb') as stream:
        opened=os.fstat(stream.fileno())
        require((before.st_dev,before.st_ino)==(opened.st_dev,opened.st_ino),'Input replaced while opening')
        for block in iter(lambda:stream.read(1<<20),b''):
            size+=len(block); require(size<=cap,'Input byte budget exhausted'); digest.update(block)
    after=path.lstat()
    require((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)==
        (after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns) and size==before.st_size,'Input changed during hashing')
    return {'path':str(path),'bytes':size,'sha256':digest.hexdigest()}


def bind(value,cap=CAP):
    require(type(value) is dict and set(value)=={'path','bytes','sha256'} and type(value['bytes']) is int
        and 0<=value['bytes']<=cap and re.fullmatch('[0-9a-f]{64}',value['sha256']),'Exact raw-byte reference required')
    require(ref(value['path'],cap)==value,'Raw-byte source/evidence binding differs'); return Path(value['path'])


def read(value):
    path=bind(value); result=strict_json(path.read_bytes()); bind(value); return result


def save(path,value,cap=1<<20):
    raw=encoded(value); require(len(raw)<=cap,'Bounded operational output exceeded')
    with Path(path).open('xb') as stream: stream.write(raw); stream.flush(); os.fsync(stream.fileno())


def uuid_value(value):
    return 'GPU-'+str(uuid.UUID(value.strip().removeprefix('GPU-')))


def memory_mib(value,cpus):
    match=re.fullmatch(r'(\d+(?:\.\d+)?)([KMGT]?)([cn]?)',value)
    require(match is not None and type(cpus) is int and cpus>0,'Unknown all-user memory request')
    scale={'':Decimal(1),'K':Decimal(1)/1024,'M':Decimal(1),'G':Decimal(1024),'T':Decimal(1024**2)}
    return Decimal(match[1])*scale[match[2]]*(cpus if match[3]=='c' else 1)


def node_memory(node_raw,queue_raw,*,already_allocated=False):
    values={}
    for name in ('CPUAlloc','CPUTot','RealMemory','AllocMem'):
        found=re.findall(r'\b'+name+r'=(\d+)(?:\s|$)',node_raw)
        require(len(found)==1,'Missing/duplicate actual controller memory/CPU field'); values[name]=int(found[0])
    require(re.search(r'\bNodeName='+re.escape(NODE)+r'(?:\s|$)',node_raw)
        and not any(flag in node_raw for flag in ('DOWN','DRAIN','UNKNOWN','NOT_RESPONDING','POWER_DOWN'))
        and 0<=values['CPUAlloc']<=values['CPUTot'] and 0<=values['AllocMem']<=values['RealMemory']
        and values['RealMemory']>0,'Unknown/unavailable node or controller allocation')
    total,seen=Decimal(0),set()
    for line in queue_raw.splitlines():
        if not line.strip(): continue
        fields=line.strip().split('|')
        require(len(fields)==5 and fields[0] not in seen and fields[1] and fields[2]
            and fields[4].isdecimal(),'Malformed/duplicate all-user queue row')
        seen.add(fields[0]); total+=memory_mib(fields[3],int(fields[4]))
    prior=max(total,Decimal(values['AllocMem']))
    after=prior+(0 if already_allocated else MEMORY_MIB)
    require(after<Decimal('.85')*values['RealMemory'],'max(all-user declared,AllocMem)+new reaches85%')
    require(already_allocated or values['CPUTot']-values['CPUAlloc']>=16,'Insufficient actual16CPU headroom')
    return {'all_user_declared_MiB':str(total),'AllocMem_MiB':values['AllocMem'],'commitment_MiB':str(prior),
        'with_this_job_MiB':str(after),'RealMemory_MiB':values['RealMemory'],'new_request_added':not already_allocated}


def physical_memory(raw):
    values={}
    for name in ('MemTotal','MemAvailable'):
        found=re.findall(r'^'+name+r':\s*(\d+) kB$',raw,re.M)
        require(len(found)==1,'Missing/duplicate physical memory observation'); values[name]=Decimal(found[0])/1024
    require(0<=values['MemAvailable']<=values['MemTotal'] and values['MemTotal']>0
        and values['MemAvailable']-MEMORY_MIB>=Decimal('.15')*values['MemTotal'],
        'Measured MemAvailable after64GiB lacks15% physical reserve')
    return {'MemTotal_MiB':str(values['MemTotal']),'MemAvailable_MiB':str(values['MemAvailable']),
        'planned_working_set_MiB':MEMORY_MIB,'reserve_fraction':'0.15'}


def fresh(observation,now=None):
    now=time.time() if now is None else now
    require(observation['returncode']==0 and -5<=now-observation['captured_unix']<=90
        and observation['captured_unix']<=observation['completed_unix']<=now+5,'Stale/failed raw Root/worker observation')


def quota(raw):
    rows=[line.split() for line in raw.splitlines() if line.split() and line.split()[0]=='/dev/sda1']
    require(len(rows)==1 and len(rows[0])>=7,'Actual unique user quota filesystem row required')
    used,soft,hard=(int(rows[0][index].rstrip('*')) for index in (1,2,3)); limits=[n for n in (soft,hard) if n>0]
    require(used>=0 and limits and (min(limits)-used)*1024-OUTPUT_BUDGET>=64<<30,
        'Fresh quota lacks64GiB reserve after bounded new2GiB output')
    return {'used_KiB':used,'soft_KiB':soft,'hard_KiB':hard,'available_bytes':(min(limits)-used)*1024,
        'planned_output_bytes':OUTPUT_BUDGET,'remaining_reserve_min_bytes':64<<30}


def gpu_idle(gpu_raw,apps_raw,original_gpu):
    rows=[]
    for line in gpu_raw.splitlines():
        if not line.strip(): continue
        fields=[item.strip() for item in line.split(',')]
        require(len(fields)==5,'Unknown actual GPU query shape')
        if uuid_value(fields[0])==GPU: rows.append(fields)
    require(len(rows)==1,'Unique selected physical GPU observation required')
    row=rows[0]
    total=Decimal(row[3])*(1<<20); free=Decimal(row[4])*(1<<20)
    require(row[1]==original_gpu['name'] and '4090' in row[1] and row[2]==original_gpu['driver_version']
        and total==original_gpu['total_bytes'] and 0<free<=total,'Actual GPU name/driver/NVML capacity differs from original')
    for line in apps_raw.splitlines():
        if line.strip(): require(uuid_value(line.split(',')[0])!=GPU,'Selected UUID has a compute process')
    return {'uuid':GPU,'name':row[1],'driver_version':row[2],'NVML_total_bytes':int(total),
        'NVML_free_bytes':int(free),'selected_UUID_compute_processes':[],
        'GPU_GRES_reservation_claimed':False,'public_lock_probe_only':True}


def parent_c0(raw,job):
    rows=[line.split('|') for line in raw.splitlines() if line.strip()]
    matches=[row for row in rows if len(row)==6 and row[0]==job]
    require(len(matches)==1 and matches[0][1:4]==['zixiao','COMPLETED','0:0']
        and matches[0][4].isdecimal() and matches[0][5].isdecimal() and int(matches[0][5])>=16,
        'Actual exact Slurm parent/User/C0/CPU proof required')
    return {'job_id':job,'elapsed_seconds':int(matches[0][4]),'allocated_cpus':int(matches[0][5])}


def supervisor_closed(value,job):
    require(str(value['job_id'])==job and value['status']=='COMPLETED' and value['exit_code']==0
        and value['first_failure'] is None and value['retirement'] is None
        and value['remaining_recorded_processes_before_retirement']==[] and value['private_storage_cleanup_errors']==[]
        and value['foreign_gpu_processes_signalled'] is False and value['gpu_uuid']==GPU
        and value['private_storage_final']['first_sampling_failure'] is None,'Actual supervisor/process/private closure required')


def numeric_gate(values):
    summary,status,config,provenance,ready=(values[name] for name in ('summary','run_status','configuration','provenance','ready'))
    require(summary['status']==status['status']=='PAIRED_GATES_PASS' and summary['full_A_numeric_acceptance'] is True
        and summary['fixed_batch_pass'] is True and summary['trajectory_pass'] is True and summary['smoke'] is False
        and summary['input']=='native_s' and summary['timing_kind']=='paired_two_resident_models_diagnostic_not_standalone_speed'
        and summary['code_sha']==config['code_sha']==CODE and summary['prereg_sha']==config['prereg_sha']==PREREG
        and summary['candidate_options_sha256']==config['candidate_options_sha256']==OPTIONS_SHA
        and summary['gpu_uuid']==config['gpu_uuid']==GPU and config['gpu_name']==config['gpu']['name']
        and '4090' in config['gpu_name'] and config['node']==NODE and config['seed']==0,
        'Complete numeric gate must bind actual4090/source/options/seed')
    require(config['model']['backbone']['dim']==512 and config['model']['backbone']['layers']==6
        and config['candidate']=={**config['reference'],'backbone_checkpointing':False}
        and config['candidate']['precision']=='fp32' and config['candidate']['tf32'] is False,
        'Original A01-only/checkpointing/FP32 contract differs')
    require(status['failure'] is None and status['cleanup_errors']==[] and status['job_id']=='4520456'
        and status['stream_cleanup']=={'errors':[],'input_descriptors_closed':True},'Numeric input/SDK cleanup did not close')
    require(config['configuration_sha256']==summary['configuration_sha256']==canonical({key:value for key,value in config.items()
        if key!='configuration_sha256'}),'Original complete configuration hash differs')
    for name,count_key,count in (('fixed_batch_gate','batches',20),('trajectory_gate','updates',500)):
        gate=values[name]
        require(gate['pass'] is True and gate[count_key]==count and len(gate['results'])==count
            and all(row['pass'] is True for row in gate['results']),'Every original20/500 gate result must pass')
    require(provenance['source_files']==config['source_sha256'] and provenance['source_inventory_sha256']==
        ready['source_inventory_sha256']==canonical(config['source_sha256'])
        and provenance['code_sha']==ready['code_sha']==CODE and provenance['full_native_A_numeric_gates_passed'] is True
        and ready['optimizer_updates']==500 and ready['status']=='H0_BYTES_VERIFIED_PENDING_OUTER_JOB_TERMINAL',
        'Saved configuration/provenance/READY source closure differs')
    return {'numeric_parent_job':'4520456','numeric_gate_scope':'this actual source/options/native-S/physical4090 only',
        'fixed_batches':20,'trajectory_updates':500,'full_A_numeric_acceptance':True,
        'standalone_speed_inferred':False,'source_inventory_sha256':provenance['source_inventory_sha256'],
        'original_GPU_observation':config['gpu'],'original_torch_GPU_total_bytes':config['gpu_total_bytes'],
        'original_driver_name_capacity_are_machine_observations':True,'SDK_verification_inferred':False}


def member_closed(position,summary,status,configuration,supervisor,accounting):
    require(summary['status']==status['status']=='STANDALONE_TIMING_COMPLETED'
        and summary['abba_position']==position and summary['role']==ORDER[position-1] and summary['series_id']==SERIES
        and summary['seed']==0 and summary['input']=='native_s' and summary['smoke'] is False
        and summary['measured_updates']==20 and summary['warmup_updates']==2 and summary['gpu_uuid']==GPU
        and summary['code_sha']==CODE and summary['prereg_sha']==PREREG and summary['candidate_options_sha256']==OPTIONS_SHA
        and summary['foreign_gpu_risk_observed'] is False and summary['padding_exploration'] is False
        and status['failure'] is None and status['cleanup_errors']==[]
        and status['stream_cleanup']=={'errors':[],'input_descriptors_closed':True},'Previous standalone member incomplete/different')
    job=str(configuration['job_id']); require(job==accounting['job_id'],'Previous actual job binding differs')
    supervisor_closed(supervisor,job)
    require(summary['configuration_sha256']==configuration['configuration_sha256']==canonical({key:value for key,value in configuration.items()
        if key!='configuration_sha256'}),'Previous standalone full configuration differs')
    return job
