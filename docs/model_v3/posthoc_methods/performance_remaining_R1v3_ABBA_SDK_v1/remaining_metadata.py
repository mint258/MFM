"""Six-cohort ordinary R1v3 metadata/stat adapter; no SDK or steps-body reads."""
from __future__ import annotations
from abba_common import *

def consumer():
    deps=read(HERE/'dependencies.json');m=load(deps['sources']['R1_admission'],'remaining_R1v3_frozen_metadata')
    require(m.verify_package(deps['sources']['R1_GPU_package']['sha256'])==deps['sources']['R1_GPU_package'],
        'Exact frozen R1v3 method required')
    return m,deps

def declared(cohort):
    m,deps=consumer();template=read(deps['sources']['R1_PLAN']);plan=read(deps['sources']['routing_PLAN'])
    require(cohort in template['cohorts'] and plan['routing_version']==7,'Only original six ordinary routing7 cohorts')
    rows=[r for r in plan['cases'] if r['old_job_id']==cohort];require(len(rows)==1,'One explicit original cohort required')
    return m,deps,rows[0],template['cohorts'][cohort]

def r2_context(ref,cohort,m):
    q=read(ref);require(q['schema']=='model_v3_remaining_Av2_R1_qualification_inputs_v1' and q['cohort']==cohort,
        'Actual same-cohort R1 qualification input required')
    numeric=read(q['Root_numeric_closure']);sdk=read(q['SDK_closure']);audit=read(q['metadata_audit_result'])
    require(numeric['schema']=='model_v3_routing7_current_full_A_v2_Root_closure_v1'
        and numeric['status']=='CURRENT_SOURCE_FULL20_AND500_V2_PASS_ROOT_CLOSED' and numeric['failure'] is None
        and numeric['full_A_numeric_acceptance'] is True and numeric['old_job_id']==cohort and numeric['actual_code_sha']==CODE
        and numeric['metadata_CPU_result']==q['metadata_audit_result'] and numeric['metadata_CPU_supervisor']==q['metadata_audit_supervisor']
        and sdk['schema']=='model_v3_routing7_current_paired_SDK_Root_closure_v1'
        and sdk['status']=='NATIVE_FULL500_AND_OFFICIAL_SELECTIVE_SYNC_CLOUD_READBACK_CLOSED' and sdk['failure'] is None
        and sdk['job_id']==numeric['job_id'] and sdk['old_job_id']==cohort and sdk['numeric_Root_closure']==q['Root_numeric_closure'],
        'Actual same-case positive R2 numeric and full500 SDK/sync Root qualifications required')
    require(audit['status']=='ALL_SELECTED_ROUTING7_FULL20_AND500_METADATA_VERIFIED_PENDING_ROOT_CPU_C0'
        and audit['failure'] is None,'Actual complete numeric metadata result required')
    rows=[r for r in audit['cases'] if r['old_job_id']==cohort and r['job_id']==numeric['job_id']]
    require(len(rows)==1,'One actual qualified numeric case required');row=rows[0]
    require(numeric['fixed']==row['fixed20'] and numeric['fixed']['passed'] is True and numeric['trajectory_updates']==500
        and numeric['maximum_loss_difference']==row['maximum_trajectory_relative_difference']
        and all(m.contains_ref(sdk,r) for r in [q['Root_numeric_closure'],*q['SDK_verifications'],*q['SDK_sync_results']]),
        'Existing numeric/typed500 qualification reference identity differs')
    cfg=read(row['closed_metadata']['configuration'])
    files={k:row['closed_metadata'][k] for k in ('summary','configuration','run_status','fixed_batch_gate','trajectory_gate')}
    gate=dict(Root_closure=q['Root_numeric_closure'],directory=str(Path(files['configuration']['path']).parent),
        files=files,Root_bound_metadata=list(row['closed_metadata'].values()))
    return q,numeric,sdk,cfg,gate

