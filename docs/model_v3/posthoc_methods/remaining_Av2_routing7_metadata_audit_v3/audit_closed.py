"""CPU-only audit of original closed routing-v7 JSON; never runs a model or SDK."""
from __future__ import annotations
import argparse, hashlib, importlib.util, json, math, os, re, socket, stat
from copy import deepcopy
from pathlib import Path

B=Path('/share/home/zixiao/descriptor_analysis'); N=B/'runs/model_v3_20261026'
HERE=Path(__file__).absolute().parent; ROUTING=N/'performance_remaining_Av2_20261029_routing_v7'
W=B/'MFM_model_v3_A_acceptance_v2_candidate_v1'
CODE='7ffe8a5557590b1481f4ca74073007f070dc6a50'; PUBLIC='2b4a4df8636e5d65915d535472ba01084ea72dab'
TREE='8f9530415034bdb885c1c765aee434797c70e7c7'; RULE='4f6ba16973ea4a30472c7fb33d3aadec974a4462'
META=2<<20; LIMIT=2<<30; RSS=56<<30
FILES={'audit_closed.py','audit_cpu.sbatch','dependencies.json','README.md'}

def need(ok,message):
    if not ok: raise ValueError(message)

def exact(a,b):
    """JSON identity including integer type: never tolerate float-rounded nanoseconds."""
    if type(a) is not type(b): return False
    if isinstance(a,dict): return a.keys()==b.keys() and all(exact(a[k],b[k]) for k in a)
    if isinstance(a,list): return len(a)==len(b) and all(exact(x,y) for x,y in zip(a,b))
    return a==b

MODEL_FLOAT_PATHS=(('head','geometry_radius'),('backbone','dropout'),
                   ('backbone','radius'),('expert','dropout'))

def planned_model_equal(original_model,planned_model):
    """Only four declared float fields may have equal finite int PLAN spelling."""
    if type(original_model) is not dict or type(planned_model) is not dict:return False
    projected=deepcopy(planned_model)
    for parent,key in MODEL_FLOAT_PATHS:
        try:original=original_model[parent][key];planned=projected[parent][key]
        except (KeyError,TypeError):return False
        if type(original) is not float or not math.isfinite(original):return False
        if type(planned) not in (int,float):return False
        if type(planned) is int and abs(planned)>(1<<53)-1:return False
        if not math.isfinite(planned) or planned!=original:return False
        projected[parent][key]=float(planned)
    return exact(original_model,projected)

def metadata_selfchecks():
    """Small metadata negatives, run inside this same original CPU audit parent."""
    checks=[]
    original={'head':{'geometry_radius':5.0},'backbone':{'dropout':0.0,'radius':8.0,'dim':512},
              'expert':{'dropout':0.0},'other':{'count':2,'precision':'fp32'}}
    planned=deepcopy(original)
    for parent,key in MODEL_FLOAT_PATHS:planned[parent][key]=int(planned[parent][key])
    need(planned_model_equal(original,planned),'Declared finite equal float fields must pass');checks.append('four_declared_float_spellings')
    for parent,key in MODEL_FLOAT_PATHS:
        bad=deepcopy(planned);bad[parent][key]=False
        need(not planned_model_equal(original,bad),'Boolean float-field spelling must fail');checks.append(parent+'.'+key+'_bool_rejected')
    for value in (512.0,False):
        bad=deepcopy(planned);bad['backbone']['dim']=value
        need(not planned_model_equal(original,bad),'Dimension type must remain exact');checks.append('dimension_'+type(value).__name__+'_rejected')
    for value in (5.000000000000001,float('inf'),float('nan')):
        bad=deepcopy(planned);bad['head']['geometry_radius']=value
        need(not planned_model_equal(original,bad),'Changed/nonfinite radius must fail');checks.append('radius_'+str(value)+'_rejected')
    bad=deepcopy(planned);bad['other']['count']=2.0
    need(not planned_model_equal(original,bad),'Other numeric field must remain exact');checks.append('other_numeric_type_rejected')
    bad=deepcopy(planned);bad['head']['extra']=1
    need(not planned_model_equal(original,bad),'Extra model field must fail');checks.append('extra_model_key_rejected')
    huge_original=deepcopy(original);huge_plan=deepcopy(planned)
    huge_original['head']['geometry_radius']=float(1<<54);huge_plan['head']['geometry_radius']=1<<54
    need(not planned_model_equal(huge_original,huge_plan),'Large int projection forbidden');checks.append('large_int_float_projection_rejected')
    stamp=1791880208985935300
    need(not exact({'mtime_ns':stamp},{'mtime_ns':float(stamp)}) and not exact({'mtime_ns':stamp},{'mtime_ns':stamp+1}),
         'Large integer provenance type/value must remain exact');checks.append('large_mtime_float_and_value_rejected')
    need(exact({'mtime_ns':stamp},{'mtime_ns':stamp}),'Exact arbitrary-width integer must pass');checks.append('exact_large_integer_preserved')
    return dict(scope='PURE_METADATA_ONLY_NO_TENSORS_OR_SCIENTIFIC_REEXECUTION',checks=checks,count=len(checks))

