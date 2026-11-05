"""Source-bound development-GPU software-memory admission; no runner or scheduler."""
from __future__ import annotations
import hashlib, importlib.util, json, os, re, stat
from decimal import Decimal, ROUND_CEILING
from pathlib import Path

B=Path('/share/home/zixiao/descriptor_analysis'); N=B/'runs/model_v3_20261026'
HERE=N/'model_GPU_auto_memory_policy_v1_source'; META=2<<20
REGISTRY_KEY='GPU_software_memory'; UID=1278; USER='zixiao'
FILES=('policy.py','legacy_bindings.json','METHODS.md','test_policy.py','source_pins.json')
PREFIX='docs/model_v3/pre_registered_methods/model_GPU_auto_memory_policy_v1/'
SCHEMA='model_v3_GPU_software_memory_registration_v1'
ACTIVE={'R','CG','CF','S','ST','RS','RF'}

def need(ok,message):
    if not ok: raise ValueError(message)

def reference(path):
    p=Path(path).absolute(); s=p.lstat()
    need(p.resolve()==p and p.is_relative_to(B) and p.suffix in ('.json','.py','.md','.sbatch') and stat.S_ISREG(s.st_mode)
         and s.st_uid==UID and s.st_nlink==1 and 0<s.st_size<=META,
         'Owned canonical bounded source/metadata required: '+str(p))
    raw=p.read_bytes(); t=p.lstat()
    need(all(getattr(s,k)==getattr(t,k) for k in ('st_dev','st_ino','st_size','st_mtime_ns','st_uid','st_nlink')),
         'Source/metadata changed while read')
    return dict(path=str(p),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())

def read(path):
    before=reference(path)
    value=json.loads(Path(path).read_bytes(),parse_constant=lambda x:(_ for _ in ()).throw(ValueError('Nonfinite JSON')))
    need(reference(path)==before,'Metadata changed while parsed')
    return value

def bound(item,parse=False):
    need(type(item) is dict and set(item)=={'path','bytes','sha256'} and type(item['bytes']) is int
         and item['bytes']>0 and type(item['sha256']) is str and re.fullmatch('[0-9a-f]{64}',item['sha256'])
         and reference(item['path'])==item,'Exact source/metadata rawref required')
    return read(item['path']) if parse else item

def verify_package(sha256):
    pin=reference(HERE/'source_pins.json'); need(pin['sha256']==sha256,'Exact shared policy pins required')
    data=read(pin['path'])
    need(data['schema']=='model_v3_GPU_auto_memory_policy_sources_v1'
         and len(data['files'])==4 and {Path(x['path']).name for x in data['files']}==set(FILES)-{'source_pins.json'},
         'Exact four policy leaves plus separate pins required')
    for item in data['files']:
        need(Path(item['path']).parent==HERE,'Fixed policy source namespace required'); bound(item)
    for item in data['protected_dependencies']: bound(item)
    approval=bound(data['approval'],True)
    need(approval['schema']=='model_v3_development_GPU_auto_memory_user_approval_v1'
         and approval['status']=='USER_EXPLICITLY_APPROVED'
         and approval['user_answer']=='采用方案，GPU 也用自动内存'
         and approval['original_software_budgets_RSS_85pct_guards_and_scientific_rules_preserved'] is True,
         'Actual explicit development-GPU automatic-memory approval required')
    return pin

def verify_publication(item):
    pub=bound(item,True)
    need(pub['schema']=='model_v3_exact_tree_publication_actual_v1'
         and pub['repository_full_name']=='mint258/MFM' and pub['branch']=='model-v3'
         and pub['public_branch_readback_verified'] is True and pub['public_Git_API_tree_readback_verified'] is True,
         'Actual shared policy exact-tree publication required')
    table={x['path']:x for x in pub['files']}; need(len(table)==len(pub['files']),'Duplicate policy publication paths')
    for name in FILES:
        raw=(HERE/name).read_bytes(); item=table[PREFIX+name]
        need(item['type']=='blob' and item['sha']==hashlib.sha1(b'blob '+str(len(raw)).encode()+bytes([0])+raw).hexdigest(),
             'Shared policy is not exact published bytes: '+name)
    return pub