def parent_C0(raw,job):
    rows=[r.split('|') for r in raw['stdout'].splitlines() if r.strip()]
    selected=[r for r in rows if r[0]==job]
    require(len(selected)==1 and len(selected[0])==7 and selected[0][1:4]==['zixiao','COMPLETED','0:0']
        and selected[0][4].isdigit() and int(selected[0][4])>0 and selected[0][5]=='16',
        'Actual current member C0/UID/16CPU/positive elapsed required')

def metadata_member(item):
    root=read(item['root']);cohort=root['cohort'];position=item['position'];m,deps,case,decl=declared(cohort)
    require(type(position) is int and 1<=position<=4 and item['role']==ROLES[position-1]
        and root['schema']=='model_v3_remaining_R1v3_SDK_member_selector_v1'
        and root['status']=='ACTUAL_CLOSED_MEMBER_METADATA_SELECTOR_ONLY' and root['position']==position
        and root['role']==item['role'] and root['series_id']==decl['series_id'],'Actual ABBA selector scope/position differs')
    family=Path(decl['family'])/('member_'+str(position));child=family/'child';job=item['job_id']
    expected=dict(configuration=child/'configuration.json',summary=child/'summary.json',run_status=child/'run_status.json',
        supervisor=family/'supervisor.json',submission=family/'control/Root_submission_actual_v1.json',
        bound_cohort=family/'control/BOUND_COHORT.json')
    metadata={key:read(item['refs'][key]) for key in item['refs']}
    for key,path in expected.items():require(item['refs'][key]['path']==str(path),'Exact current member metadata location differs')
    require(root['refs']==item['refs'] and root['job_id']==job and root['tracking_run_id']==item['run_id'],
        'Actual selector/input identity differs')
    c,s,r,sup,sub,b=[metadata[k] for k in ('configuration','summary','run_status','supervisor','submission','bound_cohort')]
    require(sub['schema']=='model_v3_remaining_Av2_R1_Root_single_submission_v1' and sub['status']=='SUBMITTED'
        and sub['source_package']==deps['sources']['R1_GPU_package'] and sub['cohort']==cohort and sub['position']==position
        and sub['role']==item['role'] and sub['series_id']==decl['series_id'] and sub['job_id']==job
        and sub['bound_cohort']==item['refs']['bound_cohort'] and sub['qualification']==item['refs']['qualification'],
        'Actual one-use R1v3 Root submission binding differs')
    m.verify_method(sub['method_publication'])
    require(sub['method_publication']==item['refs']['method_publication'] and b['source_package']==sub['source_package']
        and b['method_publication']==sub['method_publication'] and b['qualification_input']==sub['qualification']
        and b['cohort']==cohort and b['position']==position and b['role']==item['role']
        and b['case']['R1_family']==decl['family'] and b['case']['R1_series_id']==decl['series_id'],
        'Actual public method/cohort/position binding differs')
    q,numeric,sdk,ncfg,gate=r2_context(sub['qualification'],cohort,m)
    require(m.exact(ncfg,b['numeric_configuration']) and b['qualification_source_root_refs']==
        {k:q[k] for k in ('Root_numeric_closure','SDK_closure')}
        and item['refs']['R2_numeric_Root']==q['Root_numeric_closure'] and item['refs']['R2_SDK_Root']==q['SDK_closure'],
        'Actual R1 member must retain its real same-cohort R2 qualification')
    for key in ('model','optimizer','loss_policy','loss_weights','supervision','schedule','reference_configuration','a4_configuration',
                'original_shard_snapshot_prejob_sha256','data_version','candidate'):
        require(m.exact(c[key],ncfg[key]),'Original ordinary numeric configuration differs: '+key)
    require('performance_execution' not in c and 'performance_execution_request' not in c
        and m.exact(c['effective_options'],ncfg['reference'] if item['role']=='reference' else ncfg['candidate']),
        'Original ordinary effective options required; no integration/profile is invented')
    require(c['job_id']==str(sup['job_id'])==job and c['node'].split('.')[0]==case['expected_node']
        and c['gpu_uuid']==s['gpu_uuid']==sup['gpu_uuid']==case['gpu_uuid']
        and c['role']==s['role']==item['role'] and type(c['abba_position']) is type(s['abba_position']) is int
        and c['abba_position']==s['abba_position']==position and c['series_id']==s['series_id']==decl['series_id'],
        'Actual same-UUID ABBA identity differs')
    require(c['code_sha']==s['code_sha']==CODE and c['prereg_sha']==s['prereg_sha']==PUBLIC
        and type(c['seed']) is type(s['seed']) is int and c['seed']==s['seed']==0
        and c['input']==s['input']=='native_s' and c['smoke'] is s['smoke'] is False
        and c['warmup_updates']==s['warmup_updates']==2 and c['measured_updates']==s['measured_updates']==20
        and s['tracking_mode']=='offline','Original complete seed0/native2+20 source scope differs')
    require(s['status']==r['status']=='STANDALONE_TIMING_COMPLETED' and r['failure'] is None and r['cleanup_errors']==[]
        and r['stream_cleanup']['errors']==[] and r['stream_cleanup']['input_descriptors_closed'] is True
        and sup['status']=='COMPLETED' and sup['exit_code']==0 and sup['first_failure'] is None
        and sup['remaining_recorded_processes_before_retirement']==[] and sup['private_storage_cleanup_errors']==[]
        and sup['foreign_gpu_processes_signalled'] is False,'Actual original trainer/SDK/input/outer closure required')
    require(m.canonical({k:v for k,v in c.items() if k!='configuration_sha256'})==c['configuration_sha256']==s['configuration_sha256'],
        'Ordinary full config canonical hash differs')
    source=read(HERE/'dependencies.json')['runtime_sources']
    require(len(source)==61 and m.exact(c['source_sha256'],{name:ref['sha256'] for name,ref in source.items()})
        and m.exact(c['source_sha256'],ncfg['source_sha256']),'Actual same-code61 runtime identity differs')
    accounting=metadata['parent_sacct'];jobs=root['actual_four_job_ids']
    require(len(jobs)==len(set(jobs))==4 and job==jobs[position-1],'Ordered actual four-parent identity differs')
    m.parents(accounting,{j:case['expected_node'] for j in jobs});parent_C0(accounting,job)
    require(sub['predecessor'] is None if position==1 else sub['predecessor']['submission']['path']==
        str(Path(decl['family'])/('member_'+str(position-1))/'control/Root_submission_actual_v1.json'),
        'Actual sequential four-member predecessor differs')
    key=s['tracking_run_id']
    require(type(key) is str and re.fullmatch('[a-z0-9]{8}',key) and key==item['run_id']==root['tracking_run_id'],
        'Actual closed summary tracking ID required')
    require(item['SDK']==root['SDK'] and descriptor(item['SDK']['path'],128<<20)==item['SDK']
        and item['step_journal']==root['step_journal'] and descriptor(item['step_journal']['path'],32<<20)==item['step_journal'],
        'Original SDK/steps stat descriptor differs')
    path=Path(item['SDK']['path'])
    require(path.parent.parent==child/'wandb' and path.parent.name.startswith('offline-run-')
        and path.parent.name.endswith('-'+key) and path.name=='run-'+key+'.wandb'
        and item['step_journal']['path']==str(child/'steps.jsonl'),'Actual durable artifact location differs')
    return metadata