def reject_constant(value): raise ValueError('Nonfinite JSON constant: '+value)

def duplicate_checked(pairs):
    value={}
    for key,item in pairs:
        need(key not in value,'Duplicate JSON key: '+key);value[key]=item
    return value

def canonical(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

def raw(path,maximum=META):
    path=Path(path).absolute(); before=path.lstat()
    need(path.resolve()==path and path.is_relative_to(B) and stat.S_ISREG(before.st_mode)
         and before.st_uid==1278 and before.st_nlink==1 and 0<before.st_size<=maximum,
         'Owned canonical bounded source/JSON required: '+str(path))
    need(path.suffix in ('.json','.py','.sbatch','.md'),'Source/JSON only; no journals, SDK, arrays or checkpoints')
    body=path.read_bytes();after=path.lstat()
    need(tuple(getattr(before,k) for k in ('st_dev','st_ino','st_size','st_mtime_ns'))==
         tuple(getattr(after,k) for k in ('st_dev','st_ino','st_size','st_mtime_ns')),'Changed during read: '+str(path))
    return body,dict(path=str(path),bytes=len(body),sha256=hashlib.sha256(body).hexdigest())

def read(path,maximum=META):
    body,ref=raw(path,maximum)
    value=json.loads(body,parse_constant=reject_constant,object_pairs_hook=duplicate_checked)
    need(raw(path,maximum)[1]==ref,'JSON changed during parse');return value,ref

def bound(ref):
    body,current=raw(ref['path']);need(exact(current,ref),'Frozen rawref differs: '+ref['path']);return body

def load(ref,name):
    bound(ref);spec=importlib.util.spec_from_file_location(name,ref['path'])
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);bound(ref);return module

def package(pin_sha):
    pins,pref=read(HERE/'source_pins.json')
    need(pref['sha256']==pin_sha and pins['schema']=='model_v3_remaining_routing7_closed_metadata_audit_sources_v1'
         and len(pins['files'])==4 and {Path(r['path']).name for r in pins['files']}==FILES,'Exact four-leaf audit package required')
    for ref in pins['files']:
        need(Path(ref['path']).parent==HERE,'Own package leaf path differs');bound(ref)
    deps,_=read(HERE/'dependencies.json')
    need(deps['schema']=='model_v3_remaining_routing7_closed_metadata_audit_dependencies_v1','Unknown audit dependencies')
    for ref in deps['sources'].values():bound(ref)
    return pref,deps