def registry_lock(path):
    """Reuse the exact existing Native mutex; callers must not nest this mutex."""
    seed=read(HERE/'legacy_bindings.json'); source=seed['registry_lock_delegate']; bound(source)
    bound(seed['registry_lock_delegate_dependencies'])
    spec=importlib.util.spec_from_file_location('GPU_auto_memory_original_registry_delegate',source['path'])
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module.registry_lock(Path(path))

def make_registration(*,registration_id,node,gpu_uuid,software_budget_bytes,rss_limit_bytes,
                      Root_source,source_pins,slurm_memory_mode='automatic_default',status='PRE_SUBMISSION',
                      job_id=None,actual_submission=None,job_id_field='job_id',proof_refs=()):
    record=dict(schema=SCHEMA,authority='ROOT_ACTUAL',uid=UID,user=USER,registration_id=registration_id,
                node=node,gpu_uuid=gpu_uuid,software_budget_bytes=software_budget_bytes,rss_limit_bytes=rss_limit_bytes,
                Root_source=Root_source,source_pins=source_pins,slurm_memory_mode=slurm_memory_mode,status=status,
                job_id=job_id,actual_submission=actual_submission,job_id_field=job_id_field,proof_refs=list(proof_refs))
    return validate_registration(record)

def validate_registration(record):
    keys={'schema','authority','uid','user','registration_id','node','gpu_uuid','software_budget_bytes','rss_limit_bytes',
          'Root_source','source_pins','slurm_memory_mode','status','job_id','actual_submission','job_id_field','proof_refs'}
    need(type(record) is dict and set(record)==keys and record['schema']==SCHEMA
         and record['authority']=='ROOT_ACTUAL' and record['uid']==UID and record['user']==USER,
         'Exact Root-owned GPU software-budget registration required')
    need(type(record['registration_id']) is str and re.fullmatch('[A-Za-z0-9_.-]{1,160}',record['registration_id'])
         and re.fullmatch('compute-0-[0-9]+',record['node']) and re.fullmatch('GPU-[0-9a-f-]+',record['gpu_uuid']),
         'Explicit registration/node/GPU identity required')
    need(type(record['software_budget_bytes']) is int and type(record['rss_limit_bytes']) is int
         and (record['software_budget_bytes'],record['rss_limit_bytes']) in ((32<<30,28<<30),(64<<30,56<<30)),
         'Only unchanged Native32/28 or A64/56 software/RSS budgets are authorized')
    need(record['slurm_memory_mode'] in ('automatic_default','fixed_declared')
         and record['status'] in ('PRE_SUBMISSION','SUBMITTED')
         and record['job_id_field'] in ('job_id','actual_sbatch_job_id') and type(record['proof_refs']) is list,
         'Explicit memory mode and one-use submission state required')
    bound(record['Root_source']); bound(record['source_pins'])
    for item in record['proof_refs']: bound(item)
    if record['status']=='PRE_SUBMISSION':
        need(record['job_id'] is None and record['actual_submission'] is None,
             'Unsubmitted intent must have no invented job or actual submission')
    else:
        need(type(record['job_id']) is str and re.fullmatch('[0-9]+',record['job_id']), 'Actual numeric owned GPU job required')
        submission=bound(record['actual_submission'],True)
        need(submission[record['job_id_field']]==record['job_id'] and submission['status']=='SUBMITTED',
             'Software budget must bind the actual Root SUBMITTED record and job ID')
    return record