def bound_inputs(raw):
    value=read(raw);require(value['schema']=='performance_manual_R1_ABBA_log_inputs_v1' and value['scope']==SCOPE
        and len(value['members'])==4 and [m['position'] for m in value['members']]==[1,2,3,4],
        'Exactly four ordered actual ordinary R1 members required')
    members=value['members'];require(len({m['job_id'] for m in members})==len({m['run_id'] for m in members})==4,
        'Distinct actual four jobs and SDK IDs required')
    roots=[read(m['root']) for m in members];cohorts={r['cohort'] for r in roots};require(len(cohorts)==1,'One cohort only')
    cohort=next(iter(cohorts));m,deps,case,decl=declared(cohort);require(value['series_id']==decl['series_id'],'Exact actual series required')
    total=0;qualification=None;publication=None;actual_jobs=[x['job_id'] for x in members]
    for item,root in zip(members,roots):
        metadata=metadata_member(item)
        require(root['actual_four_job_ids']==actual_jobs,'All actual ordered Root jobs must agree')
        current=metadata['submission']
        if qualification is None:qualification=current['qualification'];publication=current['method_publication']
        require(current['qualification']==qualification and current['method_publication']==publication,
            'Same actual R2 and public R1v3 method required for all four members')
        total+=item['SDK']['bytes']+item['step_journal']['bytes']+item['root']['bytes']+sum(r['bytes'] for r in item['refs'].values())
    _,_,_,_,gate=r2_context(qualification,cohort,m)
    require(value['numeric_gate']==gate and total+sum(r['bytes'] for r in gate['files'].values())<=128<<20,
        'Same original numeric gate and bounded four-run population required')
    return value