def allocation(expected_node):
    job=os.environ.get('SLURM_JOB_ID','');node=socket.gethostname().split('.')[0]
    need(os.getuid()==os.geteuid()==1278 and job.isdigit()
         and os.environ.get('SLURM_CPUS_PER_TASK')=='16' and os.environ.get('CUDA_VISIBLE_DEVICES')==''
         and node==expected_node and re.fullmatch(r'compute-0-(?:[2-9]|1[0-9])',node),
         'Owned CPU16 allocation/actual CPU node with CUDA hidden required')
    group=Path('/proc/self/cgroup').read_text()
    need(re.search(r'(?:job[_/-])'+re.escape(job)+r'(?:/|\n|$)',group),'Actual CPU job cgroup differs')
    return dict(job_id=job,node=node,uid=os.getuid(),cgroup=group,
        scheduler_memory_environment={k:v for k,v in os.environ.items() if k.startswith('SLURM_MEM_')},
        Slurm_memory_mode='automatic_default',fixed_memory_requested_bytes=None,
        software_working_memory_budget_bytes=16<<30,supervisor_RSS_limit_bytes=12<<30,
        finite_physical_memory_guarantee_claimed=False)

def publication(ref,plan):
    pub=json.loads(bound(ref),parse_constant=reject_constant,object_pairs_hook=duplicate_checked)
    need(pub['schema']=='model_v3_exact_tree_publication_actual_v1' and pub['repository_full_name']=='mint258/MFM'
         and pub['branch']=='model-v3' and pub['public_branch_readback_verified'] is True
         and pub['public_Git_API_tree_readback_verified'] is True,'Actual routing publication/readbacks required')
    table={r['path']:r for r in pub['files']};need(len(table)==len(pub['files']),'Duplicate method blobs')
    for name in plan['method_files']:
        body,_=raw(ROUTING/name);row=table[plan['method_prefix']+name]
        need(row['type']=='blob' and row['sha']==hashlib.sha1(b'blob '+str(len(body)).encode()+b'\0'+body).hexdigest(),
             'Published exact routing-v7 method differs: '+name)
    policy=load(plan['dependencies']['GPU_auto_memory_policy_source'],'closed_routing7_shared_memory_source')
    policy.verify_package(plan['dependencies']['GPU_auto_memory_policy_pins']['sha256']);policy.verify_publication(ref)

def planned(deps):
    plan,planref=read(ROUTING/'PLAN.json')
    need(exact(planref,deps['sources']['routing_plan']) and plan['routing_version']==7
         and plan['schema']=='model_v3_remaining_six_A_cohort_v2_routing_execution_plan_v2'
         and plan['source_directory']==str(ROUTING) and len(plan['cases'])==6,'Frozen exact routing-v7 plan required')
    pins=json.loads(bound(deps['sources']['routing_pins']),parse_constant=reject_constant)
    need(len(pins['files'])==4 and {Path(r['path']).name for r in pins['files']}==
         {'PLAN.json','Root_submit.py','run_remaining_Av2.sbatch','METHODS.md'},'Original routing four leaves required')
    for ref in pins['files']:bound(ref)
    need(plan['current_source']==dict(local_commit=CODE,public_commit=PUBLIC,tree=TREE,worktree=str(W))
         and plan['rules']==dict(analytic_zero_both_gradient_L2_max=1e-8,fixed_batch_only_allowed=False,
             fixed_batches=20,forward_relative_l2_max=1e-5,gradient_elementwise_atol=1e-8,
             gradient_elementwise_rtol=1e-4,public_commit=RULE,trajectory_each_relative_loss_max=1e-3,
             trajectory_updates=500,version='v2'),'Original source/rules declaration differs')
    for ref in plan['dependencies'].values():bound(ref)
    seen=set()
    for case in plan['cases']:
        need(case['old_job_id'] not in seen,'Duplicate old selector');seen.add(case['old_job_id'])
        old=json.loads(bound(case['original_configuration']),parse_constant=reject_constant,object_pairs_hook=duplicate_checked)
        for key,other in [('candidate','candidate'),('reference','reference_options'),('model','model'),('data_version','original_data_version')]:
            same=planned_model_equal(old[key],case[other]) if key=='model' else exact(old[key],case[other])
            need(same,'Complete original cohort differs for '+case['old_job_id']+': '+key)
        need(old['seed']==0 and old['input']=='native_s' and old['fixed_batches']==20 and old['trajectory_updates']==500
             and case['old500_reused'] is False and case['performance_execution_request'] is None,'Original no-resume/no-opt-in full cohort required')
        need(type(old['data_version']['original_shard_snapshot']['mtime_ns']) is int
             and old['data_version']['original_shard_snapshot']['mtime_ns']==1791880208985935300,
             'Exact original integer nanoseconds required')
        need(exact(json.loads(bound(case['candidate_options'])),case['candidate']),'Original options bytes/values differ')
    guard=load(plan['dependencies']['existing_source_guard'],'closed_routing7_original_source_qualification')
    qualification=guard.validate_sources()  # Original full115 CPU4695/public7ffe; no numeric/model imports.
    auditor=load(deps['sources']['original_fixed20_auditor'],'closed_routing7_original_fixed20_auditor')
    return plan,planref,qualification,auditor