def put_registration(registry_document,record):
    """Only mutate one optional top-level map in the caller's already locked document."""
    validate_registration(record)
    table=registry_document.setdefault(REGISTRY_KEY,{})
    need(type(table) is dict,'GPU software registration map required')
    previous=table.get(record['registration_id'])
    if previous is not None:
        validate_registration(previous)
        identity=lambda x:{k:v for k,v in x.items() if k not in ('status','job_id','actual_submission')}
        need(identity(previous)==identity(record) and (previous==record or
             previous['status']=='PRE_SUBMISSION' and record['status']=='SUBMITTED'),
             'No registration identity overwrite, retry or automatic retirement')
    table[record['registration_id']]=record
    return record

def finite_declaration(text,cpus):
    """A positive finite squeue %m declaration; zero/unknown is never a guarantee."""
    match=re.fullmatch(r'(\d+(?:\.\d+)?)([KMGT]?)([cn]?)',text)
    if match is None: return None
    amount=Decimal(match[1])*{'':1<<20,'K':1<<10,'M':1<<20,'G':1<<30,'T':1<<40}[match[2]]
    if match[3]=='c': amount*=cpus
    return int(amount.to_integral_value(rounding=ROUND_CEILING)) if amount>0 else None

def _assess(node_raw,squeue_raw,meminfo_raw,*,node,software_budget_bytes,rss_limit_bytes,
            registrations,current_job_id=None,current_reservation_id=None):
    """Arithmetic over validated actual metadata; no model or payload access."""
    need((software_budget_bytes,rss_limit_bytes) in ((32<<30,28<<30),(64<<30,56<<30)),'Unchanged caller software/RSS budget required')
    need(re.search(r'\bNodeName='+re.escape(node)+r'\b',node_raw) is not None,'Actual node observation differs')
    values=dict(re.findall(r'\b(RealMemory|AllocMem)=(\d+)',node_raw))
    need('RealMemory' in values and int(values['RealMemory'])>0,'Actual node RealMemory required')
    total=int(values['RealMemory'])<<20
    available_match=re.search(r'(?m)^MemAvailable:\s+(\d+) kB\s*$',meminfo_raw)
    need(available_match is not None,'Actual MemAvailable required'); available=int(available_match[1])<<10
    by_id={r['registration_id']:r for r in registrations}
    need(len(by_id)==len(registrations),'Duplicate software registration IDs')
    self_record=by_id.get(current_reservation_id)
    need(self_record is not None and self_record['node']==node
         and self_record['software_budget_bytes']==software_budget_bytes and self_record['rss_limit_bytes']==rss_limit_bytes,
         'Caller must have one exact source-bound software registration')
    if current_job_id is None:
        need(self_record['status']=='PRE_SUBMISSION','Root admission must bind its unsubmitted intent')
    else:
        need(self_record['status']=='SUBMITTED' and self_record['job_id']==current_job_id,
             'Worker requires its exact actual SUBMITTED registration and job ID')
    by_job={}
    for item in registrations:
        if item['job_id'] is not None:
            need(item['job_id'] not in by_job,'Duplicate actual owned GPU job registrations')
            by_job[item['job_id']]=item
    owned=[]; foreign_finite=[]; foreign_unknown=[]; rows=[]; seen=set()
    for line in squeue_raw.splitlines():
        if not line.strip(): continue
        parts=line.strip().split('|')
        need(len(parts)==5 and parts[4].isdigit(),'Actual five-column node squeue observation required')
        job,user,state,memory,cpus=parts
        if state not in ACTIVE: continue
        need(job not in seen,'Duplicate active scheduler job'); seen.add(job)
        finite=finite_declaration(memory,int(cpus)); rows.append(dict(job_id=job,user=user,state=state,ReqMem_observed=memory,cpus=int(cpus)))
        if user==USER:
            item=by_job.get(job)
            need(item is not None and item['node']==node and item['status']=='SUBMITTED',
                 'HOLD: unknown or mismatched own active GPU/software role '+job)
            if job==current_job_id:
                need(item['registration_id']==current_reservation_id,'Worker registration identity differs'); continue
            if item['slurm_memory_mode']=='fixed_declared':
                need(finite is not None,'HOLD: own fixed declaration is not finite '+job)
                charge=max(item['software_budget_bytes'],finite)
            else: charge=item['software_budget_bytes']
            owned.append(dict(registration_id=item['registration_id'],job_id=job,software_budget_bytes=item['software_budget_bytes'],
                              scheduler_memory_observed=memory,slurm_memory_mode=item['slurm_memory_mode'],counted_bytes=charge,
                              Root_source=item['Root_source'],source_pins=item['source_pins'],actual_submission=item['actual_submission'],
                              finite_and_software_counted_once=True))
        elif finite is None:
            foreign_unknown.append(dict(job_id=job,user=user,scheduler_memory_observed=memory,finite_guarantee_claimed=False))
        else: foreign_finite.append(dict(job_id=job,user=user,scheduler_memory_observed=memory,counted_bytes=finite))
    if current_job_id is not None: need(current_job_id in seen,'Worker is absent from actual active scheduler observation')
    intents=[]
    for item in registrations:
        if item['node']==node and item['status']=='PRE_SUBMISSION' and item['registration_id']!=current_reservation_id:
            intents.append(dict(registration_id=item['registration_id'],counted_bytes=item['software_budget_bytes'],actual_job_id=None))
    prior=sum(x['counted_bytes'] for x in owned+foreign_finite+intents)
    need((prior+software_budget_bytes)*100<total*85,'Registered own software plus foreign finite and new software must remain below RealMemory85%')
    need(available*100>=software_budget_bytes*100+total*15,'Actual MemAvailable must cover new software budget plus node15%')
    return dict(schema='model_v3_GPU_auto_memory_assessment_v1',node=node,Slurm_memory_mode='automatic_default',
                fixed_Slurm_memory_requested_bytes=None,Slurm_finite_physical_allocation_guarantee_claimed=False,
                software_budget_bytes=software_budget_bytes,rss_limit_bytes=rss_limit_bytes,
                RealMemory_MiB=int(values['RealMemory']),observed_AllocMem_MiB=int(values['AllocMem']) if 'AllocMem' in values else None,
                MemAvailable_bytes=available,MemAvailable_MiB=available/(1<<20),prior_counted_bytes=prior,
                with_new_software_bytes=prior+software_budget_bytes,own_active_budgets=owned,
                other_presubmission_intents=intents,foreign_finite_declarations=foreign_finite,foreign_unknown_declarations=foreign_unknown,
                unknown_foreign_finite_guarantee_claimed=False,scheduler_rows=rows,current_reservation_id=current_reservation_id,
                current_job_id=current_job_id,caller_registration=self_record,self_counted_exactly_once=True)

def assess(node_raw,squeue_raw,meminfo_raw,*,node,software_budget_bytes,rss_limit_bytes,registry_path,
           current_job_id=None,current_reservation_id=None):
    """Snapshot under the original mutex. Do not call while already holding it."""
    seed=read(HERE/'legacy_bindings.json')
    legacy=seed['registrations']
    for record in legacy: validate_registration(record)
    with registry_lock(registry_path):
        registry=read(registry_path)
        need(registry['schema']=='native_S_Root_registered_reservations_v1'
             and registry['authority']=='ROOT_ACTUAL' and registry['uid']==UID,'Actual existing Root registry required')
        table=registry.get(REGISTRY_KEY,{})
        need(type(table) is dict,'GPU software registration map required')
        records=list(table.values())
        for key,record in table.items():
            validate_registration(record); need(key==record['registration_id'],'Registry record ID differs')
    return _assess(node_raw,squeue_raw,meminfo_raw,node=node,software_budget_bytes=software_budget_bytes,
                   rss_limit_bytes=rss_limit_bytes,registrations=legacy+records,current_job_id=current_job_id,
                   current_reservation_id=current_reservation_id)