def prepare_inputs(cohort,parent_ref,output):
    m,deps,case,decl=declared(cohort);members=[];jobs=[];raws=[]
    for position in range(1,5):
        family=Path(decl['family'])/('member_'+str(position));child=family/'child'
        refs={k:ref(p) for k,p in dict(configuration=child/'configuration.json',summary=child/'summary.json',
            run_status=child/'run_status.json',supervisor=family/'supervisor.json',
            submission=family/'control/Root_submission_actual_v1.json',bound_cohort=family/'control/BOUND_COHORT.json').items()}
        sub=read(refs['submission']);summary=read(refs['summary']);require(sub['status']=='SUBMITTED'
            and summary['status']=='STANDALONE_TIMING_COMPLETED','All four members must actually be closed before SDK preparation')
        jobs.append(sub['job_id']);raws.append((refs,sub,summary,family))
    require(len(set(jobs))==4,'Four distinct actual jobs required');m.parents(read(parent_ref),{j:case['expected_node'] for j in jobs})
    qualification=None;gate=None
    for position,(refs,sub,summary,family) in enumerate(raws,1):
        q,numeric,sdk,ncfg,current_gate=r2_context(sub['qualification'],cohort,m)
        if qualification is None:qualification=sub['qualification'];gate=current_gate
        require(sub['qualification']==qualification and current_gate==gate,'All four actual members must share qualification')
        refs.update(qualification=sub['qualification'],method_publication=sub['method_publication'],
            R2_numeric_Root=q['Root_numeric_closure'],R2_SDK_Root=q['SDK_closure'],parent_sacct=parent_ref)
        key=summary['tracking_run_id'];require(re.fullmatch('[a-z0-9]{8}',key),'Actual closed summary tracking ID required')
        paths=list((family/'child/wandb').glob('offline-run-*/run-'+key+'.wandb'));require(len(paths)==1,'One original closed SDK stat location required')
        sdk_descriptor=descriptor(paths[0],128<<20);steps=descriptor(family/'child/steps.jsonl',32<<20)
        selector=dict(schema='model_v3_remaining_R1v3_SDK_member_selector_v1',status='ACTUAL_CLOSED_MEMBER_METADATA_SELECTOR_ONLY',
            cohort=cohort,series_id=decl['series_id'],position=position,role=ROLES[position-1],job_id=sub['job_id'],
            tracking_run_id=key,refs=refs,actual_four_job_ids=jobs,SDK=sdk_descriptor,step_journal=steps,
            source_package=deps['sources']['R1_GPU_package'],SDK_or_steps_body_opened=False,Native_role_must_be_decoded_by_CPU=True)
        selector_ref=write(output/('member_'+str(position)+'_BOUND_METADATA.json'),selector)
        item=dict(position=position,role=ROLES[position-1],job_id=sub['job_id'],run_id=key,root=selector_ref,
            refs=refs,SDK=sdk_descriptor,step_journal=steps)
        metadata_member(item);members.append(item)
    return dict(schema='performance_manual_R1_ABBA_log_inputs_v1',scope=SCOPE,cohort=cohort,series_id=decl['series_id'],
        members=members,numeric_gate=gate,SDK_or_steps_body_opened=False)