def submission(case,plan,planref,deps):
    family=Path(case['family']);control=Path(case['control'])
    need(family==ROUTING/'trials'/('recheck_'+case['old_job_id']+'_routing_v7')
         and control==family/'control' and Path(case['child_output'])==family/'child'
         and Path(case['supervisor_record'])==family/'supervisor.json','Exact independent routing-v7 output paths required')
    value,ref=read(control/'Root_submission_actual_v1.json');job=value['job_id']
    need(value['schema']=='model_v3_remaining_Av2_routing_v7_Root_single_submission_v1'
         and value['status']=='SUBMITTED' and type(job) is str and job.isdigit()
         and value['declared_routing_version']==7 and value['old_job_id']==case['old_job_id']
         and exact(value['source_package'],deps['sources']['routing_pins']) and exact(value['plan'],planref)
         and value['automatic_retry'] is False and value['old500_or_timing_reused'] is False,
         'One actual successful Root submission required; no inferred job identity')
    need(value['Slurm_memory_mode']=='automatic_default' and value['Slurm_requested_memory_MiB'] is None
         and value['software_memory_budget_bytes']==64<<30 and value['RSS_limit_bytes']==RSS,
         'Original GPU automatic-memory software/RSS declaration differs')
    need(exact(value['Root_driver'],deps['sources']['routing_Root_driver']), 'Actual submitted Root source differs')
    installed=bound(value['installed_sbatch']);need(installed==bound(deps['sources']['routing_worker']),'Installed worker bytes differ')
    expected=['sbatch','--parsable','--partition=all','--nodelist='+case['expected_node'],'--cpus-per-task=16',
        '--time=02:00:00','--export=ALL','--output='+str(control/'slurm_%j.log'),value['installed_sbatch']['path'],case['old_job_id']]
    need(value['argv']==expected,'Original one-use automatic-memory submit argv differs')
    actual=[r for r in value['observations'] if r.get('argv')==expected]
    need(len(actual)==1 and actual[0]['returncode']==0
         and re.fullmatch(re.escape(job)+r'(?:;[A-Za-z0-9_.-]+)?',actual[0]['stdout'].strip()),
         'Exactly one actual sbatch acknowledgement required')
    for key in ('admission','quota','hold'):bound(value[key])
    publication(value['operations_publication'],plan)
    return value,ref

