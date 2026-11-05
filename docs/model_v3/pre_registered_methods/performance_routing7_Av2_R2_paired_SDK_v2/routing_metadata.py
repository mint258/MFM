"""Ordinary routing-v7 numeric closure adapter; only bounded JSON/source and SDK stat."""
from __future__ import annotations
from paired_common import *

B=BASE;N=B/'runs/model_v3_20261026';ROUTING=N/'performance_remaining_Av2_20261029_routing_v7'
W=B/'MFM_model_v3_A_acceptance_v2_candidate_v1'
SOURCE_KEYS=('CPU_supervisor','CPU_process_helpers','CPU_runtime_monitor','CPU_private_storage')

def tools():
    deps=read(HERE/'dependencies.json')
    return deps,load(deps['sources']['numeric_auditor'],'routing7_closed_numeric_metadata_primitives')

def plan_case(old_job_id):
    deps,numeric=tools();plan=read(deps['sources']['routing_plan'])
    require(plan['schema']=='model_v3_remaining_six_A_cohort_v2_routing_execution_plan_v2'
        and plan['routing_version']==7 and len(plan['cases'])==6,'Exact routing-v7 six-cohort plan required')
    selected=[r for r in plan['cases'] if r['old_job_id']==old_job_id]
    require(len(selected)==1,'Explicit one actual original cohort required')
    return plan,selected[0],numeric

def actual_sacct(body,job,node,allowed_jobs,*,metadata_cpu=None):
    if set(body)=={'path','bytes','sha256'}:body=read(body)
    columns='JobIDRaw,User,State,ExitCode,ElapsedRaw,AllocCPUS,NodeList';argv=body['argv']
    require(type(argv) is list and len(argv) in (7,8) and argv[:2]==['sacct','-X'],'Original actual sacct7 command required')
    if argv[2]=='-j':
        require(len(argv)==8 and argv[4:]==['-n','-P','-o',columns],'Original sacct7 fields/order required');ids=argv[3].split(',')
    else:
        require(len(argv)==7 and argv[2:5]==['-n','-P','-j'] and argv[6:]==['--format='+columns],
            'Original sacct7 fields/order required');ids=argv[5].split(',')
    permitted=set(allowed_jobs);cpu_job=None
    if metadata_cpu is not None:
        cpu_job=metadata_cpu['job_id']
        require(type(cpu_job) is str and cpu_job.isdigit() and cpu_job not in permitted
            and type(metadata_cpu['node']) is str,'One distinct actual metadata CPU identity required')
        permitted.add(cpu_job)
    require(len(ids)==len(set(ids)) and set(ids)<=permitted and job in ids
        and type(body['returncode']) is int and body['returncode']==0 and body['stderr']=='',
        'Actual selected C0 command return/identity required')
    rows=[r.split('|') for r in body['stdout'].splitlines() if r.strip()]
    require(len(rows)==len(ids) and all(len(r)==7 for r in rows) and {r[0] for r in rows}==set(ids),
        'Actual exact seven-column selected rows required')
    for row in rows:
        require(row[1:4]==['zixiao','COMPLETED','0:0'] and row[4].isdigit() and row[5]=='16',
            'Every recorded selected parent must be actually owned C0/16CPU')
        if row[0]==cpu_job:
            require(int(row[4])>0 and row[6]==metadata_cpu['node'],
                'Actual metadata CPU row must match its verified allocation node and positive elapsed')
    selected=[r for r in rows if r[0]==job]
    require(len(selected)==1 and selected[0][6]==node,'Actual GPU C0 target node differs')
    return dict(job_id=job,state='COMPLETED',exit_code='0:0',elapsed_seconds=int(selected[0][4]),alloc_cpus=16,node=node)