def parents(rawref,submissions,cases):
    body=json.loads(bound(rawref),parse_constant=reject_constant,object_pairs_hook=duplicate_checked)
    argv=body['argv'];jobs={x['job_id'] for x in submissions};need(len(jobs)==len(submissions),'Duplicate actual GPU job')
    columns='JobIDRaw,User,State,ExitCode,ElapsedRaw,AllocCPUS,NodeList'
    accepted=[]
    for selection in (','.join(x['job_id'] for x in submissions),','.join(sorted(jobs))):
        accepted.extend([['sacct','-X','-j',selection,'-n','-P','-o',columns],
                         ['sacct','-X','-n','-P','-j',selection,'--format='+columns]])
    need(argv in accepted and type(body['returncode']) is int and body['returncode']==0 and body['stderr']=='',
         'Actual explicit selected seven-column parent accounting required')
    rows=[r.split('|') for r in body['stdout'].splitlines() if r.strip()]
    need(len(rows)==len(jobs) and {r[0] for r in rows}==jobs,'Exact actual selected parent rows required')
    expected={s['job_id']:c['expected_node'] for s,c in zip(submissions,cases)};result={}
    for row in rows:
        need(len(row)==7 and row[1:4]==['zixiao','COMPLETED','0:0'] and row[4].isdigit()
             and row[5:]==['16',expected[row[0]]],'Every selected original GPU parent must actually be C0/16CPU/on target node')
        result[row[0]]=dict(job_id=row[0],state=row[2],exit_code=row[3],elapsed_seconds=int(row[4]),alloc_cpus=16,node=row[6])
    return result