def numeric_bundle(root_ref):
    root=read(root_ref)
    require(root['schema']=='model_v3_routing7_current_full_A_v2_Root_closure_v1'
        and root['status']=='CURRENT_SOURCE_FULL20_AND500_V2_PASS_ROOT_CLOSED' and root['failure'] is None
        and root['full_A_numeric_acceptance'] is True and root['actual_code_sha']==CODE,
        'Actual positive routing7 numeric Root document required; DRAFT/future/failed is not eligible')
    deps,numeric=tools();plan,planned,_=plan_case(root['old_job_id'])
    result=read(root['metadata_CPU_result']);sup=read(root['metadata_CPU_supervisor'])
    require(result['schema']=='model_v3_remaining_routing7_closed_metadata_audit_v1'
        and result['status']=='ALL_SELECTED_ROUTING7_FULL20_AND500_METADATA_VERIFIED_PENDING_ROOT_CPU_C0'
        and result['failure'] is None and result['source_package']==deps['sources']['numeric_source_pins'],
        'Actual complete source-pinned v3 metadata RESULT required')
    require(result['plan']==deps['sources']['routing_plan'] and 1<=len(result['cases'])<=6,
        'Actual original routing7 metadata result scope differs')
    require(result['inline_metadata_selfchecks']['count']==15
        and len(result['inline_metadata_selfchecks']['checks'])==15,'Actual v3 pure metadata controls required')
    rows=[r for r in result['cases'] if r['old_job_id']==root['old_job_id'] and r['job_id']==root['job_id']]
    require(len(rows)==1,'Exactly this actual numeric CPU case must have passed');row=rows[0]
    require(row['fixed20']['passed'] is True and row['fixed20']['batches']==20
        and row['fixed20']['outputs_each']==8 and row['fixed20']['parameters_each']==329
        and row['trajectory_updates']==500 and row['maximum_trajectory_relative_difference']<=1e-3
        and row['original_data_version_exact_integer_identity'] is True
        and root['fixed']==row['fixed20'] and root['trajectory_updates']==500
        and root['maximum_loss_difference']==row['maximum_trajectory_relative_difference'],
        'Actual original full20/329/all500 positive decisions differ')
    cpu=result['allocation'];job=cpu['job_id']
    require(str(sup['job_id'])==job and sup['status']=='COMPLETED' and sup['exit_code']==0
        and sup['first_failure'] is None and sup['remaining']==[] and sup['gpu_initialization_permitted'] is False
        and sup['launch_identity']['uid']==1278 and sup['launch_identity']['slurm_job_id']==job
        and sup['private_storage']['first_sampling_failure'] is None and sup['private_storage']['budget_bytes']==2<<30
        and sup['private_storage']['sampled_max_bytes']<=2<<30 and sup['last_total_bytes']<=2<<30,
        'Actual complete metadata CPU supervisor/process/private closure required')
    expected_sources={deps['sources'][k]['path']:deps['sources'][k]['sha256'] for k in SOURCE_KEYS}
    require(sup['sources_sha256']==expected_sources,'Original exact four metadata CPU supervision sources required')
    command=sup['command'];require(type(command) is list and len(command)>1 and Path(command[0]).is_absolute(),
        'Actual absolute metadata CPU interpreter required')
    require(command[1:4]==['-u','-B',deps['sources']['numeric_auditor']['path']]
        and sup['launch_identity']['argv']==command,'Actual source-bound metadata CPU argv differs')
    # Root may append the selector argv after the other options. Preserve the actual
    # command verbatim and check its exact six unique flags/values, without sorting it.
    tokens=command[4:];consumed=set()
    expected={'--source-pins-sha256':result['source_package']['sha256'],
        '--parent-sacct-json':result['actual_parent_sacct']['path'],
        '--parent-sacct-sha256':result['actual_parent_sacct']['sha256'],
        '--expected-node':cpu['node'],'--output-root':str(Path(root['metadata_CPU_result']['path']).parent)}
    for flag,value in expected.items():
        require(tokens.count(flag)==1,'Exactly one original metadata CPU option required: '+flag)
        index=tokens.index(flag)
        require(index+1<len(tokens) and tokens[index+1]==value,'Actual metadata CPU option differs: '+flag)
        consumed.update((index,index+1))
    require(tokens.count('--old-job-id')==1,'Exactly one original selector option required')
    index=tokens.index('--old-job-id');end=index+1
    while end<len(tokens) and not tokens[end].startswith('--'):end+=1
    require(tokens[index+1:end]==[r['old_job_id'] for r in result['cases']], 'Actual metadata CPU selectors differ')
    consumed.update(range(index,end))
    require(consumed==set(range(len(tokens))),'Unknown or duplicate metadata CPU argv tokens rejected')
    recorded=actual_sacct(root['actual_sacct'],root['job_id'],planned['expected_node'],{r['job_id'] for r in result['cases']},metadata_cpu=cpu)
    require(recorded==row['actual_parent'],'Root actual accounting differs from verified actual original GPU parent')
    closed={r['path']:r for r in root['closed_metadata']}
    require(len(closed)==len(root['closed_metadata']) and all(r in row['closed_metadata'].values() for r in closed.values()),
        'Only actual CPU-verified closed metadata references may enter Root closure')
    for key in ('configuration','summary','run_status','supervisor','fixed_batch_gate','trajectory_gate'):
        ref_row=row['closed_metadata'][key];require(closed.get(ref_row['path'])==ref_row,'Complete six actual closed references required')
    require(root['configuration_sha256']==row['configuration_sha256'],'Actual Root configuration SHA differs')
    return root,result,row,planned,plan,numeric