def audit_case(case,submission_value,sref,plan,auditor):
    job=submission_value['job_id'];out=Path(case['child_output']);family=out.parent;refs={}
    cfg,refs['configuration']=read(out/'configuration.json')
    summary,refs['summary']=read(out/'summary.json');status,refs['run_status']=read(out/'run_status.json')
    sup,refs['supervisor']=read(family/'supervisor.json')
    old=json.loads(bound(case['original_configuration']),parse_constant=reject_constant,object_pairs_hook=duplicate_checked)
    for key in ('model','candidate','reference','optimizer','loss_policy','loss_weights','supervision','schedule',
                'gradient_clip_norm','dynamic_balancer','input','seed','smoke','fixed_batches','trajectory_updates','data_version'):
        need(exact(cfg[key],old[key]),'Actual original scientific/config field differs: '+key)
    need(cfg['job_id']==status['job_id']==sup['job_id']==job and cfg['code_sha']==CODE and cfg['prereg_sha']==PUBLIC
         and cfg['gpu_uuid']==sup['gpu_uuid']==case['gpu_uuid'] and cfg['gpu_name']==case['gpu_name']
         and cfg['node'].split('.')[0]==case['expected_node'] and cfg['logical_python']==case['logical_python']
         and cfg['candidate_options_sha256']==case['candidate_options']['sha256']
         and cfg.get('performance_execution_request') is None and cfg.get('performance_execution') is None,
         'Actual current-source legacy cohort/device/ordinary execution identity differs')
    need(cfg['gpu']['uuid']==case['gpu_uuid'] and cfg['gpu']['foreign_processes']==[]
         and cfg['tracking_mode']=='offline' and cfg['downstream_data_read'] is False and cfg['original_lmdb_written'] is False,
         'Actual source-bound hardware/offline/input policy differs')
    need(cfg['checkpoint_export']['requested'] is False and cfg['checkpoint_export']['destination'] is None
         and cfg['checkpoint_export']['resume_supported'] is False,'Original no-export/no-resume policy required')
    need(canonical({k:v for k,v in cfg.items() if k!='configuration_sha256'})==cfg['configuration_sha256'],
         'Actual canonical configuration SHA differs')
    source=cfg['source_sha256'];need(type(source) is dict and len(source)>0,'Actual complete runtime source bindings required')
    for name,digest in source.items():
        relative=Path(name);need(not relative.is_absolute() and '..' not in relative.parts,'Ordinary relative runtime source required')
        need(raw(W/relative)[1]['sha256']==digest,'Actual runtime source changed: '+name)
    for key,name in [('reference_configuration','reference_configuration'),('a4_configuration','A4_configuration')]:
        need(cfg[key]=={k:v for k,v in plan['dependencies'][name].items() if k!='bytes'},'Reference config binding differs')
    need(cfg['original_shard_snapshot_prejob_sha256']==plan['common']['snapshot_sha256'],'Original NativeS snapshot differs')
    controls=cfg['deterministic_controls'];actual=controls['actual']
    need(controls['requested'] is True and controls['scope']=='both_reference_and_candidate'
         and controls['torch_imported_before_binding'] is False and controls['cuda_initialized_before_apply'] is False
         and actual['deterministic_algorithms'] is True and actual['deterministic_warn_only'] is False
         and actual['cudnn_deterministic'] is True and actual['cudnn_benchmark'] is False
         and actual['cublas_workspace_config']==':4096:8','Original deterministic controls differ')
    rule=cfg['acceptance_rules'];need(rule['schema']=='model_v3_A_acceptance_rule_binding_v2'
         and cfg['acceptance_scope']=='V2_FULL20_AND500' and rule['public_rule_commit']==RULE
         and exact(rule['rule_document'],plan['dependencies']['rule_document'])
         and exact(rule['rule_publication'],plan['dependencies']['rule_publication'])
         and exact(cfg['acceptance_rule_source_refs'],rule['source_refs']),'Exact published complete v2 rule binding differs')
    for ref in rule['source_refs'].values():bound(ref)
    gate,refs['fixed_batch_gate']=read(out/'fixed_batch_gate.json',16<<20)
    fixed=auditor.audit_fixed_gate(gate,rule);need(fixed['passed'],'Original complete fixed20 v2 did not pass')
    receipt_ids=[]
    for row in gate['results']:
        receipt=row['input_receipt'];digest=receipt['receipt_sha256']
        need(canonical({k:v for k,v in receipt.items() if k!='receipt_sha256'})==digest
             and exact(row['record_keys'],receipt['record_keys']),'Original fixed input receipt binding differs')
        receipt_ids.append(digest)
    need(summary['fixed_input_receipts_sha256']==canonical(receipt_ids),'Original full20 receipt list differs')
    del gate
    trajectory,refs['trajectory_gate']=read(out/'trajectory_gate.json')
    need(trajectory['gate']=='A_500_update_loss_trajectory' and trajectory['updates']==500
         and len(trajectory['results'])==500 and trajectory['pass'] is True,'Original complete500 required')
    maximum=0.
    for index,row in enumerate(trajectory['results'],1):
        value=auditor.number(row['relative_difference']);maximum=max(maximum,value)
        need(row['step']==index and row['pass'] is True and value<=1e-3,'Original each-point500 loss gate differs')
    need(summary['status']=='PAIRED_GATES_PASS' and all(summary[k] is True for k in
         ('full_A_numeric_acceptance','fixed_batch_pass','trajectory_pass')) and summary['code_sha']==CODE
         and summary['prereg_sha']==PUBLIC and summary['gpu_uuid']==case['gpu_uuid']
         and summary['configuration_sha256']==cfg['configuration_sha256'] and exact(summary['acceptance_rules'],rule)
         and summary['acceptance_scope']=='V2_FULL20_AND500' and summary['input']=='native_s' and summary['smoke'] is False
         and summary['candidate_options_sha256']==case['candidate_options']['sha256']
         and summary['resume_supported'] is False,'Original complete current-source summary differs')
    need(status['status']==summary['status'] and status['failure'] is None and status['cleanup_errors']==[]
         and status['stream_cleanup']['input_descriptors_closed'] is True and status['stream_cleanup']['errors']==[]
         and exact(status['acceptance_rules'],rule) and status['acceptance_scope']=='V2_FULL20_AND500'
         and status['trajectory_started'] is True and status['committed_trajectory_updates']==500
         and status['trajectory_completed'] is True and status['resume_supported'] is False,'Original complete stream/run closure required')
    need(sup['status']=='COMPLETED' and sup['exit_code']==0 and sup['first_failure'] is None and sup['retirement'] is None
         and sup['remaining_recorded_processes_before_retirement']==[] and sup['private_storage_cleanup_errors']==[]
         and sup['launch_identity']['uid']==1278 and sup['launch_identity']['slurm_job_id']==job
         and sup['foreign_gpu_processes_signalled'] is False and sup['output_budget_bytes']==LIMIT
         and sup['child_output_budget_bytes']==LIMIT-96*(1<<20) and 0<=sup['last_output_bytes']<=LIMIT
         and sup['supervisor_source_sha256']==plan['dependencies']['supervisor']['sha256'],
         'Original source-enforced RSS56G/whole2G/process/foreign/private closure differs')
    expected=[case['logical_python'],'-u','-B','tools/model_v3/paired_a_acceptance.py',
        '--candidate-options',case['candidate_options']['path'],'--reference-config',plan['dependencies']['reference_configuration']['path'],
        '--input','native_s','--seed','0','--workers','8','--max-padded-cost','8000000','--expected-gpu',case['expected_gpu'],
        '--code-sha',CODE,'--prereg-sha',PUBLIC,'--shard-snapshot-sha256',plan['common']['snapshot_sha256'],
        '--acceptance-version','v2','--acceptance-rule-document',plan['dependencies']['rule_document']['path'],
        '--acceptance-rule-document-sha256',plan['dependencies']['rule_document']['sha256'],'--acceptance-prereg-sha',RULE,
        '--acceptance-rule-publication',plan['dependencies']['rule_publication']['path'],
        '--acceptance-rule-publication-sha256',plan['dependencies']['rule_publication']['sha256'],
        '--deterministic-controls','--output',str(out)]
    need(sup['command']==sup['launch_identity']['argv']==expected,'Exact original actual child argv differs')
    storage,refs['private_storage']=read(family/'supervisor.json.storage.json')
    need(storage['schema']=='model_v3_private_storage_v1' and storage['job_id']==job and storage['uid']==1278
         and storage['private_storage_budget_bytes']==LIMIT and storage['compiler_cache_reused'] is False
         and sup['private_storage_bindings_path']==refs['private_storage']['path']
         and cfg['private_storage_bindings']=={**storage,'receipt_path':refs['private_storage']['path'],
             'receipt_sha256':refs['private_storage']['sha256']},'Original private2G receipt binding differs')
    private=sup['private_storage_final']
    need(private['budget_bytes']==LIMIT and private['first_sampling_failure'] is None and private['samples']>0
         and private['exact_peak'] is False and 0<=private['sampled_max_bytes']<=LIMIT,'Original sampled private storage bound differs')
    for key,path in [('Root_admission','Root_admission_actual_v1.json'),('GPU_memory_startup','GPU_auto_memory_startup_actual_v1.json')]:
        frame,refs[key]=read(Path(case['control'])/path)
        if key=='GPU_memory_startup':
            need(frame['job_id']==job and frame['Slurm_memory_mode']=='automatic_default'
                 and frame['fixed_memory_requested_bytes'] is None and frame['finite_physical_guarantee_claimed'] is False,
                 'Actual startup automatic-memory observation required')
    for ref in refs.values():
        read_limit=16<<20 if Path(ref['path'])==out/'fixed_batch_gate.json' else META
        need(raw(ref['path'],read_limit)[1]==ref,'Closed metadata changed during audit')
    return dict(old_job_id=case['old_job_id'],case=case['case'],job_id=job,gpu_name=cfg['gpu_name'],gpu_uuid=cfg['gpu_uuid'],
        node=case['expected_node'],submission=sref,configuration_sha256=cfg['configuration_sha256'],
        original_configuration=case['original_configuration'],original_data_version_exact_integer_identity=True,
        current_runtime_source_count=len(source),closed_metadata=refs,fixed20=fixed,trajectory_updates=500,
        maximum_trajectory_relative_difference=maximum,consumed_trajectory_base_records=summary['consumed_trajectory_base_records'],
        supervisor_RSS_limit_bytes=RSS,RSS_limit_enforced_by_bound_original_supervisor=True,
        measured_peak_RSS_bytes=None,resource_journals_not_read=True,whole_persistent_limit_bytes=LIMIT,
        private_limit_bytes=LIMIT,sampled_private_max_bytes=private['sampled_max_bytes'],exact_private_peak_claimed=False,
        SDK_audit_or_online_sync_accepted=False)

def write(path,value):
    body=(json.dumps(value,sort_keys=True,indent=2,allow_nan=False)+'\n').encode();need(len(body)<=META,'Compact output bound')
    with Path(path).open('xb') as stream:stream.write(body);stream.flush();os.fsync(stream.fileno())
    return raw(path)[1]

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-pins-sha256',required=True);parser.add_argument('--old-job-id',nargs='+',required=True)
    parser.add_argument('--parent-sacct-json',type=Path,required=True);parser.add_argument('--parent-sacct-sha256',required=True)
    parser.add_argument('--expected-node',required=True);parser.add_argument('--output-root',type=Path,required=True);args=parser.parse_args()
    alloc=allocation(args.expected_node);pref,deps=package(args.source_pins_sha256)
    output=args.output_root.absolute();need(output.resolve()==output and output.parent==N
        and output.name.startswith('remaining_Av2_routing7_metadata_actual_') and not output.exists(),
        'Fresh independent N metadata output required')
    output.mkdir(exist_ok=False)
    result=dict(schema='model_v3_remaining_routing7_closed_metadata_audit_v1',status='REJECTED',failure=None,
        source_package=pref,allocation=alloc,cases=[],scientific_work_reexecuted=False,
        model_SDK_checkpoint_array_or_step_payloads_opened=False,resource_journals_opened=False,
        author_claimed_project_execution=False,Root_GPU_closure_or_final_recipe_claimed=False)
    try:
        result['inline_metadata_selfchecks']=metadata_selfchecks()
        plan,planref,qualification,auditor=planned(deps)
        need(1<=len(args.old_job_id)<=6 and len(set(args.old_job_id))==len(args.old_job_id),'Explicit unique finite selector list required')
        case_map={r['old_job_id']:r for r in plan['cases']};cases=[case_map[key] for key in args.old_job_id]
        pairs=[submission(c,plan,planref,deps) for c in cases];values=[x[0] for x in pairs]
        _,parentref=raw(args.parent_sacct_json);need(parentref['sha256']==args.parent_sacct_sha256,'Actual saved accounting SHA differs')
        actual_parents=parents(parentref,values,cases)  # All selected C0 before opening any science gate JSON.
        result.update(plan=planref,actual_parent_sacct=parentref,source_full_CPU_qualification=qualification['CPU'])
        for case,(value,sref) in zip(cases,pairs):
            row=audit_case(case,value,sref,plan,auditor);row['actual_parent']=actual_parents[value['job_id']];result['cases'].append(row)
        need(package(args.source_pins_sha256)[0]==pref,'Audit source changed during verification')
        result['status']='ALL_SELECTED_ROUTING7_FULL20_AND500_METADATA_VERIFIED_PENDING_ROOT_CPU_C0'
    except BaseException as exc:result['failure']=dict(type=type(exc).__name__,message=str(exc))
    rref=write(output/'RESULT.json',result)
    print(json.dumps(dict(status=result['status'],failure=result['failure'],selected_cases=len(result['cases']),result=rref),sort_keys=True),flush=True)
    return int(result['failure'] is not None)

if __name__=='__main__':raise SystemExit(main())