def stat_saved(root_ref,plan_output):
    root,result,row,planned,_,_=numeric_bundle(root_ref)
    child=Path(planned['child_output']);sdks=[]
    for path in sorted((child/'wandb').glob('offline-run-*/run-*.wandb')):
        match=re.fullmatch(r'run-([a-z0-9]+)\.wandb',path.name)
        require(match and path.parent.name.endswith('-'+match[1]),'Actual offline SDK directory/runID differs')
        sdks.append(dict(run_id=match[1],descriptor=descriptor(path,128<<20)))
    require(len(sdks)==2 and len({r['run_id'] for r in sdks})==2,'Exactly two original closed offline SDK files required')
    journals={role:descriptor(child/(role+'_history.jsonl'),32<<20) for role in ('reference','candidate')}
    return write(plan_output/'saved_sdk_descriptors.json',dict(schema='performance_routing7_Av2_R2_saved_sdk_descriptors_v1',
        job_id=root['job_id'],old_job_id=root['old_job_id'],Root_closure=root_ref,sdks=sdks,journals=journals,
        SDK_and_journal_payloads_read=False,roles_not_inferred_from_directory_order=True))

def metadata_case(case):
    refs=case['refs'];m={k:read(v) for k,v in refs.items()};cfg=m['configuration'];summary=m['summary'];status=m['status']
    root,result,row,planned,plan,numeric=numeric_bundle(refs['root']);job=root['job_id']
    require(case['job_id']==job and case['old_job_id']==root['old_job_id'],'Actual explicit one-case identity differs')
    require(terminal_C0(case['actual_metadata_CPU_C0'])['job_id']==result['allocation']['job_id']
        and terminal_C0(case['actual_model_C0'])['job_id']==job,'Actual metadata CPU and original GPU C0 both required')
    require(refs['metadata_CPU_result']==root['metadata_CPU_result'] and refs['metadata_CPU_supervisor']==root['metadata_CPU_supervisor'],
        'Actual numeric CPU authority rawrefs differ')
    for key,row_key in [('configuration','configuration'),('summary','summary'),('status','run_status'),('supervisor','supervisor')]:
        require(refs[key]==row['closed_metadata'][row_key],'Actual verified metadata rawref differs')
    require(cfg['job_id']==status['job_id']==job and cfg['code_sha']==summary['code_sha']==CODE
        and cfg['prereg_sha']==summary['prereg_sha']==PUBLIC and cfg['fixed_batches']==20 and cfg['trajectory_updates']==500
        and cfg['input']=='native_s' and cfg['smoke'] is False and type(cfg['seed']) is int and cfg['seed']==0
        and cfg['tracking_mode']=='offline' and cfg['downstream_data_read'] is False and cfg['original_lmdb_written'] is False,
        'Original ordinary source/config/full20+500/offline identity differs')
    old=read(planned['original_configuration'])
    for key,other in [('candidate','candidate'),('reference','reference_options'),('model','model'),('data_version','original_data_version')]:
        planned_equal=(numeric.planned_model_equal(old[key],planned[other]) if key=='model'
                       else numeric.exact(old[key],planned[other]))
        require(numeric.exact(cfg[key],old[key]) and planned_equal,
            'Complete exact-type original cohort differs: '+key)
    for key in ('optimizer','loss_policy','loss_weights','supervision','schedule','gradient_clip_norm',
                'dynamic_balancer','input','seed','smoke','fixed_batches','trajectory_updates'):
        require(numeric.exact(cfg[key],old[key]),'Original actual configuration differs: '+key)
    require(type(cfg['data_version']['original_shard_snapshot']['mtime_ns']) is int
        and cfg['data_version']['original_shard_snapshot']['mtime_ns']==1791880208985935300,
        'Original integer nanoseconds must not pass through JS/float')
    require(cfg['candidate_options_sha256']==planned['candidate_options']['sha256']
        and cfg['gpu_uuid']==planned['gpu_uuid'] and cfg['gpu_name']==planned['gpu_name']
        and cfg['node'].split('.')[0]==planned['expected_node']
        and cfg.get('performance_execution_request') is None and cfg.get('performance_execution') is None,
        'Actual legacy ordinary selector/device differs; no manual/profile integration is invented')
    require(numeric.canonical({k:v for k,v in cfg.items() if k!='configuration_sha256'})
        ==cfg['configuration_sha256']==summary['configuration_sha256']==root['configuration_sha256'],
        'Original complete canonical configuration differs')
    require(summary['status']==status['status']=='PAIRED_GATES_PASS' and summary['full_A_numeric_acceptance'] is True
        and summary['fixed_batch_pass'] is True and summary['trajectory_pass'] is True and status['failure'] is None
        and status['cleanup_errors']==[] and status['stream_cleanup']['errors']==[]
        and status['stream_cleanup']['input_descriptors_closed'] is True and status['trajectory_started'] is True
        and status['committed_trajectory_updates']==500 and status['trajectory_completed'] is True,
        'Actual complete paired GPU stream closure required')
    rule=cfg['acceptance_rules'];deps=read(HERE/'dependencies.json')
    require(rule==summary['acceptance_rules']==status['acceptance_rules'] and rule['schema']=='model_v3_A_acceptance_rule_binding_v2'
        and rule['version']=='v2' and rule['fixed_batch_only'] is False and rule['public_rule_commit']==RULE_PUBLIC
        and cfg['acceptance_scope']==summary['acceptance_scope']==status['acceptance_scope']=='V2_FULL20_AND500'
        and rule['rule_publication']==deps['sources']['A_rule_publication']
        and rule['rule_document']==deps['sources']['A_rule_document'],'Exact complete source v2 rule binding required')
    source=cfg['source_sha256'];require(len(source)==row['current_runtime_source_count']==61,'Actual same-code61 runtime bindings required')
    for name,sha in source.items():
        relative=Path(name);require(not relative.is_absolute() and '..' not in relative.parts,'Relative runtime source required')
        require(ref(W/relative)['sha256']==sha,'Actual same-code runtime source changed')
    submission=m['submission'];require(submission['job_id']==job and submission['old_job_id']==root['old_job_id']
        and submission['status']=='SUBMITTED' and submission['declared_routing_version']==7
        and submission['source_package']==deps['sources']['routing_pins'] and submission['operations_publication']==refs['operations_publication']
        and row['submission']==refs['submission'],'Exact actual v7 Root submission required')
    require(refs['submission']['path']==str(Path(planned['control'])/'Root_submission_actual_v1.json'),
        'Submitted job must come from the exact actual v7 control')
    numeric.publication(refs['operations_publication'],plan)
    require(set(case['journals'])=={'reference','candidate'} and len(case['sdks'])==2,'Exactly two role journals/twoSDK descriptors required')
    saved=m['saved_sdk_descriptors'];require(saved['schema']=='performance_routing7_Av2_R2_saved_sdk_descriptors_v1'
        and saved['SDK_and_journal_payloads_read'] is False and saved['roles_not_inferred_from_directory_order'] is True
        and saved['Root_closure']==refs['root'] and saved['job_id']==job
        and saved['old_job_id']==case['old_job_id'] and saved['sdks']==case['sdks'] and saved['journals']==case['journals'],
        'Actual stat-only saved descriptors differ')
    for role,item in case['journals'].items():
        require(item['path']==str(Path(planned['child_output'])/(role+'_history.jsonl'))
            and descriptor(item['path'],32<<20)==item,'Original role journal location/descriptor differs')
    for item in case['sdks']:require(descriptor(item['descriptor']['path'],128<<20)==item['descriptor'],'Original SDK descriptor drift')
    return m
